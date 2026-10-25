"""Bounded real-provider WireGuard check. Never print or report private keys.

Uses the user's downloaded profile and NetCroc's encrypted vault/service backend.
An independent elevated watchdog disconnects after 240 seconds if this runner dies.
Public IPs are hashed in reports; only country codes and comparison results persist.
"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from netcroc import core,dns,vpn

REPORT=ROOT/'test-artifacts'/'live-provider-check.json'
STATE=ROOT/'test-artifacts'/'live-provider-guard.json'

def request(url):
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url,timeout=12) as response:
        return response.read(65536).decode()

def public_ip(v6=False):
    value=str(ipaddress.ip_address(request('https://api6.ipify.org' if v6 else 'https://api.ipify.org').strip()))
    if v6 and ipaddress.ip_address(value).version!=6:raise OSError('IPv6 endpoint did not return IPv6.')
    return value

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def stun_ipv4():
    transaction=os.urandom(12);magic=0x2112a442
    packet=struct.pack('!HHI',1,0,magic)+transaction
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.settimeout(5);sock.connect(('stun.cloudflare.com',3478));sock.send(packet)
        data=sock.recv(2048)
    if len(data)<20 or data[:2]!=b'\x01\x01' or data[8:20]!=transaction:raise OSError('Invalid STUN response.')
    length=int.from_bytes(data[2:4],'big');position=20
    while position+4<=min(len(data),20+length):
        kind,size=struct.unpack('!HH',data[position:position+4]);value=data[position+4:position+4+size]
        if kind==0x20 and len(value)>=8 and value[1]==1:
            raw=bytes(a^b for a,b in zip(value[4:8],struct.pack('!I',magic)))
            return socket.inet_ntop(socket.AF_INET,raw)
        position+=4+((size+3)//4)*4
    raise OSError('STUN mapped address unavailable.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile');parser.add_argument('--saved-id');parser.add_argument('--hold',type=int,default=0)
    parser.add_argument('--cleanup-name');args=parser.parse_args()
    backend=vpn.WindowsWireGuard();backend.require_admin()
    if args.cleanup_name:
        backend.runtime_path(args.cleanup_name)
        dns.atomic(STATE.with_suffix('.ready'),{'name':args.cleanup_name})
        for _ in range(240):
            time.sleep(1)
            try:
                state=json.loads(STATE.read_text())
                if state.get('name')!=args.cleanup_name or state.get('state')=='done':return
            except (OSError,ValueError):pass
        backend.disconnect(args.cleanup_name);return
    if not (args.profile or args.saved_id) or not 0<=args.hold<=90:raise ValueError('Provide a local profile and hold time between 0 and 90 seconds.')
    report={'real_provider':True,'state':'baseline','full_leak_audit':False}
    def save():REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save()
    try:
        inventory=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
            'Get-VM | Select-Object Name,State | ConvertTo-Json -Compress'],capture_output=True,text=True,timeout=15,creationflags=vpn.FLAGS)
        machines=json.loads(inventory.stdout or '[]') if inventory.returncode==0 else []
        if isinstance(machines,dict):machines=[machines]
        report['existing_vm_count']=len(machines)
        report['windows10_named_vm_available']=any('10' in m.get('Name','') and 'win' in m.get('Name','').lower() for m in machines)
    except Exception:report['vm_inventory']='unavailable'
    save()
    before=public_ip();report['baseline_ipv4_sha256']=digest(before)
    try:before6=public_ip(True);report['baseline_ipv6_available']=True
    except Exception:before6=None;report['baseline_ipv6_available']=False
    try:report['baseline_country']=json.loads(request('https://ipinfo.io/json')).get('country')
    except Exception:report['baseline_country']='unavailable'
    adapter=next(a for a in dns.adapters() if 'wi-fi' in a['name'].lower())
    original=dns.WindowsBackend().snapshot(adapter)
    store=vpn.ProfileStore(core.data_folder()/'wireguard'/'profiles')
    if args.saved_id:
        meta=next((p for p in store.profiles() if p['id']==args.saved_id),None)
        if not meta:raise ValueError('Saved provider profile was not found.')
        saved=json.loads(store._path(args.saved_id).read_text())
        import base64
        normalized=vpn.crypt(base64.b64decode(saved['protected'],validate=True),decrypt=True).decode()
    else:
        meta=store.import_file(args.profile)
        normalized,_=vpn.parse_config(Path(args.profile).read_text(encoding='utf-8-sig'))
    identifier=meta['id'];name=vpn.tunnel_name(identifier)
    report['saved_profile_id']=identifier
    report['profile_has_ipv6_default']='::/0' in normalized
    dns.atomic(STATE,{'name':name,'state':'running'})
    ready=STATE.with_suffix('.ready');ready.unlink(missing_ok=True)
    subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--cleanup-name',name],creationflags=vpn.FLAGS,close_fds=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        if ready.exists() and json.loads(ready.read_text()).get('name')==name:break
        time.sleep(.1)
    else:raise OSError('Provider disconnect guard did not start; no connection attempted.')
    try:
        report['state']='connecting';save();store.connect(identifier)
        for _ in range(30):
            status=backend.status(name)
            if status['handshake'].endswith('s ago'):break
            time.sleep(.5)
        report['handshake']=backend.status(name)['handshake'];save()
        after=public_ip();report['vpn_ipv4_sha256']=digest(after);report['ipv4_changed']=after!=before
        try:report['vpn_country']=json.loads(request('https://ipinfo.io/json')).get('country')
        except Exception:report['vpn_country']='unavailable'
        try:
            after6=public_ip(True);report['vpn_ipv6_available']=True
            report['vpn_ipv6_sha256']=digest(after6)
            report['baseline_ipv6_exposed']=before6 is not None and after6==before6
        except Exception as error:
            report['vpn_ipv6_available']=False;report['ipv6_error_type']=type(error).__name__
        try:
            mapped=stun_ipv4();report['udp_stun_succeeded']=True
            report['udp_uses_vpn_ipv4']=mapped==after;report['udp_exposes_baseline_ipv4']=mapped==before
        except Exception as error:report['udp_stun_error_type']=type(error).__name__
        report['system_dns_healthy']=dns.WindowsBackend().healthy()
        report['state']='ready for browser checks';save()
        end=time.monotonic()+args.hold
        while time.monotonic()<end:
            if (ROOT/'test-artifacts'/'provider-browser-done').exists():break
            time.sleep(1)
    except Exception as error:report['error_type']=type(error).__name__
    finally:
        try:
            store.disconnect(identifier)
            report['service_removed']=backend.state(name)=='not installed'
            report['encrypted_runtime_removed']=not backend.runtime_path(name).exists()
            if report['service_removed']:dns.atomic(STATE,{'name':name,'state':'done'})
        except Exception as error:report['cleanup_error_type']=type(error).__name__
        report['physical_adapter_dns_restored']=dns.WindowsBackend().snapshot(adapter)==original
        try:report['baseline_ipv4_restored']=public_ip()==before
        except Exception:report['baseline_ipv4_restored']=False
        report['dns_healthy_after']=dns.WindowsBackend().healthy();report['state']='finished';save()

if __name__=='__main__':main()
