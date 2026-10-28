import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc import updates
class Response:
 def __init__(self,value):self.value=value
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):return json.dumps(self.value).encode()
class UpdateTests(unittest.TestCase):
 def test_beta_and_stable_order(self):
  self.assertGreater(updates.version_key('v0.4.0'),updates.version_key('v0.4.0-beta.3'))
  self.assertGreater(updates.version_key('v0.4.0-beta.10'),updates.version_key('v0.4.0-beta.3'))
  self.assertIsNone(updates.version_key('v0.4.0-unknown'))
 def test_releases_ignore_drafts_and_compare_versions(self):
  releases=[{'tag_name':'v0.4.0-beta.4','draft':False},{'tag_name':'v9.0.0','draft':True}]
  result=updates.check(lambda *args,**kwargs:Response(releases))
  self.assertEqual(result['status'],'available');self.assertEqual(result['version'],'v0.4.0-beta.4')
  self.assertEqual(updates.check(lambda *args,**kwargs:Response([{'tag_name':'v0.4.0-beta.3'}]))['status'],'current')
if __name__=='__main__':unittest.main()
