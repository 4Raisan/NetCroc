"""macOS and Linux native command backends; commands are argument lists, never shells."""
from collections import defaultdict
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time
from types import SimpleNamespace
import psutil

NATIVE_PATH=os.pathsep.join([os.environ.get('PATH',''),'/opt/homebrew/bin','/usr/local/bin','/usr/bin','/bin','/usr/sbin','/sbin'])
def tool(name):return shutil.which(name,path=NATIVE_PATH)
from .platforms import MAC,run,require_admin,data_folder,admin,elevated_native

def default_interface():
    if MAC:
        text=run(['/sbin/route','-n','get','default'])
        match=re.search(r'interface:\s*(\S+)',text)
        if not match:raise OSError('No default interface.')
        return match[1]
    routes=json.loads(run(['ip','-j','route','get','1.1.1.1']))
    return routes[0]['dev']

def mac_services():
    text=run(['/usr/sbin/networksetup','-listnetworkserviceorder'])
    services={};name=None
    for line in text.splitlines():
        match=re.match(r'^\(\d+\) (.+)$',line)
        if match:name=match[1]
        match=re.search(r'Device: ([^)]+)',line)
        if match and name:services[match[1]]=name
    return services

def adapters():
    active={n for n,s in psutil.net_if_stats().items() if s.isup and n not in ('lo','lo0')}
    if MAC:
        return [dict(index=socket.if_nametoindex(dev),name=service,guid=dev,servers=[],device=dev) for dev,service in mac_services().items() if dev in active]
    if not tool('nmcli'):raise OSError('DNS/Wi-Fi management requires NetworkManager (nmcli). Adapter traffic still works.')
    result=[]
    for dev in sorted(active):
        connection=run(['nmcli','-g','GENERAL.CON-UUID','device','show',dev])
        if not connection or connection=='--':continue
        servers=run(['nmcli','-g','IP4.DNS','device','show',dev]).splitlines()
        result.append(dict(index=socket.if_nametoindex(dev),name=dev,guid=connection,servers=servers,device=dev))
    return result

class DnsBackend:
    def snapshot(self,adapter):
        value=dict(adapter)
        if MAC:
            raw=run(['/usr/sbin/networksetup','-getdnsservers',adapter['name']])
            servers=[]
            for token in raw.split():
                try:servers.append(str(ipaddress.ip_address(token)))
                except ValueError:pass
            value.update(servers=servers,manual=bool(servers))
        else:
            servers=run(['nmcli','-g','ipv4.dns','connection','show','uuid',adapter['guid']])
            ignore=run(['nmcli','-g','ipv4.ignore-auto-dns','connection','show','uuid',adapter['guid']])
            value.update(servers=[str(ipaddress.ip_address(v)) for v in re.split(r'[,\s]+',servers) if v],manual=True,ignore_auto=ignore=='yes')
        return value
    def set(self,original,servers):
        if not admin():return elevated_native('dns-set',dict(original=original,servers=servers))
        require_admin()
        servers=[str(ipaddress.ip_address(s)) for s in servers]
        if MAC:
            run(['/usr/sbin/networksetup','-setdnsservers',original['name'],*(servers or ['Empty'])])
        else:
            # A rollback passes the exact original DNS list, including an empty list.
            restoring=servers==original['servers']
            ignore=original.get('ignore_auto',False) if restoring else bool(servers)
            run(['nmcli','connection','modify','uuid',original['guid'],'ipv4.dns',','.join(servers),'ipv4.ignore-auto-dns','yes' if ignore else 'no'])
            run(['nmcli','device','reapply',original['device']])
    def healthy(self):
        import sys
        args=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parents[1]/'app.py')])
        try:return subprocess.run(args+['--dns-health'],timeout=20).returncode==0
        except (OSError,subprocess.TimeoutExpired):return False

