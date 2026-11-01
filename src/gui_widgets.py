"""Small reusable ttk widgets used by the calibration window."""
import math
import tkinter as tk
from tkinter import ttk

from .i18n import data_font, tr, ui_font
from .gui_dpi import DisplayScale
from .gui_theme import Theme


class StickView:
    """Square processed-output indicator with fixed-width numeric labels."""

    MARKER_ARM = 6

    def __init__(self, parent, title):
        """Build a stick display in parent, with title as its frame label."""
        self.px = px = DisplayScale(parent).pixels
        frame = ttk.LabelFrame(parent, text=title, padding=px(8))
        self.canvas = tk.Canvas(frame, width=px(174), height=px(174),
                                bg=Theme.CANVAS_BACKGROUND, highlightthickness=px(0))
        self.canvas.pack()
        self.canvas.create_rectangle(px(8), px(8), px(166), px(166), outline=Theme.STICK_BORDER, width=px(2))
        self.canvas.create_line(px(87), px(8), px(87), px(166),
                                fill=Theme.STICK_GUIDE, width=px(1))
        self.canvas.create_line(px(8), px(87), px(166), px(87),
                                fill=Theme.STICK_GUIDE, width=px(1))
        # A crosshair shows the exact X/Y position without suggesting a round
        # stick gate or obscuring the center guides.
        horizontal, vertical = self.marker_coordinates(px(87), px(87), px(self.MARKER_ARM),
                                                       px(Theme.STICK_MARKER_WIDTH))
        self.marker_x = self.canvas.create_line(*horizontal, fill=Theme.ACCENT,
                                                width=px(Theme.STICK_MARKER_WIDTH))
        self.marker_y = self.canvas.create_line(*vertical, fill=Theme.ACCENT,
                                                width=px(Theme.STICK_MARKER_WIDTH))
        self.value = ttk.Label(frame, text=tr('stick.output', x=0, y=0),
                               font=data_font(9))
        self.value.pack(pady=px((6, 0)))
        self.raw = ttk.Label(frame, text=tr('stick.raw_estimate',
                                            raw_x='—', raw_y='—'), font=data_font(9))
        self.raw.pack()
        self.frame = frame

    def update(self, x, y, raw_x='—', raw_y='—'):
        """Position output x/y on the canvas and show raw_x/raw_y estimates."""
        px = self.px
        # Leave a small inset so the marker remains inside the square at full scale.
        marker_x = px(87) + max(-1, min(1, x / 32767)) * px(71)
        marker_y = px(87) - max(-1, min(1, y / 32767)) * px(71)
        horizontal, vertical = self.marker_coordinates(marker_x, marker_y, px(self.MARKER_ARM),
                                                       px(Theme.STICK_MARKER_WIDTH))
        self.canvas.coords(self.marker_x, *horizontal)
        self.canvas.coords(self.marker_y, *vertical)
        self.value.configure(text=tr('stick.output', x=x, y=y))
        self.raw.configure(text=tr('stick.raw_estimate',
                                   raw_x=raw_x, raw_y=raw_y))

    @classmethod
    def marker_coordinates(cls, x, y, arm=None, stroke=None):
        """Return crosshair lines at x/y, using optional pixel arm and stroke sizes."""
        arm = cls.MARKER_ARM if arm is None else arm
        stroke = Theme.STICK_MARKER_WIDTH if stroke is None else stroke
        offset = 0.5 if stroke % 2 == 0 else 0
        x, y = x + offset, y + offset
        return ((x - arm, y,
                 x + arm, y),
                (x, y - arm,
                 x, y + arm))


