"""VLESS account/profile controls with explicit connection and IP verification."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
from . import vless
from .ssh_ui import SSHTab

class VlessTab(SSHTab):
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for identifier,p in self.store.profiles():
            self.tree.insert('','end',iid=identifier,text=p['label'],values=(f"{p['host']}:{p['port']}",p['security']+' / '+p['transport'],p['routing']))


    def edit(self,identifier=None):
        value=self.store.load(identifier) if identifier else dict(vless.DEFAULTS)
        window=tk.Toplevel(self.root);window.title('VLESS profile');window.geometry('740x680')
        book=ttk.Notebook(window);book.pack(fill='both',expand=True,padx=12,pady=10)
        variables={}
        groups=[('Account',[('label','Name'),('host','Server'),('port','Port'),('uuid','User UUID'),('security','Security'),('sni','TLS SNI'),('routing','Routing'),('local_port','Local SOCKS5 port')]),
            ('Transport',[('transport','Transport'),('path','WebSocket / HTTPUpgrade path'),('http_host','HTTP Host'),('service_name','gRPC service'),('flow','Flow'),('alpn','ALPN (comma separated)'),('fingerprint','TLS fingerprint')]),
            ('REALITY',[('reality_key','Server public key'),('short_id','Short ID')])]
        choices={'security':['tls','reality','none'],'transport':['tcp','ws','grpc','httpupgrade'],'routing':['socks','tun'],'flow':['','xtls-rprx-vision'],'fingerprint':['','chrome','firefox','edge','safari','random','randomized']}
        for title,fields in groups:
            page=ttk.Frame(book,padding=14);book.add(page,text=title);page.columnconfigure(1,weight=1)
            for row,(field,label) in enumerate(fields):
                ttk.Label(page,text=label).grid(row=row,column=0,sticky='w',pady=8)
                variables[field]=tk.StringVar(value=str(value[field]))
                widget=ttk.Combobox(page,textvariable=variables[field],values=choices[field],state='readonly') if field in choices else ttk.Entry(page,textvariable=variables[field],show='•' if field=='uuid' else '')
                widget.grid(row=row,column=1,sticky='ew',padx=8)
            if title=='Account':
                ttk.Label(page,text='For an imported vless:// link, use Import file on the main tab.\nSecurity none is restricted to local loopback tests.',wraplength=650).grid(row=9,column=0,columnspan=2,sticky='w',pady=14)
        ca=[value['ca_pem']]
        def import_ca():
            file=filedialog.askopenfilename(filetypes=[('Trusted CA','*.pem')])
            if file:
                raw=Path(file).read_bytes()
                if len(raw)>32768:raise ValueError('CA certificate file is too large.')
                ca[0]=raw.decode('ascii')
        def save():
            profile=value|{key:var.get() for key,var in variables.items()};profile['ca_pem']=ca[0]
            self.store.save(profile,identifier);self.refresh();window.destroy()
        buttons=ttk.Frame(window);buttons.pack(fill='x',padx=12,pady=10)
        ttk.Button(buttons,text='Import trusted CA',command=lambda:self.safe(import_ca)).pack(side='left')
        ttk.Button(buttons,text='Save',command=lambda:self.safe(save)).pack(side='right')
