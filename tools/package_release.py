"""Build on the current OS, verify the frozen app, then package runnable files only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    system=platform.system().lower();arch='arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x64'
    label={'darwin':'macos','linux':'linux','windows':'windows'}[system]
    output=ROOT/'test-artifacts/packages';output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='netcroc-native-build-') as temp:
        work=Path(temp)
        cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--name','NetCroc','--paths',str(ROOT/'src'),
             '--distpath',str(work/'dist'),'--workpath',str(work/'work'),'--specpath',str(work)]
        cmd+=['--onedir','--windowed'] if system=='darwin' else ['--onefile']+(['--windowed'] if system=='windows' else [])
        cmd+=['--add-data',str(ROOT/'assets/netcroc-transparent.png')+os.pathsep+'assets']
        # Pillow imports its Tk interpreter finder dynamically on Linux.
        if system=='linux':cmd+=['--hidden-import','PIL._tkinter_finder']
        if system=='windows':cmd+=['--icon',str(ROOT/'assets/netcroc.ico')]
        for dep in ('paramiko','cryptography','bcrypt','PyNaCl','cffi'):cmd+=['--copy-metadata',dep]
        if system!='windows':cmd+=['--copy-metadata','keyring','--collect-submodules','keyring.backends']
        subprocess.run(cmd+[str(ROOT/'src/app.py')],check=True)
        exe=work/'dist'/('NetCroc.app/Contents/MacOS/NetCroc' if system=='darwin' else 'NetCroc.exe' if system=='windows' else 'NetCroc')
        subprocess.run([sys.executable,str(ROOT/'tools/verify_bundle.py'),str(exe)],check=True)
        subprocess.run([sys.executable,str(ROOT/'tools/smoke_frozen.py'),str(exe)],check=True)
        if system=='windows':
            asset=output/f'NetCroc-{label}-{arch}.exe';shutil.copy2(exe,asset)
        elif system=='darwin':
            subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(work/'dist/NetCroc.app')],check=True)
            asset=output/f'NetCroc-{label}-{arch}.zip'
            subprocess.run(['/usr/bin/ditto','-c','-k','--sequesterRsrc','--keepParent',str(work/'dist/NetCroc.app'),str(asset)],check=True)
        else:
            asset=output/f'NetCroc-{label}-{arch}.tar.gz'
            with tarfile.open(asset,'w:gz') as tar:tar.add(exe,arcname='NetCroc')
        (ROOT/'test-artifacts'/f'package-{label}-{arch}.json').write_text(json.dumps({'asset':asset.name,'sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'source_match':True,'frozen_smoke_passed':True},indent=2),encoding='utf-8')
        print('Verified runnable package: '+asset.name)

if __name__=='__main__':main()
