"""Bounded DNS benchmarks and explicitly requested IPv4 DNS changes with rollback."""
import ctypes
import ipaddress
import json
import os
from pathlib import Path
import random
import secrets
import socket
import statistics
import struct
import subprocess
import sys
import time
if os.name=='nt':import winreg

DOMAINS=('example.com','www.microsoft.com','www.cloudflare.com')
PUBLIC={'Cloudflare':('1.1.1.1','1.0.0.1'),'Google':('8.8.8.8','8.8.4.4'),'Quad9':('9.9.9.9','149.112.112.112')}
FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)

def powershell(script):
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
        "$ErrorActionPreference='Stop'; "+script],capture_output=True,encoding='utf-8',errors='replace',
        timeout=25,creationflags=FLAGS)
    if result.returncode:
        raise OSError('Windows network operation failed. Check adapter permissions and try again.')
    return result.stdout.lstrip('\ufeff').strip()

def adapters():
    # Native IP Helper avoids slow/localized PowerShell CIM adapter enumeration.
    c=ctypes
    from ctypes import wintypes as w
    class SocketAddress(c.Structure):
        _fields_=[('address',c.c_void_p),('length',c.c_int)]
    class DnsAddress(c.Structure):pass
    DnsAddress._fields_=[('alignment',c.c_ulonglong),('next',c.POINTER(DnsAddress)),('socket',SocketAddress)]
    class Adapter(c.Structure):pass
    Adapter._fields_=[('length',w.ULONG),('index',w.DWORD),('next',c.POINTER(Adapter)),('adapter_name',c.c_char_p),
        ('unicast',c.c_void_p),('anycast',c.c_void_p),('multicast',c.c_void_p),('dns',c.POINTER(DnsAddress)),
        ('suffix',w.LPWSTR),('description',w.LPWSTR),('friendly',w.LPWSTR),('mac',c.c_ubyte*8),
        ('mac_length',w.DWORD),('flags',w.DWORD),('mtu',w.DWORD),('type',w.DWORD),('status',w.DWORD)]
    api=c.WinDLL('iphlpapi')
    api.GetAdaptersAddresses.argtypes=[w.ULONG,w.ULONG,c.c_void_p,c.c_void_p,c.POINTER(w.ULONG)]
    api.GetAdaptersAddresses.restype=w.ULONG
    size=w.ULONG(16384)
    for _ in range(3):
        buffer=c.create_string_buffer(size.value)
        code=api.GetAdaptersAddresses(2,0,None,buffer,c.byref(size))
        if code!=111:break
    if code:raise OSError(code,c.FormatError(code))
    pointer=c.cast(buffer,c.POINTER(Adapter)); result=[]
    while pointer:
        item=pointer.contents
        if item.status==1 and item.type!=24 and item.unicast:
            servers=[]; node=item.dns
            while node:
                address=node.contents.socket
                if address.length>=8 and address.address:
                    raw=c.string_at(address.address,address.length)
                    if int.from_bytes(raw[:2],'little')==2:servers.append(socket.inet_ntoa(raw[4:8]))
                node=node.contents.next
            result.append({'index':item.index,'name':item.friendly,'guid':item.adapter_name.decode('ascii').strip('{}'),'servers':servers})
        pointer=item.next
    api.GetBestInterface.argtypes=[w.DWORD,c.POINTER(w.DWORD)]
    api.GetBestInterface.restype=w.DWORD
    preferred=w.DWORD()
    api.GetBestInterface(int.from_bytes(socket.inet_aton('1.1.1.1'),'little'),c.byref(preferred))
    return sorted(result,key=lambda a:(a['index']!=preferred.value,not bool(a['servers']),a['name']))

def query(server,domain,timeout=1.5):
    ipaddress.IPv4Address(server)
    transaction=secrets.randbelow(65536)
    question=b''.join(bytes([len(part)])+part.encode('ascii') for part in domain.split('.'))+b'\0'+struct.pack('!HH',1,1)
    packet=struct.pack('!6H',transaction,0x100,1,0,0,0)+question
    started=time.perf_counter()
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout); sock.connect((server,53)); sock.send(packet)
        reply=sock.recv(4096)
    if len(reply)<12:
        raise ValueError('Short DNS response')
    rid,flags,questions,answers,_,_=struct.unpack('!6H',reply[:12])
    if rid!=transaction or not flags&0x8000 or flags&0xf or flags&0x200 or questions!=1 or answers<1 or reply[12:12+len(question)]!=question:
        raise ValueError('DNS lookup failed or requires TCP; resolver not recommended by this UDP test')
    return (time.perf_counter()-started)*1000

def benchmark(current=(),rounds=3):
    targets=[('Current '+server,(server,)) for server in current if server]+list(PUBLIC.items())
    values={name:[] for name,_ in targets}; failures={name:0 for name,_ in targets}
    jobs=[(name,servers[0],domain) for name,servers in targets for _ in range(rounds) for domain in DOMAINS]
    random.shuffle(jobs)
    for name,server,domain in jobs:
        try:
            values[name].append(query(server,domain))
        except (OSError,ValueError):
            failures[name]+=1
    rows=[]
    for name,servers in targets:
        timings=values[name]
        rows.append({'name':name,'servers':servers,'failures':failures[name],
            'median':statistics.median(timings) if timings else None,'count':len(timings),'attempts':rounds*len(DOMAINS)})
    return sorted(rows,key=lambda row:(row['failures'],row['median'] if row['median'] is not None else float('inf')))

