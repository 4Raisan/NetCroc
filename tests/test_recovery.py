"""Recovery observation and POSIX control validation without network mutations."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc import tun_service as service,posix_network as network
spec=importlib.util.spec_from_file_location('longrun_observer',Path(__file__).resolve().parents[1]/'tools/longrun_observer.py')
observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)

class RecoveryTests(unittest.TestCase):
    def test_suspension_is_separated_without_counting_it_as_observed(self):
        value=observer.interval(100,3700,50,80)
        self.assertEqual(value['observed_seconds'],30);self.assertEqual(value['suspend_estimate_seconds'],3570);self.assertTrue(value['sampling_gap'])
    def test_unknown_gap_is_not_labelled_sleep_or_full_coverage(self):
        value=observer.interval(100,3700)
        self.assertIsNone(value['suspend_estimate_seconds']);self.assertEqual(value['observed_seconds'],60)
    def test_missing_or_stalled_history_never_passes(self):
        good=dict(sampled_seconds=3600,history_read_errors=0,history_coverage_delta_seconds=3600,max_no_progress_samples=0)
        self.assertTrue(observer.evaluate(good,3600))
        for key,value in [('sampled_seconds',3000),('history_read_errors',1),('history_coverage_delta_seconds',100),('max_no_progress_samples',3)]:self.assertFalse(observer.evaluate(good|{key:value},3600))
    def test_remote_health_needs_correct_fresh_transaction(self):
        remote=service.RemoteRouting();remote.path=Path('unused');remote.token='a'*64
        with patch.object(service,'read_state',return_value=dict(token='a'*64,state='ready',updated=time.time())):self.assertTrue(remote.healthy())
        with patch.object(service,'read_state',return_value=dict(token='b'*64,state='ready',updated=time.time())):self.assertFalse(remote.healthy())
        with patch.object(service,'read_state',return_value=dict(token='a'*64,state='ready',updated=time.time()-30)):self.assertFalse(remote.healthy())
    def test_cancelled_authorization_cleans_pending_state_without_second_prompt(self):
        remote=service.RemoteRouting()
        with patch.object(service.platforms,'elevated_native',side_effect=OSError('cancelled')) as auth:
            with self.assertRaises(OSError):remote.start(Path('sing-box'),'ssh',['127.0.0.1'],port=1080)
            auth.assert_called_once();self.assertIsNone(remote.path)
    def test_linux_transitional_wifi_is_protected_but_not_shown_connected(self):
        wifi=object.__new__(network.Wifi)
        from types import SimpleNamespace
        with patch.object(network,'MAC',False),patch.object(network,'run',side_effect=['Lab name','70 (connecting)']):self.assertEqual(wifi.current(SimpleNamespace(guid='wlan0')),'')
        with patch.object(network,'MAC',False),patch.object(network,'run',return_value='synthetic-uuid'):self.assertEqual(wifi.current(SimpleNamespace(guid='wlan0'),strict=True),'synthetic-uuid')
    @unittest.skipIf(os.name=='nt','POSIX private control files')
    def test_status_rejects_symlinks_and_stale_tokens(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json';path.write_text(json.dumps(dict(token='a'*64)));path.chmod(0o600)
            service.validate_state(path,os.getuid(),'a'*64)
            with self.assertRaises(ValueError):service.validate_state(path,os.getuid(),'b'*64)
            link=Path(folder)/'elsewhere';path.rename(link);path.symlink_to(link)
            with self.assertRaises(PermissionError):service.validate_state(path,os.getuid(),'a'*64)
    @unittest.skipIf(os.name=='nt','POSIX real child cleanup')
    def test_supervisor_stops_child_after_parent_exit(self):
        from netcroc.platforms import ChildGuard
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json';path.write_text(json.dumps(dict(token='a'*64)));path.chmod(0o600)
            process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
            job=ChildGuard(process)
            try:
                with patch.object(service,'parent_alive',return_value=False):service.supervise(process,job,dict(state=str(path),token='a'*64,parent=1,created=0),os.getuid(),set(),'ncssh')
                self.assertIsNotNone(process.poll())
            finally:
                if process.poll() is None:process.kill();process.wait()

if __name__=='__main__':unittest.main()
