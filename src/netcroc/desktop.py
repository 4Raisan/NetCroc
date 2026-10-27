"""Desktop preferences, monitor geometry and controls for the app's own window."""
import ctypes as c
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk

MODES = ('Left edge', 'Right edge', 'Top middle', 'Static')
DEFAULTS = dict(overlay_enabled=False, overlay_mode='Right edge', overlay_position=None,
                overlay_alpha=.95, overlay_apps=True, overlay_network=True, overlay_vpn=True,
                close_to_tray=True, usage_minimum_mb=0)


class Preferences:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.data = DEFAULTS.copy()
        if self.path:
            try:
                if self.path.stat().st_size <= 8192: self.update(json.loads(self.path.read_text()), save=False)
            except (OSError, ValueError, TypeError): pass

    def update(self, values, save=True):
        if not isinstance(values, dict): return
        previous = self.data.copy()
        for key, default in DEFAULTS.items():
            if key not in values: continue
            value = values[key]
            valid = (isinstance(value, bool) if isinstance(default, bool) else
                     value in MODES if key == 'overlay_mode' else
                     isinstance(value, (int, float)) and .65 <= value <= 1 if key == 'overlay_alpha' else
                     type(value) is int and value in (0, 1, 5) if key == 'usage_minimum_mb' else
                     value is None or isinstance(value, list) and len(value) == 2 and all(type(n) is int and abs(n) <= 100000 for n in value))
            if valid: self.data[key] = value
        if save and self.path and self.data != previous:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
            temporary.replace(self.path)


def handle(window):
    api = c.windll.user32
    api.GetParent.argtypes = [c.c_void_p]; api.GetParent.restype = c.c_void_p
    return api.GetParent(window.winfo_id()) or window.winfo_id()


def monitor_rect(root, point=None, work=True):
    if os.name == 'nt':
        from ctypes import wintypes as w
        class Info(c.Structure):
            _fields_ = [('size', w.DWORD), ('monitor', w.RECT), ('work', w.RECT), ('flags', w.DWORD)]
        try:
            x, y = point or root.winfo_pointerxy()
            api = c.windll.user32
            api.MonitorFromPoint.argtypes = [w.POINT, w.DWORD]; api.MonitorFromPoint.restype = c.c_void_p
            api.GetMonitorInfoW.argtypes = [c.c_void_p, c.POINTER(Info)]
            info = Info(); info.size = c.sizeof(info)
            if api.GetMonitorInfoW(api.MonitorFromPoint(w.POINT(x, y), 2), c.byref(info)):
                rect = info.work if work else info.monitor
                return rect.left, rect.top, rect.right, rect.bottom
        except (OSError, tk.TclError): pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def clamp_position(position, size, rect):
    left, top, right, bottom = rect; width, height = size
    x, y = position
    return max(left, min(x, max(left, right-width))), max(top, min(y, max(top, bottom-height)))


def panel_position(mode, size, rect, saved=None):
    left, top, right, bottom = rect; width, height = size
    if mode == 'Static' and saved is not None: return clamp_position(saved, size, rect)
    x = left+8 if mode == 'Left edge' else right-width-8 if mode == 'Right edge' else left+(right-left-width)//2
    y = top+8 if mode == 'Top middle' else top+(bottom-top-height)//2
    return clamp_position((x, y), size, rect)


