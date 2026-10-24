"""Verify that a frozen executable contains the current application source code."""
import hashlib
import json
import marshal
from pathlib import Path
import sys
import types
from PyInstaller.archive.readers import CArchiveReader

def fingerprint(value):
    if isinstance(value,types.CodeType):
        return (value.co_argcount,value.co_posonlyargcount,value.co_kwonlyargcount,value.co_flags,
                value.co_code,tuple(fingerprint(c) for c in value.co_consts),value.co_names,
                value.co_varnames,value.co_freevars,value.co_cellvars,value.co_exceptiontable)
    return value

def main():
    root=Path(__file__).resolve().parents[1]
    exe=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'releases'/'NetCroc.exe'
    archive=CArchiveReader(str(exe)); pyz=archive.open_embedded_archive('PYZ.pyz')
    result={}
    for source in sorted((root/'src'/'netcroc').glob('*.py')):
        name='netcroc' if source.stem=='__init__' else 'netcroc.'+source.stem
        bundled=pyz.extract(name)
        current=compile(source.read_text(encoding='utf-8-sig'),str(source),'exec',dont_inherit=True,optimize=0)
        result[name]=fingerprint(bundled)==fingerprint(current)
    bundled=marshal.loads(archive.extract('app'))
    current=compile((root/'src'/'app.py').read_text(encoding='utf-8-sig'),str(root/'src'/'app.py'),'exec',dont_inherit=True,optimize=0)
    result['app']=fingerprint(bundled)==fingerprint(current)
    output={'executable':exe.name,'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'modules_match_current_source':result,'passed':all(result.values())}
    target=root/'test-artifacts'/'bundle-verification.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,indent=2),encoding='utf-8');print(json.dumps(output,indent=2))
    return 0 if output['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
