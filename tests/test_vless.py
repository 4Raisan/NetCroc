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
