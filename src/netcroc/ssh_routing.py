"""Optional pinned sing-box routing. Config checks never create an adapter."""
import ctypes
from ctypes import wintypes
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import platform
import subprocess
import threading
import time
import urllib.request
import zipfile
import os
import tarfile

POSIX_HASHES={'linux-amd64': '699a1b510aa4396b2176d32d1181920399ebf1e267835da6f3b598d0f7c24968', 'darwin-arm64': '0d8c7f5ed5d587b0f1a5e9772a708ec3bfa4ac4c9329604b01d8d9c2ba406838', 'darwin-amd64': 'eae86b9b033bba50b7c44ab719e4bfac0aca05efd28483390ed3aa510f32db25'}
VERSION = '1.14.4'
URL = f'https://github.com/SagerNet/sing-box/releases/download/v{VERSION}/sing-box-{VERSION}-windows-amd64.zip'
SHA256 = '99185d75d314a07dbba4a130c8ad986cbeb629a07927975636b341ca61f991df'
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def configuration(port, upstream):
    if not 1 <= int(port) <= 65535 or not upstream:
        raise ValueError('A local proxy port and upstream address are required.')
    excluded = ['127.0.0.0/8', '::1/128']
    for value in upstream:
        address = ipaddress.ip_address(value)
        excluded.append(str(address) + ('/32' if address.version == 4 else '/128'))
    return {
        'log': {'level': 'warn'},
        'dns': {'servers': [{'type': 'https', 'tag': 'remote-dns',
            'server': '1.1.1.1', 'server_port': 443, 'path': '/dns-query',
            'tls': {'enabled': True, 'server_name': 'cloudflare-dns.com'}, 'detour': 'ssh'}],
            'final': 'remote-dns'},
        'inbounds': [{'type': 'tun', 'tag': 'netcroc-tun', 'interface_name': 'NetCrocSSH' if os.name=='nt' else ('utun' if platform.system()=='Darwin' else 'ncssh'),
            'address': ['172.30.91.1/30', 'fdfe:dcba:9876::1/126'],
            'auto_route': True, 'strict_route': True, 'stack': 'mixed',
            'route_exclude_address': excluded}],
        'outbounds': [{'type': 'socks', 'tag': 'ssh', 'server': '127.0.0.1',
            'server_port': int(port), 'version': '5', 'network': 'tcp'}],
        'route': {'auto_detect_interface': True, 'rules': [
            {'port': 53, 'action': 'hijack-dns'},
            {'network': 'udp', 'action': 'reject'},
            {'network': 'icmp', 'action': 'reject'}], 'final': 'ssh'}}


