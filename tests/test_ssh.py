import os
"""Real loopback SSH/TLS and SOCKS traffic; no system network changes."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import paramiko
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from netcroc import ssh_tunnel as ssh, ssh_routing as routing


class Server(paramiko.ServerInterface):
    def __init__(self): self.logins = []; self.destinations = []
    def check_auth_password(self, username, password):
        self.logins.append((username, password))
        return paramiko.AUTH_SUCCESSFUL if (username, password) == ('tester', 'synthetic-pass') else paramiko.AUTH_FAILED
    def get_allowed_auths(self, username): return 'password'
    def check_channel_direct_tcpip_request(self, channelid, origin, destination):
        self.destinations.append(destination)
        return paramiko.OPEN_SUCCEEDED


class Endpoint:
    def __init__(self, tls=False, before=False, after=False):
        self.key = paramiko.RSAKey.generate(2048)
        self.server = Server(); self.transports = []; self.sni = []; self.closed = threading.Event()
        self.folder = tempfile.TemporaryDirectory(); folder = Path(self.folder.name)
        self.context = None; self.ca = ''; self.pin = ''
        if tls:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
            now = datetime.now(timezone.utc)
            cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
                .not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False)
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(key, hashes.SHA256()))
            self.ca = cert.public_bytes(serialization.Encoding.PEM).decode()
            self.pin = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
            (folder/'cert.pem').write_text(self.ca)
            (folder/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.context.load_cert_chain(folder/'cert.pem', folder/'key.pem')
            self.context.set_servername_callback(lambda sock, name, ctx: self.sni.append(name))
        self.before = before; self.after = after
        self.listener = socket.socket(); self.listener.bind(('127.0.0.1', 0)); self.listener.listen(); self.listener.settimeout(.2)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self.accept, daemon=True); self.thread.start()

    def accept(self):
        while not self.closed.is_set():
            try: sock, _ = self.listener.accept()
            except socket.timeout: continue
            except OSError: return
            threading.Thread(target=self.serve, args=(sock,), daemon=True).start()

    @staticmethod
    def prelude(sock):
        data = b''
        while not data.endswith(b'\r\n\r\n'):
            data += ssh.receive_exact(sock, 1)
        sock.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')

    def serve(self, sock):
        transport = None
        try:
            sock.settimeout(4)
            if self.before: self.prelude(sock)
            if self.context: sock = self.context.wrap_socket(sock, server_side=True)
            if self.after: self.prelude(sock)
            if self.context: sock = ssh.TLSStream(sock)
            transport = paramiko.Transport(sock); transport.set_log_channel('netcroc.ssh'); self.transports.append(transport)
            transport.add_server_key(self.key); transport.start_server(server=self.server)
            while not self.closed.is_set() and transport.is_active():
                channel = transport.accept(.2)
                if channel: threading.Thread(target=self.echo, args=(channel,), daemon=True).start()
        except (OSError, EOFError, paramiko.SSHException): pass
        finally:
            if transport: transport.close()
            sock.close()

    def echo(self, channel):
        try:
            while True:
                data = channel.recv(65536)
                if not data: break
                channel.sendall(data)
            channel.shutdown_write()
        except (OSError, EOFError): pass
        finally: ssh.close_stream(channel)

    def profile(self, **overrides):
        return ssh.validate(dict(host='127.0.0.1', port=self.port, username='tester', password='synthetic-pass',
            tls=self.context is not None, sni='localhost' if self.context else '', ca_pem=self.ca,
            host_key=ssh.wire_key(self.key), local_port=0,
            payload_before='CONNECT {host}:{port} HTTP/1.1' if self.before else '',
            payload_after='CONNECT {host}:{port} HTTP/1.1' if self.after else '') | overrides)

    def close(self):
        self.closed.set(); self.listener.close()
        for transport in self.transports: transport.close()
        self.thread.join(1); self.folder.cleanup()


class SSHTests(unittest.TestCase):
    def test_tls_parallel_channels(self):
        endpoint=self.endpoint(tls=True);session=self.session(endpoint.profile())
        def transfer(index):
            sock=socket.create_connection(('127.0.0.1',session.socks.port),timeout=8)
            try:
                sock.sendall(b'\x05\x01\x00');self.assertEqual(ssh.receive_exact(sock,2),b'\x05\x00')
                host=b'example.com'
                sock.sendall(b'\x05\x01\x00\x03'+bytes([len(host)])+host+struct.pack('!H',443))
                self.assertEqual(ssh.receive_exact(sock,10)[1],0)
                for sequence in range(6):
                    payload=(f'{index}:{sequence}:'.encode()*8192)[:32768]
                    sock.sendall(payload)
                    self.assertEqual(ssh.receive_exact(sock,len(payload)),payload)
            finally:sock.close()
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(transfer,range(24)))
        relays=[r for r in session.resources if isinstance(r,ssh.TLSStream)]
        session.stop()
        self.assertTrue(relays)
        self.assertTrue(all(not r.thread.is_alive() for r in relays))

    def endpoint(self, **kwargs):
        endpoint = Endpoint(**kwargs); self.addCleanup(endpoint.close); return endpoint

    def session(self, profile):
        session = ssh.Session(); self.addCleanup(session.stop); session.start(profile); return session

    def socks(self, session, domain='example.com', command=1):
        sock = socket.create_connection(('127.0.0.1', session.socks.port), timeout=4); self.addCleanup(sock.close)
        sock.sendall(b'\x05\x01\x00'); self.assertEqual(ssh.receive_exact(sock, 2), b'\x05\x00')
        encoded = domain.encode()
        sock.sendall(bytes([5, command, 0, 3, len(encoded)])+encoded+struct.pack('!H',443))
        response = ssh.receive_exact(sock,10)
        return sock, response

    def test_real_ssh_socks_domain_and_large_payload(self):
        endpoint = self.endpoint(); session = self.session(endpoint.profile())
        sock, response = self.socks(session)
        self.assertEqual(response[1], 0)
        payload = b'network-bytes-'*10000
        # Full duplex receiver prevents flow-control deadlocks on large payloads.
        result = []
        receiver = threading.Thread(target=lambda: result.append(ssh.receive_exact(sock,len(payload))))
        receiver.start(); sock.sendall(payload); receiver.join(5)
        self.assertFalse(receiver.is_alive()); self.assertEqual(result, [payload])
        self.assertEqual(endpoint.server.destinations, [('example.com',443)])
        self.assertEqual(endpoint.server.logins, [('tester','synthetic-pass')])
        session.stop(); self.assertFalse(session.transport.is_active())

    def test_tls_ca_sni_and_pre_post_payload(self):
        endpoint = self.endpoint(tls=True, before=True, after=True)
        session = self.session(endpoint.profile())
        sock, response = self.socks(session); self.assertEqual(response[1],0)
        sock.sendall(b'tls'); self.assertEqual(ssh.receive_exact(sock,3), b'tls')
        self.assertEqual(endpoint.sni,['localhost'])
        self.assertEqual(session.info['tls_mode'],'CA + hostname')

    def test_untrusted_tls_fails_before_login(self):
        endpoint = self.endpoint(tls=True)
        with self.assertRaises(ssl.SSLCertVerificationError): self.session(endpoint.profile(ca_pem=''))
        self.assertEqual(endpoint.server.logins,[])

    def test_wrong_pin_fails_before_login(self):
        endpoint = self.endpoint(tls=True)
        with self.assertRaises(ssl.SSLCertVerificationError): self.session(endpoint.profile(tls_pin='0'*64))
        self.assertEqual(endpoint.server.logins,[])

    def test_explicit_pin_allows_custom_sni(self):
        endpoint = self.endpoint(tls=True)
        session = self.session(endpoint.profile(tls_pin=endpoint.pin, sni='custom.example'))
        self.assertEqual(endpoint.sni,['custom.example']); self.assertTrue(session.info['tls_verified'])

    def test_probe_inspection_never_authenticates(self):
        endpoint = self.endpoint(tls=True)
        info = ssh.probe(endpoint.profile(ca_pem='',host_key=''),inspect=True)
        self.assertEqual(info['tls_fingerprint'],endpoint.pin)
        self.assertFalse(info['tls_verified']); self.assertEqual(endpoint.server.logins,[])

    def test_host_key_change_refuses_before_authentication(self):
        endpoint = self.endpoint(); wrong = paramiko.RSAKey.generate(2048)
        with self.assertRaises(paramiko.BadHostKeyException) as caught:
            self.session(endpoint.profile(host_key=ssh.wire_key(wrong)))
        self.assertIn('host key',ssh.friendly_error(caught.exception)); self.assertEqual(endpoint.server.logins,[])

    def test_authentication_failure_cleanup(self):
        endpoint = self.endpoint()
        with self.assertRaises(paramiko.AuthenticationException): self.session(endpoint.profile(password='wrong'))

    def test_udp_associate_refused(self):
        session = self.session(self.endpoint().profile())
        _, response = self.socks(session, command=3); self.assertEqual(response[1],7)

    def test_server_loss_stops_proxy(self):
        endpoint = self.endpoint(); session = self.session(endpoint.profile()); endpoint.transports[0].close()
        self.assertTrue(session.cancel.wait(4)); self.assertIn('disconnected',session.status.lower())

    @unittest.skipUnless(os.name=='nt','Windows native API / DPAPI test; POSIX backend has separate coverage')
    def test_dpapi_vault_and_import(self):
        endpoint = self.endpoint()
        with tempfile.TemporaryDirectory() as folder:
            store = ssh.ProfileStore(Path(folder)/'vault'); value = endpoint.profile()
            identifier = store.save(value)
            self.assertNotIn('synthetic-pass',store.path(identifier).read_text())
            self.assertEqual(store.load(identifier),value)
            source = Path(folder)/'import.json'; source.write_text(json.dumps(value))
            store.import_file(source); self.assertEqual(len(store.profiles()),2)
            store.remove(identifier); self.assertEqual(len(store.profiles()),1)
            with self.assertRaises(ValueError): store.path('../escape')

    def test_validation_expiry_payload_and_unknown_fields(self):
        endpoint = self.endpoint()
        for value in [dict(host='https://bad'),dict(port=0),dict(tls_pin='abc'),dict(host_key='bad'),dict(expires='bad'),dict(unknown=True),dict(payload_after='bad')]:
            with self.assertRaises(ValueError): ssh.validate(endpoint.profile() | value)
        with self.assertRaises(ValueError): ssh.validate(endpoint.profile(expires='2000-01-01'),credentials=True)
        self.assertEqual(ssh.render_payload('CONNECT {host}:{port}[crlf]X: {sni}',endpoint.profile()), f'CONNECT 127.0.0.1:{endpoint.port}\r\nX: 127.0.0.1\r\n\r\n'.encode())

    @unittest.skipUnless(os.name=='nt','Windows native API / DPAPI test; POSIX backend has separate coverage')
    def test_routing_config_and_nonadmin_block(self):
        config = routing.configuration(1080,['203.0.113.2','2001:db8::1'])
        self.assertIn('203.0.113.2/32',config['inbounds'][0]['route_exclude_address'])
        self.assertEqual(config['route']['rules'][1]['action'],'reject')
        with tempfile.TemporaryDirectory() as folder, patch('netcroc.ssh_routing.ctypes.windll.shell32.IsUserAnAdmin',return_value=False):
            with self.assertRaises(PermissionError): routing.Routing(folder).preflight()

    def test_child_job_kills_own_process(self):
        process = subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],creationflags=routing.HIDDEN)
        try:
            job = routing.ChildJob(process); job.close(); process.wait(timeout=4)
            self.assertIsNotNone(process.returncode)
        finally:
            if process.poll() is None: process.kill(); process.wait()

    def test_download_hash_rejection(self):
        with tempfile.TemporaryDirectory() as folder, patch('netcroc.ssh_routing.urllib.request.urlopen') as download:
            download.return_value.__enter__.return_value.read.return_value=b'bad archive'
            with self.assertRaises(ValueError): routing.Routing(folder).install()
            self.assertFalse((Path(folder)/'sing-box.exe').exists())

    @unittest.skipUnless(os.name=='nt','Windows native API / DPAPI test; POSIX backend has separate coverage')
    def test_routing_download_preserves_license_and_detects_modified_executable(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            archive.writestr('release/sing-box.exe',b'fixture-executable')
            archive.writestr('release/LICENSE',b'fixture-license')
            archive.writestr('../../outside.txt',b'not extracted')
        raw = buffer.getvalue()
        with tempfile.TemporaryDirectory() as folder, patch('netcroc.ssh_routing.urllib.request.urlopen') as download, patch.object(routing,'SHA256',hashlib.sha256(raw).hexdigest()):
            download.return_value.__enter__.return_value.read.return_value=raw
            core = routing.Routing(folder); core.install(); core.verify()
            self.assertEqual((Path(folder)/'LICENSE').read_bytes(),b'fixture-license')
            self.assertEqual(len(list(Path(folder).iterdir())),3)
            core.exe.write_bytes(b'changed')
            with self.assertRaises(ValueError): core.verify()

    @unittest.skipUnless(os.name=='nt','Windows job launch; POSIX supervisor and isolated TUN lab cover native launch')
    def test_routing_launch_is_job_protected_before_configuration_is_sent(self):
        order = []; process = MagicMock(); process.poll.return_value=None
        process.stdin.write.side_effect=lambda data: order.append('config')
        with tempfile.TemporaryDirectory() as folder:
            core = routing.Routing(folder)
            with patch.object(core,'preflight'), patch.object(core,'check'), patch.object(routing.subprocess,'Popen',return_value=process), patch.object(routing,'ChildJob',side_effect=lambda p: order.append('job') or MagicMock()), patch('psutil.net_if_addrs',return_value={'NetCrocSSH':[]}):
                core.start(1080,['192.0.2.1']); self.assertTrue(core.active)
                self.assertEqual(order,['job','config'])
                core.stop(); self.assertFalse(core.active)
                process.terminate.assert_called_once()

    @unittest.skipUnless(os.name=='nt','Windows job launch; POSIX supervisor and isolated TUN lab cover native launch')
    def test_routing_job_failure_never_receives_configuration(self):
        process = MagicMock(); process.poll.return_value=None
        with tempfile.TemporaryDirectory() as folder:
            core = routing.Routing(folder)
            with patch.object(core,'preflight'), patch.object(core,'check'), patch.object(routing.subprocess,'Popen',return_value=process), patch.object(routing,'ChildJob',side_effect=OSError('fixture failure')):
                with self.assertRaises(OSError): core.start(1080,['192.0.2.1'])
                process.stdin.write.assert_not_called(); process.terminate.assert_called_once()

    def test_http_prelude_does_not_consume_following_banner(self):
        class Stream:
            def __init__(self): self.data=io.BytesIO(b'HTTP/1.1 200 OK\r\n\r\nSSH-2.0-fixture\r\n')
            def recv(self,n): return self.data.read(n)
            def sendall(self,data): pass
        stream=Stream(); ssh.http_prelude(stream,b'CONNECT fixture\r\n\r\n')
        self.assertEqual(stream.recv(100),b'SSH-2.0-fixture\r\n')

    def test_http_prelude_rejects_bad_status_and_header_overflow(self):
        for raw in [b'HTTP/1.1 403 Forbidden\r\n\r\n',b'x'*16385]:
            stream=MagicMock(); data=io.BytesIO(raw); stream.recv.side_effect=data.read
            with self.assertRaises(OSError): ssh.http_prelude(stream,b'payload')

    def test_proxy_connect_basic_auth_and_ipv6_authority(self):
        profile=ssh.validate({'host':'2001:db8::1','tls':False,'proxy_host':'proxy.example','proxy_user':'name','proxy_password':'secret'})
        stream=MagicMock(); stream.getpeername.return_value=('192.0.2.1',8080)
        with patch.object(ssh.socket,'create_connection',return_value=stream), patch.object(ssh,'http_prelude') as prelude:
            ssh.open_stream(profile)
            payload=prelude.call_args.args[1]
            self.assertIn(b'CONNECT [2001:db8::1]:443 HTTP/1.1',payload)
            self.assertIn(base64.b64encode(b'name:secret'),payload)

    def test_socks_ipv4_and_half_close(self):
        session=self.session(self.endpoint().profile())
        sock=socket.create_connection(('127.0.0.1',session.socks.port),timeout=4); self.addCleanup(sock.close)
        sock.sendall(b'\x05\x01\x00'); ssh.receive_exact(sock,2)
        sock.sendall(b'\x05\x01\x00\x01'+socket.inet_aton('192.0.2.5')+struct.pack('!H',80))
        self.assertEqual(ssh.receive_exact(sock,10)[1],0)
        sock.sendall(b'last bytes'); sock.shutdown(socket.SHUT_WR)
        self.assertEqual(ssh.receive_exact(sock,10),b'last bytes')

    def test_cancelled_session_never_authenticates(self):
        endpoint=self.endpoint(); session=ssh.Session(); session.stop()
        with self.assertRaises(OSError): session.start(endpoint.profile())
        self.assertEqual(endpoint.server.logins,[])

    def test_port_conflict_closes_authenticated_transport(self):
        endpoint=self.endpoint(); first=self.session(endpoint.profile())
        second=ssh.Session(); self.addCleanup(second.stop)
        with self.assertRaises(OSError): second.start(endpoint.profile(local_port=first.socks.port))
        self.assertTrue(second.cancel.is_set())
