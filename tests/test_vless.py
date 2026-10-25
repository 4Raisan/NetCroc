"""Synthetic accounts; optional real sing-box loopback forwarding. No TUN routes."""
import json
import base64
import ssl
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc import vless
from netcroc.ssh_routing import ChildJob,HIDDEN
from netcroc.ssh_tunnel import receive_exact
from test_ssh import Endpoint

ROOT=Path(__file__).resolve().parents[1]
CORE=ROOT/'test-artifacts'/'verified-routing-core'
USER='12345678-1234-4234-9234-123456789abc'

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

class VlessTests(unittest.TestCase):
    def profile(self,**values):
        return vless.validate({'host':'127.0.0.1','uuid':USER,'security':'none','local_port':port()}|values)


    def test_import_link_tls_sni_websocket(self):
        value=vless.parse_link(f'vless://{USER}@server.example:443?encryption=none&security=tls&sni=tls.example&type=ws&path=%2Fsocket&host=cdn.example#My%20VPN')
        self.assertEqual(value['label'],'My VPN');self.assertEqual(value['path'],'/socket')
        out=vless.outbound(value);self.assertEqual(out['tls']['server_name'],'tls.example')
        self.assertEqual(out['transport']['headers'],{'Host':'cdn.example'})


    def test_invalid_links_never_echo_credentials(self):
        for suffix in ('allowInsecure=1','type=xhttp','type=ws&type=tcp','encryption=aes','headerType=http'):
            with self.assertRaises(ValueError) as caught:vless.parse_link(f'vless://{USER}@example.com?{suffix}')
            self.assertNotIn(USER,str(caught.exception))


    def test_reality_validation_and_vision(self):
        value=self.profile(security='reality',sni='example.com',reality_key='A'*43,short_id='0123456789abcdef',flow='xtls-rprx-vision')
        out=vless.outbound(value)
        self.assertTrue(out['tls']['reality']['enabled']);self.assertEqual(out['tls']['utls']['fingerprint'],'chrome')
        for changes in ({'short_id':'abc'},{'reality_key':'bad'},{'flow':'bad'},{'transport':'ws'}):
            with self.assertRaises(ValueError):vless.validate(value|changes)


    def test_remote_plaintext_and_injection_rejected(self):
        for changes in ({'host':'example.com'},{'host':'bad\r\nhost'},{'uuid':'bad'},{'local_port':0},{'port':True},{'path':'bad','transport':'ws'}):
            with self.assertRaises(ValueError):self.profile(**changes)


    def test_encrypted_vault_file_import_and_remove(self):
        with tempfile.TemporaryDirectory() as folder:
            store=vless.ProfileStore(Path(folder)/'profiles');value=self.profile()
            identifier=store.save(value)
            self.assertNotIn(USER,store.path(identifier).read_text())
            self.assertEqual(store.load(identifier),value)
            file=Path(folder)/'profile.txt';file.write_text(f'vless://{USER}@127.0.0.1?security=none')
            store.import_file(file);self.assertEqual(len(store.profiles()),2)
            store.remove(identifier);self.assertEqual(len(store.profiles()),1)


    def test_whole_pc_config_excludes_upstream_and_has_no_direct_fallback(self):
        config=vless.config(self.profile(routing='tun'),['203.0.113.1'])
        self.assertEqual(config['inbounds'][0]['interface_name'],'NetCrocVLESS')
        self.assertIn('203.0.113.1/32',config['inbounds'][0]['route_exclude_address'])
        self.assertEqual(config['dns']['servers'][0]['detour'],'vless')
        self.assertEqual([o['type'] for o in config['outbounds']],['vless'])


    def test_cancelled_session_does_not_launch(self):
        session=vless.Session(CORE);session.stop()
        with patch.object(session,'check_config'),patch.object(vless.subprocess,'Popen') as process:
            with self.assertRaises(OSError):session.start_profile(self.profile())
            process.assert_not_called()


    @unittest.skipUnless((CORE/'sing-box.exe').exists(),'Run tools/check_ssh_routing.py first for native core tests')
    def test_native_schema_all_supported_transports_and_reality(self):
        session=vless.Session(CORE)
        for transport in ('tcp','ws','grpc','httpupgrade'):
            session.check_config(vless.config(self.profile(security='tls',transport=transport,sni='localhost')))
        session.check_config(vless.config(self.profile(security='reality',sni='example.com',reality_key='A'*43,flow='xtls-rprx-vision')))
        session.check_config(vless.config(self.profile(routing='tun'),['127.0.0.1']))


    @unittest.skipUnless((CORE/'sing-box.exe').exists(),'Run tools/check_ssh_routing.py first for native core tests')
    def test_native_vless_tls_forwarding_and_wrong_uuid(self):
        self.native_forwarding('tcp')


    @unittest.skipUnless((CORE/'sing-box.exe').exists(),'Run tools/check_ssh_routing.py first for native core tests')
    def test_native_websocket_tls_forwarding_and_wrong_uuid(self):
        self.native_forwarding('ws')


    @unittest.skipUnless((CORE/'sing-box.exe').exists(),'Run tools/check_ssh_routing.py first for native core tests')
    def test_native_grpc_tls_forwarding_and_wrong_uuid(self):
        self.native_forwarding('grpc')


    @unittest.skipUnless((CORE/'sing-box.exe').exists(),'Run tools/check_ssh_routing.py first for native core tests')
    def test_native_httpupgrade_tls_forwarding_and_wrong_uuid(self):
        self.native_forwarding('httpupgrade')


    def native_forwarding(self,transport,security='tls',flow=''):
        fixture=Endpoint(tls=True);self.addCleanup(fixture.close)
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
        self.addCleanup(echo.server_close);self.addCleanup(echo.shutdown)
        server_port=port()
        server={'log':{'level':'warn'},'inbounds':[{'type':'vless','listen':'127.0.0.1','listen_port':server_port,
            'users':[{'uuid':USER}], 'tls':{'enabled':True,'certificate_path':str(Path(fixture.folder.name)/'cert.pem'),'key_path':str(Path(fixture.folder.name)/'key.pem')}}],
            'outbounds':[{'type':'direct','tag':'direct'}]}
        reality_public=''
        wrong_reality_public=''
        if security=='reality':
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            from cryptography.hazmat.primitives import serialization
            key=X25519PrivateKey.generate()
            private=key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption())
            public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
            reality_public=base64.urlsafe_b64encode(public).decode().rstrip('=')
            wrong_reality_public=base64.urlsafe_b64encode(X25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode().rstrip('=')
            fixture.context.minimum_version=ssl.TLSVersion.TLSv1_3
            fixture.context.set_alpn_protocols(['h2','http/1.1'])
            server['inbounds'][0]['tls']={'enabled':True,'server_name':'localhost','reality':{'enabled':True,
                'handshake':{'server':'127.0.0.1','server_port':fixture.port},
                'private_key':base64.urlsafe_b64encode(private).decode().rstrip('='),
                'short_id':['0123456789abcdef']}}
        if flow:server['inbounds'][0]['users'][0]['flow']=flow
        if transport!='tcp':
            options={'type':transport}
            if transport=='grpc':options['service_name']='netcroc-lab'
            else:options['path']='/netcroc-lab'
            server['inbounds'][0]['transport']=options
        process=subprocess.Popen([str(CORE/'sing-box.exe'),'run','-c','stdin'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=HIDDEN)
        job=ChildJob(process);self.addCleanup(process.wait,5);self.addCleanup(job.close)
        process.stdin.write(json.dumps(server).encode());process.stdin.close()
        time.sleep(.3)
        for wrong in ((False,True,'key','sid') if security=='reality' else (False,True)):
            session=vless.Session(CORE);self.addCleanup(session.stop)
            options={}
            if security=='reality':
                options={'reality_key':(wrong_reality_public if wrong=='key' else reality_public),
                    'short_id':('ffffffffffffffff' if wrong=='sid' else '0123456789abcdef')}
            p=self.profile(port=server_port,security=security,sni='localhost',ca_pem=fixture.ca,
                transport=transport,path='/netcroc-lab',service_name='netcroc-lab',flow=flow,
                uuid=('22345678-1234-4234-9234-123456789abc' if wrong is True else USER),**options)
            session.start_profile(p)
            sock=socket.create_connection(('127.0.0.1',p['local_port']),timeout=5);self.addCleanup(sock.close)
            sock.sendall(b'\x05\x01\x00');self.assertEqual(receive_exact(sock,2),b'\x05\x00')
            sock.sendall(b'\x05\x01\x00\x01\x7f\x00\x00\x01'+echo.server_address[1].to_bytes(2,'big'))
            try:
                reply=receive_exact(sock,4)
                if wrong and reply[1]!=0:continue
                self.assertEqual(reply[1],0)
                count={1:4,4:16}[reply[3]];receive_exact(sock,count+2)
                payload=b'vless tls verified';sock.sendall(payload)
                if wrong:
                    self.assertNotEqual(sock.recv(len(payload)),payload)
                else:self.assertEqual(receive_exact(sock,len(payload)),payload)
            except OSError:
                if not wrong:raise
            finally:sock.close();session.stop()
