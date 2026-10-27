import json
from pathlib import Path
import sys,unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.isp import identify,lookup

class IspTests(unittest.TestCase):
    def test_provider_names_and_unknown_exits(self):
        for name,expected in [('Hutchison Telecommunications Lanka Private Limited','Hutch'),('Dialog Axiata PLC','Dialog'),('Sri Lanka Telecom PLC','SLT'),('SLT Mobitel','Mobitel'),('Bharti Airtel Lanka','Airtel'),('Example VPN Hosting',None),('SLTC campus',None)]:
            self.assertEqual(identify({'success':True,'connection':{'isp':name}})['isp'],expected,name)

    def test_https_bounded_lookup_and_api_failure(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'success':True,'connection':{'isp':'Hutchison'}}).encode()
        with patch('netcroc.isp.urllib.request.urlopen',return_value=response) as call:
            self.assertEqual(lookup()['isp'],'Hutch')
        self.assertTrue(call.call_args.args[0].full_url.startswith('https://'))
        response.__enter__.return_value.read.assert_called_once_with(16385)
        with self.assertRaises(ValueError):identify({'success':False})
        with self.assertRaises(ValueError):identify({'success':True,'connection':[]})

    def test_restart_wait_does_not_wait_on_a_reused_process_id(self):
        from netcroc.platforms import wait_for_process_exit
        process=MagicMock();process.create_time.return_value=200
        with patch('psutil.Process',return_value=process):wait_for_process_exit(123,100)
        process.wait.assert_not_called()