class HistoryPlot:
    """Five-second axis history with linear and signed-log display modes."""

    WINDOW_SECONDS = 5.0
    AXIS_OPTIONS = {'axis.left_x': 'left_x', 'axis.left_y': 'left_y',
                    'axis.right_x': 'right_x', 'axis.right_y': 'right_y'}

    def __init__(self, parent):
        """Build the history controls and DPI-scaled canvas in parent."""
        self.px = px = DisplayScale(parent).pixels
        self.axis_key = 'left_x'
        self.scale = 'plot.logarithmic'
        frame = ttk.LabelFrame(parent, text=tr('plot.title'), padding=px(8))
        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=px((0, 5)))
        ttk.Label(controls, text=tr('plot.axis')).pack(side='left')
        self.axis_buttons = {}
        for label_key, key in self.AXIS_OPTIONS.items():
            button = ttk.Button(controls, text=tr(label_key), width=7, takefocus=False,
                                command=lambda value=key: self.select_axis(value))
            button.pack(side='left', padx=px((4, 0)))
            self.axis_buttons[key] = button
        ttk.Label(controls, text=tr('plot.scale')).pack(side='left')
        self.scale_buttons = {}
        for key in ('plot.logarithmic', 'plot.linear'):
            button = ttk.Button(controls, text=tr(key), width=11, takefocus=False,
                                command=lambda value=key: self.select_scale(value))
            button.pack(side='left', padx=px((4, 0)))
            self.scale_buttons[key] = button
        self.summary = ttk.Label(controls, text='', font=data_font(9))
        self.summary.pack(side='right')
        ttk.Label(frame, text=tr('plot.guidance'),
                  foreground=Theme.MUTED_TEXT).pack(anchor='w', pady=px((0, 4)))
        self.canvas = tk.Canvas(frame, height=px(145), bg=Theme.CANVAS_BACKGROUND, highlightthickness=px(1),
                                highlightbackground=Theme.PLOT_BORDER)
        self.canvas.pack(fill='x')
        self.frame = frame
        self.update_buttons()

    def select_axis(self, value):
        self.axis_key = value
        self.update_buttons()

    def select_scale(self, value):
        self.scale = value
        self.update_buttons()

    def update_buttons(self):
        for value, button in self.axis_buttons.items():
            button.state(['pressed'] if value == self.axis_key else ['!pressed'])
        for value, button in self.scale_buttons.items():
            button.state(['pressed'] if value == self.scale else ['!pressed'])

    def transform(self, value):
        """Map signed controller output into the plot's normalized vertical range."""
        if self.scale == 'plot.linear':
            return value / 32768.0
        # log1p keeps zero defined while expanding small center oscillations.
        return math.copysign(math.log1p(abs(value)) / math.log1p(32768), value)

    def draw(self, histories, now):
        """Redraw the selected axis from timestamped samples in the rolling window."""
        px = self.px
        axis = self.axis_key
        samples = [(stamp, value) for stamp, value in histories[axis]
                   if stamp >= now - self.WINDOW_SECONDS]
        canvas = self.canvas
        canvas.delete('all')
        width = max(canvas.winfo_width(), px(300))
        height = max(canvas.winfo_height(), px(120))
        left, right, top, bottom = px(42), width - px(8), px(8), height - px(8)
        canvas.create_rectangle(left, top, right, bottom, outline=Theme.PLOT_FRAME, width=px(1))
        canvas.create_line(left, (top + bottom) / 2, right, (top + bottom) / 2,
                           fill=Theme.PLOT_ZERO_LINE, dash=px((3, 3)), width=px(1))
        grid_values = (-32768, -10000, -1000, -100, 0, 100, 1000, 10000, 32767)
        if self.scale == 'plot.linear':
            grid_values = (-32768, -16384, 0, 16384, 32767)
        for value in grid_values:
            normalized = self.transform(value)
            y = (top + bottom) / 2 - normalized * (bottom - top) / 2
            canvas.create_line(left, y, right, y, fill=Theme.PLOT_GRID, width=px(1))
            canvas.create_text(left - px(5), y, text=str(value), anchor='e',
                               fill=Theme.MUTED_TEXT, font=data_font(7))
        points = []
        for stamp, value in samples:
            x = left + ((stamp - (now - self.WINDOW_SECONDS)) / self.WINDOW_SECONDS) * (right - left)
            y = (top + bottom) / 2 - self.transform(value) * (bottom - top) / 2
            points.extend((x, y))
        if len(points) >= 4:
            canvas.create_line(*points, fill=Theme.ACCENT, width=px(2))
        elif len(points) == 2:
            x, y = points
            canvas.create_oval(x - px(2), y - px(2), x + px(2), y + px(2), fill=Theme.ACCENT, outline='')
        if samples:
            values = [value for _, value in samples]
            self.summary.configure(text=tr('plot.summary',
                                           now=values[-1], minimum=min(values), maximum=max(values)))
        else:
            self.summary.configure(text=tr('plot.waiting'))
