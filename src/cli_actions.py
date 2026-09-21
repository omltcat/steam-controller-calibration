"""Command-line capture, inspection, backup, restore, and calibration workflows."""
import collections
import ctypes as C
import json
from pathlib import Path
import statistics
import time

from .calibration_store import (RECORD_PATHS, make_backup, read_calibration_state,
                                read_calibration_state_fresh, restore_record_bytes,
                                validate_backup, write_json)
from .protocol import (AXES, SUPPORTED_CALIBRATION_BUILD, calibration_issues,
                       decode_attributes, decode_calibration, decode_sticks)
from .sample_analysis import summarize


def capture(hid, device, info, seconds, output):
    """Save passive input reports as JSON Lines for offline inspection."""
    counts, samples = collections.Counter(), 0
    start = time.monotonic()
    buffer = (C.c_ubyte * 256)()
    # Exclusive creation makes captures append-safe and preserves earlier evidence.
    with Path(output).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(dict(kind='metadata', device=info,
            label='Firmware-processed HID values; no software correction', seconds=seconds)) + '\n')
        while time.monotonic() - start < seconds:
            count = hid.s.SDL_hid_read_timeout(device, buffer, len(buffer), 100)
            if count < 0:
                raise RuntimeError(hid.error())
            if not count:
                continue
            report = bytes(buffer[:count])
            counts[f'{report[0]:02x}'] += 1
            row = dict(kind='input', t=time.monotonic() - start, hex=report.hex())
            try:
                row['sticks'] = decode_sticks(report)
            except ValueError as error:
                row['decode_error'] = str(error)
            if row.get('sticks'):
                samples += 1
            stream.write(json.dumps(row) + '\n')
    print(json.dumps(dict(reports=counts, stick_samples=samples, output=output), indent=2))
    if not samples:
        print('No stick reports: check the HID collection/path and connection. '
              'This passive reader does not enable streaming or disable lizard mode.')


def analyze(path):
    """Print center/noise/range statistics from a passive capture."""
    values = {a: [] for a in AXES}
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('kind') != 'input':
                continue
            sticks = decode_sticks(bytes.fromhex(row['hex']))
            if sticks:
                for axis in AXES:
                    values[axis].append(sticks[axis])
    if not values[AXES[0]]:
        raise ValueError('Capture contains no supported stick reports')
    print(json.dumps({a: dict(samples=len(v), minimum=min(v), maximum=max(v),
        median=statistics.median(v), peak_to_peak=max(v)-min(v)) for a, v in values.items()}, indent=2))
    print('Median measures center only when sticks were untouched for the entire capture. '
          'Range extrema require a separate full-travel capture.')


def inspect(hid, device, info, output, experimental):
    """Read identity and optionally calibration records without writing."""
    # Never route these unvalidated storage queries through a puck or Bluetooth.
    if info['pid'] != 0x1302 or info['bus'] != 1 or info['usage_page'] < 0xFF00:
        raise ValueError('Inspect requires a direct USB 28DE:1302 vendor HID collection')
    result = dict(device=info, queries={}, calibration_write_supported=False)
    kinds = ['attributes'] + (['cal/joy_l', 'cal/joy_r'] if experimental else [])
    for kind in kinds:
        try:
            raw, data = hid.read_query(device, kind)
            item = dict(raw=raw.hex(), payload=data.hex())
            if kind == 'attributes':
                if not data or len(data) % 5:
                    raise ValueError('Malformed attribute response')
                item['attributes'] = {str(key): value for key, value in decode_attributes(data).items()}
            else:
                try:
                    item['candidate_record'] = decode_calibration(data)
                except ValueError as error:
                    item['interpretation_error'] = str(error)
            result['queries'][kind] = item
        except (RuntimeError, ValueError) as error:
            result['queries'][kind] = dict(error=str(error))
            break
    write_json(output, result)
    print(json.dumps(result, indent=2))
    print('Saved an inspection log, not a validated restorable calibration backup.')
    if any('error' in item for item in result['queries'].values()):
        raise RuntimeError('Inspection failed; see the saved log')


def backup_controller(hid, device, info, output):
    """Create a device-bound backup suitable for guarded restore."""
    if info['pid'] != 0x1302 or info['bus'] != 1 or info['usage_page'] < 0xFF00:
        raise ValueError('Backup requires a direct USB 28DE:1302 vendor HID collection')
    state = read_calibration_state(hid, device)
    if state['attributes'].get(4) != SUPPORTED_CALIBRATION_BUILD:
        raise ValueError('The connected firmware build is not supported for restoration')
    backup = make_backup(info, state)
    write_json(output, backup)
    print(json.dumps(dict(output=output, serial=info['serial'],
                          firmware_build=f'{backup["firmware_build"]:08X}',
                          fingerprint_sha256=backup['fingerprint_sha256']), indent=2))


