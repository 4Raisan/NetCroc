"""Synthetic local WireGuard service/handshake/byte test, no default routes or DNS."""
import base64
import ctypes
import json
import os
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization
from netcroc.vpn import WindowsWireGuard
from netcroc.ssh_routing import ChildJob,HIDDEN

NAME='NetCroc-'+('a'*20)

def main():
    backend=WindowsWireGuard()
    if '--cleanup' in sys.argv:
        time.sleep(60);backend.disconnect(NAME);return
    path=ROOT/'test-artifacts'/'live-wireguard-check.json'
    report={'admin':bool(ctypes.windll.shell32.IsUserAnAdmin()),'real_provider':False,'default_route_changed':False,'dns_changed':False}
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save()
    if not report['admin'] or not backend.installed():report['installed']=bool(backend.installed());save();return
    if backend.state(NAME)!='not installed':raise ValueError('Synthetic test service already exists; refusing to replace it.')
    def keypair():
        key=X25519PrivateKey.generate()
        private=key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
        public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        return base64.b64encode(private).decode(),base64.b64encode(public).decode()
    server_private,server_public=keypair();client_private,client_public=keypair()
    def udp_port():
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
    server_port=udp_port();client_port=udp_port()
    server={'log':{'level':'warn'},'endpoints':[{'type':'wireguard','tag':'lab-wg','system':False,
        'address':['10.254.97.1/24'],'private_key':server_private,'listen_port':server_port,
        'peers':[{'address':'127.0.0.1','port':client_port,'public_key':client_public,'allowed_ips':['10.254.97.2/32']}]}],
        'outbounds':[{'type':'direct','tag':'direct'}],
        'route':{'rules':[{'inbound':'lab-wg','action':'route','outbound':'direct','override_address':'127.0.0.1'}],'final':'direct'}}
    exe=ROOT/'test-artifacts'/'verified-routing-core'/'sing-box.exe'
    check=subprocess.run([str(exe),'check','-c','stdin'],input=json.dumps(server),text=True,capture_output=True,timeout=15,creationflags=HIDDEN)
    if check.returncode:report['server_config_rejected']=True;save();return
    # Guard is an independent elevated process before any service is installed.
    subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--cleanup'],creationflags=HIDDEN,close_fds=True)
    class Echo(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                while True:
                    data=self.request.recv(65536)
                    if not data:break
                    self.request.sendall(data)
            except OSError:pass
    echo=socketserver.ThreadingTCPServer(('127.0.0.1',0),Echo);echo.daemon_threads=True
    threading.Thread(target=echo.serve_forever,daemon=True).start()
    process=None;job=None
    try:
        process=subprocess.Popen([str(exe),'run','-c','stdin'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=HIDDEN)
        job=ChildJob(process);process.stdin.write(json.dumps(server).encode());process.stdin.close();time.sleep(.3)
        config=f'[Interface]\nPrivateKey = {client_private}\nAddress = 10.254.97.2/32\nListenPort = {client_port}\n[Peer]\nPublicKey = {server_public}\nAllowedIPs = 10.254.97.1/32\nEndpoint = 127.0.0.1:{server_port}\nPersistentKeepalive = 5\n'
        report['stage']='installing synthetic service';save()
        report['service_result']=backend.connect(NAME,config);save()
        for _ in range(20):
            state=backend.status(NAME)
            if state['handshake'].endswith('s ago'):break
            time.sleep(.5)
        report['status']=backend.status(NAME);save()
        with socket.create_connection(('10.254.97.1',echo.server_address[1]),timeout=8) as sock:
            payload=b'wireguard local encrypted echo'*100
            sock.sendall(payload);received=b''
            while len(received)<len(payload):
                part=sock.recv(len(payload)-len(received))
                if not part:break
                received+=part
            report['echo_verified']=received==payload
            report['payload_bytes']=len(payload)
    except Exception as error:
        report['error_type']=type(error).__name__
    finally:
        try:
            backend.disconnect(NAME)
            report['service_removed']=backend.state(NAME)=='not installed'
            report['encrypted_runtime_removed']=not backend.runtime_path(NAME).exists()
        except Exception as error:report['cleanup_error']=type(error).__name__
        if job:job.close()
        if process:
            if process.poll() is None:process.terminate()
            process.wait(timeout=5)
        echo.shutdown();echo.server_close()
        report['finished']=True;save()

if __name__=='__main__':main()
