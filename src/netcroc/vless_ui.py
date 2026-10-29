"""VLESS account/profile controls with explicit connection and IP verification."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys
import threading
from . import vless
from .ssh_ui import SSHTab
from .tool_ui import actions, help_for, StatusLine

# Windows whole-PC TUN is live-validated (admin + working server + clean teardown);
# Linux passed an isolated namespace lab. macOS whole-PC is still unvalidated.
_TUN_TAG = ' (experimental)' if sys.platform == 'darwin' else ''
MODE_LABELS = {'socks': 'Local SOCKS5', 'tun': 'Whole-PC' + _TUN_TAG}


class VlessTab(SSHTab):
    ADD_LABEL = 'Paste link'
    PROFILE_NOUN = 'VLESS profile'

    def safe(self, action):
        try: action()
        except Exception as error:
            from . import ssh_tunnel
            messagebox.showerror('VLESS', ssh_tunnel.friendly_error(error), parent=self.root)

    def __init__(self, app, notebook, folder, diagnostic=False):
        # Reuse worker/error handling and the guarded optional-core downloader.
        self.root = app.root; self.closed = False; self.busy = False; self.stopping = None
        import queue
        self.events = queue.Queue(); self.app = app
        self.store = vless.ProfileStore(folder / 'vless' / 'profiles')
        self.core_folder = folder / 'ssh' / 'routing-core'
        self.routing = vless.Session(self.core_folder); self.session = None
        tab = ttk.Frame(notebook, padding=16); notebook.add(tab, text='VLESS')
        ttk.Label(tab, text='VLESS connections', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(tab, text='1. Paste your link   2. Select the saved profile   3. Connect', wraplength=950).pack(anchor='w', pady=6)
        self.tree = ttk.Treeview(tab, columns=('server', 'security', 'mode'), show='tree headings', height=8)
        self.tree.heading('#0', text='Profile')
        for name in ('server', 'security', 'mode'): self.tree.heading(name, text=name.title())
        self.tree.pack(fill='both', expand=True, pady=8)
        self.tree.bind('<<TreeviewSelect>>', lambda _event: self._update_buttons())
        self.empty_hint = ttk.Label(tab, text='', style='Muted.TLabel', wraplength=900)
        self.bar = actions(tab, [(self.ADD_LABEL, lambda: self.safe(self.paste_links)), ('Connect', lambda: self.safe(self.connect)), ('Disconnect', lambda: self.safe(self.disconnect))], [
            ('New profile manually', lambda: self.safe(self.edit)), ('Edit selected', lambda: self.safe(lambda: self.edit(self.selected()))), ('Import file', lambda: self.safe(self.import_file)), ('Remove selected', lambda: self.safe(self.remove)),
            ('Install / repair core', lambda: self.safe(lambda: self.run(self.routing.install, lambda _: self.line.ok('Core ready.'), 'Downloading and verifying the routing core…'))), ('Check profile', lambda: self.safe(self.check_profile)), ('Verify public IP', lambda: self.safe(self.check_ip)),
            ('How to use VLESS', help_for(self.root, 'VLESS', 'Paste a provider link and select the saved profile. Importing never connects. Local SOCKS5 only affects configured apps; whole-PC mode can interrupt connectivity. Verify public IP after connecting. A ready listener does not prove server authentication or ISP package behaviour.'))])
        self.line = StatusLine(tab, 'Disconnected. Credentials are encrypted for this OS account.')
        self.status = self.line.var
        self.ip = tk.StringVar(value='No provider IP check performed.')
        ttk.Label(tab, textvariable=self.ip, wraplength=950).pack(anchor='w')
        self.rates = tk.StringVar(value='')
        self.rates_label = ttk.Label(tab, textvariable=self.rates)
        ttk.Label(tab, text='Importing never connects. Verify the public IP after connecting.', style='Muted.TLabel').pack(anchor='w', pady=6)
        self._apply_empty(0)
        if not diagnostic: self.refresh()
        self._update_buttons()
        self.timer = self.root.after(500, self.poll)

    def paste_links(self):
        old = getattr(self, 'paste_dialog', None)
        if old and old.winfo_exists(): old.lift(); return
        from tkinter.scrolledtext import ScrolledText
        dialog = self.paste_dialog = tk.Toplevel(self.root); dialog.title('Paste VLESS links'); dialog.geometry('660x340')
        body = ttk.Frame(dialog, padding=18); body.pack(fill='both', expand=True)
        ttk.Label(body, text='Paste VLESS links', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(body, text='One link per line, or comma-separated links. Importing saves profiles; it does not connect.', wraplength=610).pack(anchor='w', pady=8)
        text = ScrolledText(body, height=7, wrap='word', font=('Segoe UI', 10)); text.pack(fill='both', expand=True)
        self.paste_input = text
        error = tk.StringVar(); ttk.Label(body, textvariable=error, wraplength=610).pack(anchor='w', pady=6)
        def save():
            try:
                values = vless.parse_links(text.get('1.0', 'end-1c'))
                for value in values: self.store.save(value)
                text.delete('1.0', 'end'); self.refresh()
                self.line.ok(f'Imported {len(values)} VLESS profile(s). Choose one and Connect. Credentials are encrypted.')
                dialog.destroy()
            except (ValueError, OSError): error.set('Could not import. Paste supported vless:// links only and check that the profile folder is writable.')
        self.paste_save = save
        buttons = ttk.Frame(body); buttons.pack(fill='x')
        ttk.Button(buttons, text='Import links', style='Primary.TButton', command=save).pack(side='left')
        ttk.Button(buttons, text='Cancel', command=dialog.destroy).pack(side='right')
        text.focus_set()

    def refresh(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        items = list(self.store.profiles())
        for identifier, p in items:
            self.tree.insert('', 'end', iid=identifier, text=p['label'], values=(
                f"{p['host']}:{p['port']}", p['security'] + ' / ' + p['transport'], MODE_LABELS.get(p['routing'], p['routing'])))
        if selected and self.tree.exists(selected[0]): self.tree.selection_set(selected[0])
        self._apply_empty(len(items))
        self._update_buttons()

    def _apply_empty(self, count):
        self.tree.configure(height=8 if count else 3)
        self.tree.pack_configure(expand=bool(count))
        if count:
            self.empty_hint.pack_forget()
        else:
            self.empty_hint.configure(text='No saved profiles yet. Use "Paste link" to import a provider link, then select it and Connect.')
            self.empty_hint.pack(anchor='w', pady=(0, 8), before=self.bar.bar)

    def edit(self, identifier=None):
        value = self.store.load(identifier) if identifier else dict(vless.DEFAULTS)
        window = tk.Toplevel(self.root); window.title('VLESS profile'); window.geometry('740x680')
        book = ttk.Notebook(window); book.pack(fill='both', expand=True, padx=12, pady=10)
        variables = {}
        groups = [('Account', [('label', 'Name'), ('host', 'Server'), ('port', 'Port'), ('uuid', 'User UUID'), ('security', 'Security'), ('sni', 'TLS SNI'), ('routing', 'Routing'), ('local_port', 'Local SOCKS5 port')]),
            ('Transport', [('transport', 'Transport'), ('path', 'WebSocket / HTTPUpgrade path'), ('http_host', 'HTTP Host'), ('service_name', 'gRPC service'), ('flow', 'Flow'), ('alpn', 'ALPN (comma separated)'), ('fingerprint', 'TLS fingerprint')]),
            ('REALITY', [('reality_key', 'Server public key'), ('short_id', 'Short ID')])]
        choices = {'security': ['tls', 'reality', 'none'], 'transport': ['tcp', 'ws', 'grpc', 'httpupgrade'], 'routing': ['socks', 'tun'], 'flow': ['', 'xtls-rprx-vision'], 'fingerprint': ['', 'chrome', 'firefox', 'edge', 'safari', 'random', 'randomized']}
        for title, fields in groups:
            page = ttk.Frame(book, padding=14); book.add(page, text=title); page.columnconfigure(1, weight=1)
            for row, (field, label) in enumerate(fields):
                ttk.Label(page, text=label).grid(row=row, column=0, sticky='w', pady=8)
                variables[field] = tk.StringVar(value=str(value[field]))
                widget = ttk.Combobox(page, textvariable=variables[field], values=choices[field], state='readonly') if field in choices else ttk.Entry(page, textvariable=variables[field], show='•' if field == 'uuid' else '')
                widget.grid(row=row, column=1, sticky='ew', padx=8)
            if title == 'Account':
                ttk.Label(page, text='For an imported vless:// link, use Import file on the main tab.\nSecurity none is restricted to local loopback tests.', wraplength=650).grid(row=9, column=0, columnspan=2, sticky='w', pady=14)
        ca = [value['ca_pem']]
        def import_ca():
            file = filedialog.askopenfilename(filetypes=[('Trusted CA', '*.pem')])
            if file:
                raw = Path(file).read_bytes()
                if len(raw) > 32768: raise ValueError('CA certificate file is too large.')
                ca[0] = raw.decode('ascii')
        def save():
            profile = value | {key: var.get() for key, var in variables.items()}; profile['ca_pem'] = ca[0]
            self.store.save(profile, identifier); self.refresh(); window.destroy()
        buttons = ttk.Frame(window); buttons.pack(fill='x', padx=12, pady=10)
        ttk.Button(buttons, text='Import trusted CA', command=lambda: self.safe(import_ca)).pack(side='left')
        ttk.Button(buttons, text='Save', command=lambda: self.safe(save)).pack(side='right')

    def check_profile(self):
        value = self.store.load(self.selected())
        # Schema check only: documentation IPs stand in for upstream exclusions.
        self.run(lambda: self.routing.check_config(vless.config(value, ['192.0.2.1'])), lambda _: self.line.ok('Profile configuration accepted; provider connection not tested.'), 'Checking the profile configuration…')

    def connect(self):
        if self.stopping: raise ValueError('Disconnecting; please wait a moment.')
        if self.busy or self.session and not self.session.cancel.is_set(): raise ValueError('Disconnect the current VLESS session first.')
        ssh = self.app.dashboard.ssh_tab.session
        if ssh and not ssh.cancel.is_set(): raise ValueError('Disconnect SSH before connecting VLESS.')
        identifier = self.selected(); value = self.store.load(identifier)
        if value['routing'] == 'tun' and not messagebox.askyesno('Whole-PC VLESS' + _TUN_TAG, 'This mode changes PC-wide routes and may interrupt remote access.' + (' It is experimental on this platform.' if _TUN_TAG else '') + ' Connect now?', default='no'): return
        self.session = vless.Session(self.core_folder); session = self.session
        self.ip.set('Checking the tunnel after it starts…')
        def start_and_check():
            session.start_profile(value, identifier)
            if value['routing'] != 'socks': return ('unverified', None)
            try: return ('verified', vless.proxy_ip(value['local_port']))
            except Exception:
                session.stop()
                return ('failed', None)
        def show_result(result):
            state, ip = result
            if self.session is not session or (session.cancel.is_set() and state != 'failed'): return
            if state == 'verified':
                self.line.ok('Connected · tunnel verified · local SOCKS5 proxy')
                self.ip.set('Public IP check succeeded. Configure your app to use this proxy.')
            elif state == 'failed':
                self.line.error('Connection failed · tunnel stopped. You can select a profile and try again.')
                self.ip.set('Check the server, TLS settings and internet connection.')
            else:
                self.line.ok('Tunnel started · whole-PC connection not yet verified')
                self.ip.set('Use More → Verify public IP to check the connection.')
            self._update_buttons()
        self.run(start_and_check, show_result, 'Connecting to ' + value['host'] + ' and checking the tunnel…')

    def check_ip(self):
        if not self.session or not self.session.active: raise ValueError('Start a VLESS profile first.')
        value = self.store.load(self.session.profile_id)
        if value['routing'] == 'tun':
            # Whole-PC mode has no local listener: existing VPN IP checker follows its routes.
            self.app.dashboard.check_vpn_ip(); return
        self.run(lambda: vless.proxy_ip(value['local_port']), lambda ip: self.ip.set('Verified proxy public IP: ' + ip + ' · IP check succeeded; not a DNS/IPv6 leak test.'), 'Checking the public IP through the tunnel…')

    def remove(self):
        identifier = self.selected()
        if self.session and self.session.profile_id == identifier and not self.session.cancel.is_set(): raise ValueError('Disconnect this profile first.')
        if messagebox.askyesno('Remove VLESS profile', 'Remove this saved profile?', default='no'):
            self.store.remove(identifier); self.refresh()

    def poll(self):
        if self.closed: return
        while not self.events.empty():
            callback, value, error = self.events.get()
            self.busy = False
            self.line.stop_busy()
            if error:
                self.line.error(error); messagebox.showerror('VLESS', error, parent=self.root)
            else:
                self.safe(lambda: callback(value))
            self._update_buttons()
        # healthy() is a cheap poll/file read; the blocking teardown stays off this thread.
        if self.session and self.session.active and not self.session.healthy():
            self.disconnect(notice='The VLESS process stopped unexpectedly.')
        self.timer = self.root.after(500, self.poll)