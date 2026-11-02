"""Managed official WireGuard MSI dependency for Windows. Never installs on import."""
import base64,json,os,platform,re,subprocess,sys,tempfile,urllib.request
from pathlib import Path
BASE='https://download.wireguard.com/windows-client/'
LIMIT=16*1024*1024

def powershell(script,timeout=45):
    encoded=base64.b64encode(("$ErrorActionPreference='Stop';"+script).encode('utf-16le')).decode('ascii')
    p=subprocess.run(['powershell','-NoProfile','-NonInteractive','-OutputFormat','Text','-EncodedCommand',encoded],capture_output=True,text=True,env={k:v for k,v in os.environ.items() if k.lower()!='psmodulepath'},timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if p.returncode:raise OSError(p.stderr.strip() or 'Windows dependency operation failed')
    return p.stdout.strip()

def literal(value):return "'"+str(value).replace("'","''")+"'"
def version(value):return tuple(map(int,re.findall(r'\d+',value)[:3]))
def latest():
    if os.name!='nt':raise OSError('Managed WireGuard installation is available on Windows.')
    arch='arm64' if platform.machine().lower() in ('arm64','aarch64') else 'amd64' if platform.machine().lower() in ('amd64','x86_64') else 'x86'
    with urllib.request.urlopen(BASE,timeout=20) as response:html=response.read(512*1024).decode()
    found=re.findall(r'wireguard-'+arch+r'-(\d+\.\d+(?:\.\d+)?)\.msi',html)
    if not found:raise OSError('Official WireGuard installer list unavailable')
    number=max(found,key=version);return number,f'wireguard-{arch}-{number}.msi'

def verify(path):
    script="$s=Get-AuthenticodeSignature -LiteralPath "+literal(path)+"; if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'WireGuard LLC'){throw 'WireGuard publisher signature verification failed'}"
    powershell(script)

def download(folder,filename):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);target=folder/filename
    if target.exists():verify(target);return target
    request=urllib.request.Request(BASE+filename,headers={'User-Agent':'NetCroc-dependency-setup'})
    with urllib.request.urlopen(request,timeout=45) as response:data=response.read(LIMIT+1)
    if len(data)>LIMIT:raise OSError('WireGuard installer exceeds size limit')
    target.write_bytes(data);verify(target);return target

def installed_version(backend):
    path=backend.installed()
    if not path:return None
    return powershell('(Get-Item -LiteralPath '+literal(path)+').VersionInfo.ProductVersion')

def status(backend):
    current=installed_version(backend)
    try:number,filename=latest()
    except OSError:
        if current:raise
        base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[2]))/'assets'/'wireguard'
        arch='arm64' if platform.machine().lower() in ('arm64','aarch64') else 'amd64' if platform.machine().lower() in ('amd64','x86_64') else 'x86'
        candidates=list(base.glob('wireguard-'+arch+'-*.msi'))
        if not candidates:raise
        selected=max(candidates,key=lambda p:version(p.stem.split('-')[-1]))
        filename=selected.name;number=selected.stem.split('-')[-1]
    return {'installed':current,'latest':number,'filename':filename,'needed':not current or version(current)<version(number)}

def bundle(folder):
    number,filename=latest();path=download(folder,filename)
    return path

def install_or_update(backend):
    details=status(backend)
    if not details['needed']:return 'WireGuard '+details['installed']+' is up to date.'
    powershell("if(Get-Service -Name 'WireGuardTunnel$*' -ErrorAction SilentlyContinue | Where-Object Status -eq Running){throw 'Disconnect active WireGuard tunnels before updating.'}")
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[2]))/'assets'/'wireguard'
    candidate=base/details['filename']
    with tempfile.TemporaryDirectory(prefix='netcroc-wireguard-') as temp:
        if candidate.is_file():verify(candidate);installer=candidate
        else:installer=download(temp,details['filename'])
        args='/i "'+str(installer)+'" /passive /norestart DO_NOT_LAUNCH=1'
        script="$p=Start-Process -FilePath msiexec.exe -ArgumentList "+literal(args)+" -Verb RunAs -WindowStyle Hidden -Wait -PassThru; if($p.ExitCode -notin @(0,3010)){throw ('WireGuard installation failed: '+$p.ExitCode)}; $p.ExitCode"
        result=powershell(script,timeout=600)
    actual=installed_version(backend)
    if not actual or version(actual)<version(details['latest']):raise OSError('WireGuard installation did not complete. Retry setup.')
    return 'WireGuard '+actual+' ready.'+(' Restart Windows to finish.' if result.strip()=='3010' else '')
