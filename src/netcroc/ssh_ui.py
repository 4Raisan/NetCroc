"""Explicit, user-managed SSH/TLS connections; workers never touch Tk."""
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
from . import ssh_tunnel as ssh
from .ssh_routing import Routing
from .history import speed


class SSHTab:
    def __init__(self, app, notebook, folder, diagnostic=False):
        self.root = app.root
        self.app = app
        self.closed = False
        self.busy = False
        self.events = queue.Queue()
        self.store = ssh.ProfileStore(folder / 'ssh' / 'profiles')
        self.routing = Routing(folder / 'ssh' / 'routing-core')
        self.session = None
        self.previous = (0, 0)
        self.previous_time = time.monotonic()
        tab = ttk.Frame(notebook, padding=16)
        notebook.add(tab, text='SSH / TLS')
        ttk.Label(tab, text='SSH / TLS tunnel', font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        ttk.Label(tab, text='Use your own provider account. SNI and payload settings must match your server.\nLocal SOCKS5 affects only apps configured to use it. Whole-PC TCP requires administrator access.', wraplength=950).pack(anchor='w', pady=6)
        self.tree = ttk.Treeview(tab, columns=('server', 'mode', 'expiry'), show='tree headings', height=7)
        self.tree.heading('#0', text='Profile')
        for name in ('server', 'mode', 'expiry'):
            self.tree.heading(name, text=name.title()); self.tree.column(name, width=170)
        self.tree.pack(fill='both', expand=True, pady=6)
        line = ttk.Frame(tab); line.pack(fill='x')
        for label, action in [('New', self.edit), ('Edit', lambda: self.edit(self.selected())),
                              ('Import JSON', self.import_file), ('Remove', self.remove),
                              ('Connect', self.connect), ('Disconnect', self.disconnect)]:
            ttk.Button(line, text=label, command=lambda f=action: self.safe(f)).pack(side='left', padx=3)
        line = ttk.Frame(tab); line.pack(fill='x', pady=8)
        for label, action in [('SSH account providers ↗', lambda: webbrowser.open(ssh.SERVERS_URL)),
            ('Setup guide ↗', lambda: webbrowser.open(ssh.GUIDE_URL)),
            ('Download routing core', lambda: self.run(self.routing.install, lambda _: self.status.set('Verified routing core downloaded. No routes changed.'))),
            ('Check routing config', lambda: self.run(self.routing.check, lambda _: self.status.set('Routing configuration accepted. No routes changed.')))]:
            ttk.Button(line, text=label, command=lambda f=action: self.safe(f)).pack(side='left', padx=3)
        self.status = tk.StringVar(value='Disconnected. No system proxy or DNS settings changed.')
        self.rates = tk.StringVar(value='↓ 0 KB/s    ↑ 0 KB/s')
        ttk.Label(tab, textvariable=self.status, wraplength=950).pack(anchor='w', pady=6)
        ttk.Label(tab, textvariable=self.rates, font=('Segoe UI', 16)).pack(anchor='w')
        ttk.Label(tab, text='Whole-PC mode tunnels TCP and DNS over HTTPS; other UDP/ICMP is blocked. Closing NetCroc stops this tunnel.\nThis feature does not establish free ISP data, a speed increase, or a verified provider connection.', wraplength=950).pack(anchor='w', pady=8)
        if not diagnostic:
            self.refresh()
        self.timer = self.root.after(1000, self.poll)

    def safe(self, action):
        try:
            action()
        except Exception as error:
            messagebox.showerror('SSH / TLS', ssh.friendly_error(error), parent=self.root)

    def selected(self):
        value = self.tree.selection()
        if not value:
            raise ValueError('Choose an SSH profile first.')
        return value[0]

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for identifier, item in self.store.profiles():
            self.tree.insert('', 'end', iid=identifier, text=item['label'], values=(
                f"{item['host']}:{item['port']}", 'Whole-PC TCP' if item['routing'] == 'tun' else 'Local SOCKS5', item['expires'] or 'Not supplied'))

    def run(self, action, callback):
        if self.busy:
            raise ValueError('Wait for the current SSH action to finish, or disconnect.')
        self.busy = True
        def work():
            try:
                self.events.put((callback, action(), None))
            except Exception as error:
                self.events.put((callback, None, ssh.friendly_error(error)))
        threading.Thread(target=work, daemon=True).start()

    def import_file(self):
        path = filedialog.askopenfilename(filetypes=[('NetCroc SSH profile', '*.json')])
        if path:
            self.store.import_file(path); self.refresh()

    def remove(self):
        identifier = self.selected()
        if self.session and self.session.profile_id == identifier and not self.session.cancel.is_set():
            raise ValueError('Disconnect this profile before removing it.')
        if messagebox.askyesno('Remove profile', 'Remove this saved SSH profile?', default='no'):
            self.store.remove(identifier); self.refresh()

    def connect(self):
        vless_tab=getattr(self.app.dashboard,'vless_tab',None)
        if vless_tab and vless_tab.session and not vless_tab.session.cancel.is_set():
            raise ValueError('Disconnect VLESS before connecting SSH.')
        if self.busy or (self.session and not self.session.cancel.is_set()):
            raise ValueError('Disconnect the current session before connecting another profile.')
        identifier = self.selected(); value = self.store.load(identifier)
        ssh.validate(value, credentials=True)
        if value['routing'] == 'tun' and not messagebox.askyesno('Whole-PC TCP',
            'This changes PC-wide routing and may interrupt remote access. UDP apps may stop working. Connect now?', default='no'):
            return
        self.session = ssh.Session(self.routing if value['routing'] == 'tun' else None)
        session = self.session
        self.previous = (0, 0)
        self.previous_time = time.monotonic()
        self.status.set('Connecting…')
        self.run(lambda: session.start(value, identifier), lambda result: self.status.set(result['status']))

    def disconnect(self):
        if self.session:
            session = self.session
            session.cancel.set()
            # Closing sockets interrupts a pending handshake; cleanup may take a moment.
            threading.Thread(target=session.stop, daemon=True).start()
            self.status.set('Disconnecting…')

    def edit(self, identifier=None):
        value = self.store.load(identifier) if identifier else dict(ssh.DEFAULTS)
        window = tk.Toplevel(self.root); window.title('SSH / TLS profile'); window.geometry('720x640')
        book = ttk.Notebook(window); book.pack(fill='both', expand=True, padx=12, pady=10)
        variables = {}; texts = {}
        def page(title):
            frame = ttk.Frame(book, padding=12); book.add(frame, text=title); frame.columnconfigure(1, weight=1)
            return frame
        def entry(frame, row, field, title, secret=False):
            ttk.Label(frame, text=title).grid(row=row, column=0, sticky='w', pady=5)
            variables[field] = tk.StringVar(value=str(value[field]))
            ttk.Entry(frame, textvariable=variables[field], show='•' if secret else '').grid(row=row, column=1, sticky='ew', padx=8)
        account = page('Account')
        for row, (field, title) in enumerate([('label', 'Profile name'), ('host', 'Server hostname'), ('port', 'Server port'), ('username', 'Username'), ('password', 'Password'), ('expires', 'Expiry YYYY-MM-DD')]):
            entry(account, row, field, title, field == 'password')
        ttk.Label(account, text='Account creation and renewal happen on the provider website.\nPasswords are saved encrypted for this OS account.', wraplength=600).grid(row=7, column=0, columnspan=2, sticky='w', pady=15)
        tls = page('TLS and trust')
        variables['tls'] = tk.BooleanVar(value=value['tls'])
        ttk.Checkbutton(tls, text='Wrap SSH inside TLS (TLS 1.2 or newer)', variable=variables['tls']).grid(row=0, column=0, columnspan=2, sticky='w')
        for row, (field, title) in enumerate([('sni', 'TLS SNI hostname'), ('tls_pin', 'TLS certificate SHA-256'), ('host_key', 'SSH public host key')], 1):
            entry(tls, row, field, title)
        ttk.Label(tls, text='Verify fingerprints with your provider before trusting them. A probe never sends SSH login details.\nChanging server, SNI or proxy requires verifying identity again.', wraplength=600).grid(row=4, column=0, columnspan=2, sticky='w', pady=10)
        ca = [value['ca_pem']]
        def import_ca():
            from pathlib import Path
            path = filedialog.askopenfilename(filetypes=[('CA certificate', '*.pem')])
            if path:
                raw = Path(path).read_bytes()
                if len(raw) > 65536: raise ValueError('CA file is too large.')
                ca[0] = raw.decode('ascii')
        ttk.Button(tls, text='Import custom CA PEM', command=lambda: self.safe(import_ca)).grid(row=5, column=0, sticky='w')
        payload = page('Payload and proxy')
        for row, (field, title) in enumerate([('proxy_host', 'HTTP proxy host (optional)'), ('proxy_port', 'HTTP proxy port'), ('proxy_user', 'Proxy username'), ('proxy_password', 'Proxy password')]):
            entry(payload, row, field, title, field == 'proxy_password')
        for row, field, title in [(4, 'payload_before', 'HTTP payload before TLS'), (6, 'payload_after', 'HTTP payload after TLS')]:
            ttk.Label(payload, text=title + ' (empty = disabled)').grid(row=row, column=0, columnspan=2, sticky='w')
            widget = tk.Text(payload, height=3, width=60); widget.insert('1.0', value[field]); widget.grid(row=row+1, column=0, columnspan=2, sticky='ew', pady=4); texts[field] = widget
        ttk.Label(payload, text='Placeholders: {host}, {port}, {sni}, [crlf]. HTTP 2xx/101 response required.').grid(row=8, column=0, columnspan=2, sticky='w')
        route = page('Routing')
        entry(route, 0, 'local_port', 'Local SOCKS5 port (0 = automatic)')
        variables['routing'] = tk.StringVar(value=value['routing'])
        ttk.Radiobutton(route, text='Local SOCKS5 — configure your app to use 127.0.0.1 and this port', value='socks', variable=variables['routing']).grid(row=1, column=0, columnspan=2, sticky='w', pady=12)
        ttk.Radiobutton(route, text='Whole-PC TCP — optional core + administrator required', value='tun', variable=variables['routing']).grid(row=2, column=0, columnspan=2, sticky='w')
        ttk.Label(route, text='No automatic system proxy changes. SOCKS domain names resolve at the SSH server.\nWhole-PC mode sends DNS through the tunnel and blocks other UDP/ICMP.\nDisconnect before connecting another VPN.', wraplength=600).grid(row=3, column=0, columnspan=2, sticky='w', pady=15)
        def collect():
            result = value | {field: variable.get() for field, variable in variables.items()}
            result.update({field: widget.get('1.0', 'end-1c') for field, widget in texts.items()})
            result['ca_pem'] = ca[0]
            return ssh.validate(result)
        def probe(inspect=False):
            current = collect()
            def done(info):
                if not window.winfo_exists(): return
                text = 'SSH: ' + info['host_fingerprint'] + '\nTLS SHA-256: ' + (info['tls_fingerprint'] or 'TLS disabled')
                text += '\n\nCompare with your provider using a separate trusted channel. Save these identities?'
                if inspect: text += '\nCertificate trust was NOT verified. Saving pins this exact certificate.'
                if messagebox.askyesno('Verify server identity', text, parent=window, default='no'):
                    variables['host_key'].set(info['host_key'])
                    if inspect: variables['tls_pin'].set(info['tls_fingerprint'])
            self.run(lambda: ssh.probe(current, inspect=inspect), done)
        def inspect():
            if messagebox.askyesno('Inspect untrusted certificate', 'Inspect public fingerprints without verifying the TLS certificate? No SSH login will be sent. Independently verify the fingerprints before saving.', parent=window, default='no'):
                probe(True)
        def save():
            self.store.save(collect(), identifier); self.refresh(); window.destroy()
        buttons = ttk.Frame(window); buttons.pack(fill='x', padx=12, pady=10)
        for title, action in [('Probe verified server', probe), ('Inspect identity…', inspect), ('Save', save)]:
            ttk.Button(buttons, text=title, command=lambda f=action: self.safe(f)).pack(side='left', padx=4)

    def poll(self):
        if self.closed: return
        while not self.events.empty():
            callback, value, error = self.events.get(); self.busy = False
            if error:
                self.status.set(error); messagebox.showerror('SSH / TLS', error, parent=self.root)
            else:
                self.safe(lambda: callback(value))
        if self.session:
            state = self.session.snapshot()
            self.status.set(state['status'] + (f" · SOCKS5 127.0.0.1:{state['port']}" if not self.session.cancel.is_set() and state['port'] else ''))
            down, up = state['down'], state['up']
            now = time.monotonic(); elapsed = max(.001, now-self.previous_time)
            self.rates.set('↓ ' + speed(max(0, down-self.previous[0])/elapsed) + '    ↑ ' + speed(max(0, up-self.previous[1])/elapsed))
            self.previous = (down, up)
            self.previous_time = now
        self.timer = self.root.after(1000, self.poll)

    def close(self):
        self.closed = True
        self.root.after_cancel(self.timer)
        if self.session: self.session.stop()
