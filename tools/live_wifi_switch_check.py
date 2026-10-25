"""Switch to a user-named saved profile, then restore; never read/report keys."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from netcroc.wifi import Wifi
from netcroc import dns
STATE=ROOT/'test-artifacts'/'wifi-switch-state.json'
REPORT=ROOT/'test-artifacts'/'wifi-switch-check.json'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target-profile');parser.add_argument('--restore-profile')
    args=parser.parse_args();wifi=Wifi()
    def wait_profile(item,seconds=25):
        end=time.monotonic()+seconds
        stable=0
        while time.monotonic()<end:
            if wifi.current(item['interface'])==item['profile']:
                stable+=1
                if stable>=6:return True
            else:stable=0
            time.sleep(.5)
        return False
    try:
        if args.restore_profile:
            for _ in range(60):
                time.sleep(1)
                try:
                    if json.loads(STATE.read_text()).get('state')=='done':return
                except (OSError,ValueError):pass
            original=next(p for p in wifi.profiles() if p['profile']==args.restore_profile)
            wifi.connect(original);wait_profile(original);return
        if not args.target_profile:raise ValueError('Choose a saved target profile.')
        profiles=wifi.profiles()
        original=next(p for p in profiles if p['connected'])
        target=next(p for p in profiles if p['profile']==args.target_profile)
        if target['profile']==original['profile']:raise ValueError('Target must differ from the current profile.')
        report={'baseline_dns_healthy':dns.WindowsBackend().healthy(),'state':'switching','keys_recorded':False}
        def save():REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
        save()
        if not report['baseline_dns_healthy']:raise OSError('Baseline DNS is unhealthy; no switch attempted.')
        dns.atomic(STATE,{'state':'running'})
        subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--restore-profile',original['profile']],creationflags=dns.FLAGS,close_fds=True)
        try:
            wifi.connect(target)
            report['alternate_connected']=wait_profile(target)
            if report['alternate_connected']:report['alternate_dns_healthy']=dns.WindowsBackend().healthy()
        except Exception as error:report['error_type']=type(error).__name__
        finally:
            wifi.connect(original)
            report['original_reconnected']=wait_profile(original)
            report['dns_healthy_after']=dns.WindowsBackend().healthy()
            if report['original_reconnected'] and report['dns_healthy_after']:dns.atomic(STATE,{'state':'done'})
            report['passed']=all(report.get(k) for k in ('alternate_connected','alternate_dns_healthy','original_reconnected','dns_healthy_after'))
            report['state']='finished';save()
    finally:wifi.close()

if __name__=='__main__':main()
