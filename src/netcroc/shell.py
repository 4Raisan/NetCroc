"""Direct sidebar navigation for everyday pages and network tools."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


def logo_path():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return base / 'assets' / 'netcroc-transparent.png'


# Every style option a theme can own; a theme may omit keys to keep the built-in default.
LIGHT = dict(
    base='#f4f7f5', foreground='#18372c', side='#eaf1ed', muted='#63776d', card='#ffffff',
    button='#e8f2ec', button_active='#dce9e2', field='#ffffff', border='#dce6e0',
    theme_field='#ffffff', theme_border='#d6e3dc',
    segment='#e9efec', segment_active='#e0eae4', segment_selected='#d4ecdf', segment_text='#0e6041',
    notebook='#f4f7f5', tree='#ffffff', tree_heading='#edf3ef', tree_selected='#d7eee2',
    tree_selected_text='#124a34', stripe='#f6f9f7', rim='#69bc2a',
    primary='#126548', primary_active='#0b5038', primary_disabled='#d4e1da')
MINT = dict(LIGHT, base='#eaf7ef', side='#d8efdf', card='#ffffff', border='#c8e3d2',
            theme_border='#c8e3d2', button='#dcefe3', button_active='#cde8d9',
            segment='#dcefe3', segment_active='#d3e9dc', notebook='#eaf7ef',
            tree_heading='#dcefe3', stripe='#e2f2e8', rim='#4ea52d')
SAND = dict(LIGHT, base='#f7f4ec', side='#eee9dc', card='#fffdf8', muted='#6d6757',
            border='#e0d9c6', field='#fffdf8', theme_field='#fffdf8', theme_border='#ddd5c2',
            button='#efe9da', button_active='#e6dfcd', foreground='#332f22', segment='#efe9da',
            segment_active='#e8e1d0', segment_selected='#f0e7cf', segment_text='#7c5c1e',
            notebook='#f7f4ec', tree='#fffdf8', tree_heading='#efe9da', stripe='#f3efe4',
            rim='#b98a2e', tree_selected='#f0e2bd', tree_selected_text='#4d3a10')
GRAPHITE = dict(LIGHT, base='#1b1f24', foreground='#d7e1ea', side='#14181c', muted='#8b98a5',
                card='#232a31', button='#2c353e', button_active='#39434e', field='#1e242a',
                border='#39434e', theme_field='#1e242a', theme_border='#39434e',
                segment='#2c353e', segment_active='#333d47', segment_selected='#1d4f3c',
                segment_text='#7fe0b8', notebook='#1b1f24', tree='#1e242a', tree_heading='#2c353e',
                tree_selected='#1d4f3c', tree_selected_text='#d9f2e4', stripe='#22282e',
                rim='#0f1215', primary='#199a63', primary_active='#14845a', primary_disabled='#39434e')
SLATE = dict(GRAPHITE, base='#171b26', side='#11141d', card='#1e2333', muted='#8492ab',
             button='#25304a', button_active='#2e3a58', field='#1a2031', border='#33405f',
             theme_field='#1a2031', theme_border='#33405f', segment='#25304a',
             segment_active='#2a3550', segment_selected='#294a86', segment_text='#b9d6ff',
             notebook='#171b26', tree='#1a2031', tree_heading='#25304a', tree_selected='#294a86',
             stripe='#20263a', rim='#0b0e16', primary='#3b82f6', primary_active='#2f6fd8',
             primary_disabled='#33405f')
THEMES = {'Light': LIGHT, 'Mint': MINT, 'Sand': SAND, 'Dark': GRAPHITE, 'Graphite': GRAPHITE, 'Slate': SLATE}


class Shell:
    def __init__(self, root, app):
        self.app = app
        self.primary = {}
        self.buttons = {}
        self.pages = {}
        style = ttk.Style(root)
        style.theme_use('clam')
        style.layout('Segment.TRadiobutton', [('Toolbutton.border', {'sticky':'nswe','children':[('Toolbutton.padding',{'sticky':'nswe','children':[('Toolbutton.label',{'sticky':'nswe'})]})]})])
        style.layout('Quiet.TNotebook.Tab', [])
        # Theme-specific colours and metrics are applied by apply_theme below.
        style.configure('Copy.TButton', padding=(2, 1), font=('Segoe UI Symbol', 10), width=2)
        style.configure('TCombobox', arrowsize=14)
        style.configure('Theme.TCombobox', arrowsize=13)
        style.configure('Segment.TRadiobutton', padding=(10,7))
        style.configure('TRadiobutton', padding=(5,4), indicatorsize=12)
        style.configure('TCheckbutton', padding=(4,5), indicatorsize=14)
        root.configure(background=LIGHT['rim'])
        surface = ttk.Frame(root); surface.pack(fill='both', expand=True, padx=2, pady=2)
        app.window.round_surface(surface)
        header = ttk.Frame(surface, padding=(20, 5))
        header.pack(fill='x')
        try:
            with Image.open(logo_path()) as source:
                image = source.convert('RGBA'); image.thumbnail((52, 52), Image.Resampling.LANCZOS)
            self.logo = ImageTk.PhotoImage(image, master=root)
            ttk.Label(header, image=self.logo).pack(side='left', padx=(0, 12))
            root.iconphoto(True, self.logo)
        except OSError:
            self.logo = None
        brand = ttk.Frame(header); brand.pack(side='left')
        ttk.Label(brand, text='NetCroc', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(brand, text='Your quiet network companion.', style='Muted.TLabel',font=('Segoe UI',9)).pack(anchor='w')
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
        side_host=ttk.Frame(body,width=178);side_host.pack(side='left',fill='y',padx=(0,12));side_host.pack_propagate(False)
        self.side_canvas=tk.Canvas(side_host,highlightthickness=0,width=178)
        self.side_canvas.pack(fill='both',expand=True)
        self.sidebar=ttk.Frame(self.side_canvas,style='Sidebar.TFrame')
        side_item=self.side_canvas.create_window(0,0,window=self.sidebar,anchor='nw',width=178)
        self.sidebar.bind('<Configure>',lambda _e:self.side_canvas.configure(scrollregion=self.side_canvas.bbox('all')))
        self.side_canvas.bind('<Configure>',lambda e:self.side_canvas.itemconfigure(side_item,width=e.width,height=max(e.height,self.sidebar.winfo_reqheight())))
        def scroll_side(event):
            x,y=self.side_canvas.winfo_pointerxy()
            if self.side_canvas.winfo_rootx()<=x<=self.side_canvas.winfo_rootx()+self.side_canvas.winfo_width():
                self.side_canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
        root=self.app.root
        root.bind_all('<MouseWheel>',scroll_side,add='+')
        content = ttk.Frame(body); content.pack(side='left', fill='both', expand=True)
        self.book = ttk.Notebook(content, style='Quiet.TNotebook')
        self.book.pack(fill='both', expand=True)
        self.book.bind('<<NotebookTabChanged>>', self.changed)

    def finish(self, dashboard, keepalive):
        self.dashboard = dashboard
        self.pages = {self.book.tab(tab, 'text'): self.book.nametowidget(tab) for tab in self.book.tabs()}
        home = ttk.Frame(self.book, padding=(20, 12)); self.book.add(home, text='Home')
        tray=ttk.Frame(self.book);self.book.add(tray,text='Tray mode')
        tray_canvas=tk.Canvas(tray,highlightthickness=0)
        tray_scroll=ttk.Scrollbar(tray,orient='vertical',command=tray_canvas.yview)
        tray_canvas.configure(yscrollcommand=tray_scroll.set)
        tray_scroll.pack(side='right',fill='y');tray_canvas.pack(fill='both',expand=True)
        tray_body=ttk.Frame(tray_canvas,padding=16)
        tray_item=tray_canvas.create_window(0,0,window=tray_body,anchor='nw')
        tray_body.bind('<Configure>',lambda _e:tray_canvas.configure(scrollregion=tray_canvas.bbox('all')))
        tray_canvas.bind('<Configure>',lambda e:tray_canvas.itemconfigure(tray_item,width=e.width))
        self.tray_canvas=tray_canvas
        self.app.overlay.build_page(tray_body)
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
            button.pack(fill='x', pady=1); self.buttons[name] = button
        ttk.Separator(self.sidebar).pack(fill='x', padx=12, pady=(16, 10))
        ttk.Label(self.sidebar, text='⚙  TOOLS', style='Sidebar.TLabel', font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=14, pady=(0, 6))
        for name in self.tools:
            button = ttk.Button(self.sidebar, text=name, style='ToolNav.TButton', command=lambda n=name: self.show(n))
            button.pack(fill='x', pady=2); self.buttons[name] = button
        ttk.Separator(self.sidebar).pack(fill='x', padx=12, pady=(10, 6))
        setup=ttk.Button(self.sidebar, text='Check setup', style='SidebarAction.TButton', command=self.open_setup)
        setup.pack(fill='x', pady=3)
        from .updates import VERSION,REPO
        import webbrowser
        foot=ttk.Frame(self.sidebar,style='Sidebar.TFrame');foot.pack(side='bottom',fill='x',padx=10,pady=(0,4))
        ttk.Label(foot,text='Appearance',style='Sidebar.TLabel',font=('Segoe UI',8)).pack(anchor='w')
        self.theme_var=tk.StringVar(value=self.app.desktop.data['theme'])
        themes=ttk.Combobox(foot,textvariable=self.theme_var,values=tuple(THEMES),state='readonly',width=13,style='Theme.TCombobox')
        themes.pack(fill='x');themes.bind('<<ComboboxSelected>>',lambda _event:self.apply_theme())
        # The startup release check (about.py) only surfaces this action when a newer
        # release exists; every other outcome stays hidden instead of showing status text.
        self.update_button=ttk.Button(foot,text='Update available ↗',style='Update.TButton',width=14,command=lambda:webbrowser.open(getattr(self.about,'update_url',REPO+'/releases')))
        def update_badge(*_):
            if self.about.summary.get().startswith('Update available:'):self.update_button.pack(fill='x',pady=2)
            else:self.update_button.pack_forget()
        self.about.summary.trace_add('write',update_badge)
        ttk.Button(foot,text='★ Star on GitHub',style='SidebarAction.TButton',command=lambda:webbrowser.open(REPO)).pack(fill='x',pady=3)
        ttk.Label(foot,textvariable=self.about.latest,style='Sidebar.TLabel',font=('Segoe UI',8)).pack(anchor='w')
        self.apply_theme()
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
        country=ttk.Frame(home);country.pack(side='bottom',fill='x',pady=(12,0))
        ttk.Button(country,text='Check exit country',command=self.app.overlay.check_country).pack(side='left')
        ttk.Label(country,textvariable=self.app.overlay.status,style='Muted.TLabel').pack(side='left',padx=12)
        self.app.status.trace_add('write', lambda *_: self.update_toggle())
        self.show('Home')

    def apply_theme(self):
        theme=self.theme_var.get();palette=THEMES[theme];self.palette=palette
        style=ttk.Style(self.app.root)
        self.side_canvas.configure(bg=palette['side'])
        self.tray_canvas.configure(bg=palette['base'])
        style.configure('.', background=palette['base'], foreground=palette['foreground'], font=('Segoe UI', 10))
        style.configure('TFrame', background=palette['base'])
        style.configure('TLabel', background=palette['base'])
        style.configure('TButton', padding=(12, 6), background=palette['button'], borderwidth=0, relief='flat', focusthickness=0)
        style.map('TButton', background=[('active', palette['button_active'])])
        style.configure('TCombobox', padding=6, fieldbackground=palette['field'], bordercolor=palette['border'])
        style.configure('Theme.TCombobox', padding=(8,5), fieldbackground=palette['theme_field'],
                        background=palette['theme_field'], bordercolor=palette['theme_border'])
        style.map('Theme.TCombobox', fieldbackground=[('readonly',palette['theme_field']),('focus',palette['theme_field'])],
                  foreground=[('readonly',palette['foreground'])])
        style.configure('Segment.TRadiobutton', background=palette['segment'], borderwidth=0)
        style.map('Segment.TRadiobutton', background=[('selected',palette['segment_selected']),('active',palette['segment_active'])],
                  foreground=[('selected',palette['segment_text'])])
        style.configure('TRadiobutton', background=palette['base'])
        style.configure('TCheckbutton', background=palette['base'])
        style.configure('TNotebook', background=palette['notebook'], borderwidth=0)
        style.configure('TNotebook.Tab', background=palette['segment'], padding=(12,6))
        style.map('TNotebook.Tab', background=[('selected',palette['segment_selected'])])
        style.layout('Quiet.TNotebook', [('Notebook.client', {'sticky':'nswe'})])
        style.configure('Quiet.TNotebook', tabmargins=0, borderwidth=0)
        style.configure('TSeparator', background=palette['border'])
        style.configure('Primary.TButton', background=palette['primary'], foreground='#ffffff')
        style.map('Primary.TButton', background=[('active', palette['primary_active']), ('disabled', palette['primary_disabled'])])
        style.configure('SidebarAction.TButton',padding=(6,7),font=('Segoe UI',9),background=palette['button'],borderwidth=1,relief='solid',bordercolor=palette['border'])
        style.configure('Nav.TButton', padding=(14, 9), anchor='w', background=palette['side'], font=('Segoe UI',10))
        style.map('Nav.TButton', background=[('selected',palette['segment_selected']),('active',palette['segment_active'])])
        style.configure('ToolNav.TButton', padding=(14, 6), anchor='w', background=palette['side'], font=('Segoe UI', 9))
        style.map('ToolNav.TButton', background=[('selected',palette['segment_selected']),('active',palette['segment_active'])])
        style.configure('Sidebar.TFrame', background=palette['side'])
        style.configure('Sidebar.TLabel', background=palette['side'], foreground=palette['muted'])
        style.configure('Card.TFrame', background=palette['card'])
        style.configure('Card.TLabel', background=palette['card'])
        style.configure('Muted.TLabel', foreground=palette['muted'])
        style.configure('Treeview', background=palette['tree'], fieldbackground=palette['tree'],
                        foreground=palette['foreground'], rowheight=34, borderwidth=0, relief='flat',
                        lightcolor=palette['tree'], darkcolor=palette['tree'])
        style.configure('Treeview.Heading', padding=(10,8), background=palette['tree_heading'],
                        foreground=palette['foreground'], relief='flat', font=('Segoe UI',9,'bold'))
        style.map('Treeview', background=[('selected',palette['tree_selected'])], foreground=[('selected',palette['tree_selected_text'])])
        style.map('.', fieldbackground=[('readonly',palette['field'])])
        rim=palette.get('rim')
        if rim: self.app.root.configure(background=rim)
        from . import dashboard as dashboard_module
        dashboard_module.STRIPE=palette['stripe']
        if not self.app.diagnostic: self.app.desktop.update({'theme':theme})
        from .rounded import install
        install(style,self.app.root,palette,self)
        for combo_style in ('TCombobox','Theme.TCombobox'):
            style.configure(combo_style,background=palette['button'],foreground=palette['foreground'],arrowcolor=palette['foreground'])
            style.map(combo_style,fieldbackground=[('readonly',palette['field']),('disabled',palette['base'])],foreground=[('disabled',palette['muted']),('readonly',palette['foreground'])],selectbackground=[('readonly',palette['field'])],selectforeground=[('readonly',palette['foreground'])])
        style.configure('Treeview',stripecolor=palette['stripe'])
        style.configure('TEntry',fieldbackground=palette['field'],foreground=palette['foreground'],insertcolor=palette['foreground'])
        style.configure('Vertical.TScrollbar',background=palette['button'],troughcolor=palette['side'],arrowcolor=palette['foreground'])
        style.configure('Horizontal.TScrollbar',background=palette['button'],troughcolor=palette['side'],arrowcolor=palette['foreground'])
        for option,value in (('background',palette['field']),('foreground',palette['foreground']),('selectBackground',palette['segment_selected']),('selectForeground',palette['foreground'])):
            self.app.root.option_add('*TCombobox*Listbox.'+option,value)
        def repaint(widget):
            if isinstance(widget,ttk.Treeview):widget.tag_configure('alternate',background=palette['stripe'],foreground=palette['foreground'])
            elif isinstance(widget,tk.Text):widget.configure(background=palette['field'],foreground=palette['foreground'],insertbackground=palette['foreground'],selectbackground=palette['segment_selected'])
            elif isinstance(widget,tk.Canvas) and widget not in (self.app.dashboard.graph,self.app.dashboard.bars):widget.configure(background=palette['base'])
            for child in widget.winfo_children():repaint(child)
        repaint(self.book)
        if hasattr(self.app,'dashboard'):self.app.dashboard.apply_theme()

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
        if name=='VPN' and not self.app.diagnostic:self.dashboard.refresh_vpn()

    def open(self, name):
        self.book.select(self.pages[name])
        self.changed()

    def changed(self, _event=None):
        if not self.primary: return
        selected=self.book.select()
        for name, button in self.buttons.items():
            button.state(['selected'] if str(self.destinations[name])==selected else ['!selected'])
