"""Bounded administrator checks. No credentials or Wi-Fi passwords in reports."""
import argparse
import ctypes
import json
import os
import ipaddress
from collections import defaultdict
from pathlib import Path
import socket
import sys
import time
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.traffic import Traffic
from netcroc import dns
from netcroc.wifi import Wifi

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',required=True)
    parser.add_argument('--dns-wifi',action='store_true')
    args=parser.parse_args()
    report={'admin':bool(ctypes.windll.shell32.IsUserAnAdmin()),'dns_changed':False,'wifi_reconnected':False}
    target=Path(args.report)
    def save(): target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save()
    if not report['admin']: return 2
    class DiagnosticTraffic(Traffic):
        def __init__(self):
            self.summary=defaultdict(lambda:[0,0]);super().__init__()
        def _event(self,ptr):
            try:
                event=ptr.contents.header.id
                if event in (10,11,26,27,42,43,58,59):
                    pid=int.from_bytes(self._property(ptr,'PID',4),'little')
                    size=int.from_bytes(self._property(ptr,'size',4),'little')
                    n=16 if event in (26,27,58,59) else 4
                    source=ipaddress.ip_address(self._property(ptr,'saddr',n)).is_global
                    destination=ipaddress.ip_address(self._property(ptr,'daddr',n)).is_global
                    group=f'{event}:own={pid==os.getpid()}:source_global={source}:destination_global={destination}'
                    self.summary[group][0]+=1;self.summary[group][1]+=size
            except Exception:pass
            super()._event(ptr)
    capture=DiagnosticTraffic()
    try:
        report['capture_started']=capture.start();save()
        if report['capture_started']:
            time.sleep(1)
            try:
                # Small public download; does not upload personal information.
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open('https://www.rfc-editor.org/rfc/rfc9110.txt',timeout=15) as response:
                    report['download_payload_bytes']=len(response.read(262145))
            except Exception as error: report['download_error']=type(error).__name__
            try:
                payload=b'netcroc-synthetic-test-'*3000
                request=urllib.request.Request('https://httpbingo.org/post',data=payload,headers={'Content-Type':'text/plain'})
                with opener.open(request,timeout=15) as response:
                    result=json.loads(response.read(262144))
                    report['upload_payload_bytes']=len(payload)
                    report['upload_echo_verified']=result.get('data')==payload.decode()
            except Exception as error: report['upload_error']=type(error).__name__
            for host in ('1.1.1.1','8.8.8.8'):
                try: dns.query(host,'example.com')
                except Exception: pass
            time.sleep(3)
            values=capture.drain()
            own=[value for (pid,local),value in values.items() if pid==os.getpid()]
            report['own_download_bytes']=sum(v[0] for v in own)
            report['own_upload_bytes']=sum(v[1] for v in own)
            report['events']=capture.events;report['decode_errors']=capture.errors;report['lost']=capture.lost
            report['capture_status']=capture.status
            report['event_shape_summary']=dict(capture.summary)
    finally: capture.close();save()
    if args.dns_wifi:
        manager=dns.DnsManager(target.with_name('live-dns-restore.json'))
        adapter=next((item for item in dns.adapters() if 'wi-fi' in item['name'].lower()),None)
        if adapter:
            original=manager.backend.snapshot(adapter)
            report['dns_baseline_healthy']=manager.backend.healthy();save()
            try:
                manager.apply(adapter,['1.1.1.1'])
                report['dns_changed']=True
                report['dns_applied_healthy']=manager.backend.healthy()
            finally:
                manager.restore()
                report['dns_original_restored']=manager.backend.snapshot(adapter)==original
                report['dns_restored_healthy']=manager.backend.healthy();save()
        wifi=Wifi()
        try:
            connected=next((p for p in wifi.profiles() if p['connected']),None)
            if connected:
                # Reconnect only the current saved profile; never forget or expose its key.
                wifi.connect(connected)
                for _ in range(30):
                    time.sleep(1)
                    if wifi.current(connected['interface'])==connected['profile'] and dns.WindowsBackend().healthy():
                        report['wifi_reconnected']=True;break
                save()
        finally: wifi.close()
    report['finished']=True;save()
    return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as error:
        # Do not serialize exceptions containing system/provider configuration.
        args=sys.argv
        if '--report' in args:
            path=Path(args[args.index('--report')+1])
            data=json.loads(path.read_text()) if path.exists() else {}
            data['error_type']=type(error).__name__;path.write_text(json.dumps(data,indent=2))
        raise
