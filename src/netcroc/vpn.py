"""WireGuard profile vault and explicit Windows tunnel service control.

No connection, DNS/routing changes, downloads or elevation occur on import.
"""
import base64
import ctypes as c
from ctypes import wintypes as w
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
import psutil

PROVIDERS=(
    ('Proton VPN','Free / paid','https://protonvpn.com/support/wireguard-configurations'),
    ('Mullvad','Paid','https://mullvad.net/en/help/wireguard-app-windows'),
    ('IVPN','Paid','https://www.ivpn.net/setup/windows-10-wireguard/'),
    ('Windscribe','Pro / Build-A-Plan','https://windscribe.com/knowledge-base/articles/where-do-i-access-my-wireguard-configs'),
)
INSTALL_URL='https://www.wireguard.com/install/'
MAX_CONFIG=64*1024
FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)


def key(value):
    try:
        raw=base64.b64decode(value,validate=True)
        if len(raw)!=32 or not any(raw):raise ValueError()
    except Exception:
        raise ValueError('WireGuard keys must be nonzero 32-byte base64 values.') from None
    return value


def parse_config(text):
    """Accept standard Windows client fields only; reject scripts and unknown options."""
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_CONFIG or '\x00' in text:
        raise ValueError('Choose a UTF-8 WireGuard .conf file smaller than 64 KB.')
    interface={};peers=[];section=None
    allowed_interface={'privatekey','address','dns','mtu','listenport'}
    allowed_peer={'publickey','presharedkey','allowedips','endpoint','persistentkeepalive'}
    for line in text.lstrip('\ufeff').splitlines():
        line=line.split('#',1)[0].strip()
        if not line:continue
        if line.startswith('['):
            if line=='[Interface]' and not interface and section is None:section=interface
            elif line=='[Peer]' and interface:section={};peers.append(section)
            else:raise ValueError('Use one Interface section followed by Peer sections.')
            continue
        if section is None or '=' not in line:raise ValueError('Invalid WireGuard configuration structure.')
        name,value=(v.strip() for v in line.split('=',1));name=name.lower()
        allowed=allowed_interface if section is interface else allowed_peer
        if name not in allowed:raise ValueError('Unsupported WireGuard option; scripts and extension fields are not accepted.')
        if name in section or not value:raise ValueError('Duplicate or empty WireGuard option.')
        if any(ord(ch)<32 for ch in value):raise ValueError('Invalid control character in configuration.')
        section[name]=value
    if not {'privatekey','address'}<=interface.keys() or not peers:raise ValueError('A client profile needs PrivateKey, Address and at least one Peer.')
    key(interface['privatekey'])
    def items(value):return [v.strip() for v in value.split(',')]
    def addresses(value,network=False):
        try:
            for item in items(value):
                if network:ipaddress.ip_network(item,strict=False)
                else:ipaddress.ip_interface(item)
        except ValueError:raise ValueError('Invalid interface address or allowed network.') from None
    addresses(interface['address'])
    if 'dns' in interface:
        try:
            for value in items(interface['dns']):ipaddress.ip_address(value)
        except ValueError:raise ValueError('DNS entries must be IP addresses in this client.') from None
    for field,low,high in (('mtu',576,65535),('listenport',0,65535)):
        if field in interface:
            try:number=int(interface[field])
            except ValueError:raise ValueError('Invalid WireGuard numeric option.') from None
            if not low<=number<=high:raise ValueError('WireGuard numeric option is outside its valid range.')
    endpoints=[];routes=[];public_keys=set()
    for peer in peers:
        if not {'publickey','allowedips','endpoint'}<=peer.keys():raise ValueError('Each client Peer needs PublicKey, AllowedIPs and Endpoint.')
        key(peer['publickey'])
        if peer['publickey'] in public_keys:raise ValueError('Duplicate peer public key.')
        public_keys.add(peer['publickey'])
        if 'presharedkey' in peer:key(peer['presharedkey'])
        addresses(peer['allowedips'],True);routes.extend(items(peer['allowedips']))
        endpoint=peer['endpoint']
        match=re.fullmatch(r'(\[[0-9a-fA-F:]+\]|[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?):([0-9]{1,5})',endpoint)
        if not match or not 1<=int(match[2])<=65535:raise ValueError('Invalid peer endpoint: use host:port or [IPv6]:port.')
        if match[1].startswith('['):
            try:ipaddress.IPv6Address(match[1][1:-1])
            except ValueError:raise ValueError('Invalid IPv6 endpoint.') from None
        if 'persistentkeepalive' in peer:
            try:number=int(peer['persistentkeepalive'])
            except ValueError:raise ValueError('Invalid keepalive value.') from None
            if not 0<=number<=65535:raise ValueError('Keepalive must be between 0 and 65535.')
        endpoints.append(endpoint)
    labels={'privatekey':'PrivateKey','address':'Address','dns':'DNS','mtu':'MTU','listenport':'ListenPort','publickey':'PublicKey','presharedkey':'PresharedKey','allowedips':'AllowedIPs','endpoint':'Endpoint','persistentkeepalive':'PersistentKeepalive'}
    lines=['[Interface]']+[labels[k]+' = '+v for k,v in interface.items()]
    for peer in peers:lines+=['','[Peer]']+[labels[k]+' = '+v for k,v in peer.items()]
    full=any(ipaddress.ip_network(route,strict=False).prefixlen==0 for route in routes)
    return '\n'.join(lines)+'\n',{'endpoint':', '.join(endpoints),'peers':len(peers),'route':'Default route' if full else 'Selected networks','dns':interface.get('dns','Not specified')}


