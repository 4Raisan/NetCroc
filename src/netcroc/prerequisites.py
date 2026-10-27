"""Read-only checks for optional tools. Installation is always user initiated."""
from pathlib import Path
import os
import shutil
import sys
from . import vpn
from .ssh_routing import Routing


def inspect(folder, backend=None):
    backend = backend or vpn.ProfileStore(Path(folder)/'wireguard'/'profiles').backend
    try:
        wireguard = bool(backend.installed())
        wireguard_note = 'Installed' if wireguard else 'Not installed'
    except (OSError, ValueError):
        wireguard = False;wireguard_note = 'Could not check'
    results = [('Core application', True, 'Python and required libraries are available'),
               ('WireGuard', wireguard, wireguard_note+' · needed only for WireGuard VPN')]
    for label, path in [('SSH / VLESS routing core',Path(folder)/'ssh'/'routing-core')]:
        routing = Routing(path)
        try:
            routing.verify();ok=True;note='Verified and ready'
        except FileNotFoundError:
            ok=False;note='Not installed · optional'
        except (ValueError,OSError):
            ok=False;note='Verification failed · repair available'
        results.append((label,ok,note))
    return results
