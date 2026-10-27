"""Optional live overlays. Hover detection uses pointer position, not global input hooks."""
import json
import os
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk
import psutil
from .desktop import MODES, monitor_rect, panel_position, edge_triggered, position_window, clamp_position
from .history import speed


def vpn_signal():
    """Best-effort interface signal, never a claim that traffic is protected."""
    pattern = re.compile(r'wireguard|wintun|openvpn|vpn|proton|mullvad|avira|nord|surfshark|windscribe|tailscale|zerotier|anyconnect|globalprotect|fortinet|netcroc|^(?:tun|tap|wg|ppp)\d', re.I)
    if os.name == 'nt':
        script = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; @(Get-NetAdapter -ErrorAction Stop | Where-Object Status -eq Up | Select-Object Name,InterfaceDescription) | ConvertTo-Json -Compress"
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True,
                                timeout=6, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode: raise OSError('Network adapter inspection unavailable')
        data = json.loads(result.stdout.decode('utf-8-sig').strip() or '[]')
        data = [data] if isinstance(data, dict) else data
        names = [a['Name'] for a in data if pattern.search(a.get('Name', '')+' '+a.get('InterfaceDescription', ''))]
    else:
        names = [name for name, stats in psutil.net_if_stats().items() if stats.isup and pattern.search(name)]
    return {'active': bool(names), 'interfaces': sorted(names)}


