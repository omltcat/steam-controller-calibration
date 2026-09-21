"""SDL HID transport for the direct-USB Steam Controller vendor interface.

This module only moves allowlisted protocol packets. Encoding and validation live in
protocol.py, while persistence safeguards live in calibration_store.py.
"""
import ctypes as C
import time

from .protocol import (AXES, calibration_request, decode_sticks, feature_payload,
                       read_request, setting_request)


class HID:
    """Thin SDL HIDAPI wrapper for enumeration, feature reports, and samples."""

    def __enter__(self):
        # Enumeration must include Valve's vendor collection, not only gamepads.
        import sdl3
        self.s = sdl3
        self.s.SDL_SetHint(b'SDL_HIDAPI_ENUMERATE_ONLY_CONTROLLERS', b'0')
        if self.s.SDL_hid_init() < 0:
            raise RuntimeError(self.error())
        return self

    def __exit__(self, *args):
        # SDL owns process-wide HIDAPI initialization and cleanup.
        self.s.SDL_hid_exit()

    def error(self):
        return (self.s.SDL_GetError() or b'HID operation failed').decode(errors='replace')

    def devices(self):
        """Return only the known 2026 Valve controller product interfaces."""
        head = self.s.SDL_hid_enumerate(0x28DE, 0)
        current, result = head, []
        try:
            while current:
                info = current.contents
                if info.product_id in (0x1302, 0x1303, 0x1304, 0x1305):
                    result.append(dict(path=info.path.decode(), vid=info.vendor_id,
                        pid=info.product_id, interface=info.interface_number,
                        usage_page=info.usage_page, usage=info.usage,
                        release=info.release_number, name=info.product_string,
                        serial=info.serial_number, bus=int(info.bus_type)))
                current = C.cast(info.next, C.POINTER(self.s.SDL_hid_device_info))
        finally:
            self.s.SDL_hid_free_enumeration(head)
        return result

    def open(self, path):
        device = self.s.SDL_hid_open_path(path.encode())
        if not device:
            raise RuntimeError(self.error())
        return device

    def read_query(self, device, kind):
        """Send one allowlisted read request and decode its feature envelope."""
        request = read_request(kind)
        buffer = (C.c_ubyte * len(request)).from_buffer_copy(request)
        if self.s.SDL_hid_send_feature_report(device, buffer, len(buffer)) != len(buffer):
            raise RuntimeError('Sending read request: ' + self.error())
        # The firmware answers through a subsequent Get Feature request.
        time.sleep(0.05)
        reply = (C.c_ubyte * 65)()
        reply[0] = 1
        count = self.s.SDL_hid_get_feature_report(device, reply, len(reply))
        if count < 0:
            raise RuntimeError('Reading response: ' + self.error())
        raw = bytes(reply[:count])
        return raw, feature_payload(raw, request[1])

    def calibration_phase(self, device, phase):
        self.send_request(device, calibration_request(phase), f'calibration phase {phase}')

    def send_request(self, device, request, label):
        """Require SDL to transfer the complete fixed-size feature report."""
        buffer = (C.c_ubyte * len(request)).from_buffer_copy(request)
        count = self.s.SDL_hid_send_feature_report(device, buffer, len(buffer))
        if count != len(buffer):
            raise RuntimeError(f'Sending {label}: ' + self.error())

    def setting(self, device, operation, path, data=None):
        self.send_request(device, setting_request(operation, path, data),
                          f'{operation} for {path}')

    def sample_sticks(self, device, seconds):
        """Collect firmware-processed axes for a bounded measurement window."""
        values = {axis: [] for axis in AXES}
        buffer = (C.c_ubyte * 256)()
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            count = self.s.SDL_hid_read_timeout(device, buffer, len(buffer), 100)
            if count < 0:
                raise RuntimeError('Reading stick reports: ' + self.error())
            if count:
                sticks = decode_sticks(bytes(buffer[:count]))
                if sticks:
                    for axis in AXES:
                        values[axis].append(sticks[axis])
        return values


def select(devices, path):
    """Select an exact path or the sole direct-USB vendor HID collection."""
    if path == 'auto':
        # Col03 is the direct USB vendor collection used for feature operations.
        matches = [d for d in devices if d['pid'] == 0x1302 and d['bus'] == 1 and
                   d['usage_page'] >= 0xFF00 and d['usage'] == 1]
        if len(matches) != 1:
            raise ValueError(f'Expected one direct USB vendor collection; found {len(matches)}')
        return matches[0]
    matches = [d for d in devices if d['path'] == path]
    if len(matches) != 1:
        raise ValueError('Path is not a currently enumerated 2026 Valve device; run list again')
    return matches[0]



