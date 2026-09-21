"""Small reusable ttk widgets used by the calibration window."""
import math
import tkinter as tk
from tkinter import ttk

from .i18n import tr, ui_font


class StickView:
    """Square processed-output indicator with fixed-width numeric labels."""

    def __init__(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        self.canvas = tk.Canvas(frame, width=174, height=174, bg='#fafafa', highlightthickness=0)
        self.canvas.pack()
        outline = '#a8a8a8'
        self.canvas.create_rectangle(8, 8, 166, 166, outline=outline, width=2)
        self.canvas.create_line(87, 8, 87, 166, fill='#dedede')
        self.canvas.create_line(8, 87, 166, 87, fill='#dedede')
        # A crosshair shows the exact X/Y position without suggesting a round
        # stick gate or obscuring the center guides.
        self.marker_x = self.canvas.create_line(81, 87, 93, 87, fill='#1677c8', width=2)
        self.marker_y = self.canvas.create_line(87, 81, 87, 93, fill='#1677c8', width=2)
        self.value = ttk.Label(frame, text=tr('Output  X {x:6d}   Y {y:6d}', x=0, y=0),
                               font=('Consolas', 9))
        self.value.pack(pady=(6, 0))
        self.raw = ttk.Label(frame, text=tr('Raw est X {raw_x:>6}   Y {raw_y:>6}',
                                            raw_x='—', raw_y='—'), font=('Consolas', 9))
        self.raw.pack()
        self.frame = frame

    def update(self, x, y, raw_x='—', raw_y='—'):
        # Leave a small inset so the marker remains inside the square at full scale.
        px = 87 + max(-1, min(1, x / 32767)) * 71
        py = 87 - max(-1, min(1, y / 32767)) * 71
        self.canvas.coords(self.marker_x, px - 6, py, px + 6, py)
        self.canvas.coords(self.marker_y, px, py - 6, px, py + 6)
        self.value.configure(text=tr('Output  X {x:6d}   Y {y:6d}', x=x, y=y))
        self.raw.configure(text=tr('Raw est X {raw_x:>6}   Y {raw_y:>6}',
                                   raw_x=raw_x, raw_y=raw_y))


class HistoryPlot:
    """Five-second axis history with linear and signed-log display modes."""

    WINDOW_SECONDS = 5.0
    AXIS_OPTIONS = {'Left X': 'left_x', 'Left Y': 'left_y',
                    'Right X': 'right_x', 'Right Y': 'right_y'}

    def __init__(self, parent):
        self.axis_key = 'left_x'
        self.scale = 'Logarithmic'
        frame = ttk.LabelFrame(parent, text=tr('Recent output samples - 5 seconds'), padding=8)
        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(0, 5))
        ttk.Label(controls, text=tr('Axis:')).pack(side='left')
        self.axis_buttons = {}
        for label, key in self.AXIS_OPTIONS.items():
            button = ttk.Button(controls, text=tr(label), width=7, takefocus=False,
                                command=lambda value=key: self.select_axis(value))
            button.pack(side='left', padx=(4, 0))
            self.axis_buttons[key] = button
        ttk.Label(controls, text=tr('Scale:')).pack(side='left')
        self.scale_buttons = {}
        for label in ('Logarithmic', 'Linear'):
            button = ttk.Button(controls, text=tr(label), width=11, takefocus=False,
                                command=lambda value=label: self.select_scale(value))
            button.pack(side='left', padx=(4, 0))
            self.scale_buttons[label] = button
        self.summary = ttk.Label(controls, text='', font=('Consolas', 9))
        self.summary.pack(side='right')
        ttk.Label(frame, text=tr('A good calibration should oscillate roughly symmetrically near zero.'),
                  foreground='#666666').pack(anchor='w', pady=(0, 4))
        self.canvas = tk.Canvas(frame, height=145, bg='#fafafa', highlightthickness=1,
                                highlightbackground='#c8c8c8')
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
        if self.scale == 'Linear':
            return value / 32768.0
        # log1p keeps zero defined while expanding small center oscillations.
        return math.copysign(math.log1p(abs(value)) / math.log1p(32768), value)

    def draw(self, histories, now):
        """Redraw the selected axis from timestamped samples in the rolling window."""
        axis = self.axis_key
        samples = [(stamp, value) for stamp, value in histories[axis]
                   if stamp >= now - self.WINDOW_SECONDS]
        canvas = self.canvas
        canvas.delete('all')
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 120)
        left, right, top, bottom = 42, width - 8, 8, height - 18
        canvas.create_rectangle(left, top, right, bottom, outline='#d0d0d0')
        canvas.create_line(left, (top + bottom) / 2, right, (top + bottom) / 2,
                           fill='#a8a8a8', dash=(3, 3))
        grid_values = (-32768, -10000, -1000, -100, 0, 100, 1000, 10000, 32767)
        if self.scale == 'Linear':
            grid_values = (-32768, -16384, 0, 16384, 32767)
        for value in grid_values:
            normalized = self.transform(value)
            y = (top + bottom) / 2 - normalized * (bottom - top) / 2
            canvas.create_line(left, y, right, y, fill='#ececec')
            canvas.create_text(left - 5, y, text=str(value), anchor='e',
                               fill='#666666', font=('Consolas', 7))
        canvas.create_text(left, bottom + 10, text=tr('−5 s'), anchor='w',
                           fill='#666666', font=ui_font(7))
        canvas.create_text(right, bottom + 10, text=tr('now'), anchor='e',
                           fill='#666666', font=ui_font(7))
        # Timestamps, rather than sample indexes, keep spacing honest during pauses.
        points = []
        for stamp, value in samples:
            x = left + ((stamp - (now - self.WINDOW_SECONDS)) / self.WINDOW_SECONDS) * (right - left)
            y = (top + bottom) / 2 - self.transform(value) * (bottom - top) / 2
            points.extend((x, y))
        if len(points) >= 4:
            canvas.create_line(*points, fill='#1677c8', width=2)
        elif len(points) == 2:
            x, y = points
            canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill='#1677c8', outline='')
        if samples:
            values = [value for _, value in samples]
            self.summary.configure(text=tr('now {now:6d}   min {minimum:6d}   max {maximum:6d}',
                                           now=values[-1], minimum=min(values), maximum=max(values)))
        else:
            self.summary.configure(text=tr('waiting for samples'))