class Wifi:
    def __init__(self):
        if not MAC and not tool('nmcli'):raise OSError('Saved Wi-Fi requires NetworkManager (nmcli).')
    def interfaces(self):
        if MAC:
            text=run(['/usr/sbin/networksetup','-listallhardwareports'])
            return [SimpleNamespace(guid=m[1],description=m[1]) for m in re.findall(r'Hardware Port: (Wi-Fi|AirPort)\nDevice: (\S+)',text)]
        result=[]
        for dev in psutil.net_if_addrs():
            if Path('/sys/class/net',dev,'wireless').exists():result.append(SimpleNamespace(guid=dev,description=dev))
        return result
    def current(self,interface,strict=False):
        dev=str(interface.guid)
        if MAC:
            raw=run(['/usr/sbin/networksetup','-getairportnetwork',dev])
            return raw.split(': ',1)[1] if raw.startswith('Current Wi-Fi Network: ') else ''
        field='GENERAL.CON-UUID' if strict else 'GENERAL.CONNECTION'
        value=run(['nmcli','-g',field,'device','show',dev])
        if not strict and not run(['nmcli','-g','GENERAL.STATE','device','show',dev]).startswith('100'):return ''
        return value if value!='--' else ''
    def profiles(self):
        result=[]
        for interface in self.interfaces():
            current=self.current(interface,strict=not MAC)
            if MAC:
                names=[line.strip() for line in run(['/usr/sbin/networksetup','-listpreferredwirelessnetworks',interface.guid]).splitlines()[1:] if line.strip()]
                for name in names:result.append(dict(profile=name,ssid=name,interface=interface,connected=current==name,password='Use Reveal selected; Keychain approval may be required',auth='Saved Wi-Fi'))
            else:
                identifiers=run(['nmcli','-g','UUID','connection','show']).splitlines()
                for identifier in identifiers:
                    kind=run(['nmcli','-g','connection.type','connection','show','uuid',identifier])
                    if kind!='802-11-wireless':continue
                    name=run(['nmcli','-g','connection.id','connection','show','uuid',identifier])
                    ssid=run(['nmcli','-g','802-11-wireless.ssid','connection','show','uuid',identifier])
                    result.append(dict(profile=name,uuid=identifier,ssid=ssid,interface=interface,connected=current==identifier,password='Use Reveal selected; OS permission may be required',auth='Saved Wi-Fi'))
        return result
    def password(self,item):
        if MAC:return run(['/usr/bin/security','find-generic-password','-D','AirPort network password','-a',item['ssid'],'-w'])
        return run(['nmcli','--show-secrets','-g','802-11-wireless-security.psk','connection','show','uuid',item['uuid']]) or 'No stored personal password'
    def connect(self,item):
        if MAC:run(['/usr/sbin/networksetup','-setairportnetwork',item['interface'].guid,item['ssid']])
        else:run(['nmcli','connection','up','uuid',item['uuid'],'ifname',item['interface'].guid])
    def forget(self,item):
        current=self.current(item['interface'],strict=True)
        if current==item.get('uuid',item['profile']):raise ValueError('The active Wi-Fi profile cannot be forgotten.')
        if MAC:run(['/usr/sbin/networksetup','-removepreferredwirelessnetwork',item['interface'].guid,item['ssid']])
        else:run(['nmcli','connection','delete','uuid',item['uuid']])
    def close(self):pass

class WireGuard:
    def installed(self):return Path(tool('wg-quick')) if tool('wg-quick') and tool('wg') else None
    def require_admin(self):pass  # Individual operations use the OS authorization dialog.
    def short(self,name):
        if not re.fullmatch(r'NetCroc-[0-9a-f]{20}',name):raise ValueError('Invalid NetCroc tunnel name.')
        return 'nc'+name[8:20]
    def runtime_path(self,name):return Path('/var/run/netcroc' if MAC else '/run/netcroc')/(self.short(name)+'.conf')
    def native_name(self,name):
        short=self.short(name)
        if MAC:
            try:return Path('/var/run/wireguard',short+'.name').read_text().strip()
            except FileNotFoundError:return short
        return short
    def state(self,name):
        native=self.native_name(name)
        if native in psutil.net_if_addrs():return 'running'
        return 'not installed'
    def status(self,name):
        info=dict(service=self.state(name),handshake='Not checked')
        if info['service']=='running':
            try:
                stamps=[int(line.split()[1]) for line in run(['wg','show',self.native_name(name),'latest-handshakes']).splitlines() if len(line.split())==2]
                latest=max(stamps,default=0)
                info['handshake']=f'{max(0,int(time.time())-latest)}s ago' if latest else 'No handshake yet'
            except OSError:info['handshake']='Root permission required'
        return info
    def connect(self,name,text):
        from .vpn import parse_config
        text,_=parse_config(text)
        if not admin():return elevated_native('wg-connect',dict(name=name,text=text))
        require_admin()
        if not self.installed():raise OSError('Install wireguard-tools / wg-quick first. macOS also needs wireguard-go; DNS may require resolvconf.')
        if self.state(name)!='not installed':raise ValueError('Disconnect the existing tunnel first.')
        path=self.runtime_path(name)
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if path.parent.is_symlink() or path.parent.stat().st_uid!=0 or path.parent.stat().st_mode & 0o077:raise PermissionError('Runtime folder must be root-owned and mode 0700.')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(fd,'w') as file:file.write(text)
        try:run([self.installed(),'up',path],timeout=45)
        except Exception:
            try:run([self.installed(),'down',path],timeout=30)
            except OSError:pass
            if self.state(name)=='not installed':path.unlink(missing_ok=True)
            raise
        return self.status(name)
    def disconnect(self,name):
        if not admin():return elevated_native('wg-disconnect',dict(name=name))
        require_admin();path=self.runtime_path(name)
        if self.state(name)=='running':
            if not path.is_file():raise OSError('Runtime configuration missing; use native WireGuard recovery.')
            run([self.installed(),'down',path],timeout=45)
        if self.state(name)!='not installed':raise OSError('Tunnel is still active; recovery configuration preserved.')
        path.unlink(missing_ok=True)
        return self.status(name)

