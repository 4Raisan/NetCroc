"""Local GUI integration. No DNS changes, Wi-Fi switches, or external probes."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.ui import App

class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.withdraw();self.app=App(self.root,diagnostic=True)

    def tearDown(self):
        if self.app.worker and self.app.worker.is_alive():
            self.app.stop_event.set();self.app.worker.join(timeout=5)
        self.app.quit()

    def test_startup_with_connection_checks_already_enabled(self):
        from netcroc.core import DEFAULTS
        root=tk.Tk();root.withdraw();app=None
        try:
            with patch.dict(DEFAULTS,details=True):app=App(root,diagnostic=True)
            root.update_idletasks()
            self.assertEqual(app.log.winfo_manager(),'pack')
            app.details.set(False);app.toggle_details()
            self.assertEqual(app.log.winfo_manager(),'')
            app.details.set(True);app.toggle_details()
            self.assertEqual(app.log.winfo_manager(),'pack')
        finally:
            if app:app.quit()
            else:root.destroy()

    def test_dashboard_live_history_and_dns_results(self):
        dashboard=self.app.dashboard
        dashboard.live({'interfaces':{'Wi-Fi':(3*1024**2,1024,3*1024**2,1024)},
            'apps':{('Wi-Fi','browser.exe'):(3*1024**2,1024)},'totals':{('Wi-Fi','browser.exe'):(100,200)},
            'elapsed':1,'wifi':{'Wi-Fi':'Preview network'},'up':{'Wi-Fi'}})
        self.assertEqual(dashboard.down.get(),'↓ 3.00 MB/s')
        self.assertEqual(dashboard.up.get(),'↑ 1.00 KB/s')
        self.assertEqual(len(dashboard.apps.get_children()),1)
        dashboard.history.record([('adapter','Preview network','',1024,2048),('app','Preview network','browser.exe',500,200)],1)
        dashboard.refresh_history();self.assertEqual(len(dashboard.history_table.get_children()),1)
        dashboard.group.set('Applications');dashboard.period('This month')
        self.assertIn('500 B',dashboard.history_table.item(dashboard.history_table.get_children()[0],'values'))
        dashboard.events.put(('dns',[{'name':'test','servers':['1.1.1.1'],'median':12,'failures':0,'attempts':9}]))
        dashboard.poll();self.assertEqual(len(dashboard.dns_table.get_children()),1)

    def test_invalid_period_shows_error_not_crash(self):
        self.app.dashboard.history_period.set('bad')
        with patch('netcroc.dashboard.messagebox.showerror') as error:self.app.dashboard.refresh_history()
        error.assert_called_once()

    def test_real_local_head_runs_at_one_second_cadence(self):
        times=queue.Queue()
        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                times.put(time.monotonic());self.send_response(200);self.end_headers()
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            self.app.custom.set(f'http://127.0.0.1:{server.server_port}/')
            self.app.interval.set(1);self.app.start()
            observed=[times.get(timeout=5) for _ in range(3)]
            self.app.pause();self.app.worker.join(timeout=5)
            self.assertTrue(all(.95<=b-a<=3 for a,b in zip(observed,observed[1:])),observed)
        finally:server.shutdown();server.server_close()

    def test_comparison_dialog_completion_restores_regular_mode(self):
        from netcroc.core import comparison_summary
        self.app.compare_window()
        data=comparison_summary([(True,25,'HTTP 200')]*18)
        def completed(target,protocol,interval,stop,emit):
            emit(('OFF',data));emit(('ON',data));return {'OFF':data,'ON':data}
        with patch('netcroc.ui.run_comparison',side_effect=completed):
            self.app.begin_comparison()
            self.app.compare_worker.join(timeout=2)
            self.app.poll()
        self.assertFalse(self.app.comparing)
        self.assertIn('No clear difference',self.app.compare_text.get())
        self.assertFalse(self.app.smart.get())
        self.assertEqual(len(self.app.compare_table.get_children()),2)

    def test_cancelled_comparison_restores_previous_selections_before_resume(self):
        self.app.compare_window();self.app.running=True
        with patch('netcroc.ui.run_comparison',return_value=None):
            self.app.begin_comparison();self.app.compare_worker.join(timeout=2)
        self.app.isp.set('Dialog');self.app.smart.set(True)
        with patch.object(self.app,'start') as resume:
            self.app.poll();resume.assert_called_once_with(automatic=True)
        self.assertEqual(self.app.isp.get(),'Hutch');self.assertFalse(self.app.smart.get())

    def test_busy_adapter_reaches_smart_mode(self):
        self.app.dashboard.live({'interfaces':{'Wi-Fi':(50000,100,0,0)},'apps':{},'totals':{},
            'elapsed':1,'wifi':{},'up':{'Wi-Fi'}})
        self.assertGreater(self.app.activity[0],32768)

    def test_dns_apply_without_admin_never_calls_backend(self):
        dashboard=self.app.dashboard
        with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=0),patch('netcroc.dashboard.messagebox.showerror'),patch.object(dashboard.dns,'apply') as apply:
            dashboard.apply_dns();apply.assert_not_called()

    def test_forget_connected_profile_protection(self):
        from netcroc.wifi import Wifi
        wifi=object.__new__(Wifi)
        with patch.object(wifi,'current',return_value='active'):
            with self.assertRaises(ValueError):wifi.forget({'profile':'active','interface':object()})

    def test_live_monitor_reads_interfaces_without_admin(self):
        dashboard=self.app.dashboard
        dashboard.monitor_thread=threading.Thread(target=dashboard.monitor,daemon=True)
        dashboard.monitor_thread.start()
        found=False;deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            kind,value=dashboard.events.get(timeout=12)
            if kind=='live' and value['elapsed']>0:
                self.assertTrue(value['interfaces']);found=True;break
        self.assertTrue(found,'Live adapter sampler did not produce data')

if __name__=='__main__':unittest.main()
