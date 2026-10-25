"""Privileged POSIX routing supervisor. GUI/keyring remain under the desktop user."""
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys
import tempfile
import time
import psutil
from . import platforms


def read_state(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def parent_alive(pid,created,owner):
    try:
        process=psutil.Process(pid)
        return process.create_time()==created and process.is_running() and process.uids().real==owner and process.status()!=psutil.STATUS_ZOMBIE
    except (psutil.Error,OSError):return False


def validate_state(path,owner,token):
    path=Path(path)
    directory=path.parent.lstat();info=path.lstat()
    if path.name!='state.json' or not path.is_absolute() or not stat.S_ISDIR(directory.st_mode) or directory.st_uid!=owner or directory.st_mode&0o077:
        raise PermissionError('Routing control directory must be private and owned by the desktop user.')
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=owner or info.st_mode&0o077:raise PermissionError('Routing status must be a private regular file.')
    if not isinstance(token,str) or len(token)!=64 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid routing transaction.')
    if read_state(path).get('token')!=token:raise ValueError('Stale routing transaction.')
    return info


def write_state(path,owner,token,state,**values):
    info=validate_state(path,owner,token)
    fd=os.open(path,os.O_WRONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'w') as file:
        actual=os.fstat(file.fileno())
        if (actual.st_dev,actual.st_ino)!=(info.st_dev,info.st_ino):raise PermissionError('Routing status changed during access.')
        file.truncate()
        json.dump(dict(token=token,state=state,updated=time.time(),**values),file)


def configuration(payload):
    from .ssh_routing import Routing,configuration as ssh_config
    core=Path(payload['core']).resolve()
    routing=Routing(core.parent)
    if core!=routing.exe.resolve():raise ValueError('Unexpected routing executable name.')
    routing.verify()
    addresses=payload['upstream']
    import ipaddress
    if not isinstance(addresses,list) or not addresses or len(addresses)>32:raise ValueError('Invalid upstream exclusions.')
    addresses=[str(ipaddress.ip_address(a)) for a in addresses]
    if payload['kind']=='ssh':value=ssh_config(int(payload['port']),addresses)
    elif payload['kind']=='vless':
        from .vless import validate,config
        profile=validate(payload['profile'])
        if profile['routing']!='tun':raise ValueError('A whole-PC profile is required.')
        value=config(profile,addresses)
    else:raise ValueError('Unsupported routing kind.')
    result=subprocess.run([str(core),'check','-c','stdin'],input=json.dumps(value),text=True,capture_output=True,timeout=20)
    if result.returncode:raise ValueError('Native routing configuration rejected.')
    return core,value


def launch(payload,owner):
    platforms.require_admin()
    validate_state(payload['state'],owner,payload['token'])
    if not parent_alive(payload['parent'],payload['created'],owner):raise ValueError('Desktop application exited or changed identity.')
    configuration(payload)  # Validate before starting the detached worker.
    write_state(payload['state'],owner,payload['token'],'accepted')
    args=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).resolve().parents[1]/'app.py')])
    worker=subprocess.Popen(args+['--routing-watch'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        start_new_session=True,env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
    try:worker.stdin.write(json.dumps(dict(payload=payload,owner=owner)).encode());worker.stdin.close()
    except Exception:worker.terminate();worker.wait(5);raise
    return dict(accepted=True)


def supervise(process,job,payload,owner,before,interface):
    path=Path(payload['state']);token=payload['token'];ready=False;started=time.monotonic();last=0
    try:
        while True:
            if not parent_alive(payload['parent'],payload['created'],owner):break
            if read_state(path.with_name('stop.json')).get('token')==token:break
            if process.poll() is not None:raise OSError('Routing engine exited.')
            names=set(psutil.net_if_addrs())
            available=([name for name in names-before if name.startswith('utun')] if interface=='utun' else [interface] if interface in names else [])
            if ready and not available:raise OSError('Routing adapter disappeared.')
            if available:ready=True
            if not ready and time.monotonic()-started>15:raise TimeoutError('Routing adapter did not appear.')
            if time.monotonic()-last>=1:
                write_state(path,owner,token,'ready' if ready else 'starting',adapter=available[0] if available else '',pid=process.pid)
                last=time.monotonic()
            time.sleep(.2)
    finally:
        job.close()
        try:process.wait(5)
        except subprocess.TimeoutExpired:process.kill();process.wait(3)


def worker():
    platforms.require_admin()
    raw=b''
    while len(raw)<=131072:
        part=os.read(0,min(65536,131073-len(raw)))
        if not part:break
        raw+=part
    if len(raw)>131072:raise ValueError('Routing request too large.')
    request=json.loads(raw)
    payload=request['payload'];owner=request['owner'];path=Path(payload['state']);token=payload['token']
    validate_state(path,owner,token)
    process=None;job=None
    try:
        if not parent_alive(payload['parent'],payload['created'],owner) or read_state(path.with_name('stop.json')).get('token')==token:
            write_state(path,owner,token,'stopped');return
        core,value=configuration(payload)
        before=set(psutil.net_if_addrs())
        process=subprocess.Popen([str(core),'run','-c','stdin'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        job=platforms.ChildGuard(process)
        process.stdin.write(json.dumps(value).encode());process.stdin.close()
        supervise(process,job,payload,owner,before,value['inbounds'][0]['interface_name'])
        write_state(path,owner,token,'stopped')
    except Exception as error:
        if job:
            try:job.close()
            except OSError:pass
        if process and process.poll() is None:process.kill();process.wait(3)
        write_state(path,owner,token,'error',error_type=type(error).__name__)


class RemoteRouting:
    def __init__(self):self.folder=None;self.token=None;self.path=None
    def start(self,core,kind,upstream,**values):
        self.folder=Path(tempfile.mkdtemp(prefix='netcroc-routing-'));self.path=self.folder/'state.json';self.token=secrets.token_hex(32)
        self.path.write_text(json.dumps(dict(token=self.token,state='pending')),encoding='utf-8');self.path.chmod(0o600)
        payload=dict(core=str(Path(core).resolve()),kind=kind,upstream=list(upstream),state=str(self.path),token=self.token,
            parent=os.getpid(),created=psutil.Process().create_time(),**values)
        try:
            platforms.elevated_native('routing-start',payload)
            end=time.monotonic()+45
            while time.monotonic()<end:
                state=read_state(self.path)
                if state.get('token')==self.token:
                    if state.get('state')=='ready':return
                    if state.get('state') in ('error','stopped'):raise OSError('Privileged routing could not start; original routing restored. Check other VPNs and the optional core.')
                time.sleep(.2)
            raise TimeoutError('Privileged routing did not become ready.')
        except Exception:
            try:self.stop()
            except OSError:pass
            raise
    def healthy(self):
        state=read_state(self.path) if self.path else {}
        return state.get('token')==self.token and state.get('state')=='ready' and time.time()-state.get('updated',0)<15
    def stop(self):
        if self.path and self.path.exists():
            stop=self.path.with_name('stop.json')
            stop.write_text(json.dumps(dict(token=self.token)),encoding='utf-8');stop.chmod(0o600)
            if read_state(self.path).get('state')=='pending':
                stop.unlink(missing_ok=True);self.path.unlink(missing_ok=True);self.folder.rmdir();self.path=None;return
            end=time.monotonic()+10
            while time.monotonic()<end:
                state=read_state(self.path)
                if state.get('token')==self.token and state.get('state') in ('stopped','error'):
                    stop.unlink(missing_ok=True);self.path.unlink(missing_ok=True);self.folder.rmdir();self.path=None;return
                time.sleep(.2)
            # Preserve recovery status instead of silently claiming the routes are gone.
            raise OSError('Routing recovery is still pending. Close NetCroc to trigger parent-exit cleanup; control state was preserved.')
