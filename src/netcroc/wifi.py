"""Native WLAN APIs: locale-independent profiles, keys and connection identity."""
import ctypes as c
from ctypes import wintypes as w
import uuid
import xml.etree.ElementTree as ET

class GUID(c.Structure):
    _fields_ = [('data', c.c_ubyte * 16)]
    def __str__(self):
        return str(uuid.UUID(bytes_le=bytes(self.data)))

class Interface(c.Structure):
    _fields_ = [('guid', GUID), ('description', w.WCHAR*256), ('state', w.DWORD)]

class Profile(c.Structure):
    _fields_ = [('name', w.WCHAR*256), ('flags', w.DWORD)]

class Connection(c.Structure):
    _fields_ = [('mode', w.DWORD), ('state', w.DWORD), ('profile', w.WCHAR*256)]

class ConnectParams(c.Structure):
    _fields_ = [('mode',w.DWORD),('profile',w.LPCWSTR),('ssid',c.c_void_p),
                ('bssid',c.c_void_p),('bss_type',w.DWORD),('flags',w.DWORD)]

def parse_profile(xml):
    root = ET.fromstring(xml)
    def get(tag):
        return root.findtext('.//{*}'+tag, '')
    protected = get('protected').lower() == 'true'
    key = get('keyMaterial')
    auth = get('authentication')
    password = ('Windows permission required' if protected else key) if key else ('Open network' if auth == 'open' else 'No readable saved password')
    ssid = root.findtext('.//{*}SSID/{*}name', '') or root.findtext('{*}name','')
    return {'ssid':ssid,'password':password,'auth':auth,'auto':get('connectionMode') == 'auto'}

class Wifi:
    def __init__(self):
        self.api = c.WinDLL('wlanapi')
        self.handle = w.HANDLE()
        version = w.DWORD()
        signatures = {
            'WlanOpenHandle': [w.DWORD,c.c_void_p,c.POINTER(w.DWORD),c.POINTER(w.HANDLE)],
            'WlanCloseHandle': [w.HANDLE,c.c_void_p],
            'WlanEnumInterfaces': [w.HANDLE,c.c_void_p,c.POINTER(c.c_void_p)],
            'WlanGetProfileList': [w.HANDLE,c.POINTER(GUID),c.c_void_p,c.POINTER(c.c_void_p)],
            'WlanGetProfile': [w.HANDLE,c.POINTER(GUID),w.LPCWSTR,c.c_void_p,c.POINTER(c.c_void_p),c.POINTER(w.DWORD),c.POINTER(w.DWORD)],
            'WlanQueryInterface': [w.HANDLE,c.POINTER(GUID),w.DWORD,c.c_void_p,c.POINTER(w.DWORD),c.POINTER(c.c_void_p),c.POINTER(w.DWORD)],
            'WlanConnect': [w.HANDLE,c.POINTER(GUID),c.POINTER(ConnectParams),c.c_void_p],
            'WlanDeleteProfile': [w.HANDLE,c.POINTER(GUID),w.LPCWSTR,c.c_void_p],
            'WlanFreeMemory': [c.c_void_p],
        }
        for name,args in signatures.items():
            fn=getattr(self.api,name); fn.argtypes=args; fn.restype=w.DWORD if name != 'WlanFreeMemory' else None
        self.check(self.api.WlanOpenHandle(2,None,c.byref(version),c.byref(self.handle)))

    @staticmethod
    def check(code):
        if code:
            raise OSError(code, c.FormatError(code))

    def interfaces(self):
        ptr = c.c_void_p()
        self.check(self.api.WlanEnumInterfaces(self.handle,None,c.byref(ptr)))
        try:
            count = c.cast(ptr,c.POINTER(w.DWORD))[0]
            return [Interface.from_buffer_copy(c.string_at(ptr.value+8+i*c.sizeof(Interface),c.sizeof(Interface))) for i in range(count)]
        finally:
            self.api.WlanFreeMemory(ptr)

    def current(self, interface, strict=False):
        ptr=c.c_void_p(); size=w.DWORD(); opcode=w.DWORD()
        code=self.api.WlanQueryInterface(self.handle,c.byref(interface.guid),7,None,c.byref(size),c.byref(ptr),c.byref(opcode))
        if code:
            if strict and code != 5023:
                raise OSError(code,'Cannot verify the connected Wi-Fi. Profile removal was blocked.')
            return ''
        try:
            return c.cast(ptr,c.POINTER(Connection)).contents.profile
        finally:
            self.api.WlanFreeMemory(ptr)

    def profiles(self):
        result=[]
        for interface in self.interfaces():
            ptr=c.c_void_p()
            self.check(self.api.WlanGetProfileList(self.handle,c.byref(interface.guid),None,c.byref(ptr)))
            try:
                count=c.cast(ptr,c.POINTER(w.DWORD))[0]
                names=[Profile.from_buffer_copy(c.string_at(ptr.value+8+i*c.sizeof(Profile),c.sizeof(Profile))).name for i in range(count)]
            finally:
                self.api.WlanFreeMemory(ptr)
            current=self.current(interface)
            for name in names:
                xml=c.c_void_p(); flags=w.DWORD(4); access=w.DWORD()
                code=self.api.WlanGetProfile(self.handle,c.byref(interface.guid),name,None,c.byref(xml),c.byref(flags),c.byref(access))
                item={'profile':name,'interface':interface,'connected':name==current,'ssid':name,'password':'Windows permission required','auth':''}
                if not code:
                    try:
                        item.update(parse_profile(c.wstring_at(xml)))
                    finally:
                        self.api.WlanFreeMemory(xml)
                result.append(item)
        return result

    def connect(self,item):
        params=ConnectParams(0,item['profile'],None,None,1,0)
        self.check(self.api.WlanConnect(self.handle,c.byref(item['interface'].guid),c.byref(params),None))

    def forget(self,item):
        if self.current(item['interface'],strict=True) == item['profile']:
            raise ValueError('The connected Wi-Fi profile cannot be forgotten. This protects your current connection.')
        self.check(self.api.WlanDeleteProfile(self.handle,c.byref(item['interface'].guid),item['profile'],None))

    def close(self):
        if self.handle:
            self.api.WlanCloseHandle(self.handle,None)
            self.handle=None