class Blob(c.Structure):
    _fields_=[('size',w.DWORD),('data',c.POINTER(c.c_ubyte))]


def crypt(data,description='NetCroc WireGuard profile',decrypt=False,machine=False):
    """Windows DPAPI; machine scope is used only for the ACL-protected service file."""
    buf=c.create_string_buffer(data);source=Blob(len(data),c.cast(buf,c.POINTER(c.c_ubyte)));out=Blob()
    api=c.WinDLL('crypt32',use_last_error=True);kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[c.c_void_p];kernel.LocalFree.restype=c.c_void_p
    if decrypt:
        fn=api.CryptUnprotectData;fn.argtypes=[c.POINTER(Blob),c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p,w.DWORD,c.POINTER(Blob)]
        args=(c.byref(source),None,None,None,None,1,c.byref(out))
    else:
        fn=api.CryptProtectData;fn.argtypes=[c.POINTER(Blob),w.LPCWSTR,c.c_void_p,c.c_void_p,c.c_void_p,w.DWORD,c.POINTER(Blob)]
        args=(c.byref(source),description,None,None,None,1|(4 if machine else 0),c.byref(out))
    fn.restype=w.BOOL
    if not fn(*args):raise OSError('Windows could not protect or unlock this VPN profile for this account.')
    try:return c.string_at(out.data,out.size)
    finally:kernel.LocalFree(c.cast(out.data,c.c_void_p))


def protect_service_path(path):
    """Replace the DACL exactly, including any pre-existing explicit grants."""
    api=c.WinDLL('advapi32',use_last_error=True);kernel=c.WinDLL('kernel32',use_last_error=True)
    descriptor=c.c_void_p()
    convert=api.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes=[w.LPCWSTR,w.DWORD,c.POINTER(c.c_void_p),c.c_void_p];convert.restype=w.BOOL
    get_dacl=api.GetSecurityDescriptorDacl
    get_dacl.argtypes=[c.c_void_p,c.POINTER(w.BOOL),c.POINTER(c.c_void_p),c.POINTER(w.BOOL)];get_dacl.restype=w.BOOL
    get_owner=api.GetSecurityDescriptorOwner
    get_owner.argtypes=[c.c_void_p,c.POINTER(c.c_void_p),c.POINTER(w.BOOL)];get_owner.restype=w.BOOL
    set_acl=api.SetNamedSecurityInfoW
    set_acl.argtypes=[w.LPWSTR,w.DWORD,w.DWORD,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p];set_acl.restype=w.DWORD
    kernel.LocalFree.argtypes=[c.c_void_p];kernel.LocalFree.restype=c.c_void_p
    if not convert('O:BAG:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)',1,c.byref(descriptor),None):
        raise OSError('Windows could not prepare private VPN service storage.')
    try:
        present=w.BOOL();defaulted=w.BOOL();dacl=c.c_void_p()
        if not get_dacl(descriptor,c.byref(present),c.byref(dacl),c.byref(defaulted)) or not present.value or not dacl.value:
            raise OSError('Windows could not prepare a restricted VPN storage access list.')
        owner=c.c_void_p()
        if not get_owner(descriptor,c.byref(owner),c.byref(defaulted)) or not owner.value:
            raise OSError('Windows could not prepare the VPN storage owner.')
        name=c.create_unicode_buffer(str(path))
        if set_acl(name,1,0x80000005,owner,None,dacl,None):
            raise OSError('Windows could not restrict VPN service storage to administrators and Local System.')
    finally:kernel.LocalFree(descriptor)


