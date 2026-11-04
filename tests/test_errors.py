import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.errors import explain
class FriendlyErrorTests(unittest.TestCase):
 def test_sandbox_wifi_is_explained_without_a_driver_code(self):
  title,help=explain('[Errno 1062] The service has not been started.','wifi')
  self.assertIn('Wi-Fi',title);self.assertIn('Sandbox',help);self.assertNotIn('1062',title+help)
 def test_other_services_are_not_mislabelled_wifi(self):
  title,_=explain('[Errno 1062] The service has not been started.','vpn')
  self.assertNotIn('Wi-Fi',title)
 def test_permission_and_timeout_have_next_steps(self):
  self.assertIn('Approve',explain('Permission denied')[1])
  self.assertIn('try again',explain('timed out')[1])
if __name__=='__main__':unittest.main()
