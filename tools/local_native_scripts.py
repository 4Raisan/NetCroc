"""Create standalone install/run scripts from verified native release archives."""
import argparse,base64,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'releases'
parser=argparse.ArgumentParser()
parser.add_argument('cache',type=Path)
parser.add_argument('--output',type=Path,default=out)
args=parser.parse_args();cache=args.cache;out=args.output;out.mkdir(parents=True,exist_ok=True)
for file in cache.rglob('*'):
 if file.suffix not in ('.zip','.gz'):continue
 match=re.match(r'NetCroc-v([0-9.]+)-',file.name)
 if not match:continue
 version=match.group(1)
 data=file.read_bytes();mac=file.suffix=='.zip';arch='arm64' if 'arm64' in file.name else 'x64';system='macos' if mac else 'linux';ext='command' if mac else 'sh'
 for mode in ('Setup','Portable'):
  script='#!/bin/bash\nset -euo pipefail\nWORK=$(mktemp -d)\ntrap \'rm -rf "$WORK"\' EXIT\n'
  script+='base64 '+('-D' if mac else '-d')+' > "$WORK/payload" <<\'NETCROC_PAYLOAD\'\n'+base64.encodebytes(data).decode()+'NETCROC_PAYLOAD\n'
  if mac:
   script+='/usr/bin/ditto -x -k "$WORK/payload" "$WORK/unpacked"\n'
   script+=('mkdir -p "$HOME/Applications"\n/usr/bin/ditto "$WORK/unpacked/NetCroc/NetCroc.app" "$HOME/Applications/NetCroc.app"\nopen "$HOME/Applications/NetCroc.app"\n' if mode=='Setup' else 'open -W "$WORK/unpacked/NetCroc/NetCroc.app"\n')
  else:
   script+='tar -xzf "$WORK/payload" -C "$WORK"\nchmod +x "$WORK/NetCroc"\n'
   script+=('mkdir -p "$HOME/.local/bin"\ncp "$WORK/NetCroc" "$HOME/.local/bin/NetCroc"\necho "Installed: $HOME/.local/bin/NetCroc"\n' if mode=='Setup' else '"$WORK/NetCroc" "$@"\n')
  (out/f'NetCroc-v{version}-{system}-{arch}-{mode}.{ext}').write_text(script,encoding='utf-8',newline='\n')