def tunnel_name(identifier):
    if not re.fullmatch('[0-9a-f]{32}',identifier):raise ValueError('Invalid VPN profile identifier.')
    return 'NetCroc-'+identifier[:20]


class WindowsWireGuard:
    def installed(self):
        base=Path(os.environ.get('ProgramW6432',os.environ.get('ProgramFiles',r'C:\Program Files')))
        exe=base/'WireGuard'/'wireguard.exe'
        return exe if exe.is_file() else None

    def require_admin(self):
        if not c.windll.shell32.IsUserAnAdmin():
            raise PermissionError('Run NetCroc as administrator at the PC to connect or disconnect. Importing needs no administrator access.')

    def state(self,name):
        try:return psutil.win_service_get('WireGuardTunnel$'+name).status()
        except psutil.NoSuchProcess:return 'not installed'
        except psutil.AccessDenied:return 'unknown'

    def status(self,name):
        status=self.state(name);info={'service':status,'handshake':'Not checked'}
        exe=self.installed()
        if status=='running' and exe and c.windll.shell32.IsUserAnAdmin():
            wg=exe.with_name('wg.exe')
            if wg.is_file():
                try:
                    result=subprocess.run([str(wg),'show',name,'latest-handshakes'],capture_output=True,text=True,timeout=5,creationflags=FLAGS)
                    stamps=[int(line.split()[-1]) for line in result.stdout.splitlines() if line.split() and line.split()[-1].isdigit()] if result.returncode==0 else []
                    latest=max(stamps,default=0)
                    info['handshake']=f'{max(0,int(time.time()-latest))}s ago' if latest else 'No handshake observed'
                except (OSError,subprocess.TimeoutExpired):info['handshake']='Unavailable'
        return info

    def _run(self,args):
        try:result=subprocess.run(args,capture_output=True,timeout=30,creationflags=FLAGS)
        except (OSError,subprocess.TimeoutExpired):raise OSError('Windows VPN operation did not complete. Refresh status before retrying.') from None
        if result.returncode:raise OSError('Windows refused the VPN operation. Check WireGuard installation and administrator access.')

    def runtime_path(self,name):
        if not re.fullmatch(r'NetCroc-[0-9a-f]{20}',name):raise ValueError('Invalid NetCroc tunnel name.')
        base=Path(os.environ.get('ProgramW6432',os.environ.get('ProgramFiles',r'C:\Program Files')))
        return base/'NetCrocServiceData'/'WireGuard'/(name+'.conf.dpapi')

    def connect(self,name,text):
        self.require_admin();self.runtime_path(name);exe=self.installed()
        if not exe:raise FileNotFoundError('Install the official WireGuard Windows client first, then refresh.')
        if self.state(name)!='not installed':raise ValueError('This profile already has a tunnel service. Disconnect it before reconnecting.')
        for service in psutil.win_service_iter():
            if service.name().startswith('WireGuardTunnel$') and service.status()!='stopped':
                raise ValueError('Disconnect the other WireGuard tunnel first. NetCroc will not replace it.')
        text,_=parse_config(text);path=self.runtime_path(name)
        path.parent.mkdir(parents=True,exist_ok=True)
        for folder in (path.parent,path.parent.parent):
            if folder.is_symlink() or folder.is_junction():raise ValueError('VPN service storage must be a normal local directory.')
        # Only administrators and Local System may read the machine-protected service config.
        protect_service_path(path.parent.parent)
        protect_service_path(path.parent)
        if path.exists():raise ValueError('An earlier encrypted service file remains. Use Disconnect to clean it up before reconnecting.')
        with path.open('xb') as file:file.write(crypt(text.encode('utf-8'),description=name,machine=True))
        try:
            protect_service_path(path)
            self._run([str(exe),'/installtunnelservice',str(path)])
            # Connection is explicit; it must not silently reconnect at the next boot.
            self._run([str(Path(os.environ['SystemRoot'])/'System32'/'sc.exe'),'config','WireGuardTunnel$'+name,'start=','demand'])
        except Exception:
            try:self.disconnect(name)
            except Exception:pass
            raise
        return self.status(name)

    def disconnect(self,name):
        self.require_admin();self.runtime_path(name);exe=self.installed()
        if self.state(name)!='not installed':
            if not exe:raise FileNotFoundError('WireGuard is unavailable; use Windows service management to stop this tunnel.')
            self._run([str(exe),'/uninstalltunnelservice',name])
            deadline=time.monotonic()+10
            while self.state(name)!='not installed' and time.monotonic()<deadline:time.sleep(.2)
            if self.state(name)!='not installed':raise OSError('Tunnel service is still present. Refresh status; encrypted configuration was preserved.')
        self.runtime_path(name).unlink(missing_ok=True)
        return {'service':'not installed','handshake':'Not checked'}


