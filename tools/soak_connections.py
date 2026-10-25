"""Bounded local reconnection soak. No provider credentials or OS route changes."""
import argparse
from collections import Counter
import gc
import json
from pathlib import Path
import sys
import time
import unittest
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_vless import VlessTests
from test_ssh import SSHTests

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=180)
    args=parser.parse_args()
    if not 30<=args.seconds<=3600:raise ValueError('Use 30–3600 seconds.')
    methods=[(VlessTests,'test_native_vless_tls_forwarding_and_wrong_uuid'),
        (VlessTests,'test_native_websocket_tls_forwarding_and_wrong_uuid'),
        (VlessTests,'test_native_grpc_tls_forwarding_and_wrong_uuid'),
        (VlessTests,'test_native_httpupgrade_tls_forwarding_and_wrong_uuid'),
        (VlessTests,'test_native_reality_handshake_and_invalid_credentials'),
        (VlessTests,'test_native_reality_vision_handshake'),
        (SSHTests,'test_tls_ca_sni_and_pre_post_payload'),
        (SSHTests,'test_tls_parallel_channels'),
        (SSHTests,'test_server_loss_stops_proxy')]
    process=psutil.Process();baseline_handles=process.num_handles();baseline_rss=process.memory_info().rss
    started=time.monotonic();counts=Counter();errors=[];index=0
    output=ROOT/'test-artifacts'/'connection-soak.json'
    while time.monotonic()-started<args.seconds:
        cls,name=methods[index%len(methods)];index+=1
        result=unittest.TestResult();cls(name).run(result)
        if result.skipped:errors.append({'test':name,'kind':'skipped'})
        if result.errors or result.failures:
            errors.append({'test':name,'kind':'failure','synthetic_test_tracebacks':[detail for _,detail in result.errors+result.failures]})
        counts[name]+=1;gc.collect()
        report={'requested_seconds':args.seconds,'elapsed_seconds':round(time.monotonic()-started,2),
            'completed_cases':sum(counts.values()),'cases':dict(counts),'errors':errors,
            'handles_baseline':baseline_handles,'handles_current':process.num_handles(),
            'rss_baseline':baseline_rss,'rss_current':process.memory_info().rss,
            'remaining_children':len(process.children(recursive=True)), 'finished':False}
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        if errors:break
    gc.collect();time.sleep(1)
    report.update(finished=True,remaining_children=len(process.children(recursive=True)),handles_final=process.num_handles())
    report['passed']=not errors and not report['remaining_children'] and report['handles_final']<=baseline_handles+32
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
