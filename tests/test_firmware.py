import unittest

from src.calibration_store import (backup_calibration_issues, make_backup,
                                   validate_backup, validate_restore_firmware)
from src.firmware_support import HARDWARE_TESTED, REVIEWED, UNKNOWN, firmware_support
from src.protocol import decode_calibration


class FirmwareCompatibilityTests(unittest.TestCase):
    def test_registry_distinguishes_tested_reviewed_and_unknown(self):
        self.assertEqual(firmware_support(0x6A628345)['level'], HARDWARE_TESTED)
        self.assertEqual(firmware_support(0x6AA43B55)['level'], REVIEWED)
        self.assertEqual(firmware_support(0xDEADBEEF)['level'], UNKNOWN)

    def test_reviewed_firmware_backup_validates_without_old_allowlist(self):
        payload = bytes.fromhex('0200bd01790b5d06640649011c0b4d065306')
        record = dict(payload=payload.hex(), decoded=decode_calibration(payload))
        state = dict(attributes={4: 0x6AA43B55},
                     records={'cal/joy_l': record, 'cal/joy_r': record})
        info = dict(vid=0x28DE, pid=0x1302, release=1,
                    serial='FXA-TEST', name='Steam Controller')
        backup = make_backup(info, state)
        self.assertIs(validate_backup(backup), backup)
        self.assertEqual(backup_calibration_issues(backup), [])
        with self.assertRaisesRegex(ValueError, 'explicit confirmation'):
            validate_restore_firmware(backup, 0x6A628345)
        self.assertTrue(validate_restore_firmware(
            backup, 0x6A628345, allow_cross_firmware=True))
        self.assertFalse(validate_restore_firmware(backup, 0x6AA43B55))

    def test_cross_firmware_strict_check_rejects_bad_geometry(self):
        payload = bytes.fromhex('0200bf017f0bfb01960a4701200b3f061e0b')
        record = dict(payload=payload.hex(), decoded=decode_calibration(payload))
        state = dict(attributes={4: 0x6AA43B55},
                     records={'cal/joy_l': record, 'cal/joy_r': record})
        info = dict(vid=0x28DE, pid=0x1302, release=1,
                    serial='FXA-TEST', name='Steam Controller')
        backup = make_backup(info, state)
        issues = backup_calibration_issues(backup)
        self.assertTrue(any('center width' in issue for issue in issues))
        with self.assertRaisesRegex(ValueError, 'strict calibration checks'):
            validate_restore_firmware(backup, 0x6A628345, allow_cross_firmware=True)


if __name__ == '__main__':
    unittest.main()
