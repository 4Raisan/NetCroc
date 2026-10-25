"""Small native-platform helpers. Importing never changes system settings."""
import base64
import os
from pathlib import Path
import plistlib
import shlex
import socket
import subprocess
import sys
import time

WINDOWS=os.name=='nt'
MAC=sys.platform=='darwin'

def admin():
    if WINDOWS:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    return os.geteuid()==0

def require_admin():
    if not admin():raise PermissionError('This operation needs administrator/root access. Importing and monitoring adapter totals do not.')

def run(args,timeout=25):
    env={**os.environ,'LC_ALL':'C','LANG':'C','PATH':os.pathsep.join([os.environ.get('PATH',''),'/opt/homebrew/bin','/usr/local/bin','/usr/bin','/bin','/usr/sbin','/sbin'])}
    result=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=timeout,env=env)
    if result.returncode:raise OSError('Native network operation failed. Check required tools, permissions and connection status.')
    return result.stdout.strip()

def data_folder():
    if MAC:return Path.home()/'Library'/'Application Support'/'NetCroc'
    return Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'netcroc'

def ping_command(target):
    if WINDOWS:return ['ping.exe','-n','1','-w','1500',target]
    return ['ping','-n','-c','1','-W','1500' if MAC else '2',target]

def startup(enabled):
    args=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parents[1]/'app.py')])+['--tray']
    if MAC:
        path=Path.home()/'Library/LaunchAgents/com.netcroc.desktop.plist'
        if enabled:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(plistlib.dumps({'Label':'com.netcroc.desktop','ProgramArguments':args,'RunAtLoad':True}))
        else:path.unlink(missing_ok=True)
    else:
        path=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart/netcroc.desktop'
        if enabled:
            # Desktop Entry quoting differs from shell quoting; percent is a field code.
            quoted=' '.join('"'+a.replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"' for a in args)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('[Desktop Entry]\nType=Application\nName=NetCroc\nExec='+quoted+'\nTerminal=false\n',encoding='utf-8')
        else:path.unlink(missing_ok=True)

def crypt(data,decrypt=False):
    """AES-GCM using an OS-keyring key. Never falls back to a plaintext key file."""
    import keyring
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import threading
    with _vault_lock:
        value=keyring.get_password('NetCroc','profile-encryption-key-v1')
        if value is None:
            if decrypt:raise OSError('This OS account/keyring cannot unlock the profile.')
            value=base64.b64encode(AESGCM.generate_key(bit_length=256)).decode('ascii')
            keyring.set_password('NetCroc','profile-encryption-key-v1',value)
        cipher=AESGCM(base64.b64decode(value,validate=True))
    if decrypt:
        if not data.startswith(b'NCV1') or len(data)<32:raise ValueError('Unsupported encrypted profile.')
        return cipher.decrypt(data[4:16],data[16:],b'NetCroc profile v1')
    nonce=os.urandom(12)
    return b'NCV1'+nonce+cipher.encrypt(nonce,data,b'NetCroc profile v1')

import threading
_vault_lock=threading.Lock()

class InstanceLock:
    def __init__(self):
        import fcntl
        folder=data_folder();folder.mkdir(parents=True,exist_ok=True)
        self.file=(folder/'instance.lock').open('a+')
        try:fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:self.file.close();raise OSError('NetCroc is already running. Open its existing window/tray.') from None
    def close(self):self.file.close()

def watch_child(pid,created,fd):
    import psutil
    try:
        while os.read(fd,1):pass
    finally:os.close(fd)
    try:
        child=psutil.Process(pid)
        if child.create_time()!=created:return
        child.terminate()
        try:child.wait(3)
        except psutil.TimeoutExpired:
            if child.create_time()==created:child.kill()
    except psutil.NoSuchProcess:pass

class ChildGuard:
    """A detached helper notices pipe EOF even when the GUI process crashes."""
    def __init__(self,process):
        import psutil
        read,self.write=os.pipe()
        args=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parents[1]/'app.py')])
        try:self.guard=subprocess.Popen(args+['--child-watch',str(process.pid),str(psutil.Process(process.pid).create_time()),str(read)],pass_fds=(read,),start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
        except Exception:os.close(self.write);process.terminate();raise
        finally:os.close(read)
    def close(self):
        if self.write is not None:os.close(self.write);self.write=None
        try:self.guard.wait(timeout=5)
        except subprocess.TimeoutExpired:raise OSError('Routing cleanup helper did not finish.')

def elevated_native(action,payload):
    """Use the OS approval dialog; passwords never enter NetCroc."""
    import json,tempfile
    args=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parents[1]/'app.py')])
    fd,path=tempfile.mkstemp(prefix='netcroc-control-',suffix='.json')
    try:
        with os.fdopen(fd,'w') as file:json.dump(dict(action=action,payload=payload),file)
        command=args+['--native-control',path]
        if admin():
            result=run(command,timeout=150)
        elif MAC:
            shell=shlex.join(command)
            script='do shell script '+json.dumps(shell,ensure_ascii=False)+' with administrator privileges'
            result=run(['/usr/bin/osascript','-e',script],timeout=150)
        else:result=run(['pkexec',*command],timeout=150)
        response=json.loads(Path(path).read_text())
        if 'result' not in response:raise OSError('Native authorization did not complete.')
        return response['result']
    finally:Path(path).unlink(missing_ok=True)

def native_control(path):
    import json,stat
    from . import posix_network as native
    require_admin()
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd) as file:
        info=os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode&0o077 or info.st_size>131072:raise PermissionError('Invalid private control request.')
        request=json.load(file)
    action=request['action'];payload=request['payload']
    if action=='routing-start':
        from .tun_service import launch
        result=launch(payload,info.st_uid)
    elif action=='wg-connect':result=native.WireGuard().connect(payload['name'],payload['text'])
    elif action=='wg-disconnect':result=native.WireGuard().disconnect(payload['name'])
    elif action=='dns-set':native.DnsBackend().set(payload['original'],payload['servers']);result=True
    elif action=='dns-guard':
        state=Path(payload['path'])
        if not state.is_absolute() or state.is_symlink() or state.stat().st_uid!=info.st_uid:raise PermissionError('Invalid recovery state.')
        value=json.loads(state.read_text())
        if value.get('state')!='pending' or value.get('transaction')!=payload['transaction']:raise ValueError('Stale recovery transaction.')
        args=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parents[1]/'app.py')])
        subprocess.Popen(args+['--dns-watch',str(state),payload['transaction']],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        result=True
    else:raise ValueError('Unsupported native control action.')
    output=os.open(path,os.O_WRONLY|os.O_TRUNC|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(output,'w') as file:json.dump(dict(result=result),file)
