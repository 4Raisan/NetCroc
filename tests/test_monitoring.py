import ctypes
from datetime import date,datetime,timedelta
from pathlib import Path
import queue
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import MagicMock,patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.history import History,speed,volume
from netcroc.traffic import Rates,Traffic,Record,Header,EventTrace,LogHeader,Logfile,event_direction
from netcroc.wifi import parse_profile,GUID,Connection,connection_profile
from netcroc import dns,research
from netcroc.core import validate,DEFAULTS

class AccountingTests(unittest.TestCase):
    def test_exact_unit_boundaries(self):
        self.assertEqual(speed(0),'0.00 KB/s')
        self.assertEqual(speed(2*1024**2-1),'2048.00 KB/s')
        self.assertEqual(speed(2*1024**2),'2.00 MB/s')
        self.assertEqual(speed(1024**3-1),'1024.00 MB/s')
        self.assertEqual(speed(1024**3),'1.00 GB/s')
        self.assertEqual(volume(1024**2),'1.00 MB')

    def test_counter_baseline_elapsed_and_reset(self):
        from collections import namedtuple
        Counter=namedtuple('Counter','bytes_recv bytes_sent')
        rates=Rates()
        self.assertEqual(rates.sample({'Wi-Fi':Counter(10000,5000)},1),(0,{}))
        elapsed,result=rates.sample({'Wi-Fi':Counter(12000,6000)},3)
        self.assertEqual(elapsed,2); self.assertEqual(result['Wi-Fi'],(1000,500,2000,1000))
        self.assertEqual(rates.sample({'Wi-Fi':Counter(10,10)},4)[1]['Wi-Fi'],(0,0,0,0))

    def test_missing_adapter_new_baseline(self):
        rates=Rates(); counter=MagicMock(bytes_recv=100,bytes_sent=100)
        rates.sample({'a':counter},1); rates.sample({},2)
        self.assertEqual(rates.sample({'a':counter},3)[1],{})

    def test_midnight_split_preserves_bytes_and_coverage(self):
        history=History(':memory:')
        end=datetime.now().replace(hour=0,minute=0,second=1,microsecond=0)
        start=end-timedelta(seconds=2)
        history.record([('adapter','wifi','',101,51),('app','wifi','browser',80,40)],2,start,end)
        days=history.query(start.date().isoformat(),end.date().isoformat(),'adapter','day')
        self.assertEqual(sum(d for _,d,_ in days),101)
        self.assertEqual(sum(u for _,_,u in days),51)
        self.assertEqual(len(days),2)
        self.assertEqual(history.monitored(start.date().isoformat(),end.date().isoformat()),2)
        self.assertEqual(history.query(start.date().isoformat(),end.date().isoformat(),'app','app')[0],('browser',80,40))
        history.close()

    def test_sixty_two_day_retention_and_inclusive_dates(self):
        history=History(':memory:'); today=date.today()
        for i in range(70):
            day=(today-timedelta(days=i)).isoformat()
            history.db.execute('INSERT INTO usage VALUES(?,?,?,?,?,?)',(day,'adapter','wifi','',1,2))
        history.db.commit(); history.prune(today)
        result=history.query((today-timedelta(days=80)).isoformat(),today.isoformat(),'adapter','day')
        self.assertEqual(len(result),62)
        with self.assertRaises(ValueError):history.query(today.isoformat(),(today-timedelta(days=1)).isoformat())
        history.close()

    def test_persistence_separate_apps_networks_and_csv_formula(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'usage.db'; history=History(path)
            history.record([('adapter','=bad','',100,30),('app','=bad','browser',80,20),('adapter','Ethernet','',50,10)],1)
            history.close(); history=History(path); day=date.today().isoformat()
            self.assertEqual(sum(d for _,d,_ in history.query(day,day)),150)
            self.assertEqual(sum(d for _,d,_ in history.query(day,day,'app','app')),80)
            self.assertEqual(history.query(day,day,'app','app','=bad'),[('browser',80,20)])
            self.assertEqual(history.query(day,day,'app','app','Ethernet'),[])
            output=Path(directory)/'usage.csv'; history.export(output,day,day,'adapter','network')
            self.assertIn("'=bad",output.read_text(encoding='utf-8-sig')); history.close()

class CaptureTests(unittest.TestCase):
    def test_native_x64_layout(self):
        if ctypes.sizeof(ctypes.c_void_p)!=8:self.skipTest('x64 layout')
        self.assertEqual([ctypes.sizeof(t) for t in (Header,Record,EventTrace,LogHeader,Logfile)],[80,112,88,280,448])

    def test_tcp_udp_v4_v6_directions(self):
        for value in (10,26,42,58):self.assertEqual(event_direction(value),'up')
        for value in (11,27,43,59):self.assertEqual(event_direction(value),'down')
        self.assertIsNone(event_direction(12))

    def test_callback_counts_bytes_and_ignores_loopback(self):
        capture=Traffic(); record=Record(); record.header.id=10
        properties={'PID':(123).to_bytes(4,'little'),'size':(1500).to_bytes(4,'little'),
                    'saddr':socket.inet_aton('192.168.1.2'),'daddr':socket.inet_aton('1.1.1.1')}
        with patch.object(capture,'_property',side_effect=lambda ptr,name,length:properties[name]):
            capture._event(ctypes.pointer(record))
            self.assertEqual(capture.drain(),{(123,'192.168.1.2'):[0,1500]})
            self.assertEqual(capture.drain(),{})
            properties['daddr']=socket.inet_aton('127.0.0.1');capture._event(ctypes.pointer(record))
            self.assertEqual(capture.drain(),{})

    def test_capture_no_admin_does_not_start_session(self):
        capture=Traffic()
        with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=0),patch.object(capture.adv,'StartTraceW') as start:
            self.assertFalse(capture.start());start.assert_not_called()

    def test_decode_errors_visible(self):
        capture=Traffic(); record=Record(); record.header.id=43
        with patch.object(capture,'_property',side_effect=OSError()):capture._event(ctypes.pointer(record))
        self.assertEqual(capture.errors,1)

    def test_native_windows_tdh_reads_kernel_network_schema(self):
        capture=Traffic();record=Record()
        record.header.provider=GUID.from_buffer_copy(uuid.UUID('7dd42a49-5329-4832-8dfd-43d979153a88').bytes_le)
        record.header.id=10;record.header.version=0;record.header.opcode=10;record.header.size=80;record.header.flags=0x40
        payload=ctypes.create_string_buffer(struct.pack('<II',123,1500)+socket.inet_aton('1.1.1.1')+socket.inet_aton('192.168.1.2')+b'\0'*24)
        record.data=ctypes.addressof(payload);record.length=40
        self.assertEqual(int.from_bytes(capture._property(ctypes.pointer(record),'PID',4),'little'),123)
        self.assertEqual(int.from_bytes(capture._property(ctypes.pointer(record),'size',4),'little'),1500)
        self.assertEqual(capture._property(ctypes.pointer(record),'saddr',4),socket.inet_aton('192.168.1.2'))
        capture._event(ctypes.pointer(record))
        self.assertEqual(capture.drain(),{(123,'192.168.1.2'):[0,1500]})

    def test_native_windows_ipv4_ipv6_tcp_udp_attribution(self):
        for event_id in (10,11,26,27,42,43,58,59):
            with self.subTest(event=event_id):
                capture=Traffic();record=Record()
                record.header.provider=GUID.from_buffer_copy(uuid.UUID('7dd42a49-5329-4832-8dfd-43d979153a88').bytes_le)
                record.header.id=event_id;record.header.size=80;record.header.flags=0x40
                ipv6=event_id in (26,27,58,59);family=socket.AF_INET6 if ipv6 else socket.AF_INET
                local='fd00::2' if ipv6 else '192.168.1.2';remote='2606:4700:4700::1111' if ipv6 else '1.1.1.1'
                up=event_direction(event_id)=='up'
                tcp=event_id in (10,11,26,27)
                destination=remote if tcp or up else local;source=local if tcp or up else remote
                payload=ctypes.create_string_buffer(struct.pack('<II',123,1500)+socket.inet_pton(family,destination)+socket.inet_pton(family,source)+b'\0'*32)
                record.data=ctypes.addressof(payload);record.length=len(payload)
                capture._event(ctypes.pointer(record))
                self.assertEqual(capture.errors,0)
                self.assertEqual(capture.drain(),{(123,local):[0,1500] if up else [1500,0]})

