"""Tk entry point and presentation logic for Steam Controller calibration."""
import argparse
import collections
import queue
import time

from .gui_support import CAPTURES, PATHS, ROWS, asset_path, display_path, encode_manual_record
from .gui_widgets import HistoryPlot, StickView
from .gui_worker import ControllerWorker
from .i18n import configure, tr, tr_error, ui_font
from .protocol import AXES, SUPPORTED_CALIBRATION_BUILD, raw_lookup

import tkinter as tk
from tkinter import ttk


class App:
    """Build the window and translate worker events into visible UI state."""

    def __init__(self, root):
        self.tk, self.ttk, self.root = tk, ttk, root
        self.worker = ControllerWorker()
        self.entries, self.record_types = {}, {}
        self.live_records = {}
        self.raw_maps = {}
        self.connected = self.busy = self.has_staged = False
        self.last_sample_id = 0
        # Five seconds at the controller report rate fits comfortably in 2500 points.
        self.histories = {axis: collections.deque(maxlen=2500) for axis in AXES}
        try:
            # favicon.ico supplies the native title-bar and Windows taskbar icon.
            root.iconbitmap(default=str(asset_path('favicon.ico')))
        except tk.TclError:
            # Keep the GUI usable if a development checkout is missing its assets.
            pass
        root.title(tr('Steam Controller Calibration'))
        root.geometry('850x750')
        root.minsize(850, 750)
        style = ttk.Style()
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        # Apply the selected Windows UI font to every ttk control, including
        # buttons, entries, frames, and labels without an explicit font.
        style.configure('.', font=ui_font(9))
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text=tr('Steam Controller Calibration'),
                  font=ui_font(18, 'bold')).pack(anchor='w')
        self.connection = ttk.Label(outer, text=tr('Connecting…'))
        self.connection.pack(anchor='w', pady=(2, 12))

        # Top row: two live stick views followed by the editable raw record.
        live = ttk.Frame(outer)
        live.pack(fill='x')
        sticks = ttk.Frame(live)
        sticks.pack(side='left')
        self.left = StickView(sticks, tr('Left stick - live output'))
        self.right = StickView(sticks, tr('Right stick - live output'))
        self.left.frame.pack(side='left', padx=(0, 6))
        self.right.frame.pack(side='left', padx=(6, 0))

        editor = ttk.LabelFrame(outer, text=tr('Raw calibration values'), padding=10)
        editor.pack(in_=live, side='left', fill='y', padx=(14, 0))
        headers = ('Axis', 'Minimum', 'Center min', 'Center max', 'Maximum')
        for column, label in enumerate(headers):
            ttk.Label(editor, text=tr(label), font=ui_font(9, 'bold')).grid(
                row=0, column=column, padx=5, pady=(0, 5), sticky='w')
        for row, (label, path, axis) in enumerate(ROWS, 1):
            ttk.Label(editor, text=tr(label)).grid(row=row, column=0, padx=5, pady=3, sticky='w')
            for column, suffix in enumerate(('min', 'center_min', 'center_max', 'max'), 1):
                entry = ttk.Entry(editor, width=9, justify='right')
                entry.grid(row=row, column=column, padx=5, pady=3)
                self.entries[(path, axis, suffix)] = entry

        # The graph spans the same left/right bounds as the complete top row.
        self.history_plot = HistoryPlot(outer)
        self.history_plot.frame.pack(fill='x', pady=(12, 12))

        # Actions remain disabled while the worker owns a long controller operation.
        buttons = ttk.Frame(outer)
        buttons.pack(fill='x')
        self.read_button = ttk.Button(buttons, text=tr('Read Controller'), command=lambda: self.send('read'))
        self.stage_button = ttk.Button(buttons, text=tr('Apply Temporarily'), command=self.stage)
        self.save_button = ttk.Button(buttons, text=tr('Save to Controller'), command=self.commit)
        self.restore_button = ttk.Button(buttons, text=tr('Restore Backup…'), command=self.restore)
        self.auto_button = ttk.Button(buttons, text=tr('Automatic Calibration…'), command=self.auto_start)
        for widget in (self.read_button, self.stage_button, self.save_button,
                       self.restore_button, self.auto_button):
            widget.pack(side='left', padx=(0, 7))

        self.status = tk.StringVar(value=tr('Starting controller backend…'))
        self.instruction = tk.Label(outer, textvariable=self.status, anchor='w', justify='left',
            wraplength=715, bg='#fff0bd', fg='#713f12', font=ui_font(10, 'bold'),
            padx=10, pady=8, relief='solid', borderwidth=1)
        self.instruction.pack(fill='x', pady=(12, 6))
        self.backup = ttk.Label(outer, text='', foreground='#666666', wraplength=735)
        self.backup.pack(anchor='w')
        ttk.Label(outer, text=tr('Temporary values affect the running controller but are not saved. '
                                 'Power-cycling discards them. A backup is created on connection.'),
                  foreground='#666666', wraplength=735).pack(anchor='w', pady=(6, 0))
        self.set_enabled(False)
        self.worker.start()
        root.after(30, self.poll)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def set_instruction(self, message, tone='normal'):
        """Show a status message with a task-specific attention color."""
        colors = {
            'normal': ('#e8eef5', '#243447'),
            'hold': ('#fff0bd', '#713f12'),
            'move': ('#dcfce7', '#166534'),
            'stop': ('#fee2e2', '#991b1b'),
            'success': ('#dcfce7', '#166534'),
            'error': ('#fee2e2', '#991b1b'),
        }
        background, foreground = colors.get(tone, colors['normal'])
        self.status.set(message)
        self.instruction.configure(bg=background, fg=foreground)

    def set_enabled(self, enabled):
        """Apply connection, busy, and staged-state rules to action buttons."""
        state = 'normal' if enabled and not self.busy else 'disabled'
        for widget in (self.read_button, self.stage_button, self.restore_button, self.auto_button):
            widget.configure(state=state)
        self.save_button.configure(state='normal' if enabled and self.has_staged and not self.busy
                                   else 'disabled')

    def send(self, command, value=None):
        """Queue controller work without blocking Tk's event loop."""
        self.worker.commands.put((command, value))

    def fill_records(self, state):
        """Populate fields and rebuild inverse maps used by the Raw est labels."""
        for path in PATHS:
            record = state['records'][path]['decoded']
            self.record_types[path] = record['type']
            self.live_records[path] = record
            for axis in ('x', 'y'):
                self.raw_maps[(path, axis)] = raw_lookup(record, axis)
            for axis in ('x', 'y'):
                for suffix in ('min', 'center_min', 'center_max', 'max'):
                    entry = self.entries[(path, axis, suffix)]
                    entry.delete(0, 'end')
                    entry.insert(0, str(record[f'{axis}_{suffix}']))

    def raw_text(self, path, axis, output):
        """Estimate raw sensor position by inverting the recovered stock mapping."""
        interval = self.raw_maps.get((path, axis), {}).get(output)
        if interval is not None:
            low, high = interval
            return str(round((low + high) / 2))
        record = self.live_records.get(path)
        if not record:
            return '—'
        # Saturated outputs cover intervals; otherwise this is the inverse formula.
        if output < 0:
            width = max(((record[f'{axis}_center_min'] - record[f'{axis}_min']) * 98) // 100, 1)
            estimate = record[f'{axis}_center_min'] + output * width / 32768
        elif output > 0:
            width = max(((record[f'{axis}_max'] - record[f'{axis}_center_max']) * 98) // 100, 1)
            estimate = record[f'{axis}_center_max'] + output * width / 32767
        else:
            estimate = (record[f'{axis}_center_min'] + record[f'{axis}_center_max']) / 2
        return str(round(estimate))

    def collect_records(self):
        """Read, encode, and safety-check both records from editor fields."""
        records = {}
        problems = []
        for path in PATHS:
            fields = {'type': self.record_types[path]}
            for axis in ('x', 'y'):
                for suffix in ('min', 'center_min', 'center_max', 'max'):
                    fields[f'{axis}_{suffix}'] = self.entries[(path, axis, suffix)].get().strip()
            try:
                records[path] = encode_manual_record(fields)
            except ValueError as error:
                problems.extend(f'{path}: {tr_error(issue)}' for issue in str(error).splitlines())
        if problems:
            raise ValueError('\n'.join(problems))
        return records

    def stage(self):
        """Apply editor values to volatile controller state."""
        from tkinter import messagebox
        try:
            records = self.collect_records()
        except ValueError as error:
            messagebox.showerror(tr('Invalid calibration'), str(error), parent=self.root)
            return
        self.busy = True
        self.set_enabled(True)
        self.send('stage', records)

    def commit(self):
        """Persist the previously staged and verified editor values."""
        from tkinter import messagebox
        if not messagebox.askyesno(tr('Save calibration'),
                tr('Persist the currently staged values to the controller?'), parent=self.root):
            return
        self.busy = True
        self.set_enabled(True)
        self.send('commit')

    def restore(self):
        from tkinter import filedialog, messagebox
        filename = filedialog.askopenfilename(parent=self.root, title=tr('Select calibration backup'),
            initialdir=str(CAPTURES), filetypes=[(tr('JSON backups'), '*.json'), (tr('All files'), '*.*')])
        if not filename:
            return
        if not messagebox.askyesno(tr('Restore calibration'),
                tr('Stage, persist, and verify both records from this backup?'), parent=self.root):
            return
        self.busy = True
        self.set_enabled(True)
        self.send('restore', filename)

    def auto_start(self):
        from tkinter import messagebox
        if not messagebox.askokcancel(tr('Automatic calibration'),
                tr('KEEP BOTH STICKS UNTOUCHED after pressing OK.\n\n'
                   'There are two five-second center measurements.\nDo not move either stick until the instruction says\nROTATE BOTH STICKS NOW.'),
                parent=self.root):
            return
        self.busy = True
        self.set_enabled(True)
        self.send('auto_start')

    def poll(self):
        """Refresh live plots and drain worker events without blocking Tk."""
        from tkinter import messagebox
        # latest_sample is a replace-only snapshot, so Tk can read it lock-free.
        sample = self.worker.latest_sample
        if sample and sample[0] != self.last_sample_id:
            self.last_sample_id = sample[0]
            _, stamp, sampled_sticks = sample
            for axis in AXES:
                self.histories[axis].append((stamp, sampled_sticks[axis]))
        sticks = self.worker.latest_sticks
        if sticks:
            self.left.update(sticks['left_x'], sticks['left_y'],
                self.raw_text('cal/joy_l', 'x', sticks['left_x']),
                self.raw_text('cal/joy_l', 'y', sticks['left_y']))
            self.right.update(sticks['right_x'], sticks['right_y'],
                self.raw_text('cal/joy_r', 'x', sticks['right_x']),
                self.raw_text('cal/joy_r', 'y', sticks['right_y']))
        self.history_plot.draw(self.histories, time.monotonic())
        # Drain all pending state events before scheduling the next short poll.
        try:
            while True:
                event = self.worker.events.get_nowait()
                kind = event['kind']
                if kind == 'connected':
                    self.connected = True
                    self.connection.configure(text=tr('Connected: {name} · {serial} · firmware {firmware}',
                        name=event['info']['name'], serial=event['info']['serial'],
                        firmware=f'{SUPPORTED_CALIBRATION_BUILD:08X}'))
                    self.backup.configure(text=tr('Startup backup: {path}',
                                                  path=display_path(event['backup'])))
                    self.fill_records(event['state'])
                    self.set_instruction(tr('Ready.'))
                    self.busy = False
                elif kind == 'disconnected':
                    self.connected = self.busy = self.has_staged = False
                    self.connection.configure(text=tr('Not connected'))
                    self.backup.configure(text='')
                    self.set_instruction(event['message'])
                elif kind == 'records':
                    self.fill_records(event['state'])
                    self.set_instruction(tr('Calibration records read from controller.'))
                    self.busy = False
                elif kind == 'staged':
                    self.fill_records(event['state'])
                    self.has_staged = True
                    self.set_instruction(tr('Values are active temporarily. Test the sticks, then save to controller. Power-cycle to revert any changes.'), 'hold')
                    self.busy = False
                elif kind == 'saved':
                    self.fill_records(event['state'])
                    self.has_staged = False
                    self.set_instruction(tr('Calibration saved and verified.'), 'success')
                    self.busy = False
                elif kind == 'restored':
                    self.fill_records(event['state'])
                    self.has_staged = False
                    self.set_instruction(tr('Backup restored and verified: {path}',
                                            path=display_path(event['filename'])), 'success')
                    self.busy = False
                elif kind == 'auto_ready':
                    self.set_instruction(tr('REMOVE BOTH THUMBS FROM THE STICKS — then confirm whether to save.'), 'stop')
                    if messagebox.askyesno(tr('Commit automatic calibration'),
                            tr('Full travel was observed on all axes.\n\nREMOVE BOTH THUMBS FROM THE STICKS,\n'
                               'then choose Yes to persist and validate the new calibration.'),
                            parent=self.root):
                        self.send('auto_commit')
                    else:
                        self.send('auto_cancel')
                        self.busy = False
                elif kind == 'auto_saved':
                    self.fill_records(event['state'])
                    self.set_instruction(tr('Automatic calibration saved and validated: {path}',
                                            path=display_path(event['output'])), 'success')
                    self.has_staged = self.busy = False
                elif kind == 'status':
                    self.set_instruction(event['message'], event.get('tone', 'normal'))
                elif kind == 'error':
                    self.set_instruction(event['message'], 'error')
                    self.busy = False
                    messagebox.showerror(tr('Steam Controller Calibration'), event['message'], parent=self.root)
                self.set_enabled(self.connected)
        except queue.Empty:
            pass
        self.root.after(30, self.poll)

    def close(self):
        """Prevent closing mid-write and warn about active volatile values."""
        from tkinter import messagebox
        if self.busy:
            messagebox.showwarning(tr('Operation in progress'),
                tr('Wait for the current controller operation to finish before closing.'), parent=self.root)
            return
        if self.has_staged and not messagebox.askyesno(tr('Temporary calibration active'),
                tr('Temporary values remain active until the controller is power-cycled. Close anyway?'),
                parent=self.root):
            return
        self.send('stop')
        self.root.destroy()


def parse_args(args=None):
    """Parse the optional language override before constructing any widgets."""
    parser = argparse.ArgumentParser(description='Steam Controller calibration GUI')
    parser.add_argument('--language', choices=('auto', 'en', 'zh-CN'), default='auto',
                        help='UI language; auto follows the Windows system language')
    return parser.parse_args(args)


def main(args=None):
    import tkinter as tk
    options = parse_args(args)
    configure(options.language)
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
