"""Readable application groups without changing the original accounting records."""
from dataclasses import dataclass, field
from functools import lru_cache
import ntpath
import os
import re

UNKNOWN = 'Unattributed traffic'
ALIASES = {
    'chrome.exe': 'Google Chrome', 'brave.exe': 'Brave Browser',
    'msedge.exe': 'Microsoft Edge', 'firefox.exe': 'Mozilla Firefox',
    'svchost.exe': 'Windows Services', 'system': 'Windows System',
    'avira.vpnservice.exe': 'Avira VPN Service', 'endpointprotection.exe': 'Avira Endpoint Protection',
    'codex.exe': 'OpenAI Codex', 'netcroc.exe': 'NetCroc',
    'spotify.exe': 'Spotify', 'steam.exe': 'Steam', 'steamwebhelper.exe': 'Steam Web Helper',
    'python.exe': 'Python', 'pythonw.exe': 'Python', 'node.exe': 'Node.js',
    'onedrive.exe': 'Microsoft OneDrive', 'backgrounddownload.exe': 'Background Download',
}


def unresolved(value):
    text = str(value).strip().casefold()
    return text == UNKNOWN.casefold() or bool(re.fullmatch(r'(?:unresolved process \(pid \d+\)|pid \d+)', text))


@lru_cache(maxsize=1024)
def file_description(path):
    # Read a local VERSIONINFO resource as data. Never load or execute the file.
    if os.name != 'nt' or path.startswith(('\\\\', '//')) or not ntpath.isabs(path):
        return ''
    import ctypes as c
    from ctypes import wintypes as w
    try:
        api = c.WinDLL('version')
        api.GetFileVersionInfoSizeW.argtypes = [w.LPCWSTR, c.POINTER(w.DWORD)]
        api.GetFileVersionInfoSizeW.restype = w.DWORD
        api.GetFileVersionInfoW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p]
        api.VerQueryValueW.argtypes = [c.c_void_p, w.LPCWSTR, c.POINTER(c.c_void_p), c.POINTER(w.UINT)]
        unused = w.DWORD(); size = api.GetFileVersionInfoSizeW(path, c.byref(unused))
        if not size or size > 2 * 1024 * 1024: return ''
        data = c.create_string_buffer(size)
        if not api.GetFileVersionInfoW(path, 0, size, data): return ''
        pointer = c.c_void_p(); length = w.UINT()
        translations = []
        if api.VerQueryValueW(data, r'\VarFileInfo\Translation', c.byref(pointer), c.byref(length)):
            values = c.cast(pointer, c.POINTER(w.WORD))
            translations = [(values[i], values[i+1]) for i in range(0, min(length.value // 2, 32)-1, 2)]
        for language, encoding in translations + [(0x409, 0x4b0), (0x409, 0x4e4)]:
            for key in ('FileDescription', 'ProductName'):
                query = f'\\StringFileInfo\\{language:04x}{encoding:04x}\\{key}'
                if api.VerQueryValueW(data, query, c.byref(pointer), c.byref(length)) and length.value:
                    text = ''.join(ch for ch in c.wstring_at(pointer, min(length.value, 256)).rstrip('\0') if ch.isprintable()).strip()
                    if text: return text[:100]
    except (OSError, ValueError): pass
    return ''


@lru_cache(maxsize=2048)
def identity(value):
    value = str(value)
    if unresolved(value): return '__unknown__', UNKNOWN
    name = ntpath.basename(value.replace('/', '\\')) or value
    lower = name.casefold()
    alias=lower if lower in ALIASES else lower+'.exe' if lower+'.exe' in ALIASES else None
    if alias:return alias,ALIASES[alias]
    if lower == 'updater.exe' and 'google' in value.casefold(): return 'google-updater', 'Google Updater'
    if lower == 'chatgpt.exe' and 'openai.codex' in value.casefold(): return 'codex.exe', 'OpenAI Codex'
    description = file_description(value)
    label = description or re.sub(r'(?i)\.exe$', '', name)
    # Unknown products with the same generic binary name remain separate.
    key = value.replace('\\', '/').casefold()
    return key, label or 'Unknown application'


@dataclass
class AppUsage:
    key: object
    label: str
    down: float = 0
    up: float = 0
    sources: list = field(default_factory=list)


def aggregate(rows, minimum=0):
    groups = {}
    for source, down, up in rows:
        key, label = identity(str(source))
        item = groups.setdefault(key, AppUsage(key, label))
        item.down += down; item.up += up
        if source not in item.sources: item.sources.append(source)
    return sorted((v for v in groups.values() if v.down+v.up >= minimum), key=lambda v: v.down+v.up, reverse=True)