def restore(hid, device, info, args):
    """Run the stage-verify-commit-verify restore workflow."""
    if info['pid'] != 0x1302 or info['bus'] != 1 or info['usage_page'] < 0xFF00:
        raise ValueError('Restore requires a direct USB 28DE:1302 vendor HID collection')
    with Path(args.backup).open(encoding='utf-8') as stream:
        backup = validate_backup(json.load(stream))
    if info['serial'] != backup['device']['serial']:
        raise ValueError('Backup serial does not match the connected controller')
    current = read_calibration_state(hid, device)
    if current['attributes'].get(4) != backup['firmware_build']:
        raise ValueError('Connected firmware does not match the backup firmware')
    desired = {path: bytes.fromhex(backup['records'][path]['payload']) for path in RECORD_PATHS}
    changed = {path: current['records'][path]['payload'] != desired[path].hex()
               for path in RECORD_PATHS}
    session = dict(kind='steam-controller-2026-restore', device=info,
                   backup=args.backup, backup_fingerprint_sha256=backup['fingerprint_sha256'],
                   before=current, records_differ=changed, committed=False)
    print(json.dumps(dict(serial=info['serial'], records_differ=changed,
                          backup_fingerprint_sha256=backup['fingerprint_sha256']), indent=2))
    # Dry-run validates identity, firmware, fingerprint, and payload geometry only.
    if not args.apply:
        write_json(args.output, session)
        print('Restore dry-run passed. No setting command was sent.')
        return
    phrase = input(f'Type RESTORE {info["serial"]} to stage the backup records: ').strip()
    if phrase != f'RESTORE {info["serial"]}':
        write_json(args.output, session)
        raise RuntimeError('Restore confirmation did not match; no setting command was sent')
    try:
        # Stage is volatile. A power cycle still discards it at this point.
        for path in RECORD_PATHS:
            hid.setting(device, 'stage', path, desired[path])
        staged = read_calibration_state_fresh(hid, info)
        session['staged'] = staged
        if any(staged['records'][path]['payload'] != desired[path].hex() for path in RECORD_PATHS):
            session['recovery'] = 'Power-cycle now; no restore commit was sent.'
            write_json(args.output, session)
            raise RuntimeError('Staged records did not verify. Power-cycle to discard them.')
        phrase = input('Both staged records verified. Type COMMIT RESTORE to persist them: ').strip()
        if phrase != 'COMMIT RESTORE':
            session['recovery'] = 'Power-cycle the controller; no restore commit was sent.'
            write_json(args.output, session)
            raise RuntimeError('Restore commit cancelled. Power-cycle to discard staged records.')
        # The second explicit phrase is the boundary before persistent writes.
        for path in RECORD_PATHS:
            hid.setting(device, 'commit', path)
        session['commit_requests_sent'] = True
        after = read_calibration_state_fresh(hid, info)
        session['after'] = after
        session['committed'] = True
        session['verified'] = all(after['records'][path]['payload'] == desired[path].hex()
                                  for path in RECORD_PATHS)
        if not session['verified']:
            session['recovery'] = 'Keep this backup. Reconnect and rerun restore; persistence is uncertain.'
        write_json(args.output, session)
        if not session['verified']:
            raise RuntimeError('Persistent restore did not verify; see the session log')
        print(json.dumps(dict(restored=True, verified=True, output=args.output), indent=2))
    except Exception:
        if not Path(args.output).exists():
            session['recovery'] = ('Power-cycle if COMMIT RESTORE was not entered. If commit began, '
                                   'keep the backup and rerun restore after reconnecting.')
            write_json(args.output, session)
        raise


