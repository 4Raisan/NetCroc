"""Run the real 90-second DNS watchdog after a simulated applying-process crash.

Parent supervises the actual independent watchdog and restores in finally if
needed. No timer is shortened, and no restore callback is mocked.
"""
import ctypes
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from netcroc import dns

STATE=ROOT/'test-artifacts'/'live-timeout-dns-state.json'
REPORT=ROOT/'test-artifacts'/'live-dns-timeout-check.json'

def main():
    if not ctypes.windll.shell32.IsUserAnAdmin():raise PermissionError('Administrator access required.')
    if '--crash-child' in sys.argv:
        state=dns.DnsManager(STATE).load()
        dns.WindowsBackend().set(state['original'],['1.1.1.1'])
        # Deliberately bypass cleanup, as if the applying app had crashed.
        os._exit(23)
    adapter=next(a for a in dns.adapters() if 'wi-fi' in a['name'].lower())
    manager=dns.DnsManager(STATE)
    existing=manager.load()
    if existing and existing['state']=='pending':raise ValueError('A pending lab transaction already exists.')
    original=manager.backend.snapshot(adapter)
    if not manager.backend.healthy():raise OSError('Baseline resolver is unhealthy; no test change made.')
    dns.query('1.1.1.1','example.com')
    report={'admin':True,'watchdog_seconds':90,'state':'preparing','original_restored':False}
    def save():REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save()
    try:
        dns.atomic(STATE,{'state':'pending','original':original,'servers':['1.1.1.1'],
            'created':time.time(),'transaction':secrets.token_hex(16)})
        manager.launch_guard()
        started=time.monotonic()
        child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--crash-child'],timeout=25,creationflags=dns.FLAGS)
        report.update(state='waiting for independent watchdog',applying_process_exit=child.returncode)
        save()
        if child.returncode!=23:raise OSError('The synthetic applying process did not reach its simulated crash.')
        while time.monotonic()-started<120:
            if manager.load()['state']=='restored':break
            time.sleep(1)
        elapsed=time.monotonic()-started
        report.update(elapsed_seconds=round(elapsed,2),watchdog_restored=manager.load()['state']=='restored',
            original_restored=manager.backend.snapshot(adapter)==original)
        report['passed']=report['watchdog_restored'] and report['original_restored'] and elapsed>=85
    except Exception as error:report['error_type']=type(error).__name__
    finally:
        manager.restore()
        report['original_restored_after_cleanup']=manager.backend.snapshot(adapter)==original
        report['dns_healthy_after']=manager.backend.healthy();report['state']='finished';save()

if __name__=='__main__':main()
