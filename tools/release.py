"""Build/check runnable releases. Never runs the app or changes system settings."""
import argparse
import ast
import os
import platform
import re
import subprocess
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = {"title":"NetCroc","exe":"NetCroc","entry":"src/app.py","icon":"netcroc.ico","mode":"windowed","data":""}

def release_version():
    """Same source of truth and format as tools/package_release.py."""
    source=(ROOT/'src'/'netcroc'/'updates.py').read_text(encoding='utf-8')
    match=re.search(r"^VERSION\s*=\s*['\"]([^'\"]+)",source,re.MULTILINE)
    if not match:raise ValueError('Could not read the application version.')
    return match.group(1).split('+',1)[0]

def asset_name(kind=None):
    arch='arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x64'
    version=release_version()
    return f"{CONFIG['exe']}-v{version}-windows-{arch}.exe"


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
        if sys.platform == 'win32':
            command += ['--manifest', str(ROOT / 'assets' / 'netcroc.manifest')]
        for resource in ('netcroc-transparent.png', 'netcroc-tray-eye.ico'):
            command += ['--add-data', str(ROOT / 'assets' / resource) + os.pathsep + 'assets']
        for dependency in ('paramiko', 'cryptography', 'bcrypt', 'PyNaCl', 'cffi'):
            command += ['--copy-metadata', dependency]
        sys.path.insert(0,str(ROOT/'src'))
        from netcroc.wireguard_setup import bundle
        msi=bundle(Path(temporary)/'wireguard')
        command+=['--add-data',str(msi)+os.pathsep+'assets/wireguard']
        # Every build path stays absolute and inside the temporary directory, so nothing is
        # written into the repository while PyInstaller works.
        subprocess.run(command + [str(ROOT / CONFIG['entry'])], check=True, cwd=temporary)
        output = ROOT / 'releases'
        output.mkdir(exist_ok=True)
        built = Path(temporary) / 'output' / (CONFIG['exe'] + '.exe')
        # The versioned file is the primary product: a locked compatibility EXE must never
        # cost the build its output.
        versioned = output / asset_name()
        staged = versioned.with_name(versioned.name + '.new')
        try:
            shutil.copyfile(built, staged)
            staged.replace(versioned)
        finally:
            staged.unlink(missing_ok=True)
        print('Versioned release build: ' + versioned.name)

def prepare():
    output = ROOT / 'releases'
    output.mkdir(exist_ok=True)
    name=asset_name()
    launcher='@echo off\r\nstart "" "%~dp0'+name+'" %*\r\n'
    (output/'NetCroc.bat').write_text(launcher,encoding='ascii')
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
        if file.is_file() and file.suffix.lower() not in allowed and file.name!='NetCroc':
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