class WifiTests(unittest.TestCase):
    def test_native_connection_prefix_state_precedes_mode(self):
        name='Lab profile'.encode('utf-16-le')
        value=Connection.from_buffer_copy(struct.pack('<II',1,0)+name+bytes(512-len(name)))
        self.assertEqual(value.state,1);self.assertEqual(value.mode,0)
        self.assertEqual(connection_profile(value),'Lab profile')

    def test_transitional_profile_is_not_connected_but_cannot_be_forgotten(self):
        value=Connection();value.profile='Lab profile'
        for state in (3,5,6,7):
            value.state=state
            self.assertEqual(connection_profile(value),'')
            self.assertEqual(connection_profile(value,strict=True),'Lab profile')
        value.state=4
        self.assertEqual(connection_profile(value,strict=True),'')

    def test_plaintext_open_and_protected_keys(self):
        xml='<WLANProfile xmlns="urn:test"><name>test</name><SSIDConfig><SSID><name>ssid</name></SSID></SSIDConfig><connectionMode>auto</connectionMode><MSM><security><authEncryption><authentication>WPA2PSK</authentication></authEncryption><sharedKey><protected>false</protected><keyMaterial>example-password</keyMaterial></sharedKey></security></MSM></WLANProfile>'
        value=parse_profile(xml)
        self.assertEqual(value['ssid'],'ssid');self.assertEqual(value['password'],'example-password');self.assertTrue(value['auto'])
        self.assertEqual(parse_profile(xml.replace('<protected>false','<protected>true'))['password'],'Windows permission required')
        self.assertEqual(parse_profile('<WLANProfile><authentication>open</authentication></WLANProfile>')['password'],'Open network')

