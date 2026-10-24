"""Download verified optional core and validate config; NEVER run a TUN adapter."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from netcroc.ssh_routing import Routing

if __name__ == '__main__':
    root=Path(__file__).resolve().parents[1]
    core=Routing(root/'test-artifacts'/'verified-routing-core')
    try: core.verify()
    except (ValueError,FileNotFoundError): core.install()
    core.check(1080,['192.0.2.1','2001:db8::1'])
    print('Verified download and native configuration check passed. No routes or DNS settings changed.')
