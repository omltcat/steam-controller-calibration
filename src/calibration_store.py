"""Calibration record reads, immutable backups, verification, and rollback helpers."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import time

from .hid_transport import select
from .protocol import calibration_issues, decode_attributes, decode_calibration

BACKUP_SCHEMA = 'steam-controller-2026-stick-backup-v1'
RECORD_PATHS = ('cal/joy_l', 'cal/joy_r')


def write_json(path, value):
    # Exclusive creation protects previous captures/backups.
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)


def read_calibration_state(hid, device):
    """Read firmware identity and both validated 18-byte stick records."""
    raw_attributes, attributes_data = hid.read_query(device, 'attributes')
    result = dict(attributes_raw=raw_attributes.hex(), attributes=decode_attributes(attributes_data),
                  records={})
    for path in RECORD_PATHS:
        raw, payload = hid.read_query(device, path)
        record = decode_calibration(payload)
        if not record['bounds_valid']:
            raise RuntimeError(f'{path} returned an invalid calibration record')
        result['records'][path] = dict(raw=raw.hex(), payload=payload.hex(), decoded=record)
    return result


def read_calibration_state_fresh(hid, expected_info, settle_seconds=1.0, attempts=10):
    """Retry on fresh handles while Windows recovers from a setting write."""
    # The original handle may return DeviceIoControl errors briefly after a write.
    # Fresh handles avoid treating that Windows behavior as a failed controller write.
    time.sleep(settle_seconds)
    last_error = None
    for attempt in range(attempts):
        fresh = None
        try:
            info = select(hid.devices(), 'auto')
            if info['serial'] != expected_info['serial']:
                raise RuntimeError('The controller present after the write is not the original device')
            fresh = hid.open(info['path'])
            return read_calibration_state(hid, fresh)
        except (OSError, RuntimeError, ValueError) as error:
            last_error = error
        finally:
            if fresh:
                hid.s.SDL_hid_close(fresh)
        if attempt + 1 < attempts:
            time.sleep(1.0)
    raise RuntimeError(f'Controller did not accept feature readback after {attempts} fresh-handle '
                       f'attempts: {last_error}')


def restore_record_bytes(hid, device, info, desired):
    """Stage, verify, persist, and verify two already validated record byte strings."""
    # Verification between stage and commit preserves a safe power-cycle escape point.
    for path in RECORD_PATHS:
        hid.setting(device, 'stage', path, desired[path])
    staged = read_calibration_state_fresh(hid, info)
    if any(staged['records'][path]['payload'] != desired[path].hex() for path in RECORD_PATHS):
        raise RuntimeError('Automatic restore staging did not verify; power-cycle and restore manually')
    # Only persist after both volatile records have been read back byte-for-byte.
    for path in RECORD_PATHS:
        hid.setting(device, 'commit', path)
    after = read_calibration_state_fresh(hid, info)
    if any(after['records'][path]['payload'] != desired[path].hex() for path in RECORD_PATHS):
        raise RuntimeError('Automatic restore persistence did not verify; restore manually')
    return dict(staged=staged, after=after, verified=True)


def backup_fingerprint(serial, build, records):
    """Bind backup bytes to the controller serial, build, and record ordering."""
    digest = hashlib.sha256()
    # Domain separation prevents this digest from being confused with another format.
    digest.update(b'SC2026-STICK-BACKUP-V1\0')
    digest.update(serial.encode('utf-8'))
    digest.update(b'\0')
    digest.update(int(build).to_bytes(4, 'little'))
    for path in RECORD_PATHS:
        payload = records[path]['payload']
        digest.update(bytes.fromhex(payload) if isinstance(payload, str) else bytes(payload))
    return digest.hexdigest()


def make_backup(info, state):
    """Create the immutable JSON value written before calibration changes."""
    build = state['attributes'].get(4)
    value = dict(schema=BACKUP_SCHEMA,
                 created_utc=datetime.now(timezone.utc).isoformat(),
                 device=dict(vid=info['vid'], pid=info['pid'], release=info['release'],
                             serial=info['serial'], name=info['name']),
                 firmware_build=build, records=state['records'])
    value['fingerprint_sha256'] = backup_fingerprint(info['serial'], build, value['records'])
    return value


def validate_backup(value):
    """Reject edited or malformed backups without imposing a firmware allowlist."""
    if value.get('schema') != BACKUP_SCHEMA:
        raise ValueError('File is not a supported immutable stick backup')
    device = value.get('device', {})
    serial, build, records = device.get('serial'), value.get('firmware_build'), value.get('records', {})
    if (not isinstance(serial, str) or not serial or not isinstance(build, int)
            or isinstance(build, bool) or not 0 <= build <= 0xFFFFFFFF):
        raise ValueError('Backup identity or firmware build is unsupported')
    for path in RECORD_PATHS:
        try:
            payload = bytes.fromhex(records[path]['payload'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f'Backup has no valid {path} payload') from error
        if not decode_calibration(payload)['bounds_valid']:
            raise ValueError(f'Backup contains invalid bounds for {path}')
    expected = backup_fingerprint(serial, build, records)
    # compare_digest avoids ordinary early-exit string comparison for the fingerprint.
    if not hmac.compare_digest(value.get('fingerprint_sha256', ''), expected):
        raise ValueError('Backup fingerprint does not match its device identity and records')
    return value


def backup_calibration_issues(backup):
    """Return strict geometry issues used before a cross-firmware restore."""
    issues = []
    for path in RECORD_PATHS:
        record = decode_calibration(bytes.fromhex(backup['records'][path]['payload']))
        issues.extend(f'{path}: {issue}' for issue in calibration_issues(record))
    return issues


def validate_restore_firmware(backup, current_build, allow_cross_firmware=False):
    """Require explicit consent and strict geometry for cross-firmware restore."""
    if backup['firmware_build'] == current_build:
        return False
    if not allow_cross_firmware:
        raise ValueError('Cross-firmware restore requires explicit confirmation')
    issues = backup_calibration_issues(backup)
    if issues:
        raise ValueError('Cross-firmware backup failed strict calibration checks:\n' +
                         '\n'.join(issues))
    return True



