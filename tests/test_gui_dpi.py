"""Verify native Tk layout and canvas geometry at common Windows display scales."""

import tkinter as tk
import unittest
from unittest import mock

from src.gui import App
from src.gui_dpi import DisplayScale, enable_dpi_awareness
from src.i18n import configure
from src.protocol import AXES


class DpiLayoutTests(unittest.TestCase):
    """Exercise actual widgets without starting controller I/O or displaying windows."""

    def test_layout_and_drawings_scale_with_fonts(self):
        """Keep both languages unclipped and drawings proportional at 100–200% DPI."""
        enable_dpi_awareness()
        try:
            for language in ('en', 'zh-CN'):
                configure(language)
                for dpi in (96, 120, 144, 192):
                    with self.subTest(language=language, dpi=dpi):
                        root = tk.Tk()
                        root.withdraw()
                        try:
                            root.tk.call('tk', 'scaling', dpi / 72)
                            with mock.patch('src.gui.ControllerWorker'):
                                app = App(root)
                            px = DisplayScale(root).pixels
                            self.assertEqual(int(app.left.canvas['width']), px(174))
                            self.assertEqual(int(app.history_plot.canvas['height']), px(145))
                            self.assertGreaterEqual(root.minsize()[0], root.winfo_reqwidth())
                            self.assertGreaterEqual(root.minsize()[1], root.winfo_reqheight())
                            app.left.update(32767, -32768)
                            line = app.left.canvas.coords(app.left.marker_x)
                            self.assertAlmostEqual(line[2] - line[0], 2 * px(6))
                            self.assertEqual(float(app.left.canvas.itemcget(
                                app.left.marker_x, 'width')), px(3))
                            # Two samples exercise the trace rather than the empty graph.
                            histories = {axis: [(0, 0), (1, 32767)] for axis in AXES}
                            app.history_plot.draw(histories, 1)
                            trace = app.history_plot.canvas.find_all()[-1]
                            self.assertEqual(float(app.history_plot.canvas.itemcget(
                                trace, 'width')), px(2))
                        finally:
                            root.destroy()
        finally:
            configure('en')


if __name__ == '__main__':
    unittest.main()
