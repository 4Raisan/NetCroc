"""Portable backends: no system network mutation, no real credentials."""
import base64
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc import platforms as native,posix_network as network,core

class PortableTests(unittest.TestCase):
    def test_ping_uses_native_arguments(self):
        with patch.object(native,'WINDOWS',False),patch.object(native,'MAC',False):self.assertEqual(native.ping_command('example.com'),['ping','-n','-c','1','-W','2','example.com'])
        with patch.object(native,'WINDOWS',False),patch.object(native,'MAC',True):self.assertEqual(native.ping_command('example.com')[-2:],['1500','example.com'])
    def test_data_paths_follow_platform_conventions(self):
        with patch.object(native,'MAC',True),patch.object(Path,'home',return_value=Path('/tmp/netcroc-user')):self.assertEqual(native.data_folder(),Path('/tmp/netcroc-user/Library/Application Support/NetCroc'))
        with patch.object(native,'MAC',False),patch.dict(os.environ,{'XDG_DATA_HOME':'/tmp/xdg-data'}):self.assertEqual(native.data_folder(),Path('/tmp/xdg-data/netcroc'))
    def test_native_commands_are_not_shell_interpreted_and_errors_are_redacted(self):
        with patch.object(native.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='private-secret')) as run:
            with self.assertRaises(OSError) as caught:native.run(['nmcli','connection','show','name;bad'])
            self.assertNotIn('private-secret',str(caught.exception));self.assertIsInstance(run.call_args.args[0],list)
            self.assertNotIn('shell',run.call_args.kwargs)
    def test_keyring_cipher_round_trip_and_missing_key_fails_closed(self):
        fake=MagicMock();fake.get_password.return_value=base64.b64encode(bytes(range(32))).decode()
        with patch.dict(sys.modules,{'keyring':fake}):
            encrypted=native.crypt(b'synthetic-credential');self.assertNotIn(b'synthetic-credential',encrypted)
            self.assertEqual(native.crypt(encrypted,decrypt=True),b'synthetic-credential')
            with self.assertRaises(Exception):native.crypt(encrypted[:-1]+bytes([encrypted[-1]^1]),decrypt=True)
            fake.get_password.return_value=None
            with self.assertRaises(OSError):native.crypt(encrypted,decrypt=True)
            fake.set_password.assert_not_called()
    def test_keyring_failure_never_writes_a_plaintext_fallback(self):
        fake=MagicMock();fake.get_password.side_effect=OSError('keyring locked')
        with patch.dict(sys.modules,{'keyring':fake}),patch.object(Path,'write_bytes') as write:
            with self.assertRaises(OSError):native.crypt(b'secret')
            write.assert_not_called()
    def test_linux_dns_restore_preserves_ignore_auto_and_empty_servers(self):
        original=dict(guid='synthetic-uuid',device='wlan0',servers=[],manual=True,ignore_auto=False)
        with patch.object(network,'MAC',False),patch.object(network,'admin',return_value=True),patch.object(network,'require_admin'),patch.object(network,'run',return_value='') as run:
            network.DnsBackend().set(original,['1.1.1.1'])
            self.assertEqual(run.call_args_list[0].args[0][-1],'yes')
            network.DnsBackend().set(original,[])
            self.assertEqual(run.call_args_list[2].args[0][-3:],['','ipv4.ignore-auto-dns','no'])
    def test_mac_dns_empty_means_automatic(self):
        with patch.object(network,'MAC',True),patch.object(network,'admin',return_value=True),patch.object(network,'require_admin'),patch.object(network,'run',return_value='') as run:
            network.DnsBackend().set(dict(name='Wi-Fi',servers=[]),[])
            self.assertEqual(run.call_args.args[0],['/usr/sbin/networksetup','-setdnsservers','Wi-Fi','Empty'])
    def test_mac_network_services_include_spaces(self):
        with patch.object(network,'run',return_value='(1) Wi-Fi\n(Hardware Port: Wi-Fi, Device: en0)\n(2) USB Ethernet\n(Hardware Port: USB LAN, Device: en1)'):
            self.assertEqual(network.mac_services(),{'en0':'Wi-Fi','en1':'USB Ethernet'})
    def test_forget_current_wifi_never_runs_mutation(self):
        wifi=object.__new__(network.Wifi)
        item=dict(profile='Lab',uuid='synthetic-uuid',ssid='Lab',interface=SimpleNamespace(guid='wlan0'))
        with patch.object(wifi,'current',return_value='synthetic-uuid'),patch.object(network,'run') as run:
            with self.assertRaises(ValueError):wifi.forget(item)
            run.assert_not_called()
    def test_packet_metadata_attributes_both_directions_and_excludes_lan(self):
        traffic=network.Traffic();connections=[SimpleNamespace(pid=123,laddr=('192.168.1.2',5000),raddr=('1.1.1.1',443),type=socket.SOCK_STREAM)]
        mapping=network.socket_map(connections)
        traffic.account('1.1.1.1\t\t192.168.1.2\t\t443\t\t5000\t\t1500\t\n',mapping,{'192.168.1.2'})
        traffic.account('192.168.1.2\t\t1.1.1.1\t\t5000\t\t443\t\t200\t\n',mapping,{'192.168.1.2'})
        self.assertEqual(traffic.drain(),{(123,'192.168.1.2'):[1500,200]})
        traffic.account('192.168.1.2\t\t192.168.1.3\t\t5000\t\t443\t\t9999\t\n',mapping,{'192.168.1.2'})
        self.assertEqual(traffic.drain(),{})
    def test_ambiguous_socket_ownership_is_omitted(self):
        values=[SimpleNamespace(pid=pid,laddr=('192.168.1.2',5000),raddr=('1.1.1.1',443),type=socket.SOCK_STREAM) for pid in (1,2)]
        self.assertEqual(network.socket_map(values),{})
    def test_posix_wireguard_names_are_short_and_path_safe(self):
        backend=network.WireGuard()
        self.assertLessEqual(len(backend.short('NetCroc-'+'a'*20)),15)
        with self.assertRaises(ValueError):backend.runtime_path('../private')
    def test_native_control_defers_privilege_to_os_without_unlocking_keyring(self):
        with patch.object(network,'admin',return_value=False),patch.object(network,'elevated_native',return_value={'service':'not installed'}) as auth:
            network.WireGuard().disconnect('NetCroc-'+'a'*20)
            self.assertEqual(auth.call_args.args[0],'wg-disconnect')
    @unittest.skipIf(os.name=='nt','POSIX startup integration')
    def test_startup_only_touches_netcroc_entry(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(native,'MAC',False),patch.dict(os.environ,{'XDG_CONFIG_HOME':folder}):
            native.startup(True);path=Path(folder)/'autostart/netcroc.desktop'
            self.assertIn('--tray',path.read_text());native.startup(False);self.assertFalse(path.exists())
    @unittest.skipIf(os.name=='nt','POSIX instance locking')
    def test_second_instance_is_blocked_and_lock_released(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(native,'data_folder',return_value=Path(folder)):
            lock=native.InstanceLock()
            try:
                with self.assertRaises(OSError):native.InstanceLock()
            finally:lock.close()
            native.InstanceLock().close()
    @unittest.skipIf(os.name=='nt','POSIX parent-crash guard')
    def test_guard_kills_child_after_parent_exit(self):
        root=Path(__file__).resolve().parents[1]
        code="import sys,subprocess,os;sys.path.insert(0,sys.argv[1]);from netcroc.platforms import ChildGuard;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);g=ChildGuard(p);print(p.pid,flush=True);os._exit(23)"
        parent=subprocess.run([sys.executable,'-c',code,str(root/'src')],capture_output=True,text=True,timeout=15)
        self.assertEqual(parent.returncode,23)
        import psutil
        pid=int(parent.stdout.strip());end=time.monotonic()+8
        while time.monotonic()<end:
            try:
                if psutil.Process(pid).status()==psutil.STATUS_ZOMBIE:return
            except psutil.NoSuchProcess:return
            time.sleep(.1)
        self.fail('Routing child survived parent exit')

if __name__=='__main__':unittest.main()