def edge_triggered(mode, point, rect, width=420):
    x, y = point; left, top, right, bottom = rect
    if not left <= x < right or not top <= y < bottom: return False
    return (x-left < 4 if mode == 'Left edge' else right-1-x < 4 if mode == 'Right edge' else
            y-top < 4 and abs(x-(left+right)//2) <= width//2 if mode == 'Top middle' else mode == 'Static')


def position_window(window, size, position):
    width, height = size; x, y = position
    window.geometry(f'{width}x{height}{x:+d}{y:+d}')
    if os.name == 'nt':
        # Native positioning also handles monitors left/above the primary display.
        api = c.windll.user32
        api.SetWindowPos.argtypes = [c.c_void_p, c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_int, c.c_uint]
        api.SetWindowPos(handle(window), None, x, y, width, height, 0x14)


class WindowChrome:
    def __init__(self, app):
        self.app = app; self.root = app.root; self.maximized = False; self.restore_geometry = None
        self.root.overrideredirect(True)
        self.root.bind('<Map>', self.mapped, add='+')
        self.root.bind('<Configure>', self.round_window, add='+')
        self.region_size = None
        self.job = self.root.after_idle(self.taskbar)
        grip = ttk.Sizegrip(self.root)
        grip.place(relx=1, rely=1, x=-9, y=-9, anchor='se', width=16, height=16)
        grip.bind('<ButtonPress-1>', self.resize_start)
        grip.bind('<B1-Motion>', self.resize)

    @staticmethod
    def set_round_region(hwnd, width, height, diameter):
        # On success Windows owns the region; on failure we release it.
        if os.name != 'nt' or width < 20 or height < 20: return False
        try:
            gdi = c.windll.gdi32; user = c.windll.user32
            gdi.CreateRoundRectRgn.argtypes = [c.c_int] * 6
            gdi.CreateRoundRectRgn.restype = c.c_void_p
            gdi.DeleteObject.argtypes = [c.c_void_p]
            user.SetWindowRgn.argtypes = [c.c_void_p, c.c_void_p, c.c_int]
            region = gdi.CreateRoundRectRgn(0, 0, width + 1, height + 1, diameter, diameter)
            if not region: return False
            if user.SetWindowRgn(hwnd, region, 1): return True
            gdi.DeleteObject(region)
        except (OSError, tk.TclError): pass
        return False

    def round_window(self, event):
        if event.widget is not self.root: return
        size = (event.width, event.height)
        if size != self.region_size and self.set_round_region(handle(self.root) if os.name == 'nt' else None, *size, 24):
            self.region_size = size

    def round_surface(self, surface):
        # Inset and round the content as well as the top-level window, leaving
        # a consistent one-pixel coloured rim along the curved corners.
        self.surface = surface
        self.surface_size = None
        def reshape(event):
            if event.widget is not surface: return
            size = (event.width, event.height)
            if size != self.surface_size and self.set_round_region(surface.winfo_id(), *size, 22):
                self.surface_size = size
        surface.bind('<Configure>', reshape, add='+')

    def taskbar(self):
        self.job=None
        if os.name != 'nt' or self.app.diagnostic or self.app.closing: return
        api = c.windll.user32; hwnd = handle(self.root)
        api.GetWindowLongW.argtypes = [c.c_void_p, c.c_int]
        api.SetWindowLongW.argtypes = [c.c_void_p, c.c_int, c.c_long]
        api.SetWindowLongW(hwnd, -20, (api.GetWindowLongW(hwnd, -20) & ~0x80) | 0x40000)
        api.SetWindowLongW(hwnd, -16, api.GetWindowLongW(hwnd, -16) | 0x20000)

    def mapped(self, event):
        if event.widget is self.root and self.root.state() == 'normal':
            self.root.overrideredirect(True)
            if self.job:
                try:self.root.after_cancel(self.job)
                except tk.TclError:pass
            self.job=self.root.after_idle(self.taskbar)

    def minimize(self):
        if os.name == 'nt':
            api = c.windll.user32; api.ShowWindow.argtypes = [c.c_void_p, c.c_int]
            api.ShowWindow(handle(self.root), 6)
        else:
            self.root.overrideredirect(False); self.root.iconify()

    def maximize(self, _event=None):
        if self.maximized:
            self.root.geometry(self.restore_geometry); self.maximized = False
        else:
            self.restore_geometry = self.root.geometry()
            left, top, right, bottom = monitor_rect(self.root, (self.root.winfo_rootx()+100, self.root.winfo_rooty()+40))
            position_window(self.root, (right-left, bottom-top), (left, top)); self.maximized = True

    def bind_drag(self, widget):
        widget.bind('<ButtonPress-1>', self.drag_start)
        widget.bind('<B1-Motion>', self.drag)
        widget.bind('<Double-Button-1>', self.maximize)

    def drag_start(self, event):
        self.drag_offset = event.x_root-self.root.winfo_rootx(), event.y_root-self.root.winfo_rooty()

    def drag(self, event):
        if not hasattr(self, 'drag_offset'): return
        if self.maximized:
            self.maximize();self.drag_offset=(self.root.winfo_width()//2,24)
        x = event.x_root-self.drag_offset[0]; y = event.y_root-self.drag_offset[1]
        position_window(self.root, (self.root.winfo_width(), self.root.winfo_height()), (x, y))

    def resize_start(self, event):
        if self.maximized: self.maximize()
        self.resize_origin = event.x_root, event.y_root, self.root.winfo_width(), self.root.winfo_height()

    def resize(self, event):
        if not hasattr(self, 'resize_origin'): return
        x, y, width, height = self.resize_origin; minimum = self.root.minsize()
        self.root.geometry(f'{max(minimum[0],width+event.x_root-x)}x{max(minimum[1],height+event.y_root-y)}')

    def close(self):
        if self.job:
            try:self.root.after_cancel(self.job)
            except tk.TclError:pass
            self.job=None
