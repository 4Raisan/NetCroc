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
        pass

    def changed(self, _event=None):
        pass