class ChildJob:
    """Windows kills the routing child when the parent/job handle disappears."""
    def __init__(self, process):
        self.native=None
        if os.name!='nt':
            from .platforms import ChildGuard
            self.native=ChildGuard(process);return
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', wintypes.DWORD), ('min_working', ctypes.c_size_t),
                ('max_working', ctypes.c_size_t), ('process_limit', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                ('scheduling', wintypes.DWORD)]
        class Limits(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', ctypes.c_uint64 * 6),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError('Could not create routing safety job.')
        limits = Limits(); limits.basic.flags = 0x2000
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            self.close()
            raise OSError('Could not protect the routing process lifetime.')

    def close(self):
        if self.native is not None:
            self.native.close();self.native=None;return
        if getattr(self,'handle',None):
            self.api.CloseHandle(self.handle); self.handle = None


class Routing:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.exe = self.folder / ('sing-box.exe' if os.name=='nt' else 'sing-box')
        self.process = self.job = None
        self.active = False
        self.lock = threading.RLock()

    def install(self):
        machine=platform.machine().lower()
        if os.name=='nt':
            if machine not in ('amd64','x86_64'):raise ValueError('Windows routing core requires x64.')
            url,expected=URL,SHA256
        else:
            arch='arm64' if machine in ('arm64','aarch64') else 'amd64' if machine in ('x86_64','amd64') else ''
            target=('darwin' if platform.system()=='Darwin' else 'linux')+'-'+arch
            hashes=POSIX_HASHES
            if target not in hashes:raise ValueError('No pinned routing core for this operating system/architecture.')
            url=f'https://github.com/SagerNet/sing-box/releases/download/v{VERSION}/sing-box-{VERSION}-{target}.tar.gz'
            expected=hashes[target]
        with urllib.request.urlopen(url,timeout=45) as response:raw=response.read(100*1024*1024+1)
        if len(raw)>100*1024*1024 or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Routing download failed SHA-256 verification.')
        wanted={self.exe.name,'LICENSE'}|({'wintun.dll'} if os.name=='nt' else set())
        selected={}
        if os.name=='nt':
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for member in archive.namelist():
                    name=Path(member).name
                    if name in wanted:selected[name]=archive.read(member)
        else:
            with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
                for member in archive.getmembers():
                    name=Path(member.name).name
                    if name in wanted and member.isfile() and member.size<=100*1024*1024:selected[name]=archive.extractfile(member).read()
        if self.exe.name not in selected or 'LICENSE' not in selected:raise ValueError('Routing archive is incomplete.')
        self.folder.mkdir(parents=True,exist_ok=True)
        for name,data in selected.items():
            target=self.folder/name;temporary=target.with_suffix('.download')
            temporary.write_bytes(data)
            if os.name!='nt':temporary.chmod(0o755 if name==self.exe.name else 0o644)
            temporary.replace(target)
        (self.folder/'verified.sha256').write_text(hashlib.sha256(self.exe.read_bytes()).hexdigest(),encoding='ascii')

    def verify(self):
        try:
            expected = (self.folder / 'verified.sha256').read_text(encoding='ascii').strip()
            actual = hashlib.sha256(self.exe.read_bytes()).hexdigest()
        except OSError:
            raise FileNotFoundError('Download the optional routing core first.') from None
        if actual != expected:
            raise ValueError('Routing core changed. Download the verified copy again.')

    def check(self, port=1080, upstream=('192.0.2.1',)):
        self.verify()
        result = subprocess.run([str(self.exe), 'check', '-c', 'stdin'],
            input=json.dumps(configuration(port, upstream)), text=True,
            capture_output=True, timeout=20, creationflags=HIDDEN)
        if result.returncode:
            raise ValueError('Routing configuration was rejected by the installed core.')
        return True

    def preflight(self):
        from .platforms import admin
        if not admin():
            raise PermissionError('Whole-PC TCP mode needs Run as administrator. Local SOCKS5 does not.')
        import psutil
        for service in (psutil.win_service_iter() if os.name=='nt' else []):
            if service.name().startswith('WireGuardTunnel$') and service.status()!='stopped':
                raise ValueError('Disconnect the active WireGuard tunnel before whole-PC routing.')
        if any('wireguard' in a.lower() or a in ('NetCrocSSH','NetCrocVLESS') for a in psutil.net_if_addrs()):
            raise ValueError('Disconnect other VPN/TUN adapters before Whole-PC TCP mode.')
        if os.name!='nt' and any(n.startswith(('utun','wg','nc')) for n in psutil.net_if_addrs()):
            raise ValueError('Disconnect other VPN/TUN adapters first.')
        self.check()

    def start(self, port, upstream):
        self.preflight()
        self.check(port, upstream)
        with self.lock:
            try:
                self.process = subprocess.Popen([str(self.exe), 'run', '-c', 'stdin'],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=HIDDEN)
                # The core blocks reading stdin until it is assigned to the safety job.
                self.job = ChildJob(self.process)
                self.process.stdin.write(json.dumps(configuration(port, upstream)).encode())
                self.process.stdin.close()
                import psutil
                for _ in range(50):
                    if self.process.poll() is not None:
                        raise OSError('Routing core could not start.')
                    if os.name!='nt' or 'NetCrocSSH' in psutil.net_if_addrs():
                        self.active = True
                        return
                    time.sleep(.1)
                raise OSError('Routing adapter did not become ready.')
            except Exception:
                self.stop(); raise

    def healthy(self):
        return self.process is not None and self.process.poll() is None

    def stop(self):
        with self.lock:
            self.active = False
            if self.job:
                self.job.close(); self.job = None
            if self.process:
                if self.process.poll() is None:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=3)
                self.process = None
