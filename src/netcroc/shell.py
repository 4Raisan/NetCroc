"""Direct sidebar navigation for everyday pages and network tools."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


def logo_path():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return base / 'assets' / 'netcroc-transparent.png'


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
        style.configure('TButton', padding=(12, 6), background='#e8f2ec', borderwidth=0, relief='flat', focusthickness=0)
        style.configure('TCombobox', padding=6, fieldbackground='white', bordercolor='#dce6e0', arrowsize=14)
        style.layout('Segment.TRadiobutton', [('Toolbutton.border', {'sticky':'nswe','children':[('Toolbutton.padding',{'sticky':'nswe','children':[('Toolbutton.label',{'sticky':'nswe'})]})]})])
        style.configure('Segment.TRadiobutton', padding=(10,7),background='#e9efec',borderwidth=0)
        style.map('Segment.TRadiobutton',background=[('selected','#d4ecdf'),('active','#e0eae4')],foreground=[('selected','#0e6041')])
        style.configure('TRadiobutton', padding=(5,4), indicatorsize=12)
        style.configure('TCheckbutton', padding=(4,5), indicatorsize=14)
        style.configure('TNotebook', borderwidth=0)
        style.layout('Quiet.TNotebook', [('Notebook.client', {'sticky':'nswe'})])
        style.configure('TSeparator', background='#e2e9e5')
        style.map('TButton', background=[('active', '#dce9e2')])
        style.configure('Primary.TButton', background='#126548', foreground='white')
        style.map('Primary.TButton', background=[('active', '#0b5038'), ('disabled', '#d4e1da')])
        style.configure('Nav.TButton', padding=(14, 9), anchor='w', background='#eaf1ed', font=('Segoe UI',10))
        style.map('Nav.TButton', background=[('selected', '#dceee4'), ('active', '#e7eeea')])
        style.configure('ToolNav.TButton', padding=(14, 6), anchor='w', background='#eaf1ed', font=('Segoe UI', 9))
        style.map('ToolNav.TButton', background=[('selected', '#dceee4'), ('active', '#e7eeea')])
        style.configure('Card.TFrame', background='white')
        style.configure('Card.TLabel', background='white')
        style.configure('Muted.TLabel', foreground='#63776d')
        style.configure('Treeview', background='white', fieldbackground='white', rowheight=34, borderwidth=0, relief='flat', lightcolor='white', darkcolor='white')
        style.configure('Treeview.Heading', padding=(10,8), background='#edf3ef', relief='flat', font=('Segoe UI',9,'bold'))
        style.map('Treeview', background=[('selected','#d7eee2')],foreground=[('selected','#124a34')])
        style.layout('Quiet.TNotebook.Tab', [])
        style.configure('Quiet.TNotebook', tabmargins=0, borderwidth=0)
        root.configure(background='#69bc2a')
        surface = ttk.Frame(root); surface.pack(fill='both', expand=True, padx=2, pady=2)
        app.window.round_surface(surface)
        header = ttk.Frame(surface, padding=(24, 12))
        header.pack(fill='x')
        try:
            with Image.open(logo_path()) as source:
                image = source.convert('RGBA'); image.thumbnail((42, 42), Image.Resampling.LANCZOS)
            self.logo = ImageTk.PhotoImage(image, master=root)
            ttk.Label(header, image=self.logo).pack(side='left', padx=(0, 12))
            root.iconphoto(True, self.logo)
        except OSError:
            self.logo = None
        brand = ttk.Frame(header); brand.pack(side='left')
        ttk.Label(brand, text='NetCroc', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(brand, text='Your quiet network companion.', style='Muted.TLabel').pack(anchor='w')
        ttk.Button(header, text='×', width=3, command=app.close_window).pack(side='right')
        self.size_button=ttk.Button(header, text='□', width=3, command=app.window.maximize); self.size_button.pack(side='right',padx=4)
        app.window.size_button=self.size_button
        ttk.Button(header, text='—', width=3, command=app.window.minimize).pack(side='right')
        ttk.Button(header, text='To tray', command=app.hide).pack(side='right',padx=8)
        for widget in [header,brand,*brand.winfo_children(),*(w for w in header.winfo_children() if isinstance(w,ttk.Label))]: app.window.bind_drag(widget)
        outer = ttk.Frame(surface); outer.pack(fill='both', expand=True)
        body = ttk.Frame(outer); body.pack(fill='both', expand=True, padx=11, pady=(0, 11))
        style.configure('Sidebar.TFrame',background='#eaf1ed')
        style.configure('Sidebar.TLabel',background='#eaf1ed',foreground='#63776d')
        self.sidebar = ttk.Frame(body, width=178, style='Sidebar.TFrame'); self.sidebar.pack(side='left', fill='y', padx=(0, 12))
        self.sidebar.pack_propagate(False)
        content = ttk.Frame(body); content.pack(side='left', fill='both', expand=True)
        self.book = ttk.Notebook(content, style='Quiet.TNotebook')
        self.book.pack(fill='both', expand=True)
        self.book.bind('<<NotebookTabChanged>>', self.changed)

    def finish(self, dashboard, keepalive):
        self.dashboard = dashboard
        self.pages = {self.book.tab(tab, 'text'): self.book.nametowidget(tab) for tab in self.book.tabs()}
        home = ttk.Frame(self.book, padding=(20, 12)); self.book.add(home, text='Home')
        tray=ttk.Frame(self.book,padding=16);self.book.add(tray,text='Tray mode');self.app.overlay.build_page(tray)
        self.primary = {'Home': home, 'Connection checks':keepalive, 'Live traffic':dashboard.tab_live,
                        'Usage': dashboard.tab_history, 'Wi-Fi': dashboard.tab_wifi, 'Tray mode':tray}
        self.tools = {label: self.pages[page] for label, page in (
            ('DNS', 'DNS'), ('VPN', 'VPN'), ('SSH / TLS', 'SSH / TLS'),
            ('VLESS', 'VLESS'), ('Website tests', 'URL study'))}
        self.destinations = {**self.primary, **self.tools}
        from .about import About
        self.about=About(self.app)
        for name in self.primary:
            button = ttk.Button(self.sidebar, text=name, style='Nav.TButton', command=lambda n=name: self.show(n))
            button.pack(fill='x', pady=3); self.buttons[name] = button
        ttk.Separator(self.sidebar).pack(fill='x', padx=12, pady=(16, 10))
        ttk.Label(self.sidebar, text='TOOLS', style='Sidebar.TLabel', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=14, pady=(0, 6))
        for name in self.tools:
            button = ttk.Button(self.sidebar, text=name, style='ToolNav.TButton', command=lambda n=name: self.show(n))
            button.pack(fill='x', pady=2); self.buttons[name] = button
        ttk.Button(self.sidebar,text='About',style='ToolNav.TButton',command=self.about.show).pack(side='bottom',fill='x',pady=2)
        ttk.Label(self.sidebar,textvariable=self.about.summary,style='Sidebar.TLabel',wraplength=160,font=('Segoe UI',8)).pack(side='bottom',anchor='w',padx=12,pady=4)
        ttk.Label(home, text='Your network, at a glance', font=('Segoe UI', 21, 'bold')).pack(anchor='w', pady=(4, 6))
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
        card = ttk.Frame(home, style='Card.TFrame', padding=22); card.pack(fill='x')
        row = ttk.Frame(card, style='Card.TFrame'); row.pack(fill='x')
        ttk.Label(row, text='Keep connection active', style='Card.TLabel', font=('Segoe UI', 14, 'bold')).pack(side='left')
        self.toggle = ttk.Button(row, text='Start', style='Primary.TButton', command=self.toggle_checks)
        self.toggle.pack(side='right')
        ttk.Label(card, text='Optional checks may help with idle stalls.', style='Card.TLabel').pack(anchor='w', pady=(8, 4))
        ttk.Label(card, textvariable=self.app.status, style='Card.TLabel', wraplength=640).pack(anchor='w')
        ttk.Button(card, text='Connection settings', command=lambda: self.open('Keep-alive')).pack(anchor='w', pady=(12, 0))
        ttk.Label(home, text='Monitoring stays local. Speeds are shown in bytes per second.', style='Muted.TLabel', wraplength=650).pack(anchor='w', pady=22)
        self.app.status.trace_add('write', lambda *_: self.update_toggle())
        ttk.Button(home, text='Check setup', command=lambda: self.open_setup()).pack(anchor='w')
        self.show('Home')

    def open_setup(self):
        from .setup_ui import show
        show(self.app)

    def toggle_checks(self):
        if self.app.running or self.app.pending_start: self.app.pause()
        else: self.app.start()
        self.update_toggle()

    def update_toggle(self):
        self.toggle.configure(text='Cancel' if self.app.pending_start else 'Pause' if self.app.running else 'Start',
                              state='disabled' if self.app.comparing else 'normal')

    def show(self, name):
        self.book.select(self.destinations[name])
        self.changed()
        if name=='Usage': self.dashboard.refresh_history()

    def open(self, name):
        self.book.select(self.pages[name])
        self.changed()

    def changed(self, _event=None):
        if not self.primary: return
        selected=self.book.select()
        for name, button in self.buttons.items():
            button.state(['selected'] if str(self.destinations[name])==selected else ['!selected'])
