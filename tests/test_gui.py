import unittest
from pathlib import Path
import tempfile
from unittest import mock
from types import SimpleNamespace

from src import gui_support
from src.gui_support import asset_path, encode_manual_record
from src.gui_theme import Theme
from src.protocol import decode_calibration


class GuiCalibrationTests(unittest.TestCase):
    def test_cross_geometry_centers_even_and_odd_strokes_symmetrically(self):
        from src.gui_widgets import StickView
        with mock.patch.object(Theme, 'STICK_MARKER_WIDTH', 2):
            horizontal, vertical = StickView.marker_coordinates(87, 87)
            self.assertEqual(horizontal, (81.5, 87.5, 93.5, 87.5))
            self.assertEqual(vertical, (87.5, 81.5, 87.5, 93.5))
        with mock.patch.object(Theme, 'STICK_MARKER_WIDTH', 3):
            horizontal, vertical = StickView.marker_coordinates(87, 87)
            self.assertEqual(horizontal, (81.0, 87.0, 93.0, 87.0))
            self.assertEqual(vertical, (87.0, 81.0, 87.0, 93.0))

    def test_mouse_wheel_nudges_the_hovered_raw_value_by_one(self):
        class Entry:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

            def delete(self, _start, _end):
                self.value = ''

            def insert(self, _index, value):
                self.value = value

        from src.gui import App
        entry = Entry('1600')
        self.assertEqual(App.nudge_raw_entry(SimpleNamespace(widget=entry, delta=120)), 'break')
        self.assertEqual(entry.value, '1601')
        App.nudge_raw_entry(SimpleNamespace(widget=entry, delta=-120))
        self.assertEqual(entry.value, '1600')

    def test_development_icon_resolves_from_assets(self):
        self.assertEqual(asset_path('favicon.ico').name, 'favicon.ico')
        self.assertTrue(asset_path('favicon.ico').is_file())

    def test_new_capture_path_creates_missing_capture_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(gui_support, 'CAPTURES', Path(directory) / 'captures'):
                path = gui_support.new_capture_path('startup')
                self.assertTrue(path.parent.is_dir())
                self.assertEqual(path.parent.name, 'captures')

    def test_frozen_build_uses_executable_directory_for_captures(self):
        with mock.patch.object(gui_support.sys, 'frozen', True, create=True), \
             mock.patch.object(gui_support.sys, 'executable', r'Z:\\portable\\SteamControllerCalibration.exe'):
            self.assertEqual(gui_support._runtime_root(), Path(r'Z:\\portable'))

    def test_screenshot_values_pass_manual_validation(self):
        records = (
            dict(type=2, x_min=448, x_center_min=1627, x_center_max=1635, x_max=2937,
                 y_min=337, y_center_min=1604, y_center_max=1611, y_max=2848),
            dict(type=2, x_min=409, x_center_min=1595, x_center_max=1601, x_max=2852,
                 y_min=325, y_center_min=1603, y_center_max=1609, y_max=2773),
        )
        for fields in records:
            with self.subTest(fields=fields):
                decoded = decode_calibration(encode_manual_record(fields))
                self.assertTrue(decoded['bounds_valid'])

    def test_manual_validation_still_rejects_unsafe_geometry(self):
        fields = dict(type=2, x_min=1400, x_center_min=1600, x_center_max=1610, x_max=1800,
                      y_min=300, y_center_min=1600, y_center_max=1610, y_max=2800)
        with self.assertRaisesRegex(ValueError, 'travel span'):
            encode_manual_record(fields)


if __name__ == '__main__':
    unittest.main()
