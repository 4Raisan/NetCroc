"""User-supplied VLESS profiles via the verified sing-box core, not an Xray executable."""
import base64
import os
import sys
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import subprocess
import time
import threading
from urllib.parse import urlsplit, parse_qs, unquote
import uuid
from . import ssh_tunnel as ssh
from .ssh_routing import Routing, ChildJob, HIDDEN, configuration
from .vpn import crypt

DEFAULTS=dict(label='VLESS profile',host='',port=443,uuid='',security='tls',sni='',
    transport='tcp',path='/',http_host='',service_name='',flow='',fingerprint='',
    reality_key='',short_id='',alpn='',local_port=1081,routing='socks',ca_pem='')

def validate(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):
        raise ValueError('Unsupported VLESS profile fields.')
    result=DEFAULTS|value
    for field,default in DEFAULTS.items():
        if isinstance(default,str) and (not isinstance(result[field],str) or any(ord(c)<32 for c in result[field]) and field!='ca_pem'):
            raise ValueError('Invalid VLESS text field.')
    if len(json.dumps(result).encode())>65536: raise ValueError('VLESS profile is too large.')
    result['host']=ssh.hostname(result['host'])
    for field in ('sni','http_host'):
        if result[field]: ssh.hostname(result[field])
    for field in ('port','local_port'):
        if isinstance(result[field],(bool,float)): raise ValueError('Invalid VLESS port.')
        try: result[field]=int(result[field])
        except (ValueError,TypeError): raise ValueError('Invalid VLESS port.') from None
        if not 1<=result[field]<=65535: raise ValueError('VLESS ports must be 1–65535.')
    try: result['uuid']=str(uuid.UUID(result['uuid']))
    except (ValueError,TypeError,AttributeError): raise ValueError('Enter the provider VLESS UUID.') from None
    if result['security'] not in ('tls','reality','none') or result['routing'] not in ('socks','tun'):
        raise ValueError('Unsupported VLESS security or routing mode.')
    if result['security']=='none':
        try: local=ipaddress.ip_address(result['host']).is_loopback
        except ValueError: local=False
        if not local: raise ValueError('Unencrypted VLESS is restricted to loopback test servers. Use TLS or REALITY for remote servers.')
    if result['transport'] not in ('tcp','ws','grpc','httpupgrade'):
        raise ValueError('Supported VLESS transports: TCP, WebSocket, gRPC, HTTPUpgrade.')
    if result['flow'] not in ('','xtls-rprx-vision'):
        raise ValueError('Unsupported VLESS flow.')
    if result['flow'] and (result['transport']!='tcp' or result['security']=='none'):
        raise ValueError('Vision requires TCP with TLS or REALITY.')
    if result['fingerprint'] not in ('','chrome','firefox','edge','safari','random','randomized'):
        raise ValueError('Unsupported TLS fingerprint.')
    if result['transport'] in ('ws','httpupgrade') and not result['path'].startswith('/'):
        raise ValueError('Transport path must start with /.')
    if result['security']=='reality':
        try:
            raw=base64.urlsafe_b64decode(result['reality_key']+'='*((-len(result['reality_key']))%4))
            if len(raw)!=32 or not re.fullmatch(r'[A-Za-z0-9_-]{43}',result['reality_key']): raise ValueError()
        except Exception: raise ValueError('REALITY needs a 32-byte base64url public key.') from None
        if not re.fullmatch(r'(?:[0-9a-fA-F]{2}){0,8}',result['short_id']):
            raise ValueError('REALITY short ID must contain up to 16 hex digits in byte pairs.')
        if not result['sni']: raise ValueError('REALITY requires the provider SNI.')
        result['fingerprint']=result['fingerprint'] or 'chrome'
    result['label']=result['label'].strip()[:80] or 'VLESS profile'
    return result

