"""VLESS account/profile controls with explicit connection and IP verification."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
from . import vless
from .ssh_ui import SSHTab

class VlessTab(SSHTab):
    def __init__(self,app,notebook,folder,diagnostic=False):
        # Reuse worker/error handling and the guarded optional-core downloader.
        self.root=app.root;self.closed=False;self.busy=False
        import queue
        self.events=queue.Queue();self.app=app
        self.store=vless.ProfileStore(folder/'vless'/'profiles')
        self.core_folder=folder/'ssh'/'routing-core'
        self.routing=vless.Session(self.core_folder);self.session=None
        tab=ttk.Frame(notebook,padding=16);notebook.add(tab,text='VLESS')
        ttk.Label(tab,text='VLESS connections',font=('Segoe UI',19,'bold')).pack(anchor='w')
        ttk.Label(tab,text='Works with compatible 3x-ui / Xray servers using the sing-box engine. Bring your own account.\nSupports TCP, WebSocket, gRPC, HTTPUpgrade; TLS and REALITY. Importing never connects.',wraplength=950).pack(anchor='w',pady=6)
        self.tree=ttk.Treeview(tab,columns=('server','security','mode'),show='tree headings',height=8)
        self.tree.heading('#0',text='Profile')
        for name in ('server','security','mode'): self.tree.heading(name,text=name.title())
        self.tree.pack(fill='both',expand=True,pady=8)
        row=ttk.Frame(tab);row.pack(fill='x')
        for text,action in [('New',self.edit),('Edit',lambda:self.edit(self.selected())),('Import file',self.import_file),('Remove',self.remove),('Connect',self.connect),('Disconnect',self.disconnect)]:
            ttk.Button(row,text=text,command=lambda f=action:self.safe(f)).pack(side='left',padx=3)
        row=ttk.Frame(tab);row.pack(fill='x',pady=8)
        for text,action in [('Download core',lambda:self.run(self.routing.install,lambda _:self.status.set('Verified core downloaded.'))),('Check profile',self.check_profile),('Check public IP through proxy',self.check_ip)]:
            ttk.Button(row,text=text,command=lambda f=action:self.safe(f)).pack(side='left',padx=3)
        self.status=tk.StringVar(value='Disconnected. Credentials are encrypted for this Windows account.')
        self.ip=tk.StringVar(value='No provider IP check performed.')
        ttk.Label(tab,textvariable=self.status,wraplength=950).pack(anchor='w',pady=6)
        ttk.Label(tab,textvariable=self.ip,wraplength=950).pack(anchor='w')
        ttk.Label(tab,text='Local SOCKS5 affects only configured apps. Whole-PC mode requires administrator access and may interrupt internet.\nA ready proxy/adapter does not prove server authentication. Use Check public IP to verify an external connection.\nNo ISP billing bypass or free VPS is provided. Closing NetCroc stops this connection.',wraplength=950).pack(anchor='w',pady=10)
        if not diagnostic:self.refresh()
        self.timer=self.root.after(500,self.poll)

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

    def check_profile(self):
        value=self.store.load(self.selected())
        # Schema check only: documentation IPs stand in for upstream exclusions.
        self.run(lambda:self.routing.check_config(vless.config(value,['192.0.2.1'])),lambda _:self.status.set('Profile configuration accepted; provider connection not tested.'))

    def connect(self):
        if self.busy or self.session and not self.session.cancel.is_set():raise ValueError('Disconnect the current VLESS session first.')
        ssh=self.app.dashboard.ssh_tab.session
        if ssh and not ssh.cancel.is_set():raise ValueError('Disconnect SSH before connecting VLESS.')
        identifier=self.selected();value=self.store.load(identifier)
        if value['routing']=='tun' and not messagebox.askyesno('Whole-PC VLESS','This changes PC-wide routes and may interrupt remote access. Connect now?',default='no'):return
        self.session=vless.Session(self.core_folder);session=self.session
        self.status.set('Starting…')
        self.run(lambda:session.start_profile(value,identifier),lambda status:self.status.set(status))

    def check_ip(self):
        if not self.session or not self.session.active:raise ValueError('Start a VLESS profile first.')
        value=self.store.load(self.session.profile_id)
        if value['routing']=='tun':
            # Whole-PC mode has no local listener: existing VPN IP checker follows its routes.
            self.app.dashboard.check_vpn_ip();return
        self.run(lambda:vless.proxy_ip(value['local_port']),lambda ip:self.ip.set('Verified proxy public IP: '+ip+' · IP check succeeded; not a DNS/IPv6 leak test.'))

    def disconnect(self):
        if self.session:
            self.session.cancel.set();threading.Thread(target=self.session.stop,daemon=True).start()
            self.status.set('Disconnecting…')

    def remove(self):
        identifier=self.selected()
        if self.session and self.session.profile_id==identifier and not self.session.cancel.is_set():raise ValueError('Disconnect this profile first.')
        if messagebox.askyesno('Remove VLESS profile','Remove this saved profile?',default='no'):
            self.store.remove(identifier);self.refresh()

    def poll(self):
        if self.closed:return
        while not self.events.empty():
            callback,value,error=self.events.get();self.busy=False
            if error:self.status.set(error);messagebox.showerror('VLESS',error,parent=self.root)
            else:self.safe(lambda:callback(value))
        if self.session and self.session.active and not self.session.healthy():
            self.session.stop();self.status.set('VLESS process stopped; connection closed.')
        self.timer=self.root.after(500,self.poll)
