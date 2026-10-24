import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.core import DEFAULTS, PRESETS, Settings, validate, probe, startup_command

class CoreTests(unittest.TestCase):
    def test_presets(self):
        for isp, url in PRESETS.items():
            self.assertEqual(validate(DEFAULTS | {'isp': isp}), url)

    def test_custom_and_icmp(self):
        self.assertEqual(validate(DEFAULTS | {'custom': 'example.com'}), 'https://example.com')
        self.assertEqual(validate(DEFAULTS | {'custom': 'https://example.com/path', 'protocol': 'ICMP'}), 'example.com')
        self.assertEqual(validate(DEFAULTS | {'custom': 'https://[::1]', 'protocol': 'ICMP'}), '::1')

    def test_reject_credentials_and_flags(self):
        for target in ('https://user:pass@example.com', 'file:///test', '-t', 'x;exit', 'https://example.com:bad'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate(DEFAULTS | {'custom': target})

    def test_atomic_settings_and_invalid_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Settings(folder)
            store.save(DEFAULTS | {'isp': 'Dialog'})
            self.assertEqual(store.load()['isp'], 'Dialog')
            self.assertFalse(store.path.with_suffix('.tmp').exists())
            store.path.write_text('broken')
            self.assertEqual(store.load(), DEFAULTS)

    def test_head_no_body(self):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch('urllib.request.urlopen', return_value=response) as request:
            self.assertTrue(probe('https://example.com', 'HTTP')[0])
            self.assertEqual(request.call_args.args[0].method, 'HEAD')
            self.assertEqual(request.call_args.kwargs['timeout'], 4)
            response.read.assert_not_called()

    def test_http_error_is_response(self):
        import urllib.error
        with patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError('https://example.com', 403, '', {}, None)):
            self.assertTrue(probe('https://example.com', 'HTTP')[0])

    def test_timeout_and_hidden_ping(self):
        with patch('urllib.request.urlopen', side_effect=TimeoutError()):
            self.assertFalse(probe('https://example.com', 'HTTP')[0])
        with patch('subprocess.run', return_value=MagicMock(returncode=0)) as run:
            self.assertTrue(probe('example.com', 'ICMP')[0])
            self.assertEqual(run.call_args.args[0], ['ping.exe', '-n', '1', '-w', '1500', 'example.com'])
            self.assertNotIn('shell', run.call_args.kwargs)
            self.assertTrue(run.call_args.kwargs['creationflags'])

    def test_data_folder_preserves_legacy_history_and_uses_new_brand_for_new_users(self):
        from netcroc.core import data_folder
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ',LOCALAPPDATA=folder):
            self.assertEqual(data_folder(),Path(folder)/'NetCroc')
            (Path(folder)/'ConnectionTrayPreview').mkdir()
            self.assertEqual(data_folder(),Path(folder)/'ConnectionTrayPreview')

    def test_startup_quoted_and_tray(self):
        with patch('sys.frozen', True, create=True), patch('sys.executable', 'C:\\My App\\test.exe'):
            self.assertEqual(startup_command(), '"C:\\My App\\test.exe" --tray')

    def test_startup_only_own_registry_value(self):
        from netcroc.core import set_startup
        with patch('winreg.OpenKey', return_value=MagicMock()) as opened, patch('winreg.SetValueEx') as write, patch('winreg.DeleteValue') as remove:
            set_startup(True)
            self.assertEqual(write.call_args.args[1], 'NetCroc')
            self.assertTrue(write.call_args.args[-1].endswith('--tray'))
            self.assertEqual(remove.call_args.args[1], 'ConnectionTrayPreview')
            set_startup(False)
            self.assertEqual(remove.call_args.args[1], 'NetCroc')
            self.assertEqual(opened.call_args.args[1], r'Software\Microsoft\Windows\CurrentVersion\Run')

if __name__ == '__main__':
    unittest.main()
