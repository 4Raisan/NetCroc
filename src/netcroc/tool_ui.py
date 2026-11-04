"""Shared tool-tab controls: stateful action bars and a status line with busy/error feedback."""
import tkinter as tk
from tkinter import ttk, messagebox


def install_styles(widget):
    style = ttk.Style(widget)
    style.configure('Ok.TLabel', foreground='#177245')
    style.configure('Error.TLabel', foreground='#b3261e')
    style.configure('Busy.TLabel', foreground='#8a6d1a')


class ActionBar:
    """Primary steps stay visible; extras live in a menu. Buttons keep references so
    callers can disable them while busy or when nothing is selected."""

    def __init__(self, parent, primary, extra=()):
        self.bar = ttk.Frame(parent)
        self.bar.pack(fill='x', pady=(8, 6))
        self.buttons = {}
        self._primary = None
        for label, callback in primary:
            button = ttk.Button(self.bar, text=label, command=callback)
            button.pack(side='left', padx=(0, 6))
            self.buttons[label] = button
        if primary:
            self.set_primary(primary[0][0])
        self.menu_button = None
        if extra:
            self.menu_button = ttk.Menubutton(self.bar, text='More')
            menu = tk.Menu(self.menu_button, tearoff=False)
            for label, callback in extra:
                menu.add_command(label=label, command=callback)
            self.menu_button.configure(menu=menu)
            self.menu_button.pack(side='left')

    def set_primary(self, label):
        if self._primary == label:
            return
        for name, button in self.buttons.items():
            button.configure(style='Primary.TButton' if name == label else 'TButton')
        self._primary = label

    def enable(self, label, enabled):
        button = self.buttons.get(label)
        if button:
            button.configure(state='normal' if enabled else 'disabled')

    def set_enabled(self, mapping):
        for label, enabled in mapping.items():
            self.enable(label, enabled)


class StatusLine:
    """One line of feedback with colour and an optional indeterminate progress bar.
    Errors stay visible until the next user action instead of being overwritten."""

    def __init__(self, parent, initial='', wraplength=780):
        install_styles(parent)
        self.var = tk.StringVar(value=initial)
        self.label = ttk.Label(parent, textvariable=self.var, wraplength=wraplength)
        self.label.pack(anchor='w', pady=6)
        self.progress = ttk.Progressbar(parent, mode='indeterminate', length=240)
        self._busy = False
        self.has_error = False

    def _text(self, text, style):
        self.var.set(text)
        self.label.configure(style=style)

    def info(self, text):
        self.has_error = False
        self._text(text, 'TLabel')

    def ok(self, text):
        self.has_error = False
        self._text(text, 'Ok.TLabel')

    def busy(self, text):
        self.has_error = False
        self._text(text, 'Busy.TLabel')
        if not self._busy:
            self._busy = True
            self.progress.pack(anchor='w', pady=(0, 6), after=self.label)
            self.progress.start(12)

    def error(self, text):
        self.has_error = True
        self.stop_busy()
        self._text(text, 'Error.TLabel')

    def stop_busy(self):
        if self._busy:
            self._busy = False
            self.progress.stop()
            self.progress.pack_forget()

    @property
    def is_busy(self):
        return self._busy


def actions(parent, primary, extra=()):
    return ActionBar(parent, primary, extra)


def help_for(root, title, text):
    return lambda: messagebox.showinfo(title, text, parent=root)

class DependencyNotice:
    def __init__(self,parent,app,routing,label):
        self.app=app;self.routing=routing;self.label=label;self.busy=False
        row=ttk.Frame(parent);row.pack(fill='x',pady=6)
        self.text=tk.StringVar(value='Checking required tools…')
        ttk.Label(row,textvariable=self.text,wraplength=600).pack(side='left')
        self.button=ttk.Button(row,text='Install required tools',command=app.shell.open_setup);self.button.pack(side='right')
        self.timer=app.root.after(100,self.refresh)
    def refresh(self):
        if self.app.closing:return
        try:
            stat=self.routing.exe.stat();signature=(stat.st_mtime_ns,stat.st_size)
        except OSError:signature=None
        if signature!=getattr(self,'signature',object()) and not self.busy:
            self.signature=signature;self.busy=True
            import threading
            def work():
                try:self.routing.verify();self.ready=True
                except (OSError,ValueError):self.ready=False
                finally:self.busy=False
            threading.Thread(target=work,daemon=True).start()
        ready=getattr(self,'ready',False)
        if self.busy and not hasattr(self,'ready'):
            self.text.set('Checking required tools…')
        else:self.text.set(('Ready: '+self.label) if ready else 'Setup needed: '+self.label+'. Use Install required tools.')
        self.button.configure(state='disabled' if ready else 'normal')
        self.timer=self.app.root.after(1500,self.refresh)