def parse_link(text):
    try:
        if len(text)>65536: raise ValueError()
        url=urlsplit(text.strip())
        if url.scheme!='vless' or not url.hostname or not url.username or url.password: raise ValueError()
        values=parse_qs(url.query,keep_blank_values=True,strict_parsing=True)
        supported={'encryption','security','sni','type','path','host','serviceName','flow','fp','pbk','sid','alpn','headerType'}
        if set(values)-supported or any(len(v)!=1 for v in values.values()): raise ValueError()
        query={key:items[0] for key,items in values.items()}
        if query.get('encryption','none')!='none' or query.get('headerType','none')!='none': raise ValueError()
        result=dict(host=url.hostname,port=url.port or 443,uuid=unquote(url.username),label=unquote(url.fragment) or 'VLESS profile',
            security=query.get('security','tls'),transport=query.get('type','tcp'))
        for source,target in [('sni','sni'),('path','path'),('host','http_host'),('serviceName','service_name'),('flow','flow'),('fp','fingerprint'),('pbk','reality_key'),('sid','short_id'),('alpn','alpn')]:
            if source in query: result[target]=query[source]
        return validate(result)
    except Exception:
        raise ValueError('Invalid or unsupported VLESS link. Import one TCP/WS/gRPC/HTTPUpgrade profile with TLS or REALITY; subscription URLs and insecure certificate overrides are not accepted.') from None

class ProfileStore(ssh.ProfileStore):
    def save(self,value,identifier=None):
        value=validate(value);identifier=identifier or uuid.uuid4().hex
        path=self.path(identifier);self.folder.mkdir(parents=True,exist_ok=True)
        protected=base64.b64encode(crypt(json.dumps(value).encode(),description='NetCroc VLESS profile')).decode()
        temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps({'id':identifier,'protected':protected}),encoding='utf-8');temporary.replace(path)
        return identifier
    def load(self,identifier):
        try:
            value=json.loads(self.path(identifier).read_text(encoding='utf-8'))
            return validate(json.loads(crypt(base64.b64decode(value['protected'],validate=True),decrypt=True)))
        except Exception: raise ValueError('Could not unlock this VLESS profile for this Windows account.') from None
    def profiles(self):
        items=[]
        for path in self.folder.glob('*.json'):
            try:
                p=self.load(path.stem)
                items.append((path.stem,{k:p[k] for k in ('label','host','port','security','transport','routing')}))
            except (OSError,ValueError): pass
        return sorted(items,key=lambda item:item[1]['label'].lower())
    def import_file(self,path):
        with Path(path).open('rb') as source: raw=source.read(65537)
        if len(raw)>65536: raise ValueError('VLESS profile file is too large.')
        try:
            text=raw.decode('utf-8-sig').strip()
            value=parse_link(text) if text.startswith('vless://') else validate(json.loads(text))
        except Exception: raise ValueError('Import a supported VLESS link file or NetCroc VLESS JSON profile.') from None
        return self.save(value)

def outbound(value,server=None):
    p=validate(value)
    result={'type':'vless','tag':'vless','server':server or p['host'],'server_port':p['port'],'uuid':p['uuid']}
    if p['flow']: result['flow']=p['flow']
    if p['security']!='none':
        tls={'enabled':True,'server_name':p['sni'] or p['host'],'min_version':'1.2'}
        if p['ca_pem']: tls['certificate']=p['ca_pem']
        if p['alpn']: tls['alpn']=[a.strip() for a in p['alpn'].split(',') if a.strip()]
        if p['fingerprint']: tls['utls']={'enabled':True,'fingerprint':p['fingerprint']}
        if p['security']=='reality': tls['reality']={'enabled':True,'public_key':p['reality_key'],'short_id':p['short_id']}
        result['tls']=tls
    if p['transport']!='tcp':
        transport={'type':p['transport']}
        if p['transport']=='grpc': transport['service_name']=p['service_name']
        else:
            transport['path']=p['path']
            if p['http_host']:
                if p['transport']=='ws': transport['headers']={'Host':p['http_host']}
                else: transport['host']=p['http_host']
        result['transport']=transport
    return result

def config(value,upstream=None):
    p=validate(value)
    if p['routing']=='tun':
        if not upstream: raise ValueError('Resolve the upstream server before whole-PC routing.')
        result=configuration(p['local_port'],upstream)
        result['inbounds'][0]['interface_name']='NetCrocVLESS' if os.name=='nt' else ('utun' if sys.platform=='darwin' else 'ncvless')
        result['outbounds']=[outbound(p,upstream[0])]
        result['dns']['servers'][0]['detour']='vless'
        # VLESS supports UDP through XUDP. ICMP remains rejected.
        result['route']['rules']=[{'port':53,'action':'hijack-dns'},{'network':'icmp','action':'reject'}]
        result['route']['final']='vless'
    else:
        result={'log':{'level':'warn'},'inbounds':[{'type':'socks','tag':'local','listen':'127.0.0.1','listen_port':p['local_port']}],
            'outbounds':[outbound(p,upstream[0] if upstream else None)],'route':{'final':'vless'}}
    return result

