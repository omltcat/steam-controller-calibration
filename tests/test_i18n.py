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

    def test_english_preserves_canonical_wording_exactly(self):
        i18n.configure('en')
        source = 'ROTATE BOTH STICKS NOW — use their full circular travel for 12 seconds.'
        self.assertEqual(i18n.tr(source), source)
        self.assertEqual(
            i18n.tr('Connected: {name} · {serial} · firmware {firmware}',
                    name='Steam Controller', serial='FXA123', firmware='6A628345'),
            'Connected: Steam Controller · FXA123 · firmware 6A628345')

    def test_simplified_chinese_catalog_and_formatting(self):
        self.assertEqual(i18n.configure('zh-CN'), 'zh-CN')
        self.assertEqual(i18n.ui_font(10, 'bold'), ('Microsoft YaHei UI', 10, 'bold'))
        self.assertEqual(i18n.tr('Apply Temporarily'), '临时应用')
        self.assertEqual(i18n.tr('Startup backup: {path}', path='captures/test.json'),
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

    def test_every_literal_gui_translation_call_has_a_chinese_entry(self):
        source_dir = Path(__file__).resolve().parents[1] / 'src'
        missing = set()
        for name in ('gui.py', 'gui_widgets.py', 'gui_worker.py'):
            tree = ast.parse((source_dir / name).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == 'tr' and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    source = node.args[0].value
                    if source not in i18n.ZH_CN:
                        missing.add(source)
        self.assertEqual(missing, set())


if __name__ == '__main__':
    unittest.main()
