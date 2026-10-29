import os
import base64
from contextlib import nullcontext
"""Local GUI integration. No DNS changes, Wi-Fi switches, or external probes."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import gc
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
    def test_setup_dialog_checks_without_installing(self):
        with patch('netcroc.setup_ui.inspect',return_value=[('Core application',True,'Ready')]), \
             patch.object(self.app.dashboard.ssh_tab.routing,'install') as install:
            self.app.shell.open_setup()
            self.assertTrue(self.app.setup_dialog.winfo_exists())
            install.assert_not_called()
            self.app.setup_dialog.destroy()

    def test_live_rows_keep_selection_when_values_and_order_change(self):
        from netcroc.dashboard import rows
        tree=self.app.dashboard.apps
        rows(tree,[('Browser','1 KB/s','2 KB/s','4 KB'),('Updater','2 KB/s','1 KB/s','3 KB')])
        selected=tree.get_children()[0];tree.selection_set(selected)
        rows(tree,[('Updater','3 KB/s','1 KB/s','4 KB'),('Browser','2 KB/s','2 KB/s','5 KB')])
        self.assertEqual(tree.selection(),(selected,))
        self.assertEqual(tree.item(selected,'values')[0],'Browser')
        self.assertEqual(tree.index(selected),1)
        before=tree.get_children();rows(tree,[('Updater','3 KB/s','1 KB/s','4 KB'),('Browser','2 KB/s','2 KB/s','5 KB')])
        self.assertEqual(tree.get_children(),before)

    def test_simple_navigation_preserves_tools_without_starting_network(self):
        shell=self.app.shell
        self.assertEqual(shell.book.select(),str(shell.primary['Home']))
        with patch('netcroc.ui.probe') as probe, patch.object(self.app.dashboard,'test_dns') as dns_test:
            for name in shell.destinations:
                shell.show(name); self.root.update_idletasks()
                self.assertEqual(shell.book.select(),str(shell.destinations[name]))
            for name in shell.pages:
                shell.open(name); self.root.update_idletasks()
                self.assertEqual(shell.book.select(),str(shell.pages[name]))
                selected=[n for n,b in shell.buttons.items() if b.instate(['selected'])]
                self.assertEqual(len(selected),1)
                self.assertEqual(str(shell.destinations[selected[0]]),shell.book.select())
            shell.show('Home'); self.root.update_idletasks()
            self.assertEqual([n for n,b in shell.buttons.items() if b.instate(['selected'])],['Home'])
            probe.assert_not_called(); dns_test.assert_not_called()
        self.assertEqual(list(shell.tools),['DNS','VPN','SSH / TLS','VLESS','Website tests'])
        self.assertNotIn('Tools',[shell.book.tab(p,'text') for p in shell.book.tabs()])
        self.assertIsNone(self.app.dashboard.ssh_tab.session)
        self.assertIsNone(self.app.dashboard.vless_tab.session)

    def test_sidebar_links_fit_the_minimum_window(self):
        # Use one isolated Tk interpreter so other tests' destroyed roots cannot
        # receive timer callbacks when the native window is mapped.
        import subprocess
        source=str(Path(__file__).resolve().parents[1]/'src')
        script=f"""import sys, tkinter as tk
