"""Stage a verified Windows release and apply it after NetCroc exits."""
import base64
import hashlib
import hmac
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import urllib.request

from .updates import REPO, VERSION, version_key

LIMIT = 150 * 1024 * 1024


def windows_target():
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        return None
    return Path(sys.executable).resolve()


def installed(target):
    import winreg
    key = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\NetCroc.Desktop_is1'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as entry:
            location = winreg.QueryValueEx(entry, 'InstallLocation')[0]
        return (Path(location) / 'NetCroc.exe').resolve() == target
    except OSError:
        return False


def select_asset(release, setup):
    tag = release.get('version', '')
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag) or version_key(tag) <= version_key(VERSION):
        raise ValueError('No newer stable release is available.')
    mode = 'Setup' if setup else 'Portable'
    name = f'NetCroc-{tag}-windows-x64-{mode}.exe'
    url = f'{REPO}/releases/download/{tag}/{name}'
    for asset in release.get('assets', []):
        if not isinstance(asset, dict) or asset.get('name') != name:
            continue
        digest = asset.get('digest') or ''
        size = asset.get('size')
        if (asset.get('state') == 'uploaded' and asset.get('browser_download_url') == url
                and re.fullmatch(r'sha256:[0-9a-f]{64}', digest)
                and type(size) is int and 0 < size <= LIMIT):
            return url, digest[7:], size
    raise ValueError('This release has no verified download for your installation.')


def download(url, digest, size, path, opener=urllib.request.urlopen):
    request = urllib.request.Request(url, headers={'User-Agent': 'NetCroc-updater'})
    checksum = hashlib.sha256()
    received = 0
    with opener(request, timeout=30) as response, path.open('xb') as output:
        destination = urlsplit(response.geturl())
        if destination.scheme != 'https' or destination.hostname not in {
            'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'
        }:
            raise ValueError('Unexpected release download host.')
        while chunk := response.read(256 * 1024):
            received += len(chunk)
            if received > size:
                raise ValueError('The update download is larger than expected.')
            checksum.update(chunk)
            output.write(chunk)
    if received != size or not hmac.compare_digest(checksum.hexdigest(), digest):
        raise ValueError('Update verification failed. NetCroc was left unchanged.')


APPLY = r"""
$ErrorActionPreference = 'Stop'
$target = $env:NETCROC_UPDATE_TARGET
$payload = $env:NETCROC_UPDATE_PAYLOAD
$folder = [IO.Path]::GetDirectoryName($payload)
$backup = $null
$replaced = $false
$stage = $null
try {
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    do {
        $running = Get-Process -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -eq $target }
        if (!$running) { break }
        if ([DateTime]::UtcNow -ge $deadline) { throw 'NetCroc did not close.' }
        Start-Sleep -Milliseconds 350
    } while ($true)
    if ($env:NETCROC_UPDATE_MODE -eq 'setup') {
        $directory = [IO.Path]::GetDirectoryName($target)
        $arguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOCLOSEAPPLICATIONS /DIR="' + $directory + '"'
        $process = Start-Process -FilePath $payload -ArgumentList $arguments -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw 'Setup did not complete.' }
    } else {
        $stage = $target + '.' + [Guid]::NewGuid().ToString('N') + '.new'
        Copy-Item -LiteralPath $payload -Destination $stage
        $backup = $stage + '.bak'
        [IO.File]::Replace($stage, $target, $backup)
        $replaced = $true
    }
    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
    Start-Process -FilePath $target
    if ($replaced) { Remove-Item -LiteralPath $backup -ErrorAction SilentlyContinue }
} catch {
    $failure = $_.Exception.Message
    if ($replaced) {
        try { [IO.File]::Replace($backup, $target, $null) }
        catch { $failure += ' Previous executable saved at ' + $backup }
    }
    Add-Type -AssemblyName System.Windows.Forms
    [void][Windows.Forms.MessageBox]::Show($failure, 'NetCroc update failed')
} finally {
    if ($stage) { Remove-Item -LiteralPath $stage -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $payload -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $folder -ErrorAction SilentlyContinue
}
"""


def stage_update(release):
    target = windows_target()
    if target is None or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('In-app updates currently require a packaged Windows x64 build.')
    setup = installed(target)
    url, digest, size = select_asset(release, setup)
    folder = Path(tempfile.mkdtemp(prefix='netcroc-update-'))
    payload = folder / 'update.exe'
    try:
        download(url, digest, size, payload)
    except Exception:
        shutil.rmtree(folder)
        raise
    return target, payload, setup


def launch_update(target, payload, setup):
    environment = dict(os.environ, NETCROC_UPDATE_TARGET=str(target),
                       NETCROC_UPDATE_PAYLOAD=str(payload),
                       NETCROC_UPDATE_MODE='setup' if setup else 'portable')
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = base64.b64encode(APPLY.encode('utf-16-le')).decode('ascii')
    try:
        subprocess.Popen([str(powershell), '-NoProfile', '-NonInteractive', '-EncodedCommand', command],
                         env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        shutil.rmtree(payload.parent)
        raise
