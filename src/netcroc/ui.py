import ctypes
import os
import json
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
import pystray
from .core import DEFAULTS, PRESETS, Settings, validate, probe, set_startup, smart_interval, run_comparison, comparison_verdict, time

def icon_image(color='#38bdf8'):
    from .shell import logo_path
    try:
        with Image.open(logo_path()) as source:
            image = source.convert('RGBA').resize((64, 64), Image.Resampling.LANCZOS)
        ImageDraw.Draw(image).ellipse((49, 49, 63, 63), fill=color, outline='white', width=2)
        return image
    except OSError:
        pass
    image = Image.new('RGBA', (64, 64))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, 62, 62), radius=16, fill='#142338')
    for x, height in ((14, 12), (27, 23), (40, 36)):
        draw.rounded_rectangle((x, 49-height, x+9, 49), radius=3, fill=color)
    return image

class App:
    def __init__(self, root, diagnostic=False):
        self.root, self.diagnostic = root, diagnostic
        self.store = Settings()
        from .desktop import Preferences
        self.desktop = Preferences(None if diagnostic else self.store.folder/'desktop.json')
        saved = DEFAULTS.copy() if diagnostic else self.store.load()
        self.events = queue.Queue()
        self.stop_event = None
        self.worker = None
        self.tray = None
        self.running = False
        self.comparing = False
        self.compare_stop = threading.Event()
        self.activity = (0, 0)
        self.closing = False
        self.isp_busy = False
        self.isp_serial = 0
        self.pending_start = False
        self.isp_wifi = None
        self.isp_wifi_timer = None
        self.isp_checked_at = None
        self.isp_checked_network = None
        self.isp_cached = None
        self.isp_cached_error = None
        root.title('NetCroc · Your quiet network companion.')
        width=min(1120,max(900,root.winfo_screenwidth()-80))
        height=min(800,max(600,root.winfo_screenheight()-120))
        root.geometry(f'{width}x{height}')
        root.minsize(min(1000,width),min(720,height))
        root.protocol('WM_DELETE_WINDOW', self.close_window)
        from .desktop import WindowChrome
        self.window = WindowChrome(self)
        from .shell import Shell
        self.shell = Shell(root, self)
        notebook = self.shell.book
        keepalive = ttk.Frame(notebook)
        notebook.add(keepalive, text='Keep-alive')
        viewport=tk.Canvas(keepalive,highlightthickness=0,bg='#f4f7f5')
        scroll=ttk.Scrollbar(keepalive,orient='vertical',command=viewport.yview)
        viewport.configure(yscrollcommand=scroll.set)
        viewport.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        outer=ttk.Frame(viewport,padding=24)
        content=viewport.create_window((0,0),window=outer,anchor='nw')
        outer.bind('<Configure>',lambda _event:viewport.configure(scrollregion=viewport.bbox('all')))
        viewport.bind('<Configure>',lambda event:viewport.itemconfigure(content,width=event.width))
        ttk.Label(outer, text='Connection checks', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Optional HEAD checks may help idle stalls. No guaranteed speed increase.').pack(anchor='w', pady=(6, 20))
        self.isp = tk.StringVar(value=saved['isp'])
        self.auto_isp = tk.BooleanVar(value=saved['auto_isp'])
        self.isp_detection = tk.StringVar(value='Automatic lookup uses your public network, not the Wi-Fi name.')
        self.custom = tk.StringVar(value=saved['custom'])
        self.interval = tk.IntVar(value=saved['interval'])
        self.protocol = tk.StringVar(value=saved['protocol'])
        self.details = tk.BooleanVar(value=saved['details'])
        self.startup = tk.BooleanVar(value=saved['startup'])
        self.smart = tk.BooleanVar(value=saved['smart'])
        ttk.Label(outer, text='Your ISP').pack(anchor='w')
        self.isp_box = ttk.Combobox(outer, textvariable=self.isp, values=list(PRESETS), state='readonly')
        self.isp_box.pack(fill='x', pady=(5, 4))
        self.isp_box.bind('<<ComboboxSelected>>', self.manual_isp)
        isp_row = ttk.Frame(outer); isp_row.pack(fill='x')
        ttk.Checkbutton(isp_row, text='Detect ISP automatically', variable=self.auto_isp, command=self.change_isp_mode).pack(side='left')
        ttk.Button(isp_row, text='Detect again', command=lambda: self.detect_isp(force=True)).pack(side='right')
        ttk.Label(outer, textvariable=self.isp_detection, wraplength=740).pack(anchor='w', pady=(3, 8))
        self.advanced = ttk.Frame(outer)
        self.advanced_button = ttk.Button(outer,text='More settings',command=self.toggle_advanced)
        self.advanced_button.pack(anchor='w',pady=6)
        ttk.Label(self.advanced, text='Custom website or IP (optional)').pack(anchor='w')
        ttk.Entry(self.advanced, textvariable=self.custom).pack(fill='x', pady=(5, 12))
        row = ttk.Frame(self.advanced)
        row.pack(fill='x')
        ttk.Label(row, text='Every').pack(side='left')
        ttk.Combobox(row, textvariable=self.interval, values=(1, 5, 10, 15, 30), width=5, state='readonly').pack(side='left', padx=8)
        ttk.Label(row, text='seconds after each check · no overlap').pack(side='left')
        ttk.Combobox(row, textvariable=self.protocol, values=('HTTP', 'ICMP'), width=7, state='readonly').pack(side='right')
        ttk.Checkbutton(self.advanced, text='Run automatically when I sign in', variable=self.startup).pack(anchor='w', pady=(18, 4))
        ttk.Checkbutton(self.advanced, text='Optional smart mode: use at least 15s between checks while adapter traffic is busy', variable=self.smart).pack(anchor='w')
        ttk.Checkbutton(self.advanced, text='Show connection checks', variable=self.details, command=self.toggle_details).pack(anchor='w')
        ttk.Label(self.advanced, text='1 second can mean 86,400 checks/day. Failures back off; no setting changes occur automatically.', wraplength=900).pack(anchor='w', pady=10)
        self.status = tk.StringVar(value='Ready · '+saved['isp'])
        self.status_label=ttk.Label(outer, textvariable=self.status, wraplength=740)
        self.status_label.pack(anchor='w', pady=(18,10))
        buttons = ttk.Frame(outer)
        buttons.pack(fill='x')
        self.start_button = ttk.Button(buttons, text='Save & Start', command=self.start)
        self.start_button.pack(side='left')
        ttk.Button(buttons, text='Pause', command=self.pause).pack(side='left', padx=6)
        ttk.Button(buttons, text='Compare OFF / ON…', command=self.compare_window).pack(side='left', padx=6)
        ttk.Button(buttons, text='Hide to tray', command=self.hide).pack(side='right')
        ttk.Button(buttons, text='Quit', command=self.quit).pack(side='right', padx=6)
        self.log = tk.Text(outer, height=5, state='disabled', font=('Consolas', 9))
        footer = ttk.Frame(outer)
        footer.pack(side='bottom', fill='x', pady=(12, 0))
        ttk.Button(footer, text='GitHub ↗', command=lambda: webbrowser.open('https://github.com/4Raisan/NetCroc')).pack(side='left')
        ttk.Label(footer, text='Local monitoring · Optional WireGuard VPN', font=('Segoe UI', 9)).pack(side='right')
        self.toggle_details()
        from .dashboard import Dashboard
        self.dashboard = Dashboard(self, notebook, diagnostic)
        from .tray_mode import TrayOverlay
        self.overlay = TrayOverlay(self, self.desktop)
        self.shell.finish(self.dashboard, keepalive)
        root.after(150, self.poll)
        if not diagnostic and self.auto_isp.get(): root.after(700, self.detect_isp)

    def values(self):
        return dict(isp=self.isp.get(), custom=self.custom.get().strip(), interval=self.interval.get(),
                    protocol=self.protocol.get(), details=self.details.get(), startup=self.startup.get(), smart=self.smart.get(), auto_isp=self.auto_isp.get())

    def network_key(self):
        live = getattr(self.dashboard, 'last_live', None) or {}
        return tuple(sorted(live.get('wifi', {}).items())), tuple(sorted(live.get('up', ())))

    def observe_wifi(self, wifi):
        # Called on the Tk thread with the monitor's current connected SSIDs.
        current = tuple(sorted(wifi.items()))
        if current == self.isp_wifi: return
        self.isp_wifi = current
        if not self.auto_isp.get(): return
        # Invalidate even while disconnected: an old network's in-flight
        # result must never be assigned to the new one.
        self.isp_serial += 1; self.isp_busy = False
        self.isp_checked_at = None; self.isp_checked_network = None
        self.isp_cached = None; self.isp_cached_error = None
        if self.isp_wifi_timer:
            self.root.after_cancel(self.isp_wifi_timer); self.isp_wifi_timer = None
        if not current:
            self.isp_detection.set('Wi-Fi disconnected · waiting for a network.')
            return
        self.isp_detection.set('Wi-Fi changed · detecting your provider…')
        def check():
            self.isp_wifi_timer = None
            if self.auto_isp.get() and self.isp_wifi == current:
                self.detect_isp()
        self.isp_wifi_timer = self.root.after(2000, check)

    def manual_isp(self, _event=None):
        self.auto_isp.set(False)
        if self.isp_wifi_timer:
            self.root.after_cancel(self.isp_wifi_timer); self.isp_wifi_timer = None
        self.isp_serial += 1; self.isp_busy = False; self.pending_start = False
        self.isp_detection.set('Manual choice · '+self.isp.get())
        if hasattr(self, 'shell'): self.shell.update_toggle()

    def change_isp_mode(self):
        if self.auto_isp.get(): self.detect_isp()
        else: self.manual_isp()

    def detect_isp(self, force=False, start_after=False):
        self.pending_start = self.pending_start or start_after
        if self.isp_busy: return
        now = time.monotonic()
        if self.isp_checked_at is not None and now-self.isp_checked_at < (30 if force else 1800) and self.isp_checked_network==self.network_key():
            self.receive_isp(self.isp_serial,self.isp_cached,self.isp_cached_error,cached=True)
            return
        self.isp_serial += 1; serial = self.isp_serial
        self.isp_busy = True
        self.isp_detection.set('Checking your network provider…')
        if start_after: self.status.set('Detecting ISP before starting checks…')
        self.shell.update_toggle()
        def work():
            try:
                from .isp import lookup
                value = lookup(); error = None
            except Exception as failure:
                value = None; error = type(failure).__name__
            self.events.put(('isp', (serial, value, error)))
        threading.Thread(target=work, daemon=True).start()

    def receive_isp(self, serial, value, error, cached=False):
        if serial != self.isp_serial: return
        self.isp_busy = False
        if not cached:
            self.isp_checked_at = time.monotonic(); self.isp_checked_network = self.network_key()
            self.isp_cached = value; self.isp_cached_error = error
        if self.auto_isp.get() and value and value.get('isp'):
            self.isp.set(value['isp'])
            self.isp_detection.set('Detected '+value['isp']+' · public network lookup. VPNs may show a different provider.' + (' Restart checks to use this ISP.' if self.running and not self.custom.get().strip() else ''))
            if not self.diagnostic:
                try: self.store.save(self.values())
                except (ValueError, OSError): pass
            if not self.running: self.status.set('Ready · '+self.isp.get())
        elif value and value.get('isp'):
            self.isp_detection.set('Detected '+value['isp']+' · keeping your manual choice '+self.isp.get()+'.')
        elif value:
            self.isp_detection.set(value['provider']+' · no matching preset; keeping '+self.isp.get()+'. Choose manually if needed.')
        else:
            self.isp_detection.set('Could not detect ISP; keeping '+self.isp.get()+'. You can choose it manually.')
            if self.auto_isp.get() and self.isp_wifi and not self.isp_wifi_timer:
                expected = self.isp_wifi
                def retry():
                    self.isp_wifi_timer = None
                    if self.auto_isp.get() and self.isp_wifi == expected:
                        self.isp_checked_at = None
                        self.detect_isp()
                self.isp_wifi_timer = self.root.after(30000, retry)
        resume = self.pending_start; self.pending_start = False
        self.shell.update_toggle()
        if resume: self.start(automatic=True, resolved=True)

    def enable_app_tracking(self):
        from .platforms import admin
        if os.name != 'nt' or admin():
            self.shell.open('Live traffic'); return
        if self.dashboard.ssh_tab.session or self.dashboard.vless_tab.session:
            messagebox.showinfo('Enable app tracking', 'Disconnect your SSH/VLESS tunnel before restarting NetCroc.'); return
        import subprocess
        import psutil
        args = ([] if getattr(sys, 'frozen', False) else [str(__import__('pathlib').Path(__file__).resolve().parents[1]/'app.py')])
        args += ['--after-exit', str(os.getpid()), str(psutil.Process().create_time())]
        if self.running: args.append('--resume-checks')
        try:
            if not self.diagnostic: self.store.save(self.values())
            launch = ctypes.windll.shell32.ShellExecuteW
            launch.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
            launch.restype = ctypes.c_void_p
            result = launch(None, 'runas', sys.executable, subprocess.list2cmdline(args), None, 1) or 0
            if result <= 32:
                messagebox.showinfo('App tracking not enabled', 'Windows approval was not given. Network totals continue recording.'); return
            self.quit()
        except (OSError, ValueError) as error:
            messagebox.showerror('Enable app tracking', str(error))

    def toggle_advanced(self):
        if self.advanced.winfo_manager():
            self.advanced.pack_forget();self.advanced_button.configure(text='More settings')
        else:
            self.advanced.pack(fill='x',before=self.status_label);self.advanced_button.configure(text='Fewer settings')

    def toggle_details(self):
        if self.details.get():
            self.log.pack(fill='x', pady=(12, 0), before=self.log.master.winfo_children()[-1])
        else:
            self.log.pack_forget()

    def start(self, automatic=False, resolved=False):
        if self.comparing:
            return
        if self.worker and self.worker.is_alive():
            if not automatic:
                messagebox.showinfo('Already running', 'Pause before changing the connection settings.')
            return
        if self.auto_isp.get() and not resolved and not self.custom.get().strip():
            self.detect_isp(start_after=True); return
        try:
            settings = self.values()
            target = validate(settings)
            if not self.diagnostic:
                set_startup(settings['startup'])
                self.store.save(settings)
        except (ValueError, OSError, tk.TclError) as error:
            fix = ('Check folder access and Windows startup permissions, then retry.'
                   if isinstance(error, OSError) else 'Check your ISP, interval and custom website/IP, then retry.')
            messagebox.showerror('Could not start', str(error) + '\n\nHow to fix: ' + fix)
            return
        self.stop_event = threading.Event()
        self.running = True
        self.status.set('Running · ' + settings['isp'])
        self.start_button.configure(state='disabled')
        def work():
            failures = 0
            while not self.stop_event.is_set():
                result = probe(target, settings['protocol'])
                if self.stop_event.is_set():
                    break
                # Refused/rate-limited/error HTTP endpoints must not be hammered at 1 Hz.
                unsuitable = not result[0] or any(f'HTTP {code} ' in result[2] for code in (403, 405, 429)) or result[2].startswith('HTTP 5')
                failures = min(failures + 1, 6) if unsuitable else 0
                base = smart_interval(settings['interval'], settings['smart'], self.activity, time.monotonic())
                period = max(base, min(60, 2 ** failures)) if failures else base
                if any(f'HTTP {code} ' in result[2] for code in (403, 405, 429)):
                    period = max(period, 60)
                if unsuitable or period != settings['interval']:
                    result = (result[0], result[1], result[2] + f' · next check in {period}s')
                self.events.put(('result', result))
                if self.stop_event.wait(period):
                    break
            self.events.put(('stopped', None))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()
        self.update_tray()

    def compare_window(self):
        if getattr(self, 'compare_dialog', None) and self.compare_dialog.winfo_exists():
            self.compare_dialog.lift(); return
        dialog=self.compare_dialog=tk.Toplevel(self.root)
        dialog.title('Does keep-alive help?'); dialog.geometry('730x400')
        body=ttk.Frame(dialog,padding=18);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Compare keep-alive OFF / ON',font=('Segoe UI',15,'bold')).pack(anchor='w')
        ttk.Label(body,text='6 minutes: OFF then ON, 3 minutes each. Both phases measure every 10s.\nOFF still sends sparse measurement requests. ON adds your selected regular interval.\nSmart mode is suspended for this comparison. Keep location and other activity similar.\nMeasures response times and failed checks, not download speed or game ping.',wraplength=690).pack(anchor='w',pady=10)
        self.compare_text=tk.StringVar(value='Uses the ISP, target and protocol currently selected on Keep-alive.')
        ttk.Label(body,textvariable=self.compare_text,wraplength=690).pack(anchor='w',pady=8)
        self.compare_table=ttk.Treeview(body,columns=('phase','median','p95','failed'),show='headings',height=2)
        for col,label in zip(('phase','median','p95','failed'),('Keep-alive','Median response','Slow response (p95)','Failed checks')):
            self.compare_table.heading(col,text=label);self.compare_table.column(col,width=160)
        self.compare_table.pack(fill='x')
        buttons=ttk.Frame(body);buttons.pack(fill='x',pady=12)
        self.compare_button=ttk.Button(buttons,text='Start comparison',command=self.begin_comparison);self.compare_button.pack(side='left')
        ttk.Button(buttons,text='Cancel',command=self.compare_stop.set).pack(side='left',padx=8)
        def close():
            if self.comparing:
                self.compare_stop.set();self.compare_text.set('Cancelling… wait for the current check to finish.');return
            dialog.destroy()
        dialog.protocol('WM_DELETE_WINDOW',close)

    def begin_comparison(self):
        if self.comparing:return
        try:
            settings=self.values();target=validate(settings)
        except (ValueError,tk.TclError) as error:
            messagebox.showerror('Check comparison settings',str(error));return
        self.compare_original=settings.copy()
        was_running=self.running
        old_worker=self.worker
        self.pause();self.comparing=True;self.compare_stop.clear()
        self.compare_button.configure(state='disabled');self.start_button.configure(state='disabled')
        self.compare_table.delete(*self.compare_table.get_children())
        self.compare_text.set('Preparing comparison…')
        def work():
            outcome=None
            try:
                if old_worker:old_worker.join(timeout=6)
                if old_worker and old_worker.is_alive():
                    self.events.put(('comparison','Previous check is still stopping. Try again.'));return
                outcome=run_comparison(target,settings['protocol'],settings['interval'],self.compare_stop,
                    lambda value:self.events.put(('comparison',value)))
            except Exception as error:
                self.events.put(('comparison','Comparison failed: '+type(error).__name__))
            finally:self.events.put(('comparison_done',(outcome,was_running)))
        self.compare_worker=threading.Thread(target=work,daemon=True);self.compare_worker.start()

    def pause(self):
        if self.pending_start:
            self.isp_serial += 1; self.pending_start = False; self.isp_busy = False
        if self.comparing:
            self.compare_stop.set()
        if self.stop_event:
            self.stop_event.set()
        self.running = False
        self.status.set('Paused')
        self.update_tray()

    def close_window(self):
        if self.desktop.data['close_to_tray'] and self.tray: self.hide()
        else: self.quit()

    def hide(self):
        if self.tray:
            self.root.withdraw()
        elif not self.diagnostic:
            messagebox.showinfo('Tray unavailable', 'Use Quit to close the app. The tray icon could not be created.')

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def update_tray(self, good=None):
        if self.tray:
            self.tray.title = 'NetCroc · ' + ('Running' if self.running else 'Paused')
            self.tray.icon = icon_image('#34d399' if self.running and good is not False else '#94a3b8')
            self.tray.update_menu()

    def create_tray(self):
        def send(action):
            return lambda icon, item: self.events.put((action, None))
        self.tray = pystray.Icon('NetCroc', icon_image(), 'NetCroc · Ready',
            pystray.Menu(pystray.MenuItem('Open', send('open'), default=True),
                         pystray.MenuItem('Start', send('start'), enabled=lambda item: not self.running),
                         pystray.MenuItem('Pause', send('pause'), enabled=lambda item: self.running),
                         pystray.MenuItem('Overlay', send('overlay'), checked=lambda item:self.desktop.data['overlay_enabled']),
                         pystray.MenuItem('Quit', send('quit'))))
        self.tray.run_detached()

    def poll(self):
        if self.closing:
            return
        while not self.events.empty():
            action, value = self.events.get()
            if action == 'isp':
                self.receive_isp(*value)
            elif action == 'result':
                good, duration, text = value
                self.status.set(('Running · ' if good else 'Retrying · ') + text)
                self.update_tray(good)
                self.log.configure(state='normal')
                self.log.insert('end', f'{text} · {duration} ms total\n')
                if int(self.log.index('end-1c').split('.')[0]) > 100:
                    self.log.delete('1.0', '2.0')
                self.log.see('end')
                self.log.configure(state='disabled')
            elif action == 'comparison':
                if isinstance(value,tuple):
                    phase,data=value
                    fmt=lambda v:'—' if v is None else f'{v:.0f} ms'
                    self.compare_table.insert('', 'end',values=(phase,fmt(data['median']),fmt(data['p95']),f"{data['failures']}/{data['attempts']}"))
                else:self.compare_text.set(value)
            elif action == 'comparison_done':
                outcome,resume=value;self.comparing=False
                self.compare_button.configure(state='normal');self.start_button.configure(state='normal')
                if outcome:
                    self.compare_text.set(comparison_verdict(outcome['OFF'],outcome['ON'])+' Repeat to confirm; this is one sequential trial.')
                else:self.compare_text.set(self.compare_text.get()+' · Stopped; no complete comparison.')
                if resume and not self.closing:
                    for key,old in self.compare_original.items():getattr(self,key).set(old)
                    self.start(automatic=True)
            elif action == 'stopped':
                if not self.comparing:self.start_button.configure(state='normal')
            elif action == 'overlay': self.overlay.enabled.set(not self.overlay.enabled.get())
            elif action == 'open': self.show()
            elif action == 'start': self.start()
            elif action == 'pause': self.pause()
            elif action == 'quit':
                self.quit()
                return
        if os.name=='nt' and getattr(self, 'show_event', None) and ctypes.windll.kernel32.WaitForSingleObject(self.show_event, 0) == 0:
            self.show()
        self.root.after(150, self.poll)

    def quit(self):
        if self.closing:return
        self.closing = True
        self.compare_stop.set()
        if self.stop_event:
            self.stop_event.set()
        if self.tray:
            self.tray.stop()
        self.window.close()
        self.overlay.close()
        self.dashboard.close()
        self.root.destroy()

def main():
    diagnostic = '--diagnostics' in sys.argv
    if os.name!='nt':return posix_main(diagnostic)
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateEventW.restype = ctypes.c_void_p
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.SetEvent.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = event = None
    if not diagnostic:
        # Share the legacy lock while earlier releases may still be running.
        mutex = kernel.CreateMutexW(None, False, 'Local\\ConnectionTrayPreview')
        exists = kernel.GetLastError() == 183
        event = kernel.CreateEventW(None, False, False, 'Local\\ConnectionTrayPreview.Show')
        if exists:
            kernel.SetEvent(event)
            kernel.CloseHandle(event)
            kernel.CloseHandle(mutex)
            return
    root = tk.Tk()
    if diagnostic: root.withdraw()
    app = App(root, diagnostic)
    app.show_event = event
    if diagnostic:
        root.update_idletasks()
        app.compare_window()
        assert not app.smart.get() and app.compare_button.winfo_exists()
        app.compare_dialog.destroy()
        app.details.set(True)
        app.toggle_details()
        root.update_idletasks()
        Path = __import__('pathlib').Path
        Path(sys.argv[sys.argv.index('--diagnostics')+1]).write_text(json.dumps({'gui': 'passed', 'tabs': len(app.dashboard.notebook.tabs()), 'main_destinations': list(app.shell.primary), 'tool_destinations': list(app.shell.tools), 'isps': list(PRESETS), 'startup_changed': False, 'network_sent': False, 'capture_started': False, 'dns_changed': False, 'wifi_changed': False}), encoding='utf-8')
        app.quit()
        return
    try:
        app.create_tray()
    except Exception:
        app.tray = None
        app.status.set('Tray unavailable · restart the app; use Quit below to exit.')
        ttk.Button(root, text='Quit', command=app.quit).pack()
    if '--resume-checks' in sys.argv and '--tray' not in sys.argv: app.start(automatic=True)
    if '--tray' in sys.argv and app.tray:
        app.start(automatic=True)
        app.hide()
    try:
        root.mainloop()
    finally:
        if event: kernel.CloseHandle(event)
        if mutex: kernel.CloseHandle(mutex)


def posix_main(diagnostic):
    from .platforms import InstanceLock
    lock=None if diagnostic else InstanceLock()
    root=tk.Tk()
    try:
        if diagnostic:root.withdraw()
        app=App(root,diagnostic)
        if diagnostic:
            root.update_idletasks()
            from pathlib import Path
            Path(sys.argv[sys.argv.index('--diagnostics')+1]).write_text(json.dumps(dict(gui='passed',tabs=len(app.dashboard.notebook.tabs()),main_destinations=list(app.shell.primary),tool_destinations=list(app.shell.tools),startup_changed=False,network_sent=False,capture_started=False,dns_changed=False,wifi_changed=False)),encoding='utf-8')
            app.quit();return
        try:app.create_tray()
        except Exception:app.tray=None
        if '--tray' in sys.argv:
            app.start(automatic=True)
            if app.tray:app.hide()
        root.mainloop()
    finally:
        if lock:lock.close()