class TrayOverlay:
    def __init__(self, app, preferences):
        self.app = app; self.root = app.root; self.preferences = preferences
        data = preferences.data
        self.enabled = tk.BooleanVar(value=data['overlay_enabled'])
        self.mode = tk.StringVar(value=data['overlay_mode'])
        self.apps = tk.BooleanVar(value=data['overlay_apps'])
        self.network = tk.BooleanVar(value=data['overlay_network'])
        self.vpn = tk.BooleanVar(value=data['overlay_vpn'])
        self.close_to_tray = tk.BooleanVar(value=data['close_to_tray'])
        self.alpha = tk.StringVar(value=f"{round(data['overlay_alpha']*100)}%")
        self.status = tk.StringVar(value='Exit country has not been checked.')
        self.events = queue.Queue(); self.signal = None; self.country = None
        self.signature = None; self.last_network_read = 0; self.network_busy = False
        self.last_country_request = None; self.country_busy = False
        self.visible = False; self.last_inside = 0; self.closed = False
        self.panel = tk.Toplevel(self.root); self.panel.netcroc_overlay=True; self.panel.withdraw()
        self.panel.title('NetCroc network overlay'); self.panel.overrideredirect(True)
        self.panel.attributes('-topmost', True)
        if os.name == 'nt': self.panel.wm_attributes('-toolwindow', True)
        self.background = '#10251d'
        self.canvas = tk.Canvas(self.panel, bg=self.background, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        if os.name == 'nt':
            self.canvas.configure(bg='#010203'); self.panel.wm_attributes('-transparentcolor', '#010203')
        self.body = tk.Frame(self.canvas, bg=self.background)
        self.body_window = self.canvas.create_window((18, 12), window=self.body, anchor='nw')
        self.canvas.bind('<Configure>', self.draw_panel)
        top = tk.Frame(self.body, bg=self.background); top.pack(fill='x')
        tk.Label(top, text='NetCroc', bg=self.background, fg='#a7d9bf', font=('Segoe UI', 10, 'bold')).pack(side='left')
        tk.Button(top, text='Open', command=self.open_app, bg=self.background, fg='white', bd=0).pack(side='right')
        tk.Button(top, text='×', command=lambda:self.enabled.set(False), bg=self.background, fg='white', bd=0).pack(side='right', padx=6)
        self.rates = tk.StringVar(); self.network_text = tk.StringVar(); self.apps_text = tk.StringVar(); self.vpn_text = tk.StringVar()
        labels = []
        for value, font, color in ((self.rates, ('Segoe UI', 17, 'bold'), '#f4fff8'),
                                   (self.network_text, ('Segoe UI', 9), '#c5d9cd'),
                                   (self.apps_text, ('Segoe UI', 9), '#f0f7f2'),
                                   (self.vpn_text, ('Segoe UI', 9), '#9cd9c0')):
            label = tk.Label(self.body, textvariable=value, font=font, bg=self.background, fg=color, anchor='w', justify='left')
            label.pack(fill='x', pady=(5, 0)); labels.append(label)
        self.labels = labels
        for widget in [self.canvas, self.body, top, *labels, top.winfo_children()[0]]:
            widget.bind('<ButtonPress-1>', self.drag_start); widget.bind('<B1-Motion>', self.drag)
            widget.bind('<ButtonRelease-1>', self.drag_end)
        for variable in (self.enabled, self.mode, self.apps, self.network, self.vpn, self.close_to_tray, self.alpha):
            variable.trace_add('write', lambda *_:self.apply())
        self.apply()
        self.timer = self.root.after(200, self.tick)

    def build_page(self, parent):
        self.page = parent
        ttk.Label(parent,text='Tray & overlay',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(parent,text='A little window into your network.',style='Muted.TLabel').pack(anchor='w',pady=(4,16))
        card=ttk.Frame(parent,style='Card.TFrame',padding=16);card.pack(fill='x',pady=(0,12))
        top=ttk.Frame(card,style='Card.TFrame');top.pack(fill='x')
        ttk.Checkbutton(top,text='Show live overlay',variable=self.enabled).pack(side='left')
        ttk.Button(top,text='Go to tray',command=self.app.hide).pack(side='right')
        ttk.Label(card,text='Choose where it appears',style='Card.TLabel').pack(anchor='w',pady=(14,6))
        modes=ttk.Frame(card,style='Card.TFrame');modes.pack(fill='x')
        for title,mode in [('Left','Left edge'),('Right','Right edge'),('Top','Top middle'),('Floating','Static')]:
            ttk.Radiobutton(modes,text=title,variable=self.mode,value=mode,style='Segment.TRadiobutton').pack(side='left',padx=(0,6))
        ttk.Label(card,text='Edge: move your mouse to reveal. Floating: drag it anywhere.',style='Card.TLabel',wraplength=650).pack(anchor='w',pady=(10,0))
        card=ttk.Frame(parent,style='Card.TFrame',padding=16);card.pack(fill='x',pady=(0,12))
        ttk.Label(card,text='Make it yours',style='Card.TLabel',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,8))
        for title,variable in [('Top apps',self.apps),('Wi-Fi & ISP',self.network),('VPN & exit country',self.vpn)]:
            ttk.Checkbutton(card,text=title,variable=variable).pack(anchor='w')
        more=ttk.Frame(parent)
        def toggle():
            if more.winfo_manager():more.pack_forget();button.configure(text='More options')
            else:more.pack(fill='x',pady=8);button.configure(text='Fewer options')
        button=ttk.Button(parent,text='More options',command=toggle);button.pack(anchor='w')
        line=ttk.Frame(more);line.pack(fill='x',pady=4)
        ttk.Label(line,text='Opacity').pack(side='left',padx=(0,10))
        ttk.Combobox(line,textvariable=self.alpha,values=('100%','95%','85%','75%'),state='readonly',width=7).pack(side='left')
        ttk.Button(line,text='Reset position',command=self.reset_position).pack(side='left',padx=12)
        ttk.Checkbutton(more,text='Close button sends NetCroc to tray',variable=self.close_to_tray).pack(anchor='w',pady=6)
        ttk.Button(more,text='Check exit country',command=self.check_country).pack(anchor='w',pady=6)
        ttk.Label(more,textvariable=self.status,wraplength=650).pack(anchor='w')
        from .dashboard import info_dialog
        ttk.Button(more,text='How VPN detection works',command=lambda:info_dialog(self.root,'VPN detection','An active tunnel interface is a hint, not proof of protection. Country is the checked public exit, not a guess from a profile name. App-only proxies may have a different exit. Country lookup uses ipwho.is.')).pack(anchor='w',pady=6)
        ttk.Button(more,text='Quit NetCroc',command=self.app.quit).pack(anchor='w',pady=6)

    def apply(self):
        if self.closed: return
        try:
            alpha = float(self.alpha.get().rstrip('%'))/100
            self.preferences.update(dict(overlay_enabled=self.enabled.get(), overlay_mode=self.mode.get(),
                overlay_apps=self.apps.get(), overlay_network=self.network.get(), overlay_vpn=self.vpn.get(),
                close_to_tray=self.close_to_tray.get(), overlay_alpha=alpha))
            self.panel.attributes('-alpha', alpha)
        except (ValueError, OSError, tk.TclError): self.status.set('Preferences could not be saved; this session still works.')
        for label,shown in zip(self.labels,[True,self.network.get(),self.apps.get(),self.vpn.get()]):
            label.pack_forget()
            if shown:label.pack(fill='x',pady=(5,0))
        if not self.enabled.get() or self.mode.get()!=getattr(self,'applied_mode',None): self.hide_panel()
        self.applied_mode=self.mode.get()

    def reset_position(self):
        self.preferences.update({'overlay_position': None}); self.hide_panel()

    def draw_panel(self, event):
        self.canvas.delete('surface'); radius = 28; width = event.width; height = event.height
        points = (radius,0,width-radius,0,width,0,width,radius,width,height-radius,width,height,width-radius,height,
                  radius,height,0,height,0,height-radius,0,radius,0,0)
        self.canvas.create_polygon(points, smooth=True, splinesteps=24, fill=self.background, outline='', tags='surface')
        self.canvas.tag_lower('surface'); self.canvas.itemconfigure(self.body_window, width=max(100, width-36))
        for label in self.labels: label.configure(wraplength=max(100, width-36))

    def open_app(self): self.app.show()

    def hide_panel(self):
        self.panel.withdraw(); self.visible = False

    def check_country(self, auto=False):
        if self.country_busy: return
        now = time.monotonic()
        if self.last_country_request is not None and now-self.last_country_request < (300 if auto else 30):
            if not auto:self.status.set('Please wait 30 seconds between country checks.')
            return
        self.country_busy = True; self.last_country_request = now
        signature = self.signature; self.status.set('Checking the public exit country…')
        def work():
            try:
                from .isp import exit_location
                result = exit_location(); self.events.put(('country', (signature, result)))
            except Exception: self.events.put(('country-error', None))
        threading.Thread(target=work, daemon=True).start()

    def receive(self):
        while not self.events.empty():
            kind, value = self.events.get()
            if kind == 'network':
                self.network_busy = False
                signature = tuple(value['interfaces'])
                if self.signal is not None and signature != self.signature:
                    self.country = None; self.status.set('Network tunnel changed; check the exit country again.')
                self.signature = signature; self.signal = value
                if value['active'] and self.country is None and not self.app.diagnostic:
                    self.check_country(auto=True)
            elif kind == 'network-error': self.network_busy = False; self.signal = None
            elif kind == 'country':
                self.country_busy = False; signature, result = value
                if signature == self.signature:
                    self.country = dict(result, checked=time.monotonic())
                    self.status.set('Public exit: '+result['country']+' · checked now. This is not a DNS-leak test.')
            elif kind == 'country-error':
                self.country_busy = False; self.country = None; self.status.set('Country lookup unavailable; no country will be assumed.')

    def update_text(self):
        dashboard = self.app.dashboard
        self.set_text(self.rates, dashboard.down.get()+'    '+dashboard.up.get())
        sample = getattr(dashboard, 'overlay_snapshot', {})
        cached = self.app.isp_cached or {}
        provider = cached.get('isp') or cached.get('provider') or 'not checked'
        self.set_text(self.network_text, ('Wi-Fi / network: '+sample.get('network', 'not connected')[:48]+'\nISP / provider: '+provider[:48]) if self.network.get() else '')
        apps = sample.get('apps', [])[:2 if self.mode.get() == 'Top middle' else 3]
        text = 'Top apps now: '+('\n'.join(name[:30]+' · '+speed(rate) for name, rate in apps) if apps else 'no app traffic measured')
        self.set_text(self.apps_text, text if self.apps.get() else '')
        signal = 'VPN / tunnel interface active' if self.signal and self.signal['active'] else 'No VPN interface detected' if self.signal else 'VPN status not checked'
        if self.country:
            age = int((time.monotonic()-self.country['checked'])/60)
            signal += '\nPublic exit: '+self.country['country']+f' · checked {age}m ago'
        else: signal += '\nExit country: not checked'
        self.set_text(self.vpn_text, signal if self.vpn.get() else '')

    @staticmethod
    def set_text(variable, value):
        if variable.get() != value: variable.set(value)

    def tick(self):
        if self.closed or self.app.closing: return
        self.receive(); now = time.monotonic()
        page_open = hasattr(self, 'page') and self.app.shell.book.select() == str(self.page)
        if (self.enabled.get() or page_open) and not self.app.diagnostic and not self.network_busy and now-self.last_network_read >= 10:
            self.network_busy = True; self.last_network_read = now
            def work():
                try: self.events.put(('network', vpn_signal()))
                except Exception: self.events.put(('network-error', None))
            threading.Thread(target=work, daemon=True).start()
        if self.signal and self.signal['active'] and self.country and now-self.country['checked']>=300 and not self.app.diagnostic:
            self.check_country(auto=True)
        if self.enabled.get():
            self.update_text(); point = self.root.winfo_pointerxy(); mode = self.mode.get()
            area = monitor_rect(self.root, point); screen = monitor_rect(self.root, point, work=False)
            width=500 if mode=='Top middle' else 370
            self.canvas.itemconfigure(self.body_window,width=width-36)
            for label in self.labels:label.configure(wraplength=width-36)
            self.body.update_idletasks()
            size=(width,min(area[3]-area[1],max(90,self.body.winfo_reqheight()+24)))
            if mode == 'Static' or edge_triggered(mode, point, screen, size[0]):
                self.last_inside = now
                if not self.visible or getattr(self,'last_size',None)!=size:
                    self.last_size=size
                    saved = self.preferences.data['overlay_position'] if mode == 'Static' else None
                    area = monitor_rect(self.root, saved) if saved else area
                    position_window(self.panel, size, panel_position(mode, size, area, saved))
                    self.panel.deiconify(); self.visible = True
            elif self.visible:
                x, y = self.panel.winfo_rootx(), self.panel.winfo_rooty()
                if x <= point[0] < x+self.panel.winfo_width() and y <= point[1] < y+self.panel.winfo_height(): self.last_inside = now
                elif now-self.last_inside > .45: self.hide_panel()
        elif self.visible: self.hide_panel()
        self.timer = self.root.after(150 if self.enabled.get() else 400, self.tick)

    def drag_start(self, event):
        if self.mode.get() == 'Static': self.drag_offset = event.x_root-self.panel.winfo_rootx(), event.y_root-self.panel.winfo_rooty()

    def drag(self, event):
        if self.mode.get() != 'Static' or not hasattr(self, 'drag_offset'): return
        size = self.panel.winfo_width(), self.panel.winfo_height()
        position = event.x_root-self.drag_offset[0], event.y_root-self.drag_offset[1]
        area = monitor_rect(self.root, (event.x_root, event.y_root))
        position_window(self.panel, size, clamp_position(position, size, area))

    def drag_end(self, _event=None):
        if self.mode.get() == 'Static' and self.visible:
            self.preferences.update({'overlay_position': [self.panel.winfo_rootx(), self.panel.winfo_rooty()]})

    def close(self):
        self.closed = True
        try: self.root.after_cancel(self.timer); self.panel.destroy()
        except tk.TclError: pass
