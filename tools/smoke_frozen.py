"""Read-only frozen UI/DNS checks. Dummy watchdog state cannot mutate DNS."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

def write(path,value):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value),encoding='utf-8');temporary.replace(path)

def main():
    root=Path(__file__).resolve().parents[1];exe=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'releases'/'NetCroc.exe'
    output=root/'test-artifacts';output.mkdir(exist_ok=True)
    gui=output/'frozen-gui.json'
    result=subprocess.run([str(exe),'--diagnostics',str(gui)],timeout=150)
    assert result.returncode==0
    info=json.loads(gui.read_text(encoding='utf-8'));assert info.get('tabs')==9
    assert not any(info.get(key) for key in ('startup_changed','network_sent','capture_started','dns_changed','wifi_changed'))
    state=output/'frozen-watchdog.json';ready=state.with_suffix('.ready');token='read-only-packaged-watchdog-test'
    # Deliberately no original DNS configuration: even an unexpected timeout
    # would fail before reaching WindowsBackend.set, rather than touching a NIC.
    write(state,{'state':'pending','transaction':token})
    ready.unlink(missing_ok=True)
    child=subprocess.Popen([str(exe),'--dns-watch',str(state),token],
        env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'},creationflags=subprocess.CREATE_NO_WINDOW)
    became_ready=False
    try:
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            try:
                if json.loads(ready.read_text())['transaction']==token:
                    became_ready=True;break
            except (OSError,ValueError,KeyError):pass
            if child.poll() is not None:break
            time.sleep(.2)
    finally:
        write(state,{'state':'committed','transaction':token})
        try:code=child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            child.kill();raise RuntimeError('Frozen watchdog failed to exit')
    assert became_ready and code==0
    result={'gui':info,'watchdog_independent_startup_and_noop_exit':True,
            'dns_resolution_health_exit':'not run','actual_dns_mutation_tested':False,
            'wifi_changed':False,'uac_requested':False}
    write(output/'frozen-smoke.json',result)
    try:
        health_report=output/'frozen-dns-health.txt'
        health=subprocess.run([str(exe),'--dns-health','--dns-health-report',str(health_report)],timeout=90)
        assert health_report.read_text()==str(health.returncode)
        result['dns_resolution_health_exit']=health.returncode
    except subprocess.TimeoutExpired:
        result['dns_resolution_health_exit']='timeout';write(output/'frozen-smoke.json',result);raise
    write(output/'frozen-smoke.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