sys.path.insert(0,{source!r})
from netcroc.ui import App
root=tk.Tk();app=App(root,diagnostic=True)
try:
    root.geometry('1000x720');root.deiconify();root.update()
    tab=app.dashboard
    tab.history.record([('app','test','chrome.exe',2*1024**2,0)],1)
    tab.group.set('Applications');app.shell.show('Usage');root.update()
    assert tab.bars.winfo_y()+tab.bars.winfo_height()<=tab.history_body.winfo_height()
    assert tab.history_footer.winfo_y()+tab.history_footer.winfo_height()<=tab.tab_history.winfo_height()
    assert root.overrideredirect()
    app.window.maximize();root.update();assert app.window.maximized
    app.window.maximize();root.update();assert not app.window.maximized
    from netcroc.desktop import monitor_rect,position_window
    left,top,right,bottom=monitor_rect(root,(root.winfo_rootx()+100,root.winfo_rooty()+40))
    position_window(root,(right-left,bottom-top),(left,top));root.update()
    app.window.restore_geometry=None;app.window.maximized=False;app.window.maximize();root.update()
    assert root.winfo_width()<right-left and root.winfo_height()<bottom-top
    if sys.platform=='win32':
        import ctypes
        from netcroc.desktop import handle
        gdi=ctypes.windll.gdi32;user=ctypes.windll.user32
        gdi.CreateRectRgn.argtypes=[ctypes.c_int]*4;gdi.CreateRectRgn.restype=ctypes.c_void_p
        gdi.PtInRegion.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int]
        gdi.DeleteObject.argtypes=[ctypes.c_void_p]
        user.GetWindowRgn.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
        region=gdi.CreateRectRgn(0,0,1,1)
        try:
            assert user.GetWindowRgn(handle(root),region)>0
            assert not gdi.PtInRegion(region,0,0)
            assert gdi.PtInRegion(region,50,50)
        finally:gdi.DeleteObject(region)
        surface=app.window.surface
        assert int(surface.pack_info()['padx'])==2 and int(surface.pack_info()['pady'])==2
        assert root.cget('background')=='#69bc2a'
        region=gdi.CreateRectRgn(0,0,1,1)
        try:
            assert user.GetWindowRgn(surface.winfo_id(),region)>0
            assert not gdi.PtInRegion(region,0,0)
            assert gdi.PtInRegion(region,50,50)
        finally:gdi.DeleteObject(region)
        app.diagnostic=False;app.window.taskbar();app.diagnostic=True
        app.window.minimize();root.update()
        ctypes.windll.user32.IsIconic.argtypes=[ctypes.c_void_p]
        assert ctypes.windll.user32.IsIconic(handle(root))
        app.show();root.update();assert not ctypes.windll.user32.IsIconic(handle(root))
    sidebar=app.shell.sidebar
    for name,button in app.shell.buttons.items():
        assert button.winfo_height()>1,name
        assert button.winfo_y()+button.winfo_height()<=sidebar.winfo_height(),name
        assert button.winfo_x()+button.winfo_width()<=sidebar.winfo_width(),name
