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
        ttk.Label(tools, text='Tools', font=('Segoe UI', 21, 'bold')).pack(anchor='w', pady=12)
        for title, page in self.pages.items():
            if page not in self.primary.values():
                ttk.Button(tools, text=title, command=lambda n=title: self.open(n)).pack(anchor='w', pady=4)
        self.show('Home')

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
        for name, button in self.buttons.items():
            button.state(['selected'] if str(self.primary[name])==selected else ['!selected'])
