import sys,unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc import wireguard_setup as w
class WireGuardSetupTests(unittest.TestCase):
 def test_current_install_never_runs_installer(self):
  with patch.object(w,'status',return_value={'needed':False,'installed':'1.1.1'}),patch.object(w,'powershell') as run:
   self.assertIn('up to date',w.install_or_update(Mock()));run.assert_not_called()
 def test_installed_version_comparison(self):
  with patch.object(w,'installed_version',return_value='1.0.0'),patch.object(w,'latest',return_value=('1.1.1','wireguard-amd64-1.1.1.msi')):
   self.assertTrue(w.status(Mock())['needed'])
 def test_newer_local_is_not_downgraded(self):
  with patch.object(w,'installed_version',return_value='2.0.0'),patch.object(w,'latest',return_value=('1.1.1','wireguard-amd64-1.1.1.msi')):
   self.assertFalse(w.status(Mock())['needed'])
 def test_active_tunnel_stops_install_before_download(self):
  with patch.object(w,'status',return_value={'needed':True}),patch.object(w,'powershell',side_effect=OSError('Disconnect active tunnels')),patch.object(w,'download') as download:
   with self.assertRaises(OSError):w.install_or_update(Mock())
   download.assert_not_called()
 def test_signature_failure_rejects_cached_installer(self):
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'test.msi').write_bytes(b'invalid')
   with patch.object(w,'verify',side_effect=OSError('bad signature')):
    with self.assertRaises(OSError):w.download(tmp,'test.msi')
 def test_install_uses_elevation_and_suppresses_separate_ui(self):
  with patch.object(w,'status',return_value={'needed':True,'latest':'1.1.1','filename':'test.msi'}),patch.object(w,'powershell',side_effect=['','0']) as run,patch.object(w,'download',return_value=Path('test.msi')),patch.object(w,'installed_version',return_value='1.1.1'):
   self.assertIn('ready',w.install_or_update(Mock()))
   script=run.call_args_list[-1].args[0]
   self.assertIn('-Verb RunAs',script);self.assertIn('DO_NOT_LAUNCH=1',script);self.assertIn('/norestart',script)
 def test_cancelled_installer_is_reported(self):
  with patch.object(w,'status',return_value={'needed':True,'latest':'1.1.1','filename':'test.msi'}),patch.object(w,'powershell',side_effect=['',OSError('cancelled')]),patch.object(w,'download',return_value=Path('test.msi')):
   with self.assertRaisesRegex(OSError,'cancelled'):w.install_or_update(Mock())
if __name__=='__main__':unittest.main()