def calibrate(hid, device, info, args):
    """Run firmware sampling with an immutable backup and rollback checks."""
    if info['pid'] != 0x1302 or info['bus'] != 1 or info['usage_page'] < 0xFF00:
        raise ValueError('Calibration requires a direct USB 28DE:1302 vendor HID collection')
    if info['serial'] != args.serial:
        raise ValueError('The connected controller serial does not match --serial')
    before = read_calibration_state(hid, device)
    build = before['attributes'].get(4)
    if build != SUPPORTED_CALIBRATION_BUILD:
        raise ValueError(f'Firmware {build:#010x} is not the analyzed build '
                         f'{SUPPORTED_CALIBRATION_BUILD:#010x}')
    session = dict(kind='steam-controller-2026-calibration', device=info,
                   firmware_build=build, before=before, committed=False)
    backup_path = args.backup or (args.output + '.backup.json')
    backup = make_backup(info, before)
    write_json(backup_path, backup)
    session['immutable_backup'] = backup_path
    session['backup_fingerprint_sha256'] = backup['fingerprint_sha256']
    print(f'Immutable restorable backup saved before calibration: {backup_path}')
    print(f'Leave both sticks completely untouched for the next {args.center_seconds:g} seconds.')
    time.sleep(1)
    center = summarize(hid.sample_sticks(device, args.center_seconds))
    session['preflight_center'] = center
    print(json.dumps(center, indent=2))
    if any(abs(center[a]['median']) > args.center_limit or
           center[a]['peak_to_peak'] > args.center_noise_limit for a in AXES):
        write_json(args.output, session)
        raise RuntimeError('Center preflight failed; no calibration command was sent')
    # The default command is a read-only preflight; --apply unlocks firmware phases.
    if not args.apply:
        write_json(args.output, session)
        print('Read-only preflight passed. Calibration writes remain disabled pending safe '
              'candidate-record validation.')
        return
    phrase = input(f'Type the controller serial {args.serial} to begin volatile sampling: ').strip()
    if phrase != args.serial:
        write_json(args.output, session)
        raise RuntimeError('Serial confirmation did not match; no calibration command was sent')
    # Phase 1 measures the untouched center window in volatile firmware buffers.
    hid.calibration_phase(device, 1)
    session['center_phase_sent'] = True
    time.sleep(args.center_seconds)
    # Phase 2 must be active before inviting any movement. The original trial
    # printed the instruction first, contaminating phase-1 center extrema.
    hid.calibration_phase(device, 2)
    session['range_phase_sent'] = True
    print(f'Rotate BOTH sticks around their complete circular travel for {args.range_seconds:g} seconds.')
    range_values = summarize(hid.sample_sticks(device, args.range_seconds))
    session['range_observation'] = range_values
    print(json.dumps(range_values, indent=2))
    reached = all(range_values[a]['minimum'] <= -args.range_threshold and
                  range_values[a]['maximum'] >= args.range_threshold for a in AXES)
    if not reached:
        session['recovery'] = 'Power-cycle the controller; phase 3 was not sent, so flash was not committed.'
        write_json(args.output, session)
        raise RuntimeError('Full travel was not observed on every axis. Nothing was committed. '
                           'Power-cycle the controller before retrying.')
    phrase = input('Type COMMIT to persist the newly sampled center and range: ').strip()
    if phrase != 'COMMIT':
        session['recovery'] = 'Power-cycle the controller; phase 3 was not sent, so flash was not committed.'
        write_json(args.output, session)
        raise RuntimeError('Commit cancelled. Power-cycle the controller to discard volatile sampling.')
    # Phase 3 is the only automatic-calibration step that persists candidates.
    hid.calibration_phase(device, 3)
    after = read_calibration_state_fresh(hid, info)
    session['after'] = after
    session['committed'] = True
    session['records_changed'] = {
        path: before['records'][path]['payload'] != after['records'][path]['payload']
        for path in before['records']
    }
    session['record_issues'] = {
        path: calibration_issues(after['records'][path]['decoded']) for path in RECORD_PATHS
    }
    # Phase 3 cannot be previewed, so unsafe geometry is restored immediately.
    if any(session['record_issues'].values()):
        desired = {path: bytes.fromhex(before['records'][path]['payload']) for path in RECORD_PATHS}
        session['automatic_restore_reason'] = 'Post-commit record geometry failed safety checks'
        try:
            session['automatic_restore'] = restore_record_bytes(hid, device, info, desired)
        except RuntimeError as error:
            session['automatic_restore'] = dict(verified=False, error=str(error))
        write_json(args.output, session)
        if session['automatic_restore'].get('verified'):
            raise RuntimeError('New calibration was unsafe and the original records were '
                               'automatically restored; see the session log')
        raise RuntimeError('New calibration was unsafe and automatic restore failed. '
                           'Run the restore command with the immutable backup immediately.')
    write_json(args.output, session)
    print(json.dumps(dict(records_changed=session['records_changed'], output=args.output), indent=2))
    if not all(session['records_changed'].values()):
        raise RuntimeError('Commit returned, but one or more records did not change; inspect the session log')



