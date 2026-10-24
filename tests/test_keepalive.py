import sys
import threading
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.core import DEFAULTS, smart_interval, comparison_summary, comparison_verdict, run_comparison

class FakeStop:
    def __init__(self):self.now=0;self.cancelled=False
    def is_set(self):return self.cancelled
    def wait(self,seconds):self.now+=seconds;return self.cancelled

class KeepaliveTests(unittest.TestCase):
    def test_smart_is_optional_and_preserves_idle_interval(self):
        self.assertFalse(DEFAULTS['smart'])
        self.assertEqual(smart_interval(1,False,(999999,10),11),1)
        self.assertEqual(smart_interval(1,True,(0,10),11),1)
        self.assertEqual(smart_interval(1,True,(999999,10),11),15)
        self.assertEqual(smart_interval(30,True,(999999,10),11),30)
        self.assertEqual(smart_interval(1,True,(999999,10),16),1)

    def test_summary_includes_failures_without_invented_latency(self):
        data=comparison_summary([(True,10,''),(False,4000,''),(True,30,'')])
        self.assertEqual(data,dict(attempts=3,failures=1,median=20,p95=30))
        self.assertIsNone(comparison_summary([(False,4000,'')])['p95'])

    def test_equal_measurements_with_extra_on_traffic(self):
        stop=FakeStop();calls=[];events=[]
        def check(*args):calls.append(stop.now);return True,25,'HTTP 200 server responded'
        result=run_comparison('local','HTTP',1,stop,events.append,duration=120,spacing=10,
                              clock=lambda:stop.now,check=check)
        self.assertEqual(result['OFF']['attempts'],12)
        self.assertEqual(result['ON']['attempts'],12)
        self.assertGreater(len([t for t in calls if t>=120]),12)
        self.assertEqual(comparison_verdict(result['OFF'],result['ON']),'No clear difference in this run.')

    def test_cancellation_and_endpoint_refusal_are_inconclusive(self):
        stop=FakeStop();stop.cancelled=True
        self.assertIsNone(run_comparison('', 'HTTP',1,stop,lambda x:None,clock=lambda:stop.now))
        stop=FakeStop();calls=[]
        def refused(*args):calls.append(1);return True,25,'HTTP 429 server responded'
        self.assertIsNone(run_comparison('', 'HTTP',1,stop,lambda x:None,clock=lambda:stop.now,check=refused))
        self.assertEqual(len(calls),1)

    def test_verdict_requires_data_and_does_not_hide_failures(self):
        off=dict(attempts=18,failures=0,median=50,p95=100)
        self.assertIn('Lower',comparison_verdict(off,off|{'p95':70}))
        self.assertIn('Worse',comparison_verdict(off,off|{'p95':70,'failures':2}))
        self.assertIn('Inconclusive',comparison_verdict(off,off|{'attempts':2}))

if __name__=='__main__':unittest.main()
