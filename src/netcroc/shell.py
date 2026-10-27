"""Four everyday destinations, with specialist controls one level deeper."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class Shell:
    def __init__(self, root, app):
        self.app = app
        self.primary = {}
        self.buttons = {}
        self.pages = {}
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', background='#f4f7f5', foreground='#18372c', font=('Segoe UI', 10))
        style.configure('TFrame', background='#f4f7f5')
        style.configure('TLabel', background='#f4f7f5')
        style.configure('TButton', padding=(14, 9), background='#e7eeea', borderwidth=0)
        style.map('TButton', background=[('active', '#dce9e2')])
        style.configure('Primary.TButton', background='#126548', foreground='white')
        style.map('Primary.TButton', background=[('active', '#0b5038'), ('disabled', '#d4e1da')])
        style.configure('Nav.TButton', padding=(20, 11), anchor='w', background='#f4f7f5')
        style.map('Nav.TButton', background=[('selected', '#dceee4'), ('active', '#e7eeea')])
        style.configure('Card.TFrame', background='white')
        style.configure('Card.TLabel', background='white')
        style.configure('Muted.TLabel', foreground='#63776d')
        style.configure('Treeview', background='white', fieldbackground='white', rowheight=30, borderwidth=0)
        style.configure('Treeview.Heading', padding=8, background='#e7eeea')
        style.layout('Quiet.TNotebook.Tab', [])
        style.configure('Quiet.TNotebook', tabmargins=0, borderwidth=0)
        root.configure(background='#f4f7f5')
        header = ttk.Frame(root, padding=(24, 16))
        header.pack(fill='x')
        self.logo = None
        brand = ttk.Frame(header); brand.pack(side='left')
        ttk.Label(brand, text='NetCroc', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(brand, text='Your quiet network companion.', style='Muted.TLabel').pack(anchor='w')
        ttk.Button(header, text='Quit', command=app.quit).pack(side='right')
        ttk.Button(header, text='Hide', command=app.hide).pack(side='right', padx=8)
        body = ttk.Frame(root); body.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        self.sidebar = ttk.Frame(body, width=145); self.sidebar.pack(side='left', fill='y', padx=(0, 12))
        content = ttk.Frame(body); content.pack(side='left', fill='both', expand=True)
        self.back = ttk.Button(content, text='‹  Back to Tools', command=lambda: self.show('Tools'))
        self.book = ttk.Notebook(content, style='Quiet.TNotebook')
        self.book.pack(fill='both', expand=True)
        self.book.bind('<<NotebookTabChanged>>', self.changed)

    def finish(self, dashboard, keepalive):
        self.dashboard = dashboard
        self.pages = {self.book.tab(tab, 'text'): self.book.nametowidget(tab) for tab in self.book.tabs()}
        home = ttk.Frame(self.book, padding=(20, 12)); self.book.add(home, text='Home')
        tools = ttk.Frame(self.book, padding=(20, 12)); self.book.add(tools, text='Tools')
        self.primary = {'Home': home, 'Usage': dashboard.tab_history, 'Wi-Fi': dashboard.tab_wifi, 'Tools': tools}
        for name in self.primary:
            button = ttk.Button(self.sidebar, text=name, style='Nav.TButton', command=lambda n=name: self.show(n))
            button.pack(fill='x', pady=3); self.buttons[name] = button
        ttk.Label(home, text='Your connection at a glance', font=('Segoe UI', 21, 'bold')).pack(anchor='w', pady=(4, 6))
        self.network = tk.StringVar(value='Waiting for connection data…')
        ttk.Label(home, textvariable=self.network, style='Muted.TLabel').pack(anchor='w', pady=(0, 22))
        rates = ttk.Frame(home); rates.pack(fill='x')
        for column, (label, value) in enumerate((('Download', dashboard.down), ('Upload', dashboard.up))):
            rates.columnconfigure(column, weight=1, uniform='rates')
            card = ttk.Frame(rates, style='Card.TFrame', padding=22)
            card.grid(row=0, column=column, sticky='nsew', padx=(0, 8) if column==0 else (8, 0))
            ttk.Label(card, text=label, style='Card.TLabel').pack(anchor='w')
            ttk.Label(card, textvariable=value, style='Card.TLabel', font=('Segoe UI', 25, 'bold')).pack(anchor='w', pady=(8, 4))
        ttk.Button(home, text='See apps and live graph  →', command=lambda: self.open('Live traffic')).pack(anchor='w', pady=(12, 24))
        ttk.Label(home, text='Monitoring stays local. Speeds are shown in bytes per second.', style='Muted.TLabel', wraplength=650).pack(anchor='w', pady=22)
        card = ttk.Frame(home, style='Card.TFrame', padding=22); card.pack(fill='x')
        row = ttk.Frame(card, style='Card.TFrame'); row.pack(fill='x')
        ttk.Label(row, text='Keep connection active', style='Card.TLabel', font=('Segoe UI', 14, 'bold')).pack(side='left')
        self.toggle = ttk.Button(row, text='Start', style='Primary.TButton', command=self.toggle_checks)
        self.toggle.pack(side='right')
        ttk.Label(card, text='Optional checks may help with idle stalls.', style='Card.TLabel').pack(anchor='w', pady=(8, 4))
        ttk.Label(card, textvariable=self.app.status, style='Card.TLabel', wraplength=640).pack(anchor='w')
        ttk.Button(card, text='Connection settings', command=lambda: self.open('Keep-alive')).pack(anchor='w', pady=(12, 0))
        ttk.Label(tools, text='Tools', font=('Segoe UI', 21, 'bold')).pack(anchor='w', pady=(4, 6))
        ttk.Label(tools, text='Choose a tool when you need it.', style='Muted.TLabel').pack(anchor='w', pady=(0, 20))
        grid = ttk.Frame(tools); grid.pack(fill='x')
        choices = [('Connection checks', 'ISP, interval and optional keep-alive.', 'Keep-alive'),
                   ('DNS', 'Test lookup times or restore your settings.', 'DNS'),
                   ('VPN', 'Import and connect a WireGuard profile.', 'VPN'),
                   ('Live traffic', 'View per-app speed and the live graph.', 'Live traffic'),
                   ('SSH / TLS', 'Advanced · your own tunnel account.', 'SSH / TLS'),
                   ('VLESS', 'Advanced · your own server profile.', 'VLESS'),
                   ('Website tests', 'Advanced · compare ISP targets.', 'URL study')]
        for index, (title, detail, page) in enumerate(choices):
            col=index%2; grid.columnconfigure(col, weight=1, uniform='tools')
            tile=ttk.Frame(grid, style='Card.TFrame', padding=14)
            tile.grid(row=index//2, column=col, sticky='nsew', padx=(0, 8) if col==0 else (8, 0), pady=(0, 12))
            ttk.Button(tile, text=title+'  →', command=lambda p=page: self.open(p)).pack(anchor='w')
            ttk.Label(tile, text=detail, style='Card.TLabel', wraplength=270).pack(anchor='w', pady=(8, 0))
        self.app.status.trace_add('write', lambda *_: self.update_toggle())
        self.show('Home')

    def toggle_checks(self):
        if self.app.running: self.app.pause()
        else: self.app.start()
        self.update_toggle()

    def update_toggle(self):
        self.toggle.configure(text='Pause' if self.app.running else 'Start',
                              state='disabled' if self.app.comparing else 'normal')

    def show(self, name):
        self.book.select(self.primary[name])
        self.changed()
        if name=='Usage': self.dashboard.refresh_history()

    def open(self, name):
        self.book.select(self.pages[name])
        self.changed()

    def changed(self, _event=None):
        if not self.primary: return
        selected=self.book.select()
        primary=next((n for n,p in self.primary.items() if str(p)==selected), None)
        for name, button in self.buttons.items():
            button.state(['selected'] if name==(primary or 'Tools') else ['!selected'])
        if primary: self.back.pack_forget()
        else: self.back.pack(anchor='w', pady=(0, 6), before=self.book)
