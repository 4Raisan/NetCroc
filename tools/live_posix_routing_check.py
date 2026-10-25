"""Real Linux TUN checks inside a fresh network namespace, no external network."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import psutil
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from netcroc import ssh_routing as routing,ssh_tunnel as ssh,vless
from netcroc.platforms import run,ChildGuard
from test_ssh import Endpoint
CORE=Path(os.environ.get('NETCROC_LAB_CORE',str(ROOT/'test-artifacts/verified-routing-core')))


def port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def echo():
    with socket.create_connection(('198.18.0.1',8080),timeout=8) as sock:
        payload=b'isolated real TUN forwarding';sock.sendall(payload)
        assert ssh.receive_exact(sock,len(payload))==payload


def gone(name):
    end=time.monotonic()+15
    while time.monotonic()<end:
        if name not in psutil.net_if_addrs():return True
        time.sleep(.2)
    return False


def main():
    if sys.platform!='linux' or os.geteuid()!=0 or os.environ.get('NETCROC_ISOLATED_LAB')!='1':raise PermissionError('Only the explicitly isolated Linux root lab may run this tool.')
    if os.stat('/proc/self/ns/net').st_ino==os.stat('/proc/1/ns/net').st_ino:raise PermissionError('Refusing the host network namespace.')
    if not Path('/dev/net/tun').exists():raise OSError('TUN device is unavailable; this test did not run.')
    run(['ip','link','set','lo','up'])
    run(['ip','link','add','lab0','type','dummy'])
    run(['ip','addr','add','192.0.2.2/24','dev','lab0']);run(['ip','link','set','lab0','up'])
    run(['ip','route','add','default','dev','lab0'])
    endpoint=Endpoint(tls=True);session=ssh.Session();route=routing.Routing(CORE);client=None;server=None;job=None
    report=dict(isolated_namespace=True,external_network=False,provider_account=False)
    try:
        session.start(endpoint.profile())
        route.start(session.socks.port,['127.0.0.1']);echo()
        report['ssh_tun_data']=True;route.stop();report['ssh_cleanup']=gone('ncssh')
        server_port=port();user='12345678-1234-4234-9234-123456789abc'
        config={'log':{'level':'warn'},'inbounds':[{'type':'vless','listen':'127.0.0.1','listen_port':server_port,'users':[{'uuid':user}]}],
            'outbounds':[{'type':'socks','tag':'echo','server':'127.0.0.1','server_port':session.socks.port,'version':'5'}],'route':{'final':'echo'}}
        server=subprocess.Popen([str(CORE/'sing-box'),'run','-c','stdin'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        job=ChildGuard(server);server.stdin.write(json.dumps(config).encode());server.stdin.close();time.sleep(.3)
        profile=dict(host='127.0.0.1',port=server_port,uuid=user,security='none',routing='tun')
        client=vless.Session(CORE);client.start_profile(profile);echo()
        report['vless_tun_data']=True;client.stop();report['vless_cleanup']=gone('ncvless')
        code="import os,sys,json;sys.path.insert(0,sys.argv[1]);from netcroc.vless import Session;s=Session(sys.argv[2]);s.start_profile(json.loads(sys.argv[3]));os._exit(23)"
        result=subprocess.run([sys.executable,'-c',code,str(ROOT/'src'),str(CORE),json.dumps(profile)],timeout=50)
        assert result.returncode==23
        report['parent_crash_cleanup']=gone('ncvless')
        report['passed']=all(report.get(k) for k in ('ssh_tun_data','ssh_cleanup','vless_tun_data','vless_cleanup','parent_crash_cleanup'))
        (ROOT/'test-artifacts/isolated-posix-routing.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2));assert report['passed']
    finally:
        if client:client.stop()
        route.stop()
        if job:job.close()
        if server:server.wait(5)
        session.stop();endpoint.close()

if __name__=='__main__':main()