class ProfileStore:
    def __init__(self,folder,backend=None):
        self.folder=Path(folder);self.backend=backend or WindowsWireGuard()

    def _path(self,identifier):
        tunnel_name(identifier)
        return self.folder/(identifier+'.json')

    def profiles(self):
        result=[]
        for path in self.folder.glob('*.json'):
            try:
                data=json.loads(path.read_text(encoding='utf-8'));tunnel_name(data['id'])
                if path!=self._path(data['id']):continue
                item={k:data[k] for k in ('id','label','endpoint','peers','route','dns')}
                if not all(isinstance(item[k],str) for k in ('label','endpoint','route','dns')) or not isinstance(item['peers'],int):continue
                result.append(item)
            except (OSError,ValueError,KeyError,TypeError):continue
        return sorted(result,key=lambda item:item['label'].lower())

    def import_file(self,path):
        path=Path(path)
        if path.suffix.lower()!='.conf' or path.stat().st_size>MAX_CONFIG:raise ValueError('Choose a WireGuard .conf file smaller than 64 KB.')
        try:text=path.read_text(encoding='utf-8-sig')
        except (UnicodeError,OSError):raise ValueError('Could not read this UTF-8 configuration file.') from None
        return self.add(text,path.stem)

    def add(self,text,label):
        text,meta=parse_config(text)
        identifier=uuid.uuid4().hex
        label=''.join(ch for ch in label if ch.isprintable()).strip()[:80] or 'WireGuard profile'
        data={'id':identifier,'label':label,**meta,'protected':base64.b64encode(crypt(text.encode('utf-8'))).decode('ascii')}
        self.folder.mkdir(parents=True,exist_ok=True)
        with self._path(identifier).open('x',encoding='utf-8') as file:json.dump(data,file)
        return {k:v for k,v in data.items() if k!='protected'}

    def connect(self,identifier):
        self.backend.require_admin()
        data=json.loads(self._path(identifier).read_text(encoding='utf-8'))
        try:text=crypt(base64.b64decode(data['protected'],validate=True),decrypt=True).decode('utf-8')
        except Exception:raise ValueError('Could not unlock this profile. Re-import it using this Windows account.') from None
        return self.backend.connect(tunnel_name(identifier),text)

    def disconnect(self,identifier):return self.backend.disconnect(tunnel_name(identifier))

    def remove(self,identifier):
        if self.backend.state(tunnel_name(identifier))!='not installed':raise ValueError('Disconnect and remove the tunnel service before deleting this saved profile.')
        self._path(identifier).unlink()
