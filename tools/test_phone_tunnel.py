"""Offline-controlled, bounded VLESS checks using already encrypted saved profiles."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from netcroc.core import data_folder
from netcroc import vless
REPORT=ROOT/'releases'/'tunnel-test-results.json'

def direct_ip():
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('https://api.ipify.org',timeout=8) as response:
        import ipaddress
        return str(ipaddress.ip_address(response.read(64).decode().strip()))

def check_profile(identifier):
    store=vless.ProfileStore(data_folder()/'vless'/'profiles')
    profile=store.load(identifier)
    # A free loopback port avoids colliding with the running GUI's proxy.
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    profile['routing']='socks';profile['local_port']=port
    session=vless.Session(data_folder()/'ssh'/'routing-core')
    result={'connected':False,'stages':{}}
    stages=result['stages']
    start=time.monotonic()
    try:
        addresses=socket.getaddrinfo(profile['host'],profile['port'],type=socket.SOCK_STREAM)
        stages['dns']={'ok':True,'elapsed_ms':round((time.monotonic()-start)*1000),'addresses':len(addresses)}
    except Exception as error:
        stages['dns']={'ok':False,'error_type':type(error).__name__};return result
    start=time.monotonic()
    try:
        sock=socket.create_connection((profile['host'],profile['port']),timeout=12)
        stages['tcp']={'ok':True,'elapsed_ms':round((time.monotonic()-start)*1000)}
    except Exception as error:
        stages['tcp']={'ok':False,'error_type':type(error).__name__};return result
    if profile['security']=='tls':
        start=time.monotonic()
        try:
            sock.settimeout(12)
            with ssl.create_default_context().wrap_socket(sock,server_hostname=profile['sni'] or profile['host']):
                stages['tls']={'ok':True,'elapsed_ms':round((time.monotonic()-start)*1000)}
        except ssl.SSLCertVerificationError as error:
            sock.close();stages['tls']={'ok':False,'error_type':type(error).__name__,'verify_code':error.verify_code}
        except Exception as error:
            sock.close();stages['tls']={'ok':False,'error_type':type(error).__name__}
    else:sock.close();stages['tls']={'ok':None,'note':'TLS probe is not applicable to this security mode.'}
    try:
        start=time.monotonic()
        session.start_profile(profile,identifier)
        stages['local_proxy']={'ok':True,'elapsed_ms':round((time.monotonic()-start)*1000)}
        start=time.monotonic()
        vless.proxy_ip(port)
        stages['tunnel_https']={'ok':True,'elapsed_ms':round((time.monotonic()-start)*1000)}
        result['connected']=True
    except Exception as error:
        result['error_type']=type(error).__name__
        stage='tunnel_https' if stages.get('local_proxy',{}).get('ok') else 'local_proxy'
        stages[stage]={'ok':False,'error_type':type(error).__name__,'elapsed_ms':round((time.monotonic()-start)*1000)}
    finally:session.stop()
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile-id');parser.add_argument('--preflight',action='store_true');parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args()
    if args.profile_id:
        try:print(json.dumps(check_profile(args.profile_id)))
        except Exception as error:print(json.dumps({'connected':False,'error_type':type(error).__name__}))
        return
    store=vless.ProfileStore(data_folder()/'vless'/'profiles')
    items=store.profiles()
    if not items:
        raise ValueError('No accessible saved VLESS profiles found. Import a link in NetCroc using this Windows account, then run the tester again.')
    core=vless.Session(data_folder()/'ssh'/'routing-core')
    try:core.verify()
    except (FileNotFoundError,ValueError):
        if args.preflight or not args.prepare:
            raise RuntimeError('Routing core missing or damaged. Run Test-Tunnel.bat while normal internet is connected to prepare it.') from None
        print('Preparing the verified routing core. Keep normal internet connected...',flush=True)
        try:core.install();core.verify()
        except Exception:
            raise RuntimeError('Could not prepare the routing core. Reconnect normal internet and run Test-Tunnel.bat again. The hotspot test has not started.') from None
    if args.preflight:print('Ready:',len(items),'saved profiles and verified local core. No network request was sent.');return
    print('NetCroc phone hotspot test\n')
    if len(items)>1:
        print('Saved VLESS profiles:')
        for number,(_,meta) in enumerate(items,1):print(f"  {number}. {meta['label']}")
        print('  0. Test all profiles')
        while True:
            choice=input('Choose a profile number (or 0 for all): ').strip()
            if choice.isdigit() and 0<=int(choice)<=len(items):break
            print('Enter one of the listed numbers.')
        if int(choice):items=[items[int(choice)-1]]
    print('This test uses small requests. It does not change system routes, DNS, or Wi-Fi.')
    print('It cannot prove which mobile data allowance is charged.')
    print('1. Note your normal-data balance and package balance.\n2. Connect this PC to the Honor hotspot.\n3. Avoid other internet activity during the test.')
    input('\nPress Enter when connected to the hotspot (Codex may be offline)... ')
    report={'tested_at':datetime.now().astimezone().isoformat(),'scope':'Manual phone-hotspot session; no network identity assumed','billing_verified':False,'dns_changed':False,'routes_changed':False,'profiles':[]}
    try:direct_ip();report['direct_internet']='working'
    except Exception as error:report['direct_internet']='unavailable';report['direct_error_type']=type(error).__name__
    REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Direct internet:',report['direct_internet'],flush=True)
    for identifier,meta in items:
        print('Testing',meta['label']+'...',flush=True)
        try:
            child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--profile-id',identifier],capture_output=True,text=True,timeout=75,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result=json.loads(child.stdout) if child.returncode==0 else {'connected':False,'error_type':'TestProcessFailed'}
        except subprocess.TimeoutExpired:result={'connected':False,'error_type':'TestTimeout'}
        except (ValueError,OSError):result={'connected':False,'error_type':'TestFailed'}
        report['profiles'].append({'name':meta['label'],**result})
        REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('  '+('PASS: public HTTPS IP request worked through the tunnel.' if result['connected'] else 'FAIL: tunnel did not carry the test request.'),flush=True)
        for stage,detail in result.get('stages',{}).items():
            print('   ',stage+':', 'OK' if detail.get('ok') is True else ('SKIPPED' if detail.get('ok') is None else detail.get('error_type','FAILED')),flush=True)
    report['finished']=True;REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('\nResults saved to:',REPORT)
    print('Check your balances again. Reconnect normal internet and tell Codex: test finished.')

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError) as error:
        print('Test could not start:',str(error));sys.exit(1)
    except FileNotFoundError as error:
        print('A required local file is missing:',error.filename or 'routing core / Python component')
        print('Run this tester from the main NetCroc releases folder while normal internet is connected.');sys.exit(1)
    except Exception as error:
        print('Test could not start:',type(error).__name__)
        print('Python:',sys.executable)
        print('App data folder:',data_folder())
        print('No Wi-Fi, DNS or route settings were changed.');sys.exit(1)
