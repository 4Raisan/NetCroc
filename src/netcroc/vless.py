"""User-supplied VLESS profiles via the verified sing-box core, not an Xray executable."""
import base64
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