def atomic(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp'); tmp.write_text(json.dumps(value),encoding='utf-8'); tmp.replace(path)

class WindowsBackend:
    def snapshot(self,adapter):
        key=r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{'+adapter['guid'].strip('{}')+'}'
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,key) as handle:
            try: manual=winreg.QueryValueEx(handle,'NameServer')[0].strip()
            except FileNotFoundError: manual=''
        return {'index':int(adapter['index']),'guid':adapter['guid'],'name':adapter['name'],
                'manual':bool(manual),'servers':manual.replace(',',' ').split() if manual else []}

    def valid_adapter(self,state):
        guid=state['guid'].strip('{}').lower()
        return next((a for a in adapters() if a['guid'].strip('{}').lower()==guid and a['index']==state['index']),None)

    def set(self,state,servers):
        if not self.valid_adapter(state):
            raise OSError('The selected adapter changed or disconnected. No DNS change was made.')
        index=int(state['index'])
        for server in servers:
            ipaddress.IPv4Address(server)
        if not servers:
            commands=[['netsh.exe','interface','ipv4','set','dnsservers',f'name={index}','source=dhcp']]
        else:
            commands=[['netsh.exe','interface','ipv4','set','dnsservers',f'name={index}','source=static',f'address={servers[0]}','validate=no']]
            commands += [['netsh.exe','interface','ipv4','add','dnsservers',f'name={index}',f'address={server}',f'index={i+1}','validate=no'] for i,server in enumerate(servers[1:],1)]
        for command in commands:
            run=subprocess.run(command,capture_output=True,timeout=15,creationflags=FLAGS)
            if run.returncode:
                raise OSError('Windows refused the DNS change. Run NetCroc as administrator.')

    def healthy(self):
        # Separate process bounds Windows resolver hangs; no user traffic is interrupted.
        args=[sys.executable]
        if not getattr(sys,'frozen',False):args.append(str(Path(__file__).resolve().parents[1]/'app.py'))
        try:
            return subprocess.run(args+['--dns-health'],timeout=20,creationflags=FLAGS).returncode==0
        except (OSError,subprocess.TimeoutExpired):
            return False

class DnsManager:
    def __init__(self,path,backend=None,guard=None):
        self.path=Path(path); self.backend=backend or WindowsBackend(); self.guard=guard or self.launch_guard

    def load(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else None

    def launch_guard(self):
        args=[sys.executable]
        if not getattr(sys,'frozen',False):
            args.append(str(Path(__file__).resolve().parents[1]/'app.py'))
        transaction=self.load()['transaction']
        # A frozen watchdog must own its extracted runtime so it survives parent exit.
        from .platforms import admin,elevated_native
        child=None
        if os.name!='nt' and not admin():
            elevated_native('dns-guard',dict(path=str(self.path.resolve()),transaction=transaction))
        else:
            child=subprocess.Popen(args+['--dns-watch',str(self.path),transaction],creationflags=FLAGS,close_fds=True,
                env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
        ready=self.path.with_suffix('.ready');deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            try:
                if json.loads(ready.read_text(encoding='utf-8')).get('transaction')==transaction:return
            except (OSError,ValueError):pass
            if child is not None and child.poll() is not None:raise OSError('DNS rollback protection could not start. No DNS change was made.')
            time.sleep(.1)
        raise TimeoutError('DNS rollback protection did not become ready. No DNS change was made.')

    def apply(self,adapter,servers):
        from .platforms import admin
        if os.name=='nt' and not admin():
            raise PermissionError('Run NetCroc as administrator to apply DNS. Benchmarks need no administrator access.')
        if self.load() and self.load()['state']=='pending':
            raise ValueError('Restore the pending DNS transaction first.')
        servers=list(servers)
        if not servers: raise ValueError('Select a resolver first.')
        for server in servers:
            for domain in DOMAINS:
                query(server,domain)
        if not self.backend.healthy():
            raise OSError('Baseline DNS is not healthy. Current settings were left unchanged.')
        original=self.backend.snapshot(adapter)
        existing=self.load()
        if existing and existing['state']=='committed' and existing['original']['guid']==original['guid']:
            original=existing['original']
        elif existing and existing['state']=='committed':
            raise ValueError('Restore the previous adapter before applying DNS on another adapter.')
        state={'state':'pending','original':original,'servers':servers,'created':time.time(),'transaction':secrets.token_hex(16)}
        atomic(self.path,state)
        try:
            # Independent watchdog exists BEFORE the first setting changes.
            self.guard()
            self.backend.set(original,servers)
            if not self.backend.healthy():
                raise OSError('New DNS failed validation. Restoring the original configuration.')
            state['state']='committed'; atomic(self.path,state)
        except Exception:
            self.restore()
            raise

    def restore(self):
        state=self.load()
        if not state or state['state']=='restored': return
        original=state['original']
        self.backend.set(original,original['servers'] if original['manual'] else [])
        state['state']='restored'; atomic(self.path,state)

def watchdog(path,transaction=None):
    manager=DnsManager(path)
    state=manager.load()
    if not state or state['state']!='pending' or state.get('transaction')!=transaction:return
    atomic(Path(path).with_suffix('.ready'),{'transaction':transaction})
    # Allow bounded preflight/apply/health checks. On crash or timeout, restore.
    for _ in range(90):
        time.sleep(1)
        state=manager.load()
        if not state or state['state']!='pending' or state.get('transaction')!=transaction: return
    manager.restore()

if os.name != "nt":
    from .posix_network import adapters, DnsBackend as WindowsBackend