class Session(Routing):
    def __init__(self,folder):
        super().__init__(folder);self.status='Disconnected';self.profile_id=None;self.cancel=threading.Event()
    def check_config(self,value):
        self.verify()
        result=subprocess.run([str(self.exe),'check','-c','stdin'],input=json.dumps(value),text=True,capture_output=True,timeout=20,creationflags=HIDDEN)
        if result.returncode: raise ValueError('The routing core rejected this VLESS configuration.')
    def start_profile(self,value,identifier=None):
        p=validate(value)
        if p['routing']=='tun': self.preflight()
        upstream=sorted(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(p['host'],p['port'],type=socket.SOCK_STREAM)),key=lambda ip:ipaddress.ip_address(ip).version)
        value=config(p,upstream);self.check_config(value)
        self.profile_id=identifier
        with self.lock:
            try:
                if p['routing']=='tun' and os.name!='nt':
                    if self.cancel.is_set():raise OSError('VLESS connection cancelled.')
                    from .tun_service import RemoteRouting
                    self.remote=RemoteRouting();self.remote.start(self.exe,'vless',upstream,profile=p)
                    if self.cancel.is_set():raise OSError('VLESS connection cancelled.')
                    self.active=True;self.status='Ready · whole-PC VLESS · provider connection not yet verified';return self.status
                if self.cancel.is_set(): raise OSError('VLESS connection cancelled.')
                self.process=subprocess.Popen([str(self.exe),'run','-c','stdin'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=HIDDEN)
                self.job=ChildJob(self.process)
                self.process.stdin.write(json.dumps(value).encode());self.process.stdin.close()
                for _ in range(50):
                    if self.cancel.is_set(): raise OSError('VLESS connection cancelled.')
                    if self.process.poll() is not None: raise OSError('VLESS core failed to start.')
                    if p['routing']=='socks':
                        try:
                            with socket.create_connection(('127.0.0.1',p['local_port']),timeout=.2) as probe:
                                probe.sendall(b'\x05\x01\x00');ready=ssh.receive_exact(probe,2)==b'\x05\x00'
                        except OSError: ready=False
                    else:
                        import psutil
                        ready=any(name.startswith(('utun','ncvless')) for name in psutil.net_if_addrs()) if os.name!='nt' else 'NetCrocVLESS' in psutil.net_if_addrs()
                    if ready:
                        self.active=True;self.status='Ready · '+('local SOCKS5 127.0.0.1:'+str(p['local_port']) if p['routing']=='socks' else 'whole-PC VLESS')+' · provider connection not yet verified'
                        return self.status
                    time.sleep(.1)
                raise OSError('VLESS listener/adapter did not become ready.')
            except Exception: self.stop();raise
    def stop(self):
        self.cancel.set()
        super().stop();self.status='Disconnected'

def proxy_ip(port):
    """HTTPS IP check with DNS and TCP carried through the local SOCKS listener."""
    import ssl
    import ipaddress
    sock=socket.create_connection(('127.0.0.1',int(port)),timeout=12)
    try:
        sock.sendall(b'\x05\x01\x00')
        if ssh.receive_exact(sock,2)!=b'\x05\x00': raise OSError('SOCKS authentication refused.')
        host=b'api.ipify.org'
        sock.sendall(b'\x05\x01\x00\x03'+bytes([len(host)])+host+b'\x01\xbb')
        reply=ssh.receive_exact(sock,4)
        if reply[1]!=0: raise OSError('Provider could not reach IP check service.')
        size={1:4,4:16}.get(reply[3])
        if reply[3]==3: size=ssh.receive_exact(sock,1)[0]
        if size is None: raise OSError('Invalid SOCKS reply.')
        ssh.receive_exact(sock,size+2)
        with ssl.create_default_context().wrap_socket(sock,server_hostname=host.decode()) as secure:
            secure.sendall(b'GET / HTTP/1.0\r\nHost: api.ipify.org\r\nConnection: close\r\n\r\n')
            data=b''
            while len(data)<16384:
                part=secure.recv(4096)
                if not part: break
                data+=part
        header,body=data.split(b'\r\n\r\n',1)
        if header.split(b'\r\n')[0].split()[1]!=b'200': raise OSError('IP check failed.')
        return str(ipaddress.ip_address(body.decode().strip()))
    finally: sock.close()