class DnsTests(unittest.TestCase):
    def test_dns_packet_success_and_failure(self):
        fake=MagicMock(); fake.__enter__.return_value=fake
        def answer(size):
            packet=fake.send.call_args.args[0]
            return packet[:2]+struct.pack('!5H',0x8180,1,1,0,0)+packet[12:]+b'\xc0\x0c'+struct.pack('!HHIH',1,1,60,4)+socket.inet_aton('93.184.216.34')
        fake.recv.side_effect=answer
        with patch('socket.socket',return_value=fake):self.assertGreaterEqual(dns.query('1.1.1.1','example.com'),0)
        fake.recv.side_effect=None;fake.recv.return_value=b'bad'
        with patch('socket.socket',return_value=fake),self.assertRaises(ValueError):dns.query('1.1.1.1','example.com')

    def test_benchmark_does_not_pick_fast_failing_server(self):
        def lookup(server,domain):
            if server=='1.1.1.1':raise TimeoutError()
            return 10 if server=='8.8.8.8' else 20
        with patch.object(dns,'query',side_effect=lookup):
            result=dns.benchmark([],rounds=2)
        self.assertEqual(result[0]['name'],'Google'); self.assertEqual(result[-1]['name'],'Cloudflare')

    def manager(self,directory,healthy):
        backend=MagicMock(); backend.snapshot.return_value={'index':1,'guid':'test','name':'Wi-Fi','manual':False,'servers':[]}
        backend.healthy.side_effect=healthy
        return dns.DnsManager(Path(directory)/'dns.json',backend=backend,guard=MagicMock())

    def test_dns_success_saves_original_before_mutation_and_restores_dhcp(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=self.manager(directory,[True,True])
            def changed(state,servers):self.assertTrue(manager.path.exists());self.assertEqual(manager.load()['state'],'pending')
            manager.backend.set.side_effect=changed
            with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=1),patch.object(dns,'query',return_value=1):manager.apply({},['1.1.1.1'])
            self.assertEqual(manager.load()['state'],'committed');manager.guard.assert_called_once()
            manager.backend.set.side_effect=None;manager.restore()
            self.assertEqual(manager.backend.set.call_args.args[1],[]);self.assertEqual(manager.load()['state'],'restored')

    def test_dns_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=self.manager(directory,[True,False])
            with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=1),patch.object(dns,'query',return_value=1),self.assertRaises(OSError):manager.apply({},['1.1.1.1'])
            self.assertEqual(manager.load()['state'],'restored');self.assertEqual(manager.backend.set.call_count,2)

    def test_dns_no_admin_never_mutates(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=self.manager(directory,[])
            with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=0),self.assertRaises(PermissionError):manager.apply({},['1.1.1.1'])
            manager.backend.set.assert_not_called();self.assertFalse(manager.path.exists())

    def test_dns_preflight_failure_never_mutates(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=self.manager(directory,[])
            with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=1),patch.object(dns,'query',side_effect=TimeoutError()),self.assertRaises(TimeoutError):manager.apply({},['1.1.1.1'])
            manager.backend.set.assert_not_called()

    def test_dns_watchdog_restores_crashed_transaction(self):
        manager=MagicMock();manager.load.return_value={'state':'pending'}
        with patch.object(dns,'DnsManager',return_value=manager),patch.object(dns,'atomic'),patch('time.sleep'):dns.watchdog('unused')
        manager.restore.assert_called_once()

    def test_dns_watchdog_leaves_committed_settings(self):
        manager=MagicMock();manager.load.return_value={'state':'committed'}
        with patch.object(dns,'DnsManager',return_value=manager),patch('time.sleep'):dns.watchdog('unused')
        manager.restore.assert_not_called()

    def test_old_watchdog_cannot_restore_new_transaction(self):
        manager=MagicMock();manager.load.return_value={'state':'pending','transaction':'new'}
        with patch.object(dns,'DnsManager',return_value=manager),patch('time.sleep'):dns.watchdog('unused','old')
        manager.restore.assert_not_called()

    def test_watchdog_starts_independently_and_confirms_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=dns.DnsManager(Path(directory)/'dns.json')
            dns.atomic(manager.path,{'state':'pending','transaction':'test'})
            def spawn(*args,**kwargs):
                self.assertEqual(kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'],'1')
                dns.atomic(manager.path.with_suffix('.ready'),{'transaction':'test'})
                return MagicMock()
            with patch.object(dns.subprocess,'Popen',side_effect=spawn):manager.launch_guard()

    def test_failed_guard_never_applies_candidate_dns(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=self.manager(directory,[True]);manager.guard.side_effect=OSError('guard failed')
            with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=1),patch.object(dns,'query',return_value=1),self.assertRaises(OSError):manager.apply({},['1.1.1.1'])
            # Only restoring the original configuration is permitted after guard failure.
            self.assertEqual(manager.backend.set.call_count,1)
            self.assertEqual(manager.backend.set.call_args.args[1],[])

    def test_native_adapter_read_finds_real_names(self):
        values=dns.adapters()
        self.assertTrue(all(isinstance(a['index'],int) and a['name'] and a['guid'] for a in values))

    def test_isolated_dns_health_helper_exits_with_bounded_status(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'health.txt'
            result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'src'/'app.py'),'--dns-health',
                '--dns-health-report',str(report)],timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertIn(result.returncode,(0,2))
            self.assertTrue(report.exists(),'Health flag opened another mode instead of the read-only helper')
            self.assertEqual(report.read_text(),str(result.returncode))

class StudyTests(unittest.TestCase):
    def test_one_second_interval_and_slt(self):
        self.assertEqual(validate(DEFAULTS|{'interval':1,'isp':'SLT'}),'https://www.slt.lk/robots.txt')

    def test_recommendation_requires_repeated_success(self):
        values=[{'isp':'Hutch','url':'bad','success':1,'attempts':3,'median_ms':1},
                {'isp':'Hutch','url':'good','success':3,'attempts':3,'median_ms':100}]
        self.assertEqual(research.recommendations(values),{'Hutch':'good'})

    def test_refused_endpoint_study_does_not_repeat(self):
        with patch.dict(research.CANDIDATES,{'Hutch':('https://example.com/',)},clear=True),patch.object(research,'head',return_value={'status':429,'ms':1}) as head:
            self.assertEqual(research.study()[0]['attempts'],1);head.assert_called_once()

if __name__=='__main__':unittest.main()