class Traffic:
    """Optional TShark IP payload attribution. Metadata only; no capture files."""
    def __init__(self):
        self.pending=defaultdict(lambda:[0,0]);self.lock=threading.Lock();self.closed=False
        self.process=None;self.events=self.errors=self.lost=0;self.status='Not started'
    def start(self):
        if not tool('tshark'):raise OSError('Per-app capture requires TShark and capture permissions. Adapter totals work without it.')
        self.interface=default_interface()
        args=[tool('tshark'),'-n','-l','-i',self.interface,'-s','256','-f','tcp or udp','-T','fields','-E','occurrence=f']
        for field in ('ip.src','ipv6.src','ip.dst','ipv6.dst','tcp.srcport','udp.srcport','tcp.dstport','udp.dstport','tcp.len','udp.length'):args+=['-e',field]
        self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        from .platforms import ChildGuard
        self.guard=ChildGuard(self.process)
        self.status='TShark TCP/UDP payload attribution on '+self.interface+'; short-lived/unresolved sockets omitted; capture loss unavailable'
        self.thread=threading.Thread(target=self.consume,daemon=True);self.thread.start();return True
    def consume(self):
        mapping={};local=set();at=0
        try:
            for line in self.process.stdout:
                if self.closed:break
                if time.monotonic()-at>1:
                    mapping=socket_map(psutil.net_connections(kind='inet'))
                    local={a.address.split('%')[0] for values in psutil.net_if_addrs().values() for a in values if a.family in (socket.AF_INET,socket.AF_INET6)};at=time.monotonic()
                self.account(line,mapping,local)
        except (OSError,psutil.Error):self.errors+=1
        finally:
            self.status='Per-app capture stopped or permission denied; captured history is incomplete'
            if self.process and self.process.poll() is None:self.process.terminate()
    def account(self,line,mapping,local):
        try:
            f=line.rstrip('\n').split('\t')
            if len(f)!=10:return
            src=f[0] or f[1];dst=f[2] or f[3];tcp=bool(f[4]);sport=int(f[4] or f[5]);dport=int(f[6] or f[7])
            down=dst in local;address=dst if down else src;remote=src if down else dst
            if address not in local or not ipaddress.ip_address(remote).is_global:return
            lport=dport if down else sport;rport=sport if down else dport
            pid=mapping.get((tcp,address,lport,remote,rport))
            if pid is None:pid=mapping.get((tcp,address,lport,'',0))
            if pid is None:return
            size=int(f[8]) if tcp else max(0,int(f[9])-8)
            with self.lock:self.pending[(pid,address)][0 if down else 1]+=size;self.events+=1
        except (ValueError,IndexError):self.errors+=1
    def drain(self):
        with self.lock:value=dict(self.pending);self.pending.clear();return value
    def close(self):
        self.closed=True
        if self.process and self.process.poll() is None:self.process.terminate()
        if hasattr(self,'guard'):self.guard.close()
        if self.process:
            try:self.process.wait(5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.process.stdout.close()
        if hasattr(self,'thread'):self.thread.join(2)

def socket_map(connections):
    result={};ambiguous=set()
    for c in connections:
        if not c.pid or not c.laddr:continue
        remote=c.raddr or ('',0)
        key=(c.type==socket.SOCK_STREAM,c.laddr[0],c.laddr[1],remote[0],remote[1])
        if key in result and result[key]!=c.pid:ambiguous.add(key)
        result[key]=c.pid
    for key in ambiguous:result.pop(key,None)
    return result
