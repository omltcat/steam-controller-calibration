import struct
import unittest

from src.protocol import (calibration_issues, calibration_request, decode_calibration,
                          decode_stick_touches, decode_sticks, encode_calibration,
                          feature_payload, raw_lookup, read_request, scale_raw_stick_axis,
                          setting_request)


class ProtocolTests(unittest.TestCase):
    def test_signed_sticks_and_report_versions(self):
        for report_id, length in ((0x42, 54), (0x45, 46), (0x47, 46)):
            report = bytearray(length)
            report[0] = report_id
            struct.pack_into('<hhhh', report, 10, -32768, 32767, -123, 456)
            self.assertEqual(list(decode_sticks(report).values()), [-32768, 32767, -123, 456])
            with self.assertRaises(ValueError):
                decode_sticks(report[:17])
        self.assertIsNone(decode_sticks(b'\x43\0'))

    def test_stick_touch_bits(self):
        report = bytearray(54)
        report[0] = 0x42
        struct.pack_into('<I', report, 2, (1 << 24) | (1 << 20))
        self.assertEqual(decode_stick_touches(report), {'left': True, 'right': True})
        struct.pack_into('<I', report, 2, 0)
        self.assertEqual(decode_stick_touches(report), {'left': False, 'right': False})
        self.assertIsNone(decode_stick_touches(b'\x43\0'))
        with self.assertRaises(ValueError):
            decode_stick_touches(bytes([0x42, 0]))

    def test_request_allowlist(self):
        self.assertEqual(read_request('cal/joy_l')[:13], b'\x01\xed\x0acal/joy_l\0')
        self.assertEqual(len(read_request('cal/joy_r')), 64)
        for forbidden in ('0xbf', 'cal/trg_l', 'stage', 'factory-reset', 'cal/joy_l\0oops'):
            with self.assertRaises(ValueError):
                read_request(forbidden)

    def test_calibration_phase_allowlist(self):
        self.assertEqual(calibration_request(1)[:5], b'\x01\xd8\x02\x00\x01')
        self.assertEqual(calibration_request(3)[:5], b'\x01\xd8\x02\x00\x03')
        self.assertEqual(calibration_request(0)[:5], b'\x01\xd8\x02\x00\x00')
        self.assertEqual(len(calibration_request(2)), 64)
        for phase in (-1, 4, 0xBF):
            with self.assertRaises(ValueError):
                calibration_request(phase)

    def test_restore_request_allowlist_and_layout(self):
        valid = struct.pack('<9H', 1, 100, 4000, 2000, 2100, 100, 4000, 2000, 2100)
        staged = setting_request('stage', 'cal/joy_l', valid)
        self.assertEqual(staged[:13], b'\x01\xee\x1ccal/joy_l\0')
        self.assertEqual(staged[13:31], valid)
        self.assertEqual(setting_request('commit', 'cal/joy_r')[:13],
                         b'\x01\xef\x0acal/joy_r\0')
        self.assertEqual(len(staged), 64)
        for args in (('stage', 'cal/trg_l', valid), ('stage', 'cal/joy_l', bytes(18)),
                     ('stage', 'cal/joy_l', None), ('commit', 'cal/joy_l', valid),
                     ('erase', 'cal/joy_l', None)):
            with self.assertRaises(ValueError):
                setting_request(*args)

    def test_response_rejects_wrong_routing_and_lengths(self):
        self.assertEqual(feature_payload(b'\x01\xed\x02ab', 0xED), b'ab')
        for reply in (b'', b'\x02\xed\0', b'\x01\xbf\0', b'\x01\xed\x12\0',
                      bytes([1, 0xED, 62]) + bytes(62)):
            with self.assertRaises(ValueError):
                feature_payload(reply, 0xED)

    def test_record_validation(self):
        valid = struct.pack('<9H', 1, 100, 4000, 2000, 2100, 100, 4000, 2000, 2100)
        decoded = decode_calibration(valid)
        self.assertTrue(decoded['bounds_valid'])
        self.assertEqual(calibration_issues(decoded), [])
        self.assertEqual(encode_calibration(decoded), valid)
        self.assertFalse(decode_calibration(bytes(18))['bounds_valid'])
        for data in (b'', b'\0', valid + b'\0'):
            with self.assertRaises(ValueError):
                decode_calibration(data)

        with self.assertRaises(ValueError):
            encode_calibration(dict(decoded, x_center_min=5000))

    def test_failed_hardware_record_is_rejected(self):
        failed = bytes.fromhex('0200bf017f0bfb01960a4701200b3f061e0b')
        issues = calibration_issues(decode_calibration(failed))
        self.assertTrue(any('center width' in issue for issue in issues))

    def test_raw_to_output_reference_and_inverse_intervals(self):
        record = decode_calibration(bytes.fromhex('0200bd01790b5d06640649011c0b4d065306'))
        self.assertEqual(scale_raw_stick_axis(1632, 445, 2937, 1629, 1636), 0)
        lookup = raw_lookup(record, 'x')
        self.assertEqual(lookup[0], (1629, 1636))
        self.assertEqual(lookup[32767], (2910, 4095))
        self.assertEqual(lookup[-32768], (0, 469))
        self.assertEqual(lookup[128], (1641, 1641))


if __name__ == '__main__':
    unittest.main()
