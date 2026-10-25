"""Windows ETW network byte events. Captures metadata, never packet payloads."""
import ctypes as c
from ctypes import wintypes as w
import ipaddress
import os
import socket
import threading
import uuid
from collections import defaultdict
import psutil
from .wifi import GUID

U64=c.c_ulonglong
P=c.c_void_p

class Wnode(c.Structure):
    _fields_=[('size',w.ULONG),('provider',w.ULONG),('historical',U64),('timestamp',c.c_longlong),
              ('guid',GUID),('context',w.ULONG),('flags',w.ULONG)]

class Properties(c.Structure):
    _fields_=[('wnode',Wnode),('buffer',w.ULONG),('minimum',w.ULONG),('maximum',w.ULONG),
              ('max_file',w.ULONG),('mode',w.ULONG),('flush',w.ULONG),('enable',w.ULONG),
              ('age',w.LONG),('buffers',w.ULONG),('free',w.ULONG),('events_lost',w.ULONG),
              ('written',w.ULONG),('log_lost',w.ULONG),('real_lost',w.ULONG),('thread',P),
              ('file_offset',w.ULONG),('name_offset',w.ULONG)]

class Header(c.Structure):
    _fields_=[('size',w.USHORT),('type',w.USHORT),('flags',w.USHORT),('property',w.USHORT),
              ('tid',w.ULONG),('pid',w.ULONG),('timestamp',c.c_longlong),('provider',GUID),
              ('id',w.USHORT),('version',c.c_ubyte),('channel',c.c_ubyte),('level',c.c_ubyte),
              ('opcode',c.c_ubyte),('task',w.USHORT),('keyword',U64),('times',U64),('activity',GUID)]

class Record(c.Structure):
    _fields_=[('header',Header),('context',w.ULONG),('extended_count',w.USHORT),
              ('length',w.USHORT),('extended',P),('data',P),('user',P)]

class EventTrace(c.Structure):
    _fields_=[('header',c.c_ubyte*48),('instance',w.ULONG),('parent',w.ULONG),
              ('parent_guid',GUID),('data',P),('length',w.ULONG),('context',w.ULONG)]

class LogHeader(c.Structure):
    _fields_=[('buffer',w.ULONG),('version',w.ULONG),('provider',w.ULONG),('cpus',w.ULONG),
              ('end',c.c_longlong),('resolution',w.ULONG),('max_file',w.ULONG),('mode',w.ULONG),
              ('written',w.ULONG),('instance',GUID),('logger',w.LPWSTR),('filename',w.LPWSTR),
              ('timezone',c.c_ubyte*172),('boot',c.c_longlong),('frequency',c.c_longlong),
              ('start',c.c_longlong),('reserved',w.ULONG),('lost',w.ULONG)]

CALLBACK=c.WINFUNCTYPE(None,c.POINTER(Record))
BUFFER_CALLBACK=c.WINFUNCTYPE(w.ULONG,P)

class Logfile(c.Structure):
    _fields_=[('file',w.LPWSTR),('logger',w.LPWSTR),('current',c.c_longlong),
              ('read',w.ULONG),('mode',w.ULONG),('event',EventTrace),('header',LogHeader),
              ('buffer_callback',BUFFER_CALLBACK),('size',w.ULONG),('filled',w.ULONG),('lost',w.ULONG),
              ('callback',CALLBACK),('kernel',w.ULONG),('context',P)]

class Descriptor(c.Structure):
    _fields_=[('name',U64),('index',w.ULONG),('reserved',w.ULONG)]

SEND={10,26,42,58}
RECEIVE={11,27,43,59}

def event_direction(event_id):
    return 'up' if event_id in SEND else 'down' if event_id in RECEIVE else None

