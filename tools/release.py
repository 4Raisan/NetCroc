"""Build/check runnable releases. Never runs the app or changes system settings."""
import argparse
import ast
import re
import subprocess
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = {"title":"NetCroc","exe":"NetCroc","entry":"src/app.py","icon":"netcroc.ico","mode":"windowed","data":""}

def source_files():
    for item in sorted(ROOT.iterdir()):
        if item.is_file() and item.suffix in ('.py', '.bat', '.md', '.txt') or item.name == '.gitignore':
            yield item
        elif item.is_dir() and item.name in ('src', 'assets', 'tests', 'tools', 'docs'):
            yield from sorted(p for p in item.rglob('*')
                              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')

def build():
    if not (3, 12) <= sys.version_info[:2] < (3, 15):
        raise SystemExit('Build requires Windows Python 3.12-3.14. Released EXEs already contain Python.')
    try:
        import PyInstaller
    except ImportError:
        raise SystemExit('Build tool missing. Run: python -m pip install PyInstaller==6.22.3')
    with tempfile.TemporaryDirectory(prefix='local-release-') as temporary:
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
                   '--' + CONFIG['mode'], '--name', CONFIG['exe'],
                   '--icon', str(ROOT / 'assets' / CONFIG['icon']), '--paths', str(ROOT / 'src'),
                   '--distpath', str(Path(temporary) / 'output'), '--workpath', str(Path(temporary) / 'work'),
                   '--specpath', temporary]
        subprocess.run(command + [str(ROOT / CONFIG['entry'])], check=True)
        (ROOT / 'releases').mkdir(exist_ok=True)
        candidate = ROOT / 'releases' / (CONFIG['exe'] + '.exe.new')
        try:
            shutil.copyfile(Path(temporary) / 'output' / (CONFIG['exe'] + '.exe'), candidate)
            candidate.replace(ROOT / 'releases' / (CONFIG['exe'] + '.exe'))
        except PermissionError:
            raise SystemExit('Release EXE is locked or not writable. Quit the running app from its tray/menu, check folder permissions, then retry --build. The previous EXE remains available.')
        finally:
            candidate.unlink(missing_ok=True)

def prepare():
    output = ROOT / 'releases'
    output.mkdir(exist_ok=True)
    if CONFIG['exe']:
        name = CONFIG['exe']
        title = CONFIG['title']
        launcher = f"""@echo off
setlocal
title {title}
if not exist "%~dp0{name}.exe" (
    echo ERROR: {name}.exe is missing from this folder.
    echo FIX: Keep this BAT beside {name}.exe in releases.
    echo Python is bundled in the EXE; no separate install is needed.
    pause
    exit /b 2
)
start "" /wait "%~dp0{name}.exe" %*
set "result=%errorlevel%"
if not "%result%"=="0" (
    echo ERROR: {title} exited with code %result%.
    echo FIX: Read the app error message. Check folder access and Windows Security protection history.
    echo If damaged, replace the EXE with a fresh complete release.
    pause
)
exit /b %result%
"""
        (output / (name + '.bat')).write_text(launcher, encoding='ascii')
    print('Runnable releases only; no source ZIPs or checksum files generated.')

def check():
    for file in source_files():
        if file.suffix == '.py':
            ast.parse(file.read_text(encoding='utf-8-sig'), filename=str(file))
        elif file.suffix == '.svg':
            ET.parse(file)
    for target in re.findall(r'\]\(([^)]+)\)', (ROOT / 'README.md').read_text(encoding='utf-8')):
        if '://' not in target and not target.startswith('#'):
            destination = ROOT / target.split('#')[0]
            if not destination.exists() and not target.startswith('releases/'):
                raise ValueError('Broken README link: ' + target)
    for file in (ROOT / 'releases').glob('*'):
        allowed = ('.exe', '.bat')
        if file.is_file() and file.suffix.lower() not in allowed:
            raise ValueError('Unexpected release file: ' + file.name)
    print('Source syntax, assets, README links and runnable release layout passed.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='Build the standalone EXE (requires PyInstaller).')
    parser.add_argument('--check', action='store_true', help='Check source and runnable releases only.')
    args = parser.parse_args()
    if args.check:
        check()
    else:
        if args.build:
            build()
        prepare()
        check()
