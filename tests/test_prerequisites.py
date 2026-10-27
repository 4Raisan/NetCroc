import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.prerequisites import inspect
class SetupTests(unittest.TestCase):
 def test_missing_and_damaged_cores_are_reported_without_installing(self):
  class Backend:
   def installed(self):return None
  with tempfile.TemporaryDirectory() as tmp:
   found=inspect(tmp,Backend())
   self.assertEqual([x[1] for x in found],[True,False,False])
   self.assertIn('optional',found[-1][2])
   core=Path(tmp)/'ssh'/'routing-core';core.mkdir(parents=True)
   (core/('sing-box.exe' if sys.platform=='win32' else 'sing-box')).write_bytes(b'changed')
   (core/'verified.sha256').write_text('bad')
   self.assertIn('Verification failed',inspect(tmp,Backend())[-1][2])
if __name__=='__main__':unittest.main()
