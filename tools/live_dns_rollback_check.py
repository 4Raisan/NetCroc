"""Real Windows DNS mutation/restore with a deliberately failed post-apply check."""
import ctypes
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc import dns

def main():
    root=Path(__file__).resolve().parents[1]/'test-artifacts'
    report={'admin':bool(ctypes.windll.shell32.IsUserAnAdmin()),'failure_injection':'post-apply health check returns false; not a real resolver outage'}
    path=root/'live-dns-rollback-check.json'
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save()
    if not report['admin']:return
    adapter=next(a for a in dns.adapters() if 'wi-fi' in a['name'].lower())
    class FailingPostCheck(dns.WindowsBackend):
        calls=0
        def healthy(self):
            self.calls+=1
            return False if self.calls==2 else super().healthy()
    backend=FailingPostCheck();before=backend.snapshot(adapter)
    manager=dns.DnsManager(root/'live-forced-dns-restore.json',backend=backend)
    try:
        manager.apply(adapter,['1.1.1.1'])
        report['unexpected_success']=True
    except OSError:
        state=manager.load()
        report['rollback_state']=state['state'] if state else 'not started'
        report['health_calls']=backend.calls
    finally:
        manager.restore()
        report['original_restored']=backend.snapshot(adapter)==before
        report['dns_healthy_after']=dns.WindowsBackend().healthy()
        report['finished']=True;save()

if __name__=='__main__':main()
