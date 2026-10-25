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


    def test_invalid_links_never_echo_credentials(self):
        for suffix in ('allowInsecure=1','type=xhttp','type=ws&type=tcp','encryption=aes','headerType=http'):
            with self.assertRaises(ValueError) as caught:vless.parse_link(f'vless://{USER}@example.com?{suffix}')
            self.assertNotIn(USER,str(caught.exception))


    def test_remote_plaintext_and_injection_rejected(self):
        for changes in ({'host':'example.com'},{'host':'bad\r\nhost'},{'uuid':'bad'},{'local_port':0},{'port':True},{'path':'bad','transport':'ws'}):
            with self.assertRaises(ValueError):self.profile(**changes)
