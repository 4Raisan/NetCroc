import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.app_names import aggregate,identity,UNKNOWN
from netcroc.desktop import Preferences,edge_triggered,panel_position,clamp_position,MODES

class DesktopTests(unittest.TestCase):
    def test_app_groups_preserve_bytes_and_never_reassign_historic_pids(self):
        rows=[(r'C:\Program Files\Google\Chrome\Application\chrome.exe',200,100),
              (r'C:\Other\chrome.exe',100,50),('Unresolved process (PID 100)',30,5),('PID 200',20,10)]
        groups=aggregate(rows)
        self.assertEqual(len(groups),2)
        self.assertEqual(sum(v.down for v in groups),350)
        self.assertEqual(sum(v.up for v in groups),165)
        chrome=next(v for v in groups if v.label=='Google Chrome')
        self.assertEqual(len(chrome.sources),2)
        unknown=next(v for v in groups if v.label==UNKNOWN)
        self.assertEqual(unknown.down+unknown.up,65)
        self.assertNotIn('PID',unknown.label)

    def test_volume_threshold_uses_combined_download_upload_after_grouping(self):
        rows=[('chrome.exe',700000,0),(r'C:\Apps\chrome.exe',400000,0),('brave.exe',100,0)]
        self.assertEqual([v.label for v in aggregate(rows,1024**2)],['Google Chrome'])
        self.assertEqual(aggregate(rows,5*1024**2),[])
        self.assertEqual(len(rows),3)

    def test_known_names_and_location_are_separate(self):
        self.assertEqual(identity(r'C:\Program Files (x86)\Avira\VPN\Avira.VpnService.exe')[1],'Avira VPN Service')
        self.assertEqual(identity('/opt/google/chrome/chrome')[1],'Google Chrome')

    def test_preferences_are_validated_and_static_position_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'desktop.json';prefs=Preferences(path)
            prefs.update(dict(overlay_mode='Static',overlay_enabled=True,overlay_position=[-1200,150],usage_minimum_mb=5))
            loaded=Preferences(path)
            self.assertEqual(loaded.data['overlay_position'],[-1200,150])
            loaded.update(dict(overlay_mode='bad',overlay_position=['bad',0],usage_minimum_mb=-1))
            self.assertEqual(loaded.data['overlay_mode'],'Static')
            self.assertEqual(loaded.data['usage_minimum_mb'],5)
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_all_four_overlay_modes_and_negative_monitor_coordinates(self):
        rect=(-1920,0,0,1080)
        self.assertTrue(edge_triggered('Left edge',(-1919,500),rect))
        self.assertTrue(edge_triggered('Right edge',(-1,500),rect))
        self.assertTrue(edge_triggered('Top middle',(-960,1),rect))
        self.assertFalse(edge_triggered('Top middle',(-1800,1),rect))
        self.assertFalse(edge_triggered('Left edge',(-1800,500),rect))
        self.assertEqual(panel_position('Static',(370,200),rect,[-5000,5000]),(-1920,880))
        for mode in MODES:
            x,y=panel_position(mode,(370,200),rect)
            self.assertTrue(-1920<=x<=-370)
            self.assertTrue(0<=y<=880)

    def test_vpn_hint_uses_interfaces_not_running_application_names(self):
        from netcroc.tray_mode import vpn_signal
        result=MagicMock(returncode=0,stdout=json.dumps([{'Name':'Ethernet','InterfaceDescription':'Normal physical NIC'}]).encode())
        with patch('netcroc.tray_mode.os.name','nt'),patch('netcroc.tray_mode.subprocess.run',return_value=result):
            self.assertFalse(vpn_signal()['active'])
            result.stdout=json.dumps([{'Name':'Ethernet 2','InterfaceDescription':'Avira Phantom VPN Adapter'}]).encode()
            self.assertTrue(vpn_signal()['active'])