finally:app.quit()
"""
        result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_home_toggle_uses_existing_start_and_pause(self):
        with patch.object(self.app,'start') as start:
            self.app.shell.toggle_checks();start.assert_called_once()
        self.app.running=True
        with patch.object(self.app,'pause') as pause:
            self.app.shell.toggle_checks();pause.assert_called_once()
        self.app.running=False

    def test_wifi_simple_columns_search_and_actions_keep_the_right_profile(self):
        from types import SimpleNamespace
        tab=self.app.dashboard
        item=lambda name,connected:dict(profile=name,connected=connected,password='synthetic',auth='test',interface=SimpleNamespace(description='test'))
        tab.events.put(('wifi',[item('Z network',True),item('A network',False)]));tab.poll()
        self.assertEqual(tuple(tab.wifi_table['columns']),('Network','Status','Password','Copy'))
        self.assertEqual(tab.visible_profiles[0]['profile'],'Z network')
        tab.wifi_search.set('a network')
        self.assertEqual(len(tab.wifi_table.get_children()),1)
        tab.wifi_table.selection_set(tab.wifi_table.get_children()[0])
        self.assertEqual(tab.selected_wifi()['profile'],'A network')
        with patch('netcroc.dashboard.messagebox.showinfo') as details:tab.wifi_details()
        self.assertIn('Security: test',details.call_args.args[1])

    def test_empty_app_history_explains_missing_data_and_hides_the_blank_chart(self):
        tab=self.app.dashboard
        tab.group.set('Applications');tab.refresh_history()
        self.assertEqual(tab.history_empty.winfo_manager(),'pack')
        self.assertEqual(tab.bars.winfo_manager(),'')
        self.assertIn('not been recorded',tab.history_empty_title.get())
        tab.history.record([('adapter','test','',100,200)],1)
        tab.show_network_history()
        self.assertEqual(tab.history_empty.winfo_manager(),'')
        self.assertEqual(len(tab.history_table.get_children()),1)
        self.assertEqual(tab.bars.winfo_manager(),'pack')

    def test_wifi_copy_cell_uses_only_clicked_row(self):
        from types import SimpleNamespace
        tab=self.app.dashboard
        tab.visible_profiles=[{'password':'first-test-key'},{'password':'second-test-key'}]
        with patch.object(tab.wifi_table,'identify_column',return_value='#4'), \
             patch.object(tab.wifi_table,'identify_row',return_value='row'), \
             patch.object(tab.wifi_table,'index',return_value=1), \
             patch.object(self.root,'clipboard_clear'),patch.object(self.root,'clipboard_append') as copy:
            tab.copy_wifi_cell(SimpleNamespace(x=1,y=1))
            copy.assert_called_once_with('second-test-key')

    def test_vless_paste_validates_before_saving_and_never_connects(self):
        tab=self.app.dashboard.vless_tab
        with patch.object(tab.store,'save',return_value='id') as save,patch.object(tab,'refresh'),patch.object(tab,'connect') as connect:
            tab.paste_links();tab.paste_input.insert('1.0','vless://bad');tab.paste_save();save.assert_not_called()
            tab.paste_input.delete('1.0','end')
            tab.paste_input.insert('1.0','vless://00000000-0000-4000-8000-000000000001@server.example:443?security=tls&type=tcp#Test')
            tab.paste_save();save.assert_called_once();connect.assert_not_called()
            self.assertFalse(tab.paste_dialog.winfo_exists())

    def test_retry_app_tracking_requests_capture_restart(self):
        from unittest.mock import patch
        with patch('netcroc.platforms.admin',return_value=True),patch('netcroc.ui.os.name','nt'),patch.object(self.app.shell,'open') as opened:
            self.app.enable_app_tracking()
            self.assertTrue(self.app.dashboard.capture_retry.is_set())
            self.assertIn('Retrying',self.app.dashboard.capture_status.get())
            opened.assert_called_once_with('Live traffic')

    def test_tunnel_buttons_reflect_selection_and_session(self):
        for tab in (self.app.dashboard.ssh_tab, self.app.dashboard.vless_tab):
            self.assertEqual(str(tab.bar.buttons['Connect']['state']), 'disabled')
            self.assertEqual(str(tab.bar.buttons['Disconnect']['state']), 'disabled')
        tab = self.app.dashboard.ssh_tab
        tab.tree.insert('', 'end', iid='a' * 32, text='Synthetic', values=('h:443', 'Local SOCKS5', ''))
        tab.tree.selection_set('a' * 32); tab._update_buttons()
        self.assertEqual(str(tab.bar.buttons['Connect']['state']), 'normal')
        self.assertEqual(str(tab.bar.buttons['Disconnect']['state']), 'disabled')
        class LiveSession:
            cancel = threading.Event(); started = 1
        tab.session = LiveSession(); tab._update_buttons()
        self.assertEqual(str(tab.bar.buttons['Connect']['state']), 'disabled')
        self.assertEqual(str(tab.bar.buttons['Disconnect']['state']), 'normal')
        tab.session = None; tab.tree.delete('a' * 32); tab._update_buttons()

    def test_failed_disconnect_is_reported_not_silently_disconnected(self):
        tab = self.app.dashboard.ssh_tab
        class BadSession:
            cancel = threading.Event()
            def stop(self): raise OSError('Routing recovery is still pending.')
        tab.session = BadSession()
        with patch('netcroc.ssh_ui.messagebox.showerror') as dialog:
            tab.disconnect()
            tab.stopping.join(timeout=5)
            tab.poll()
            dialog.assert_called_once()
        self.assertTrue(tab.line.has_error)
        self.assertIn('Disconnect incomplete', tab.status.get())
        self.assertIsNone(tab.session)

    def test_vless_health_drop_disconnects_off_the_gui_thread(self):
        tab = self.app.dashboard.vless_tab
        worker_threads = []
        class DyingSession:
            cancel = threading.Event(); active = True; profile_id = None
            def healthy(self): return False
            def stop(self): worker_threads.append(threading.current_thread() is not threading.main_thread())
        tab.session = DyingSession()
        tab.poll()
        self.assertIsNotNone(tab.stopping)
        tab.stopping.join(timeout=5)
        self.assertEqual(worker_threads, [True])

    def test_stale_vpn_selection_raises_valueerror_not_stopiteration(self):
        dash = self.app.dashboard
        dash.vpn_table.insert('', 'end', iid='b' * 32, values=('Gone', 'h:1', 'r', 'stopped', '—'))
        dash.vpn_table.selection_set('b' * 32)
        dash.vpn_profiles = []
        with self.assertRaises(ValueError):
            dash.selected_vpn()
        dash.vpn_table.delete('b' * 32)

    def test_status_error_survives_live_poll(self):
        tab = self.app.dashboard.ssh_tab
        tab.line.error('Synthetic failure')
        class FakeSession:
            cancel = threading.Event(); started = 1
            def snapshot(self): return {'status': 'Connected', 'port': 1080, 'down': 0, 'up': 0}
        tab.session = FakeSession()
        tab.poll()
        self.assertTrue(tab.line.has_error)
        self.assertIn('Synthetic failure', tab.status.get())
        tab.session = None

    def test_auto_isp_waits_before_starting_and_manual_override_wins(self):
        self.app.isp.set('Airtel')
        with patch('netcroc.ui.threading.Thread'),patch('netcroc.ui.probe') as probe:
            self.app.start();probe.assert_not_called()
        self.assertTrue(self.app.pending_start)
        with patch.object(self.app,'start') as resume:
            self.app.receive_isp(self.app.isp_serial,{'isp':'Hutch','provider':'Hutchison'},None)
        self.assertEqual(self.app.isp.get(),'Hutch')
        resume.assert_called_once_with(automatic=True,resolved=True)
        old=self.app.isp_serial
        self.app.isp.set('Dialog');self.app.manual_isp()
        self.app.receive_isp(old,{'isp':'Hutch','provider':'Hutchison'},None)
        self.assertEqual(self.app.isp.get(),'Dialog')
        self.assertFalse(self.app.auto_isp.get())
        self.app.auto_isp.set(True);self.app.change_isp_mode()
        self.assertEqual(self.app.isp.get(),'Hutch')

    def test_wifi_change_invalidates_old_lookup_and_detects_only_in_auto_mode(self):
        app=self.app
        app.isp.set('Airtel');app.auto_isp.set(True)
        with patch('netcroc.ui.threading.Thread'):
            app.detect_isp(); old=app.isp_serial
            app.observe_wifi({'Wi-Fi':'First'})
            app.observe_wifi({'Wi-Fi':'Second'})
            app.receive_isp(old,{'isp':'Hutch','provider':'Hutchison'},None)
            self.assertNotEqual(app.isp.get(),'Hutch')
            self.root.after_cancel(app.isp_wifi_timer);app.isp_wifi_timer=None
            app.detect_isp()
            app.receive_isp(app.isp_serial,{'isp':'Dialog','provider':'Dialog'},None)
            self.assertEqual(app.isp.get(),'Dialog')
            app.manual_isp(); serial=app.isp_serial
            app.observe_wifi({'Wi-Fi':'Third'})
            self.assertEqual(app.isp_serial,serial)
            self.assertEqual(app.isp.get(),'Dialog')

    def test_new_wifi_schedules_detection_and_failed_lookup_retries(self):
        app=self.app; app.auto_isp.set(True)
        scheduled=[]
        with patch.object(self.root,'after',side_effect=lambda delay,fn: scheduled.append((delay,fn)) or 'timer'), \
             patch('netcroc.ui.threading.Thread') as worker:
            app.observe_wifi({'Wi-Fi':'New network'})
            self.assertEqual(scheduled[-1][0],2000)
            scheduled.pop()[1]()
            worker.assert_called_once()
            app.receive_isp(app.isp_serial,None,'TimeoutError')
            self.assertEqual(scheduled[-1][0],30000)
            scheduled.pop()[1]()
            self.assertEqual(worker.call_count,2)

    def test_failed_isp_lookup_preserves_manual_target_and_can_still_start(self):
        self.app.isp.set('Hutch');self.app.pending_start=True
        with patch.object(self.app,'start') as start:
            self.app.receive_isp(self.app.isp_serial,None,'TimeoutError')
        self.assertEqual(self.app.isp.get(),'Hutch')
        self.assertIn('Could not detect',self.app.isp_detection.get())
        start.assert_called_once_with(automatic=True,resolved=True)

    @unittest.skipUnless(os.name=='nt','Windows approval flow')
    def test_declined_app_tracking_approval_keeps_the_app_running(self):
        with patch('netcroc.platforms.admin',return_value=False),patch('ctypes.windll.shell32.ShellExecuteW',return_value=5),patch('netcroc.ui.messagebox.showinfo'),patch.object(self.app,'quit') as quit:
            self.app.enable_app_tracking();quit.assert_not_called()

    def test_usage_friendly_names_filters_and_responsive_chart(self):
        tab=self.app.dashboard
        tab.history.record([('app','test',r'C:\Program Files\Google\Chrome\chrome.exe',2*1024**2,0),
                            ('app','test','Unresolved process (PID 1)',300,100),
                            ('app','test','Unresolved process (PID 2)',300,100)],1)
        tab.group.set('Applications');tab.refresh_history()
        labels=[tab.history_table.item(i,'values')[0] for i in tab.history_table.get_children()]
        self.assertEqual(labels,['Google Chrome','Unattributed traffic'])
        tab.history_minimum.set(1);tab.refresh_history()
        self.assertEqual(len(tab.history_table.get_children()),1)
        tab.history_minimum.set(5);tab.refresh_history()
        self.assertIn('No apps match',tab.history_empty_title.get())
        tab.history_minimum.set(0);tab.refresh_history()
        tab.bars.configure(width=400,height=100);self.root.update_idletasks();tab.draw_history_bars()
        self.assertTrue(tab.bars.find_all())

    def test_overlay_hovers_without_starting_a_network_or_guessing_country(self):
        overlay=self.app.overlay
        overlay.mode.set('Left edge');overlay.enabled.set(True)
        self.root.after_cancel(overlay.timer)
        with patch('netcroc.tray_mode.monitor_rect',return_value=(0,0,1920,1080)),patch.object(self.root,'winfo_pointerxy',return_value=(0,400)),patch.object(overlay.panel,'deiconify'),patch('netcroc.tray_mode.time.monotonic',return_value=100):
            overlay.tick()
        self.assertTrue(overlay.visible)
        self.root.after_cancel(overlay.timer)
        with patch('netcroc.tray_mode.monitor_rect',return_value=(0,0,1920,1080)),patch.object(self.root,'winfo_pointerxy',return_value=(1800,800)),patch('netcroc.tray_mode.time.monotonic',return_value=101):
            overlay.tick()
        self.assertFalse(overlay.visible)
        overlay.signal={'active':True,'interfaces':['VPN']};overlay.update_text()
        self.assertIn('not checked',overlay.vpn_text.get())
        overlay.enabled.set(False)

    def test_vless_profile_screen_and_no_automatic_connection(self):
        tab=self.app.dashboard.vless_tab
        self.assertIsNone(tab.session)
        with patch('netcroc.vless_ui.vless.Session') as session:
            with self.assertRaises(ValueError):tab.connect()
            session.assert_not_called()
        tab.edit()
        window=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel) and not getattr(w,'netcroc_overlay',False))
        window.destroy()
    def test_ssh_tab_and_editor_have_all_configuration_pages(self):
        tab=self.app.dashboard.ssh_tab
        self.assertEqual(list(self.app.shell.primary),['Home','Connection checks','Live traffic','Usage','Wi-Fi','Tray mode'])
        tab.edit()
        windows=[w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel) and not getattr(w,'netcroc_overlay',False)]
        self.assertEqual(len(windows),1)
        books=[w for w in windows[0].winfo_children() if isinstance(w,__import__('tkinter').ttk.Notebook)]
        self.assertEqual(len(books[0].tabs()),4)
        windows[0].destroy()

    def test_ssh_connect_missing_profile_does_not_start_network(self):
        tab=self.app.dashboard.ssh_tab
        with patch('netcroc.ssh_ui.ssh.Session') as session:
            with self.assertRaises(ValueError): tab.connect()
            session.assert_not_called()

    def test_ssh_editor_save_is_encrypted_without_connecting(self):
        import tempfile
        from netcroc.ssh_tunnel import ProfileStore
        tab=self.app.dashboard.ssh_tab
        keyring_patch=patch('keyring.get_password',return_value=base64.b64encode(bytes(range(32))).decode()) if os.name!='nt' else nullcontext()
        with keyring_patch,tempfile.TemporaryDirectory() as folder:
            tab.store=ProfileStore(Path(folder))
            identifier=tab.store.save({'host':'example.com','password':'synthetic-only'})
            tab.refresh(); self.assertEqual(len(tab.tree.get_children()),1)
            self.assertNotIn('synthetic-only',str(tab.tree.item(identifier)))
            self.assertIsNone(tab.session)

    def setUp(self):
        # Tk cycles must be finalized on their owning thread, before workers allocate.
        gc.collect()
        self.root=tk.Tk();self.root.withdraw();self.app=App(self.root,diagnostic=True)

    def tearDown(self):
        if self.app.worker and self.app.worker.is_alive():
            self.app.stop_event.set();self.app.worker.join(timeout=5)
        self.app.quit()
        self.app=None
        self.root=None
        gc.collect()

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

    @unittest.skipUnless(os.name=='nt','POSIX requests native authorization inside the backend')
    def test_dns_apply_without_admin_never_calls_backend(self):
        dashboard=self.app.dashboard
        with patch('ctypes.windll.shell32.IsUserAnAdmin',return_value=0),patch('netcroc.dashboard.messagebox.showerror'),patch.object(dashboard.dns,'apply') as apply:
            dashboard.apply_dns();apply.assert_not_called()

    def test_forget_connected_profile_protection(self):
        from netcroc.wifi import Wifi
        wifi=object.__new__(Wifi)
        with patch.object(wifi,'current',return_value='active'):
            with self.assertRaises(ValueError):wifi.forget({'profile':'active','interface':object()})

    def test_vpn_profile_table_and_ipv4_baseline_display(self):
        dashboard=self.app.dashboard
        item={'id':'a'*32,'label':'Example','endpoint':'vpn.example.com:51820','route':'Default route','dns':'1.1.1.1','peers':1}
        dashboard.events.put(('vpn',[(item,{'service':'not installed','handshake':'Not checked'})]))
        dashboard.events.put(('vpn-ip',('192.0.2.1',True)))
        dashboard.poll()
        self.assertEqual(len(dashboard.vpn_table.get_children()),1)
        self.assertEqual(dashboard.vpn_baseline,'192.0.2.1')
        dashboard.events.put(('vpn-ip',('192.0.2.2',False)));dashboard.poll()
        self.assertIn('changed from baseline',dashboard.vpn_ip.get())
        self.assertIn('not a DNS-leak test',dashboard.vpn_ip.get())

    def test_vpn_nonadmin_action_does_not_connect_or_ask_confirmation(self):
        dashboard=self.app.dashboard
        item={'id':'a'*32,'label':'Example'}
        with patch.object(dashboard,'selected_vpn',return_value=item),patch.object(dashboard.vpn_store.backend,'require_admin',side_effect=PermissionError('admin needed')),patch('netcroc.dashboard.messagebox.showerror'),patch('netcroc.dashboard.messagebox.askyesno') as confirm,patch.object(dashboard.vpn_store,'connect') as connect:
            dashboard.vpn_action('connect');confirm.assert_not_called();connect.assert_not_called()

    def test_live_monitor_reads_interfaces_without_admin(self):
        dashboard=self.app.dashboard
        # Hosted Windows runners may already be elevated; exercise the named
        # non-admin adapter sampler instead of accidentally starting ETW capture.
        with patch('netcroc.dashboard.Traffic.start',side_effect=PermissionError('adapter-only test')):
            dashboard.monitor_thread=threading.Thread(target=dashboard.monitor,daemon=True)
            dashboard.monitor_thread.start()
            found=False;deadline=time.monotonic()+12
            try:
                while time.monotonic()<deadline:
                    kind,value=dashboard.events.get(timeout=12)
                    if kind=='live' and value['elapsed']>0:
                        self.assertTrue(value['interfaces']);found=True;break
            finally:
                dashboard.stop.set();dashboard.monitor_thread.join(timeout=5)
            self.assertFalse(dashboard.monitor_thread.is_alive())
            self.assertTrue(found,'Live adapter sampler did not produce data')

if __name__=='__main__':unittest.main()
