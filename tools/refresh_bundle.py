"""Refresh pure Python code after a completed PyInstaller 6.22.3 build.

Refuses new imports: changed dependencies require a full release.py --build.
Preserves bootloader/resources/native payloads; verifies Python code before replacement.
"""
import dis
import hashlib
import json
import marshal
from pathlib import Path
import sys
import tempfile
import types
import PyInstaller
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter,ZlibArchiveWriter
from PyInstaller.utils.win32.winutils import update_exe_pe_checksum
from verify_bundle import fingerprint

def imports(code):
    result={i.argval for i in dis.get_instructions(code) if i.opname=='IMPORT_NAME'}
    for value in code.co_consts:
        if isinstance(value,types.CodeType):result.update(imports(value))
    return result

class RawArchive(CArchiveWriter):
    def _write_entry(self,fp,entry):
        name,blob,compressed,kind=entry
        return self._write_blob(fp,blob,name,kind,compress=compressed)

def main():
    if PyInstaller.__version__!='6.22.3':raise SystemExit('Requires the original PyInstaller 6.22.3 build tool.')
    root=Path(__file__).resolve().parents[1];exe=root/'test-artifacts'/'packaging-base.exe'
    output=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'releases'/'NetCroc.exe'
    if output.parent!=(root/'releases').resolve():raise SystemExit('Output must stay inside this project releases folder.')
    archive=CArchiveReader(str(exe));pyz=archive.open_embedded_archive('PYZ.pyz')
    rename=lambda name:name.replace('connection_tray','netcroc')
    code={rename(name):pyz.extract(name) for name,entry in pyz.toc.items() if entry[0]!=3}
    refreshed=[]
    for source in sorted((root/'src'/'netcroc').glob('*.py')):
        name='netcroc' if source.stem=='__init__' else 'netcroc.'+source.stem
        if name not in code:raise SystemExit(f'New module {name}: perform a full rebuild.')
        current=compile(source.read_text(encoding='utf-8-sig'),str(source),'exec',dont_inherit=True,optimize=0)
        if imports(current)-{rename(i) for i in imports(code[name])}:raise SystemExit(f'New imports in {name}: perform a full rebuild.')
        if fingerprint(current)!=fingerprint(code[name]):refreshed.append(name)
        code[name]=current
    app=compile((root/'src'/'app.py').read_text(encoding='utf-8-sig'),'app.py','exec',dont_inherit=True,optimize=0)
    if imports(app)-{rename(i) for i in imports(marshal.loads(archive.extract('app')))}:raise SystemExit('New app imports: perform a full rebuild.')
    entries=[]
    for name,(kind,_,_) in pyz.toc.items():
        if kind not in (0,1,3):raise SystemExit('Unsupported PYZ entry; perform a full rebuild.')
        name=rename(name)
        source='-' if kind==3 else name.replace('.','/')+('/__init__.py' if kind==1 else '.py')
        entries.append((name,source,'PYMODULE'))
    prefix=exe.read_bytes()[:archive._start_offset]
    with tempfile.TemporaryDirectory(prefix='netcroc-python-refresh-') as folder:
        folder=Path(folder);new_pyz=folder/'PYZ.pyz'
        ZlibArchiveWriter(str(new_pyz),entries,code_dict=code)
        raw=[(option,b'',False,'o') for option in archive.options]
        for name,(_,_,_,compressed,kind) in archive.toc.items():
            blob=new_pyz.read_bytes() if name=='PYZ.pyz' else marshal.dumps(app) if name=='app' else archive.extract(name)
            raw.append((name,blob,bool(compressed),kind))
        if 'python314.dll' not in archive.toc:raise SystemExit('Unexpected Python runtime; perform a full rebuild.')
        package=folder/'NetCroc.pkg';RawArchive(str(package),raw,'python314.dll')
        candidate=output.with_suffix('.exe.new')
        try:
            candidate.write_bytes(prefix+package.read_bytes());update_exe_pe_checksum(str(candidate))
            check=CArchiveReader(str(candidate));new=check.open_embedded_archive('PYZ.pyz')
            for name in code:
                if fingerprint(code[name])!=fingerprint(new.extract(name)):raise RuntimeError('Refreshed archive did not verify')
            for name in archive.toc:
                if name not in ('app','PYZ.pyz') and archive.extract(name)!=check.extract(name):raise RuntimeError('Native/runtime payload changed')
            if fingerprint(app)!=fingerprint(marshal.loads(check.extract('app'))):raise RuntimeError('App entry did not verify')
            candidate.replace(output)
        finally:
            candidate.unlink(missing_ok=True)
    result={'refreshed_modules':refreshed,'dependency_imports_unchanged':True,'native_payloads_unchanged':True,
            'executable':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
    (root/'test-artifacts'/'python-refresh.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
