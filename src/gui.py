"""Tk entry point and presentation logic for Steam Controller calibration."""
import argparse
import collections
import json
import queue
import time
import webbrowser

from .calibration_store import backup_calibration_issues, validate_backup
from .firmware_support import HARDWARE_TESTED, REVIEWED, firmware_support
from .gui_support import CAPTURES, PATHS, asset_path, display_path, encode_manual_record
from .gui_theme import Theme
from .gui_widgets import HistoryPlot, StickView
from .gui_worker import ControllerWorker
from .i18n import ISSUES_URL, REPOSITORY_URL, configure, tr, tr_error, ui_font, current_language
from .protocol import AXES, raw_lookup

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

VERSION = '1.1.1'

class App:
    """Build the window and translate worker events into visible UI state."""

    def __init__(self, root):
        self.tk, self.ttk, self.root = tk, ttk, root
        self.worker = ControllerWorker()
        self.entries, self.record_types = {}, {}
        self.live_records = {}
        self.raw_maps = {}
        self.connected = self.busy = self.has_staged = False
        self.write_authorized = False
        self.current_build = None
        self.current_serial = None
        self.last_sample_id = 0
        # Five seconds at the controller report rate fits comfortably in 2500 points.
        self.histories = {axis: collections.deque(maxlen=2500) for axis in AXES}
        try:
            # favicon.ico supplies the native title-bar and Windows taskbar icon.
            root.iconbitmap(default=str(asset_path('favicon.ico')))
        except tk.TclError:
            # Keep the GUI usable if a development checkout is missing its assets.
            pass
        root.title(tr('app.title'))
        root.geometry(f'{Theme.WINDOW_WIDTH}x{Theme.WINDOW_HEIGHT}')
        root.minsize(Theme.WINDOW_WIDTH, Theme.WINDOW_HEIGHT)
        style = ttk.Style()
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        self.apply_system_font()
        # Apply the selected Windows UI font to every ttk control, including
        # buttons, entries, frames, and labels without an explicit font.
        style.configure('.', font=ui_font(9))
        outer = ttk.Frame(root, padding=16,)
        outer.pack(fill='both', expand=True)
        title_frame = ttk.Frame(outer)
        title_frame.pack(fill='x')
        ttk.Label(title_frame, text=tr('app.title'),
                  font=ui_font(18, 'bold')).pack(side='left', anchor='w')
        ttk.Label(title_frame, text=(f'v{VERSION}')).pack(
            side='left', anchor='s', padx=(8, 0), pady=(0, 0 if current_language() == 'zh-CN' else 3))
        self.connection = ttk.Label(outer, text=tr('connection.connecting'))
        self.connection.pack(anchor='w', pady=(2, 12))

        # Top row: two live stick views followed by the editable raw record.
        live = ttk.Frame(outer)
        live.pack(fill='x')
        sticks = ttk.Frame(live)
        sticks.pack(side='left')
        self.left = StickView(sticks, tr('stick.left_title'))
        self.right = StickView(sticks, tr('stick.right_title'))
        self.left.frame.pack(side='left', padx=(0, 6))
        self.right.frame.pack(side='left', padx=(6, 0))

        editor = ttk.LabelFrame(outer, text=tr('editor.title'), padding=10)
        editor.pack(in_=live, side='left', fill='y', padx=(14, 0))
        headers = ('editor.axis', 'editor.minimum', 'editor.center_min',
                   'editor.center_max', 'editor.maximum')
        for column, label_key in enumerate(headers):
            ttk.Label(editor, text=tr(label_key), font=ui_font(9, 'bold')).grid(
                row=0, column=column, padx=5, pady=(0, 5), sticky='w')
        rows = (('axis.left_x', 'cal/joy_l', 'x'), ('axis.left_y', 'cal/joy_l', 'y'),
                ('axis.right_x', 'cal/joy_r', 'x'), ('axis.right_y', 'cal/joy_r', 'y'))
        for row, (label_key, path, axis) in enumerate(rows, 1):
            ttk.Label(editor, text=tr(label_key)).grid(row=row, column=0, padx=5, pady=3, sticky='w')
            for column, suffix in enumerate(('min', 'center_min', 'center_max', 'max'), 1):
                entry = ttk.Entry(editor, width=9, justify='right')
                entry.grid(row=row, column=column, padx=5, pady=3)
                # Bind each box itself so only the value under the pointer moves.
                entry.bind('<MouseWheel>', self.nudge_raw_entry)
                self.entries[(path, axis, suffix)] = entry

        # The graph spans the same left/right bounds as the complete top row.
        self.history_plot = HistoryPlot(outer)
        self.history_plot.frame.pack(fill='x', pady=(12, 12))

        # Actions remain disabled while the worker owns a long controller operation.
        buttons = ttk.Frame(outer)
        buttons.pack(fill='x')
        self.read_button = ttk.Button(buttons, text=tr('button.read'), command=lambda: self.send('read'))
        self.stage_button = ttk.Button(buttons, text=tr('button.stage'), command=self.stage)
        self.save_button = ttk.Button(buttons, text=tr('button.save'), command=self.commit)
        self.restore_button = ttk.Button(buttons, text=tr('button.restore'), command=self.restore)
        self.auto_button = ttk.Button(buttons, text=tr('button.auto'), command=self.auto_start)
        for widget in (self.read_button, self.stage_button, self.save_button,
                       self.restore_button, self.auto_button):
            widget.pack(side='left', padx=(0, 7))

        self.status = tk.StringVar(value=tr('status.starting'))
        self.instruction = tk.Label(outer, textvariable=self.status, anchor='w', justify='left',
            wraplength=715, bg=Theme.STATUS_TONES['hold'][0], fg=Theme.STATUS_TONES['hold'][1],
            font=ui_font(10, 'bold'), padx=10, pady=8, relief='solid', borderwidth=1)
        self.instruction.pack(fill='x', pady=(12, 3))
        self.backup = ttk.Label(outer, text='', foreground=Theme.MUTED_TEXT, wraplength=735)
        self.backup.pack(anchor='w')
        ttk.Label(outer, text=tr('status.temporary_explanation'),
                  foreground=Theme.MUTED_TEXT, wraplength=735).pack(anchor='w', pady=(2, 0))
        # Keep project support at the bottom without making the main controls wider.
        footer = ttk.Frame(outer)
        footer.pack(anchor='w', pady=(2, 0))
        author = ttk.Label(footer, text=tr('footer.author'), foreground=Theme.HYPERLINK, cursor='hand2')
        author.pack(side='left')
        author.bind('<Button-1>', lambda _event: webbrowser.open(tr('footer.author_link')))
        ttk.Label(footer, text=tr('footer.license'), foreground=Theme.MUTED_TEXT).pack(side='left')
        ttk.Label(footer, text=tr('footer.problem'), foreground=Theme.MUTED_TEXT).pack(side='left')
        issues = ttk.Label(footer, text=tr('footer.issues_link'), foreground=Theme.HYPERLINK, cursor='hand2')
        issues.pack(side='left')
        ttk.Label(footer, text=tr('footer.star'), foreground=Theme.MUTED_TEXT).pack(side='left')
        repository = ttk.Label(footer, text=tr('footer.repository_link'),
                               foreground=Theme.HYPERLINK, cursor='hand2')
        repository.pack(side='left')
        issues.bind('<Button-1>', lambda _event: webbrowser.open(ISSUES_URL))
        repository.bind('<Button-1>', lambda _event: webbrowser.open(REPOSITORY_URL))
        self.set_enabled(False)
        self.worker.start()
        root.after(30, self.poll)
        root.protocol('WM_DELETE_WINDOW', self.close)

    @staticmethod
    def apply_system_font():
        """Set Tk's named fonts so native Tk labels use the selected UI family."""
        family = ui_font(9)[0]
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont',
                     'TkCaptionFont', 'TkSmallCaptionFont', 'TkIconFont', 'TkTooltipFont'):
            try:
                tkfont.nametofont(name).configure(family=family)
            except tk.TclError:
                # Some Tk builds do not expose every named system font.
                continue

    def set_instruction(self, message, tone='normal'):
        """Show a status message with a task-specific attention color."""
        background, foreground = Theme.STATUS_TONES.get(tone, Theme.STATUS_TONES['normal'])
        self.status.set(message)
        self.instruction.configure(bg=background, fg=foreground)

    @staticmethod
    def nudge_raw_entry(event):
        """Change the hovered raw calibration value by one wheel step."""
        try:
            current = int(event.widget.get().strip())
        except ValueError:
            # Do not replace partially typed text with a guessed value.
            return 'break'
        step = 1 if event.delta > 0 else -1
        updated = max(0, min(0xFFFF, current + step))
        event.widget.delete(0, 'end')
        event.widget.insert(0, str(updated))
        return 'break'

    def set_enabled(self, enabled):
        """Apply connection, busy, and staged-state rules to action buttons."""
        read_state = 'normal' if enabled and not self.busy else 'disabled'
        write_state = ('normal' if enabled and self.write_authorized and not self.busy
                       else 'disabled')
        self.read_button.configure(state=read_state)
        for widget in (self.stage_button, self.restore_button, self.auto_button):
            widget.configure(state=write_state)
        self.save_button.configure(state='normal' if enabled and self.write_authorized
                                   and self.has_staged and not self.busy
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
            messagebox.showerror(tr('dialog.invalid_calibration'), str(error), parent=self.root)
            return
        self.busy = True
        self.set_enabled(True)
        self.send('stage', records)

    def commit(self):
        """Persist the previously staged and verified editor values."""
        from tkinter import messagebox
        if not messagebox.askyesno(tr('dialog.save_calibration'),
                tr('prompt.persist_staged'), parent=self.root):
            return
        self.busy = True
        self.set_enabled(True)
        self.send('commit')

    def restore(self):
        from tkinter import filedialog, messagebox
        filename = filedialog.askopenfilename(parent=self.root, title=tr('dialog.select_backup'),
            initialdir=str(CAPTURES), filetypes=[(tr('filetype.json'), '*.json'), (tr('filetype.all'), '*.*')])
        if not filename:
            return
        try:
            with open(filename, encoding='utf-8') as stream:
                backup = validate_backup(json.load(stream))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            messagebox.showerror(tr('dialog.invalid_backup'), tr_error(str(error)),
                                 parent=self.root)
            return
        backup_build = backup['firmware_build']
        if backup['device']['serial'] != self.current_serial:
            messagebox.showerror(tr('dialog.invalid_backup'),
                                 tr('error.other_controller_backup'),
                                 parent=self.root)
            return
        cross_firmware = backup_build != self.current_build
        if cross_firmware:
            issues = backup_calibration_issues(backup)
            if issues:
                messagebox.showerror(tr('dialog.invalid_backup'),
                    tr('prompt.cross_firmware_invalid',
                       issues='\n'.join(tr_error(issue) for issue in issues)), parent=self.root)
                return
            if not messagebox.askyesno(tr('dialog.cross_firmware_restore'),
                    tr('prompt.cross_firmware',
                       backup_firmware=f'{backup_build:08X}',
                       current_firmware=f'{self.current_build:08X}'), parent=self.root):
                return
        elif not messagebox.askyesno(tr('dialog.restore_calibration'),
                tr('prompt.restore'), parent=self.root):
            return
        self.busy = True
        self.set_enabled(True)
        self.send('restore', dict(filename=filename,
                                  allow_cross_firmware=cross_firmware))

    def auto_start(self):
        from tkinter import messagebox
        if not messagebox.askokcancel(tr('dialog.auto_calibration'),
                tr('prompt.auto_start'),
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
                    self.current_build = event['firmware_build']
                    self.current_serial = event['info']['serial']
                    support = firmware_support(self.current_build)
                    support_text = tr(f'support.{support["level"]}')
                    self.connection.configure(text=tr('connection.connected',
                        name=event['info']['name'], serial=event['info']['serial'],
                        firmware=f'{self.current_build:08X}', support=support_text))
                    self.backup.configure(text=tr('status.backup_path',
                                                  path=display_path(event['backup'])))
                    self.fill_records(event['state'])
                    self.write_authorized = support['level'] == HARDWARE_TESTED
                    if support['level'] == REVIEWED:
                        self.write_authorized = messagebox.askyesno(tr('dialog.reviewed_firmware'),
                            tr('prompt.reviewed_firmware',
                               firmware=f'{self.current_build:08X}'), parent=self.root)
                    elif support['level'] != HARDWARE_TESTED:
                        self.write_authorized = messagebox.askyesno(tr('dialog.unknown_firmware'),
                            tr('prompt.unknown_firmware',
                               firmware=f'{self.current_build:08X}'), parent=self.root)
                    if self.write_authorized:
                        if support['level'] == HARDWARE_TESTED:
                            self.set_instruction(tr('status.ready'))
                        else:
                            self.set_instruction(tr('status.writes_enabled',
                                                    support=support_text,
                                                    firmware=f'{self.current_build:08X}'), 'hold')
                    else:
                        self.set_instruction(tr('status.writes_disabled'), 'hold')
                    self.busy = False
                elif kind == 'disconnected':
                    self.connected = self.busy = self.has_staged = False
                    self.write_authorized = False
                    self.current_build = None
                    self.current_serial = None
                    self.connection.configure(text=tr('connection.not_connected'))
                    self.backup.configure(text='')
                    self.set_instruction(event['message'])
                elif kind == 'records':
                    self.fill_records(event['state'])
                    self.set_instruction(tr('status.records_read'))
                    self.busy = False
                elif kind == 'staged':
                    self.fill_records(event['state'])
                    self.has_staged = True
                    self.set_instruction(tr('status.staged'), 'hold')
                    self.busy = False
                elif kind == 'saved':
                    self.fill_records(event['state'])
                    self.has_staged = False
                    self.set_instruction(tr('status.saved'), 'success')
                    self.busy = False
                elif kind == 'restored':
                    self.fill_records(event['state'])
                    self.has_staged = False
                    self.set_instruction(tr('status.restored',
                                            path=display_path(event['filename'])), 'success')
                    self.busy = False
                elif kind == 'auto_ready':
                    self.set_instruction(tr('status.auto_ready'), 'stop')
                    if messagebox.askyesno(tr('dialog.commit_auto'),
                            tr('prompt.auto_commit'),
                            parent=self.root):
                        self.send('auto_commit')
                    else:
                        self.send('auto_cancel')
                        self.busy = False
                elif kind == 'auto_saved':
                    self.fill_records(event['state'])
                    self.set_instruction(tr('status.auto_saved',
                                            path=display_path(event['output'])), 'success')
                    self.has_staged = self.busy = False
                elif kind == 'status':
                    self.set_instruction(event['message'], event.get('tone', 'normal'))
                elif kind == 'error':
                    self.set_instruction(event['message'], 'error')
                    self.busy = False
                    messagebox.showerror(tr('app.title'), event['message'], parent=self.root)
                self.set_enabled(self.connected)
        except queue.Empty:
            pass
        self.root.after(30, self.poll)

    def close(self):
        """Prevent closing mid-write and warn about active volatile values."""
        from tkinter import messagebox
        if self.busy:
            messagebox.showwarning(tr('dialog.operation_in_progress'),
                tr('prompt.close_busy'), parent=self.root)
            return
        if self.has_staged and not messagebox.askyesno(tr('dialog.temporary_active'),
                tr('prompt.close_staged'),
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
