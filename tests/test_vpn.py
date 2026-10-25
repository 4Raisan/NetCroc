"""Synthetic keys only. No tunnel installation, DNS changes or elevation."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc import vpn

PRIVATE=base64.b64encode(bytes(range(1,33))).decode('ascii')
PUBLIC=base64.b64encode(bytes(range(2,34))).decode('ascii')
CONFIG=f"""[Interface]
PrivateKey = {PRIVATE}
Address = 10.2.0.2/32, fd00::2/128
DNS = 10.2.0.1
[Peer]
PublicKey = {PUBLIC}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = vpn.example.com:51820
PersistentKeepalive = 25
"""

class VpnTests(unittest.TestCase):
    def test_normalize_and_redacted_metadata(self):
        text,meta=vpn.parse_config('# comment\n'+CONFIG)
        self.assertEqual(meta['peers'],1)
        self.assertEqual(meta['route'],'Default route')
        self.assertNotIn(PRIVATE,json.dumps(meta))
        self.assertNotIn(PUBLIC,json.dumps(meta))
        self.assertEqual(vpn.parse_config(text)[0],text)

    def test_reject_hooks_unknown_fields_duplicate_values_and_secrets_in_errors(self):
        for bad in (CONFIG+'PostUp = dangerous-command',CONFIG.replace('DNS =','Table ='),CONFIG.replace('Address =','PrivateKey ='),CONFIG.replace(PRIVATE,'private-secret-invalid'),CONFIG.replace('[Peer]','[Other]')):
            with self.subTest(config=bad[:12]):
                with self.assertRaises(ValueError) as error:vpn.parse_config(bad)
                self.assertNotIn('private-secret-invalid',str(error.exception))
                self.assertNotIn(PRIVATE,str(error.exception))

    def test_reject_invalid_endpoints_addresses_keys_and_numeric_options(self):
        for a,b in (('vpn.example.com:51820','-flag:80'),('vpn.example.com:51820','vpn.example.com:0'),('vpn.example.com:51820','[invalid]:443'),('10.2.0.2/32','not-an-ip'),('10.2.0.1','dns.example.com'),('25','70000'),(PUBLIC,'bad'),(PRIVATE,base64.b64encode(bytes(32)).decode())):
            with self.subTest(value=b),self.assertRaises(ValueError):vpn.parse_config(CONFIG.replace(a,b))
        with self.assertRaises(ValueError):vpn.parse_config(CONFIG+'x'*vpn.MAX_CONFIG)
        with self.assertRaises(ValueError):vpn.parse_config(CONFIG+'\x00')

    def test_ipv6_endpoint_split_routes_and_multiple_peers(self):
        value=CONFIG.replace('vpn.example.com:51820','[2001:db8::1]:443').replace('0.0.0.0/0, ::/0','192.168.5.0/24')
        _,meta=vpn.parse_config(value)
        self.assertEqual(meta['route'],'Selected networks')
        _,meta=vpn.parse_config(value+'\n[Peer]\nPublicKey = '+PRIVATE+'\nAllowedIPs = 10.4.0.0/24\nEndpoint = second.example.com:53\n')
        self.assertEqual(meta['peers'],2)

    def test_dpapi_user_and_machine_round_trip(self):
        for machine in (False,True):
            protected=vpn.crypt(b'synthetic-secret-only',description='NetCroc-test',machine=machine)
            self.assertNotIn(b'synthetic-secret-only',protected)
            self.assertEqual(vpn.crypt(protected,decrypt=True),b'synthetic-secret-only')

    def test_profile_persistence_is_encrypted_and_import_has_no_backend_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            backend=MagicMock();store=vpn.ProfileStore(Path(folder)/'profiles',backend)
            source=Path(folder)/'provider.conf';source.write_text(CONFIG)
            item=store.import_file(source)
            saved=(store.folder/(item['id']+'.json')).read_text()
            self.assertNotIn(PRIVATE,saved)
            self.assertNotIn(PUBLIC,saved)
            backend.connect.assert_not_called();backend.require_admin.assert_not_called()
            reopened=vpn.ProfileStore(store.folder,backend)
            self.assertEqual(reopened.profiles(),[item])
            reopened.connect(item['id'])
            backend.connect.assert_called_once()
            self.assertIn(PRIVATE,backend.connect.call_args.args[1])
            self.assertEqual(source.read_text(),CONFIG)

    def test_connect_requires_admin_before_unlocking_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            backend=MagicMock();backend.require_admin.side_effect=PermissionError('no admin')
            store=vpn.ProfileStore(folder,backend)
            with patch.object(vpn,'crypt') as decrypt,self.assertRaises(PermissionError):store.connect('a'*32)
            decrypt.assert_not_called();backend.connect.assert_not_called()

    def test_remove_blocks_existing_tunnel_and_only_removes_selected_saved_file(self):
        with tempfile.TemporaryDirectory() as folder:
            backend=MagicMock();store=vpn.ProfileStore(folder,backend)
            one=store.add(CONFIG,'one');two=store.add(CONFIG,'two')
            backend.state.return_value='running'
            with self.assertRaises(ValueError):store.remove(one['id'])
            backend.state.return_value='not installed';store.remove(one['id'])
            self.assertEqual([v['id'] for v in store.profiles()],[two['id']])
            with self.assertRaises(ValueError):store.remove('../outside')

    def test_corrupt_saved_profile_is_not_exposed(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder,'broken.json').write_text('{broken')
            store=vpn.ProfileStore(folder)
            self.assertEqual(store.profiles(),[])
            with self.assertRaises(ValueError):vpn.tunnel_name('../bad')
            with self.assertRaises(ValueError):store.backend.runtime_path('../bad')

    def test_import_wrong_extension_and_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.txt';path.write_text(CONFIG)
            store=vpn.ProfileStore(Path(folder)/'vault')
            with self.assertRaises(ValueError):store.import_file(path)
            path=Path(folder)/'bad.conf';path.write_text('x'*(vpn.MAX_CONFIG+1))
            with self.assertRaises(ValueError):store.import_file(path)
            self.assertFalse(store.folder.exists())

    def test_backend_nonadmin_connect_and_disconnect_never_invoke_commands(self):
        backend=vpn.WindowsWireGuard()
        with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=0),patch.object(backend,'_run') as run:
            with self.assertRaises(PermissionError):backend.connect('NetCroc-'+'a'*20,CONFIG)
            with self.assertRaises(PermissionError):backend.disconnect('NetCroc-'+'a'*20)
            run.assert_not_called()

    def test_backend_writes_encrypted_runtime_and_service_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            backend=vpn.WindowsWireGuard();name='NetCroc-'+'a'*20;path=Path(folder)/'service'/(name+'.conf.dpapi')
            with patch.object(backend,'require_admin'),patch.object(backend,'installed',return_value=Path('C:/WireGuard/wireguard.exe')),patch.object(backend,'state',return_value='not installed'),patch.object(backend,'runtime_path',return_value=path),patch.object(backend,'_run') as run,patch.object(vpn,'protect_service_path') as protect,patch.object(backend,'status',return_value={'service':'running','handshake':'No handshake observed'}),patch.object(vpn.psutil,'win_service_iter',return_value=[]):
                status=backend.connect(name,CONFIG)
                self.assertEqual(status['service'],'running')
                self.assertNotIn(PRIVATE.encode(),path.read_bytes())
                self.assertIn(PRIVATE,vpn.crypt(path.read_bytes(),decrypt=True).decode())
                commands=[call.args[0] for call in run.call_args_list]
                self.assertEqual([call.args[0] for call in protect.call_args_list],[path.parent.parent,path.parent,path])
                self.assertEqual(commands[0][1],'/installtunnelservice')
                self.assertEqual(commands[1][-2:],['start=','demand'])
                backend.disconnect(name);self.assertFalse(path.exists())

    def test_backend_refuses_other_running_tunnels(self):
        backend=vpn.WindowsWireGuard();service=MagicMock();service.name.return_value='WireGuardTunnel$other';service.status.return_value='running'
        with patch.object(backend,'require_admin'),patch.object(backend,'installed',return_value=Path('C:/WireGuard/wireguard.exe')),patch.object(backend,'state',return_value='not installed'),patch.object(vpn.psutil,'win_service_iter',return_value=[service]),patch.object(backend,'_run') as run:
            with self.assertRaises(ValueError):backend.connect('NetCroc-'+'a'*20,CONFIG)
            run.assert_not_called()

    def test_failed_install_triggers_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            backend=vpn.WindowsWireGuard();name='NetCroc-'+'a'*20
            path=Path(folder)/'service'/(name+'.conf.dpapi')
            with patch.object(backend,'require_admin'),patch.object(backend,'installed',return_value=Path('C:/WireGuard/wireguard.exe')),patch.object(backend,'state',return_value='not installed'),patch.object(backend,'runtime_path',return_value=path),patch.object(vpn.psutil,'win_service_iter',return_value=[]),patch.object(backend,'_run',side_effect=OSError('failed')),patch.object(vpn,'protect_service_path'),patch.object(backend,'disconnect') as disconnect:
                with self.assertRaises(OSError):backend.connect(name,CONFIG)
                disconnect.assert_called_once_with(name)

    def test_native_service_descriptor_parses_without_applying_permissions(self):
        native=vpn.c.WinDLL('advapi32',use_last_error=True)
        original=vpn.c.WinDLL
        setter=MagicMock(return_value=0)
        api=SimpleNamespace(ConvertStringSecurityDescriptorToSecurityDescriptorW=native.ConvertStringSecurityDescriptorToSecurityDescriptorW,GetSecurityDescriptorDacl=native.GetSecurityDescriptorDacl,GetSecurityDescriptorOwner=native.GetSecurityDescriptorOwner,SetNamedSecurityInfoW=setter)
        with patch.object(vpn.c,'WinDLL',side_effect=lambda name,**kwargs:api if name=='advapi32' else original(name,**kwargs)):
            vpn.protect_service_path(Path('synthetic-not-created'))
        setter.assert_called_once()
        self.assertEqual(setter.call_args.args[1:3],(1,0x80000005))
        self.assertIsNotNone(setter.call_args.args[3])
        self.assertFalse(Path('synthetic-not-created').exists())

    def test_acl_failure_never_writes_service_credentials_or_starts_tunnel(self):
        with tempfile.TemporaryDirectory() as folder:
            backend=vpn.WindowsWireGuard();name='NetCroc-'+'a'*20
            path=Path(folder)/'service'/(name+'.conf.dpapi')
            with patch.object(backend,'require_admin'),patch.object(backend,'installed',return_value=Path('C:/WireGuard/wireguard.exe')),patch.object(backend,'state',return_value='not installed'),patch.object(backend,'runtime_path',return_value=path),patch.object(vpn.psutil,'win_service_iter',return_value=[]),patch.object(vpn,'protect_service_path',side_effect=OSError('ACL failed')),patch.object(backend,'_run') as run:
                with self.assertRaises(OSError):backend.connect(name,CONFIG)
                self.assertFalse(path.exists());run.assert_not_called()

    def test_running_service_is_not_reported_as_a_handshake(self):
        backend=vpn.WindowsWireGuard()
        with patch.object(backend,'state',return_value='running'),patch.object(backend,'installed',return_value=None):
            status=backend.status('NetCroc-'+'a'*20)
        self.assertEqual(status,{'service':'running','handshake':'Not checked'})

if __name__=='__main__':unittest.main()
