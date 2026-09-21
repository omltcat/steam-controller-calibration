import ast
from pathlib import Path
import unittest
from unittest import mock

from src import i18n
from src.gui import parse_args


class LocalizationTests(unittest.TestCase):
    def tearDown(self):
        # Other tests and imports should always begin with the English fallback.
        i18n.configure('en')

    def test_english_catalog_preserves_canonical_wording_exactly(self):
        i18n.configure('en')
        self.assertEqual(i18n.tr('status.rotate'),
                         'ROTATE BOTH STICKS NOW — use their full circular travel for 12 seconds.')
        self.assertEqual(
            i18n.tr('connection.connected', name='Steam Controller', serial='FXA123',
                    firmware='6A628345', support='hardware tested'),
            'Connected: Steam Controller · FXA123 · firmware 6A628345 (hardware tested)')

    def test_simplified_chinese_catalog_and_formatting(self):
        self.assertEqual(i18n.configure('zh-CN'), 'zh-CN')
        self.assertEqual(i18n.ui_font(10, 'bold'), ('Microsoft YaHei UI', 10, 'bold'))
        self.assertEqual(i18n.tr('button.stage'), '临时应用')
        self.assertEqual(i18n.tr('status.backup_path', path='captures/test.json'),
                         '启动备份：captures/test.json')
        self.assertEqual(i18n.tr_error('cal/joy_l: calibration bounds are not ordered'),
                         'cal/joy_l: 校准边界顺序不正确')

    def test_auto_uses_detected_language(self):
        with mock.patch.object(i18n, 'detect_system_language', return_value='zh-CN'):
            self.assertEqual(i18n.configure('auto'), 'zh-CN')

    def test_command_line_override_choices(self):
        self.assertEqual(parse_args(['--language', 'en']).language, 'en')
        self.assertEqual(parse_args(['--language', 'zh-CN']).language, 'zh-CN')
        self.assertEqual(parse_args([]).language, 'auto')

    def test_english_uses_existing_ui_font(self):
        i18n.configure('en')
        self.assertEqual(i18n.ui_font(10, 'bold'), ('Segoe UI', 10, 'bold'))
        self.assertEqual(i18n.data_font(9), ('Consolas', 9))

    def test_data_labels_remain_monospace_in_chinese(self):
        i18n.configure('zh-CN')
        self.assertEqual(i18n.data_font(9), ('Consolas', 9))

    def test_gui_translation_calls_use_catalog_message_ids(self):
        source_dir = Path(__file__).resolve().parents[1] / 'src'
        missing = set()
        for name in ('gui.py', 'gui_widgets.py', 'gui_worker.py'):
            tree = ast.parse((source_dir / name).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == 'tr' and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    key = node.args[0].value
                    if key not in i18n.EN or key not in i18n.CATALOGS['zh-CN']:
                        missing.add(key)
        self.assertEqual(missing, set())

    def test_every_catalog_message_has_a_simplified_chinese_translation(self):
        self.assertEqual(set(i18n.EN), set(i18n.ZH_CN))
        untranslated = [key for key, english in i18n.EN.items()
                        if i18n.CATALOGS['zh-CN'][key] == english]
        self.assertEqual(untranslated, [])

    def test_repository_and_issues_links_are_canonical(self):
        self.assertEqual(i18n.REPOSITORY_URL,
                         'https://github.com/omltcat/steam-controller-calibration')
        self.assertEqual(i18n.ISSUES_URL, f'{i18n.REPOSITORY_URL}/issues')

    def test_firmware_write_status_does_not_imply_a_special_backup(self):
        i18n.configure('en')
        self.assertEqual(i18n.tr('status.writes_enabled', support='unknown',
                                 firmware='12345678'),
                         'Write operations enabled for unknown firmware 12345678.')


if __name__ == '__main__':
    unittest.main()
