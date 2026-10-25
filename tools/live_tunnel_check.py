"""Administrator lab: synthetic local VLESS server, bounded whole-PC routing test.

No provider account is created. A local server exits through the existing Wi-Fi;
public IP equality is expected. Independent job lifetimes contain both children.
"""
import ctypes
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from netcroc import vless,dns
from netcroc.ssh_routing import ChildJob,HIDDEN
from test_ssh import Endpoint

def main():
    crash='--crash' in sys.argv
    path=ROOT/'test-artifacts'/('live-tunnel-crash.json' if crash else 'live-tunnel-check.json')
    report={'admin':bool(ctypes.windll.shell32.IsUserAnAdmin()),'real_provider':False}
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save()
    if not report['admin']:return
    adapter=next(a for a in dns.adapters() if 'wi-fi' in a['name'].lower())
    before=dns.WindowsBackend().snapshot(adapter)
    def ip():
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('https://api.ipify.org',timeout=12) as response:
            return response.read(100).decode().strip()
    baseline=ip()
    report['baseline_ip_available']=bool(baseline);save()
    fixture=Endpoint(tls=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    core=ROOT/'test-artifacts'/'verified-routing-core'
    server={'log':{'level':'warn'},'inbounds':[{'type':'vless','listen':'127.0.0.1','listen_port':port,
        'users':[{'uuid':'12345678-1234-4234-9234-123456789abc'}],
        'tls':{'enabled':True,'certificate_path':str(Path(fixture.folder.name)/'cert.pem'),'key_path':str(Path(fixture.folder.name)/'key.pem')}}],
        'outbounds':[{'type':'direct','tag':'direct','bind_interface':adapter['name']}]}
    process=None;job=None;session=vless.Session(core)
    deadline=threading.Timer(50,session.stop);deadline.daemon=True
    try:
        process=subprocess.Popen([str(core/'sing-box.exe'),'run','-c','stdin'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=HIDDEN)
        job=ChildJob(process);process.stdin.write(json.dumps(server).encode());process.stdin.close();time.sleep(.3)
        deadline.start()
        profile={'host':'127.0.0.1','port':port,'uuid':'12345678-1234-4234-9234-123456789abc','security':'tls','sni':'localhost','ca_pem':fixture.ca,'routing':'tun'}
        report['stage']='starting TUN';save()
        session.start_profile(profile)
        report['tun_ready']=session.active;report['stage']='testing HTTPS';save()
        if crash:
            report['simulated_parent_exit']=True;save()
            os._exit(23)
        current=ip()
        report['https_through_tunnel']=bool(current)
        report['same_ip_as_local_exit_expected']=current==baseline
        report['dns_healthy_during_tunnel']=dns.WindowsBackend().healthy();save()
    except Exception as error:
        report['error_type']=type(error).__name__
        # These operations use synthetic data only, but still avoid dumping configs.
    finally:
        session.stop();deadline.cancel()
        if job:job.close()
        if process:
            if process.poll() is None:process.terminate()
            process.wait(timeout=5)
        fixture.close()
        import psutil
        for _ in range(30):
            if 'NetCrocVLESS' not in psutil.net_if_addrs():break
            time.sleep(.2)
        report['tun_removed']='NetCrocVLESS' not in psutil.net_if_addrs()
        report['original_dns_restored']=dns.WindowsBackend().snapshot(adapter)==before
        report['dns_healthy_after']=dns.WindowsBackend().healthy()
        report['finished']=True;save()

if __name__=='__main__':main()