class Traffic:
    def __init__(self):
        self.lock=threading.Lock()
        self.pending=defaultdict(lambda:[0,0])
        self.status='Per-app capture requires Run as administrator; adapter totals still work.'
        self.session=U64(); self.consumer=None; self.closed=False
        self.errors=0; self.events=0; self.lost=0
        self.name='NetCroc-'+str(os.getpid())+'-'+uuid.uuid4().hex[:8]
        self.adv=c.WinDLL('advapi32'); self.tdh=c.WinDLL('tdh')
        signatures={
            'StartTraceW':([c.POINTER(U64),w.LPCWSTR,P],w.ULONG),
            'EnableTraceEx2':([U64,c.POINTER(GUID),w.ULONG,c.c_ubyte,U64,U64,w.ULONG,P],w.ULONG),
            'ControlTraceW':([U64,w.LPCWSTR,P,w.ULONG],w.ULONG),
            'OpenTraceW':([c.POINTER(Logfile)],U64),
            'ProcessTrace':([c.POINTER(U64),w.ULONG,P,P],w.ULONG),
            'CloseTrace':([U64],w.ULONG),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(self.adv,name); fn.argtypes=args; fn.restype=result
        self.tdh.TdhGetProperty.argtypes=[c.POINTER(Record),w.ULONG,P,w.ULONG,c.POINTER(Descriptor),w.ULONG,P]
        self.tdh.TdhGetProperty.restype=w.ULONG
        self.callback=CALLBACK(self._event)
        self.buffer_callback=BUFFER_CALLBACK(self._buffer)

    def _buffer(self,ptr):
        self.lost=c.cast(ptr,c.POINTER(Logfile)).contents.lost
        return 0 if self.closed else 1

    def _property(self,record,name,length):
        text=c.create_unicode_buffer(name)
        descriptor=Descriptor(c.addressof(text),0xffffffff,0)
        data=c.create_string_buffer(length)
        code=self.tdh.TdhGetProperty(record,0,None,1,c.byref(descriptor),length,data)
        if code:
            raise OSError(code,'ETW schema unavailable')
        return data.raw

    def _event(self,ptr):
        try:
            direction=event_direction(ptr.contents.header.id)
            if not direction:
                return
            # TDH reads the installed Windows manifest, rather than guessing payload offsets.
            pid=int.from_bytes(self._property(ptr,'PID',4),'little')
            size=int.from_bytes(self._property(ptr,'size',4),'little')
            ipv6=ptr.contents.header.id in {26,27,58,59}
            source=self._property(ptr,'saddr',16 if ipv6 else 4)
            destination=self._property(ptr,'daddr',16 if ipv6 else 4)
            family=socket.AF_INET6 if ipv6 else socket.AF_INET
            # Kernel TCP events identify the connection endpoints (saddr=local,
            # daddr=remote) even on RECV. UDP uses packet source/destination.
            # Confirmed with live known-payload transfer on Windows, not only
            # synthetic records: reversing TCP RECV silently discarded downloads.
            tcp=ptr.contents.header.id in {10,11,26,27}
            local=socket.inet_ntop(family,source if tcp or direction=='up' else destination)
            remote=socket.inet_ntop(family,destination if tcp or direction=='up' else source)
            if not ipaddress.ip_address(remote).is_global:
                return
            with self.lock:
                self.pending[(pid,local)][direction=='up']+=size
                self.events+=1
        except Exception:
            # ctypes callbacks must never unwind into Windows.
            self.errors+=1

    def start(self):
        if not c.windll.shell32.IsUserAnAdmin():
            return False
        size=c.sizeof(Properties)+2048
        self.storage=c.create_string_buffer(size)
        props=c.cast(self.storage,c.POINTER(Properties)).contents
        props.wnode.size=size; props.wnode.flags=0x20000; props.wnode.context=1
        props.wnode.guid=GUID.from_buffer_copy(uuid.uuid4().bytes_le)
        props.buffer=64; props.minimum=8; props.maximum=64; props.mode=0x100
        props.flush=1; props.name_offset=c.sizeof(Properties)
        code=self.adv.StartTraceW(c.byref(self.session),self.name,self.storage)
        if code:
            self.status=f'Per-app capture unavailable (Windows {code}). Adapter totals remain available.'
            return False
        provider=GUID.from_buffer_copy(uuid.UUID('7dd42a49-5329-4832-8dfd-43d979153a88').bytes_le)
        try:
            code=self.adv.EnableTraceEx2(self.session,c.byref(provider),1,5,0xffffffffffffffff,0,0,None)
            if code:
                raise OSError(code,'Cannot enable network provider')
            self.logfile=Logfile()
            self.logfile.logger=self.name; self.logfile.mode=0x100|0x10000000
            self.logfile.callback=self.callback; self.logfile.buffer_callback=self.buffer_callback
            self.consumer=U64(self.adv.OpenTraceW(c.byref(self.logfile)))
            if self.consumer.value == 0xffffffffffffffff:
                raise OSError('Cannot consume network events')
            self.thread=threading.Thread(target=self._consume,daemon=True)
            self.thread.start()
            self.status='Per-app Internet TCP/UDP capture active (global remote addresses; LAN/loopback excluded).'
            return True
        except Exception:
            self.close()
            raise

    def _consume(self):
        code=self.adv.ProcessTrace(c.byref(self.consumer),1,None,None)
        if code and not self.closed:
            self.status=f'Per-app capture stopped (Windows {code}); data is incomplete.'

    def drain(self):
        with self.lock:
            result=dict(self.pending); self.pending.clear()
            return result

    def close(self):
        self.closed=True
        if self.session.value:
            self.adv.ControlTraceW(self.session,None,self.storage,1)
            self.session=U64()
        if self.consumer is not None and self.consumer.value != 0xffffffffffffffff:
            self.adv.CloseTrace(self.consumer)
            self.consumer=None

class Rates:
    """No boot-time totals or counter resets are mistaken for current speed."""
    def __init__(self):
        self.previous={}; self.at=None

    def sample(self,counters,now):
        elapsed=now-self.at if self.at is not None else 0
        result={}
        for name,values in counters.items():
            old=self.previous.get(name)
            if old is not None and elapsed > 0:
                down=max(0,values.bytes_recv-old.bytes_recv)
                up=max(0,values.bytes_sent-old.bytes_sent)
                # A reset/reconnect is a new baseline, not a sample of negative traffic.
                if values.bytes_recv < old.bytes_recv or values.bytes_sent < old.bytes_sent:
                    down=up=0
                result[name]=(down/elapsed,up/elapsed,down,up)
        self.previous=counters; self.at=now
        return elapsed,result

def process_identity(pid):
    try:
        proc=psutil.Process(pid)
        return proc.exe() or proc.name()
    except (psutil.Error,OSError):
        return 'System' if pid in (0,4) else f'Unresolved process (PID {pid})'
