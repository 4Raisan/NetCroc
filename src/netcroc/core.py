import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlsplit

PRESETS = {'Dialog': 'https://www.dialog.lk/robots.txt', 'SLT': 'https://www.slt.lk/robots.txt', 'Mobitel': 'https://www.mobitel.lk/robots.txt',
           'Hutch': 'https://hutch.lk/robots.txt', 'Airtel': 'https://www.airtel.lk/robots.txt'}
DEFAULTS = dict(isp='Hutch', custom='', interval=1, protocol='HTTP', details=False, startup=False, smart=False)

def validate(settings):
    if settings['isp'] not in PRESETS or settings['interval'] not in (1, 5, 10, 15, 30):
        raise ValueError('Choose an ISP and an available interval.')
    if settings['protocol'] not in ('HTTP', 'ICMP'):
        raise ValueError('Choose HTTP or ICMP.')
    target = settings['custom'].strip() or PRESETS[settings['isp']]
    if len(target) > 2048:
        raise ValueError('Target is too long.')
    if '://' not in target:
        target = 'https://' + target
    parsed = urlsplit(target)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use a website URL or host without login details.')
    host = parsed.hostname
    if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-:' for c in host) or host.startswith('-'):
        raise ValueError('Enter a valid website or IP address.')
    try:
        parsed.port
    except ValueError:
        raise ValueError('Invalid port.') from None
    return target if settings['protocol'] == 'HTTP' else host

def probe(target, protocol):
    start = time.monotonic()
    try:
        if protocol == 'HTTP':
            request = urllib.request.Request(target, method='HEAD', headers={'User-Agent': 'NetCroc/0.3'})
            try:
                with urllib.request.urlopen(request, timeout=4) as response:
                    status = response.status
            except urllib.error.HTTPError as response:
                status = response.code
                response.close()
            return True, round((time.monotonic()-start)*1000), f'HTTP {status} · server responded'
        from .platforms import ping_command
        result = subprocess.run(ping_command(target), capture_output=True,
                                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0), timeout=4)
        return result.returncode == 0, round((time.monotonic()-start)*1000), 'Ping reply' if result.returncode == 0 else 'No ping reply'
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return False, round((time.monotonic()-start)*1000), type(error).__name__ + ' · check connection or target'

def data_folder():
    if os.name!='nt':
        from .platforms import data_folder as native_folder
        return native_folder()
    base=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))
    legacy=base/'ConnectionTrayPreview'
    return legacy if legacy.exists() else base/'NetCroc'


class Settings:
    def __init__(self, folder=None):
        self.folder = Path(folder) if folder is not None else data_folder()
        self.path = self.folder / 'settings.json'

    def load(self):
        try:
            value = DEFAULTS | json.loads(self.path.read_text(encoding='utf-8'))
            validate(value)
            return value
        except (OSError, ValueError, TypeError, KeyError):
            return DEFAULTS.copy()

    def save(self, value):
        validate(value)
        self.folder.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
        temporary.replace(self.path)

def startup_command():
    if getattr(sys, 'frozen', False):
        return subprocess.list2cmdline([sys.executable, '--tray'])
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    return subprocess.list2cmdline([str(pythonw), str(Path(__file__).resolve().parents[1] / 'app.py'), '--tray'])

def set_startup(enabled):
    if os.name!='nt':
        from .platforms import startup
        return startup(enabled)
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            # Install the replacement before removing the old sign-in command.
            winreg.SetValueEx(key, 'NetCroc', 0, winreg.REG_SZ, startup_command())
        for name in (('ConnectionTrayPreview',) if enabled else ('ConnectionTrayPreview','NetCroc')):
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass

def smart_interval(interval, enabled, activity, now):
    """Use a conservative activity threshold; stale/missing samples preserve normal mode."""
    rate, sampled = activity
    return max(interval, 15) if enabled and 0 <= now-sampled <= 5 and rate >= 32*1024 else interval


def comparison_summary(samples):
    good = sorted(ms for ok, ms, _ in samples if ok)
    n = len(good)
    return dict(attempts=len(samples), failures=len(samples)-n,
                median=((good[(n-1)//2]+good[n//2])/2 if n else None),
                p95=(good[max(0, (95*n+99)//100-1)] if n else None))


def comparison_verdict(off, on):
    if min(off['attempts'], on['attempts']) < 10 or off['median'] is None or on['median'] is None:
        return 'Inconclusive: too few usable checks.'
    a=off['failures']/off['attempts']; b=on['failures']/on['attempts']
    tolerance=max(10, off['p95']*.1)
    if b < a and on['p95'] <= off['p95']+tolerance:
        return 'Fewer failed checks with keep-alive ON in this run.'
    if b > a or on['p95'] > off['p95']+tolerance:
        return 'Worse check results with keep-alive ON in this run.'
    if on['p95'] < off['p95']-tolerance:
        return 'Lower slow-response time with keep-alive ON in this run.'
    return 'No clear difference in this run.'


def run_comparison(target, protocol, interval, stop, emit, duration=180, spacing=10,
                   clock=time.monotonic, check=probe):
    """Sparse equal-cadence measurement in both phases; extra ON traffic is not scored."""
    summaries={}
    failures=0
    for phase in ('OFF', 'ON'):
        start=clock(); end=start+duration; next_measure=start; next_keep=start
        samples=[]
        while clock() < end:
            if stop.is_set(): return None
            now=clock(); measure=now >= next_measure
            if measure or (phase=='ON' and now >= next_keep):
                result=check(target, protocol)
                if stop.is_set(): return None
                # Abort rather than repeatedly hitting a refusing/overloaded endpoint.
                if protocol=='HTTP' and result[2].startswith(('HTTP 4','HTTP 5')):
                    emit('Endpoint refused or is overloaded. Comparison inconclusive; choose another target.')
                    return None
                if measure:
                    samples.append(result)
                    next_measure += spacing
                    while next_measure <= clock(): next_measure += spacing
                failures=min(failures+1,6) if not result[0] else 0
                next_keep=clock()+max(interval, min(60,2**failures) if failures else interval)
                emit(f'{phase}: {len(samples)} measured checks · {max(0,int(end-clock()))}s left')
            else:
                due=min(next_measure, next_keep) if phase=='ON' else next_measure
                if stop.wait(min(.25, max(.01, due-clock()), max(.01,end-clock()))): return None
        summaries[phase]=comparison_summary(samples)
        emit((phase,summaries[phase]))
    return summaries
