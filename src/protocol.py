"""Strictly allowlisted Triton inspection and calibration formats."""
import struct

AXES = ('left_x', 'left_y', 'right_x', 'right_y')
# CLI automatic calibration remains locked to the hardware-tested build. The GUI
# uses firmware_support.py for reviewed and explicitly accepted unknown builds.
SUPPORTED_CALIBRATION_BUILD = 0x6A628345
# On-device order: record type, then min/max/center band for X and Y.
STICK_FIELDS = ('type', 'x_min', 'x_max', 'x_center_min', 'x_center_max',
                'y_min', 'y_max', 'y_center_min', 'y_center_max')
RAW_STICK_LIMIT = 4095


def decode_sticks(report):
    """Decode firmware-processed stick values, not ADC samples. ID included."""
    sizes = {0x42: 54, 0x45: 46, 0x47: 46}
    if not report or report[0] not in sizes:
        return None
    if len(report) < sizes[report[0]]:
        raise ValueError('Truncated Triton state report')
    # All supported report revisions keep the four signed stick axes at byte 10.
    return dict(zip(AXES, struct.unpack_from('<hhhh', report, 10)))


def decode_stick_touches(report):
    """Decode the two capacitive stick-touch bits from a Triton state report."""
    sizes = {0x42: 54, 0x45: 46, 0x47: 46}
    if not report or report[0] not in sizes:
        return None
    if len(report) < sizes[report[0]]:
        raise ValueError('Truncated Triton state report')
    # The 32-bit button field starts at byte 2; bits 24 and 20 are stick touch.
    buttons = struct.unpack_from('<I', report, 2)[0]
    return {'left': bool(buttons & (1 << 24)),
            'right': bool(buttons & (1 << 20))}


def decode_calibration(data):
    """Decode the 18-byte RE storage layout; does not establish stock compatibility."""
    if len(data) != 18:
        raise ValueError(f'Expected an 18-byte stick record; received {len(data)} bytes')
    fields = dict(zip(STICK_FIELDS, struct.unpack('<9H', data)))
    fields['bounds_valid'] = all(
        fields[f'{a}_min'] < fields[f'{a}_center_min'] <= fields[f'{a}_center_max'] < fields[f'{a}_max']
        for a in ('x', 'y'))
    return fields


def encode_calibration(fields):
    """Encode one strictly validated 18-byte stick calibration record."""
    try:
        values = [int(fields[name]) for name in STICK_FIELDS]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Calibration record fields must be integers') from error
    if any(value < 0 or value > 0xFFFF for value in values):
        raise ValueError('Calibration values must fit unsigned 16-bit storage')
    data = struct.pack('<9H', *values)
    decoded = decode_calibration(data)
    if not decoded['bounds_valid']:
        raise ValueError('Each axis must satisfy min < center_min <= center_max < max')
    return data


def calibration_issues(record):
    """Return reasons a numerically ordered record is unsafe for stick mapping."""
    issues = []
    if not record.get('bounds_valid'):
        return ['calibration bounds are not ordered']
    for axis in ('x', 'y'):
        minimum, maximum = record[f'{axis}_min'], record[f'{axis}_max']
        center_min, center_max = record[f'{axis}_center_min'], record[f'{axis}_center_max']
        span = maximum - minimum
        center_width = center_max - center_min
        # These checks reject the failure mode seen when movement polluted phase 1.
        if span < 1500:
            issues.append(f'{axis} travel span {span} is below 1500')
        if center_width > max(200, span // 10):
            issues.append(f'{axis} center width {center_width} exceeds 10% of travel')
        if center_min - minimum < span // 5 or maximum - center_max < span // 5:
            issues.append(f'{axis} center window is too close to a travel limit')
    return issues


def scale_raw_stick_axis(sample, minimum, maximum, center_min, center_max):
    """Reference of the recovered stock piecewise mapping, including 2% endpoint margin."""
    # The center interval maps exactly to zero. Each side scales independently.
    if sample < center_min:
        denominator = max(((center_min - minimum) * 98) // 100, 1)
        value = int((sample - center_min) * 32768 / denominator)
        return max(-32768, min(0, value))
    if sample > center_max:
        denominator = max(((maximum - center_max) * 98) // 100, 1)
        value = int((sample - center_max) * 32767 / denominator)
        return max(0, min(32767, value))
    return 0


def raw_lookup(record, axis, raw_limit=RAW_STICK_LIMIT):
    """Map each processed output to the raw-value interval capable of producing it."""
    arguments = (record[f'{axis}_min'], record[f'{axis}_max'],
                 record[f'{axis}_center_min'], record[f'{axis}_center_max'])
    result = {}
    for sample in range(raw_limit + 1):
        output = scale_raw_stick_axis(sample, *arguments)
        if output in result:
            result[output] = (result[output][0], sample)
        else:
            result[output] = (sample, sample)
    return result


def read_request(kind):
    """Only allow identified read queries; 64 bytes including report ID, per SDL."""
    if kind == 'attributes':
        opcode, payload = 0x83, b''
    elif kind in ('cal/joy_l', 'cal/joy_r'):
        opcode, payload = 0xED, kind.encode('ascii') + b'\0'
    else:
        raise ValueError('Only attributes and the two stick records may be queried')
    # Feature reports use: report ID, opcode, payload length, payload, zero padding.
    return bytes([1, opcode, len(payload)]) + payload + bytes(61 - len(payload))


def calibration_request(phase):
    """Build the exact-build 0xD8 request. Payload byte 0 is ignored by 6A628345."""
    if phase not in (0, 1, 2, 3):
        raise ValueError('Calibration phase must be 0 (cancel), 1 (center), 2 (range), or 3 (commit)')
    payload = bytes([0, phase])
    return bytes([1, 0xD8, len(payload)]) + payload + bytes(61 - len(payload))


def setting_request(operation, path, data=None):
    """Build exact-build setting stage/commit requests for stick records only."""
    if path not in ('cal/joy_l', 'cal/joy_r'):
        raise ValueError('Only the two stick calibration records may be restored')
    if operation == 'stage':
        if data is None:
            raise ValueError('Stage requires an 18-byte record')
        decoded = decode_calibration(data)
        if not decoded['bounds_valid']:
            raise ValueError('Refusing to stage an invalid calibration record')
        opcode = 0xEE
        payload = path.encode('ascii') + b'\0' + bytes(data)
    elif operation == 'commit':
        if data is not None:
            raise ValueError('Commit accepts a path only')
        opcode = 0xEF
        payload = path.encode('ascii') + b'\0'
    else:
        raise ValueError('Setting operation must be stage or commit')
    if len(payload) > 61:
        raise ValueError('Setting payload is too large')
    return bytes([1, opcode, len(payload)]) + payload + bytes(61 - len(payload))


def feature_payload(reply, opcode):
    """Validate a feature reply envelope and return only its declared payload."""
    if len(reply) < 3 or reply[0] != 1 or reply[1] != opcode:
        raise ValueError('Unexpected feature response ID/opcode (possibly another HID client)')
    length = reply[2]
    if length > 61 or length + 3 > len(reply):
        raise ValueError('Invalid or truncated feature response length')
    return reply[3:3 + length]


def decode_attributes(data):
    """Decode repeated one-byte key/four-byte little-endian value entries."""
    if not data or len(data) % 5:
        raise ValueError('Malformed attribute response')
    return {data[i]: int.from_bytes(data[i + 1:i + 5], 'little')
            for i in range(0, len(data), 5)}
