"""Background controller I/O and guarded calibration workflows for the GUI.

The Tk thread never talks to HID directly. ControllerWorker owns the device handle,
receives commands through a queue, and publishes small event dictionaries back to Tk.
"""
import ctypes as C
import json
from pathlib import Path
import queue
import threading
import time

from .calibration_store import (make_backup, read_calibration_state,
                                read_calibration_state_fresh, restore_record_bytes,
                                validate_backup, validate_restore_firmware, write_json)
from .hid_transport import HID, select
from .protocol import AXES, calibration_issues, decode_stick_touches, decode_sticks
from .gui_support import (CENTER_SECONDS, PATHS, RANGE_SECONDS, RECONNECT_SECONDS,
                          new_capture_path)
from .i18n import tr, tr_error
from .sample_analysis import summarize


class ControllerWorker(threading.Thread):
    """Own the HID handle and serialize controller operations off the Tk thread."""

    def __init__(self):
        super().__init__(daemon=True)
        # Commands flow Tk -> worker; events flow worker -> Tk.
        self.commands = queue.Queue()
        self.events = queue.Queue()
        self.latest_sticks = None
        self.latest_sample = None
        self.sample_id = 0
        self.running = True
        self.hid = self.device = self.info = None
        self.startup_backup = self.current_state = self.staged = self.auto = None

    def emit(self, kind, **values):
        self.events.put(dict(kind=kind, **values))

    def run(self):
        """Poll commands/input and quietly rediscover controllers after unplugging."""
        try:
            with HID() as hid:
                self.hid = hid
                buffer = (C.c_ubyte * 256)()
                next_connect = 0.0
                while self.running:
                    # Never block on the command queue; input reports must keep flowing.
                    try:
                        command, value = self.commands.get_nowait()
                    except queue.Empty:
                        command = None
                    if command == 'stop':
                        self.running = False
                        continue
                    if not self.device:
                        # Missing hardware is a normal idle state, so retry without a dialog.
                        if time.monotonic() >= next_connect:
                            try:
                                self.connect()
                            except (OSError, RuntimeError, ValueError, KeyError) as error:
                                self.emit('disconnected', message=self.connection_wait_message(error))
                                next_connect = time.monotonic() + RECONNECT_SECONDS
                        time.sleep(0.05)
                    elif command:
                        # Device disappearance is handled as hotplug; real operation errors
                        # are sent to the GUI for a visible error dialog.
                        try:
                            self.handle(command, value)
                        except (OSError, RuntimeError, ValueError, KeyError) as error:
                            if self.controller_present():
                                self.emit('error', message=tr_error(str(error)))
                            else:
                                self.disconnect(tr('connection.disconnected'))
                                next_connect = time.monotonic() + RECONNECT_SECONDS
                    else:
                        # Idle time is used to maintain the live view and history plot.
                        count = hid.s.SDL_hid_read_timeout(self.device, buffer, len(buffer), 20)
                        if count > 0:
                            try:
                                sticks = decode_sticks(bytes(buffer[:count]))
                            except ValueError:
                                sticks = None
                            if sticks:
                                self.publish_sticks(sticks)
                        elif count < 0:
                            self.disconnect(tr('connection.disconnected'))
                            next_connect = time.monotonic() + RECONNECT_SECONDS
        except Exception as error:
            self.emit('error', message=tr('error.backend_stopped', error=error))
        finally:
            self.close_device()

    def close_device(self):
        if self.device and self.hid:
            self.hid.s.SDL_hid_close(self.device)
        self.device = None

    def refresh_device(self):
        """Reopen the same controller after a firmware setting write settles."""
        expected_serial = self.info['serial'] if self.info else None
        self.close_device()
        time.sleep(0.25)
        info = select(self.hid.devices(), 'auto')
        if expected_serial and info['serial'] != expected_serial:
            raise RuntimeError(tr('connection.different_controller'))
        self.info = info
        self.device = self.hid.open(info['path'])

    @staticmethod
    def connection_wait_message(error):
        message = str(error)
        if message.startswith('Expected one direct USB vendor collection; found 0'):
            return tr('connection.no_controller')
        if message.startswith('Expected one direct USB vendor collection; found'):
            return tr('connection.one_controller')
        return tr('connection.not_ready', message=message)

    def controller_present(self):
        try:
            return bool(self.info and any(device['serial'] == self.info['serial']
                       for device in self.hid.devices()))
        except Exception:
            return False

    def disconnect(self, message):
        # Never carry staged bytes or an automatic session onto a replacement device.
        self.close_device()
        self.info = self.startup_backup = self.current_state = self.staged = self.auto = None
        self.latest_sticks = self.latest_sample = None
        self.emit('disconnected', message=message)

    def connect(self):
        """Open, identify, back up, and announce a direct-USB controller."""
        self.close_device()
        info = select(self.hid.devices(), 'auto')
        device = self.hid.open(info['path'])
        try:
            state = read_calibration_state(self.hid, device)
            build = state['attributes'].get(4)
            if not isinstance(build, int):
                raise RuntimeError(tr('connection.unsupported_firmware'))
        except Exception:
            self.hid.s.SDL_hid_close(device)
            raise
        self.info, self.device = info, device
        self.staged = self.auto = None
        # Every connection gets the same local startup snapshot. Firmware support
        # status affects write warnings later in Tk; it never changes this backup.
        backup = make_backup(info, state)
        path = new_capture_path('gui-startup-backup')
        write_json(path, backup)
        self.startup_backup = backup
        self.current_state = state
        self.emit('connected', info=info, backup=str(path), state=state,
                  firmware_build=build)

    def publish_sticks(self, sticks):
        # Replacing one immutable snapshot avoids sharing mutable axis dictionaries.
        self.sample_id += 1
        self.latest_sticks = sticks
        self.latest_sample = (self.sample_id, time.monotonic(), dict(sticks))

    def sample_sticks(self, seconds):
        """Collect processed axes while continuing to feed the live display."""
        values = {axis: [] for axis in AXES}
        buffer = (C.c_ubyte * 256)()
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            count = self.hid.s.SDL_hid_read_timeout(self.device, buffer, len(buffer), 100)
            if count < 0:
                raise RuntimeError(tr('error.read_sticks', error=self.hid.error()))
            if not count:
                continue
            sticks = decode_sticks(bytes(buffer[:count]))
            if sticks:
                self.publish_sticks(sticks)
                for axis in AXES:
                    values[axis].append(sticks[axis])
        return values

    def wait_for_stick_release(self, timeout=10.0, stable_reports=8):
        """Require both capacitive stick sensors to be released before phase 3."""
        buffer = (C.c_ubyte * 256)()
        deadline = time.monotonic() + timeout
        clear_reports = 0
        observed = {'reports': 0, 'left_touched': 0, 'right_touched': 0}
        while time.monotonic() < deadline:
            count = self.hid.s.SDL_hid_read_timeout(self.device, buffer, len(buffer), 100)
            if count < 0:
                raise RuntimeError(tr('error.read_touch', error=self.hid.error()))
            if not count:
                continue
            report = bytes(buffer[:count])
            sticks = decode_sticks(report)
            touches = decode_stick_touches(report)
            if sticks:
                self.publish_sticks(sticks)
            if touches is None:
                continue
            observed['reports'] += 1
            observed['left_touched'] += int(touches['left'])
            observed['right_touched'] += int(touches['right'])
            # Consecutive clear reports reject a single noisy capacitive transition.
            clear_reports = clear_reports + 1 if not any(touches.values()) else 0
            if clear_reports >= stable_reports:
                observed['clear_reports_required'] = stable_reports
                return observed
        raise RuntimeError(tr('error.touch_release_required'))

    def observe_stick_touches(self, seconds=0.5):
        """Record post-commit touch reports to distinguish controller and Steam latches."""
        buffer = (C.c_ubyte * 256)()
        end = time.monotonic() + seconds
        observed = {'reports': 0, 'left_touched': 0, 'right_touched': 0}
        while time.monotonic() < end:
            count = self.hid.s.SDL_hid_read_timeout(self.device, buffer, len(buffer), 100)
            if count < 0:
                raise RuntimeError(tr('error.read_post_commit_touch', error=self.hid.error()))
            if not count:
                continue
            report = bytes(buffer[:count])
            sticks = decode_sticks(report)
            touches = decode_stick_touches(report)
            if sticks:
                self.publish_sticks(sticks)
            if touches is not None:
                observed['reports'] += 1
                observed['left_touched'] += int(touches['left'])
                observed['right_touched'] += int(touches['right'])
        return observed

    def handle(self, command, value):
        """Dispatch one command queued by the presentation layer."""
        if command == 'stop':
            self.running = False
        elif command == 'read':
            self.current_state = read_calibration_state(self.hid, self.device)
            self.emit('records', state=self.current_state)
        elif command == 'stage':
            self.stage(value)
        elif command == 'commit':
            self.commit()
        elif command == 'restore':
            self.restore_file(value)
        elif command == 'auto_start':
            self.auto_start()
        elif command == 'auto_commit':
            self.auto_commit()
        elif command == 'auto_cancel':
            # Phase 0 removes the volatile sampling callback without persisting.
            self.hid.calibration_phase(self.device, 0)
            self.auto = None
            self.emit('status', message=tr('status.auto_cancelled'))

    def stage(self, records):
        # Staging is volatile; verify its readback before enabling persistent Save.
        self.emit('status', message=tr('status.staging'))
        for path in PATHS:
            self.hid.setting(self.device, 'stage', path, records[path])
        staged = read_calibration_state_fresh(self.hid, self.info)
        if any(staged['records'][p]['payload'] != records[p].hex() for p in PATHS):
            raise RuntimeError(tr('error.temporary_readback'))
        self.staged = records
        self.current_state = staged
        self.refresh_device()
        self.emit('staged', state=staged)

    def commit(self):
        # Persist only the bytes that were already verified during staging.
        if not self.staged:
            raise ValueError(tr('error.stage_before_save'))
        self.emit('status', message=tr('status.saving'))
        for path in PATHS:
            self.hid.setting(self.device, 'commit', path)
        after = read_calibration_state_fresh(self.hid, self.info)
        if any(after['records'][p]['payload'] != self.staged[p].hex() for p in PATHS):
            raise RuntimeError(tr('error.persisted_readback'))
        self.current_state, self.staged = after, None
        self.refresh_device()
        self.emit('saved', state=after)

    def restore_file(self, request):
        # Validation binds the backup to the current serial and firmware build.
        if isinstance(request, dict):
            filename = request['filename']
            allow_cross_firmware = bool(request.get('allow_cross_firmware'))
        else:
            filename, allow_cross_firmware = request, False
        with Path(filename).open(encoding='utf-8') as stream:
            backup = validate_backup(json.load(stream))
        if backup['device']['serial'] != self.info['serial']:
            raise ValueError(tr('error.other_controller_backup'))
        current_build = self.current_state['attributes'].get(4)
        validate_restore_firmware(backup, current_build, allow_cross_firmware)
        desired = {p: bytes.fromhex(backup['records'][p]['payload']) for p in PATHS}
        result = restore_record_bytes(self.hid, self.device, self.info, desired)
        self.current_state, self.staged = result['after'], None
        self.refresh_device()
        self.emit('restored', state=result['after'], filename=str(filename))

    def auto_start(self):
        """Collect center/range candidates without persisting them."""
        self.emit('status', tone='hold',
                  message=tr('status.center_check'))
        before = read_calibration_state(self.hid, self.device)
        backup = make_backup(self.info, before)
        backup_path = new_capture_path('before-auto-calibration')
        write_json(backup_path, backup)
        center = summarize(self.sample_sticks(CENTER_SECONDS))
        # This passive preflight catches gross drift/noise before entering firmware mode.
        if any(abs(center[a]['median']) > 5000 or center[a]['peak_to_peak'] > 3000 for a in AXES):
            raise RuntimeError(tr('error.center_preflight'))
        phase_started = False
        try:
            self.emit('status', tone='hold',
                      message=tr('status.center_collect'))
            self.hid.calibration_phase(self.device, 1)
            phase_started = True
            time.sleep(CENTER_SECONDS)
            # Switch the firmware to range collection before inviting movement.
            self.hid.calibration_phase(self.device, 2)
            self.emit('status', tone='move',
                      message=tr('status.rotate'))
            ranges = summarize(self.sample_sticks(RANGE_SECONDS))
            reached = all(ranges[a]['minimum'] <= -20000 and ranges[a]['maximum'] >= 20000
                          for a in AXES)
            if not reached:
                raise RuntimeError(tr('error.full_travel'))
        except Exception:
            if phase_started:
                try:
                    self.hid.calibration_phase(self.device, 0)
                except RuntimeError:
                    pass
            raise
        self.auto = dict(before=before, backup=backup, backup_path=str(backup_path),
                         center=center, ranges=ranges)
        self.emit('auto_ready', backup=str(backup_path), ranges=ranges)

    def auto_commit(self):
        """Persist candidates, validate geometry, and roll back unsafe results."""
        if not self.auto:
            raise ValueError(tr('error.no_auto_pending'))
        self.emit('status', tone='stop',
                  message=tr('status.wait_touch_release'))
        try:
            pre_commit_touch = self.wait_for_stick_release()
        except RuntimeError:
            # A stuck touch bit can latch Steam Input's gyro activator, so abort safely.
            self.hid.calibration_phase(self.device, 0)
            self.auto = None
            raise RuntimeError(tr('error.touch_not_released'))
        self.emit('status', message=tr('status.committing_auto'))
        self.hid.calibration_phase(self.device, 3)
        after = read_calibration_state_fresh(self.hid, self.info)
        post_commit_touch = self.observe_stick_touches()
        issues = {p: calibration_issues(after['records'][p]['decoded']) for p in PATHS}
        # Preserve enough telemetry to distinguish controller touch state from a
        # host-side Steam Input latch if gyro activation misbehaves again.
        session = dict(kind='steam-controller-2026-gui-calibration', device=self.info,
                       firmware_build=after['attributes'].get(4),
                       immutable_backup=self.auto['backup_path'], before=self.auto['before'],
                       preflight_center=self.auto['center'], range_observation=self.auto['ranges'],
                       pre_commit_touch=pre_commit_touch,
                       post_commit_touch=post_commit_touch,
                       after=after, record_issues=issues, committed=True)
        output = new_capture_path('gui-calibration-session')
        if any(issues.values()):
            # Candidate bytes are already persistent here; restore the connection backup.
            desired = {p: bytes.fromhex(self.auto['before']['records'][p]['payload']) for p in PATHS}
            try:
                rollback = restore_record_bytes(self.hid, self.device, self.info, desired)
                session['automatic_restore'] = rollback
                self.current_state = rollback['after']
            except RuntimeError as error:
                session['automatic_restore'] = dict(verified=False, error=str(error))
            write_json(output, session)
            self.auto = None
            self.refresh_device()
            if session['automatic_restore'].get('verified'):
                self.emit('records', state=self.current_state)
                raise RuntimeError(tr('error.auto_rolled_back'))
            raise RuntimeError(tr('error.auto_rollback_failed'))
        write_json(output, session)
        self.current_state, self.auto, self.staged = after, None, None
        self.refresh_device()
        self.emit('auto_saved', state=after, output=str(output))




