"""User-configured SSH, SSH-over-TLS and loopback SOCKS5 forwarding.

No system routes, DNS, proxy preferences or account registrations are changed here.
SSH host keys and TLS identities are checked before any SSH password is sent.
"""
import base64
from datetime import date
import hashlib
import hmac
import ipaddress
import json
import logging
from pathlib import Path
import re
import socket
import ssl
import struct
import threading
import time
import uuid

import paramiko
from .vpn import crypt

GUIDE_URL = 'https://blog.fastssh.com/vpn-protocol/ssh/how-to-create-a-free-ssh-account/'
SERVERS_URL = 'https://www.fastssh.com/page/ssh-ssl-stunnel-servers'
DEFAULTS = dict(label='SSH TLS profile', host='', port=443, username='', password='',
                tls=True, sni='', tls_pin='', ca_pem='', host_key='', expires='',
                proxy_host='', proxy_port=8080, proxy_user='', proxy_password='',
                payload_before='', payload_after='', local_port=1080, routing='socks')
SECRET_FIELDS = ('password', 'proxy_password', 'username', 'proxy_user',
                 'payload_before', 'payload_after', 'ca_pem')
LIMIT = 128 * 1024
logger = logging.getLogger('netcroc.ssh')
logger.addHandler(logging.NullHandler())
logger.propagate = False


def hostname(value):
    if not isinstance(value, str) or not value or len(value) > 253:
        raise ValueError('Enter a server hostname or IP address.')
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', value):
        raise ValueError('Hostnames must not contain URLs, paths, spaces or login details.')
    if any(not part or len(part) > 63 or part.startswith('-') or part.endswith('-')
           for part in value.split('.')):
        raise ValueError('Invalid hostname.')
    return value


def validate(value, credentials=False):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('Unrecognized SSH profile fields.')
    result = DEFAULTS | value
    for field, default in DEFAULTS.items():
        if isinstance(default, str):
            if not isinstance(result[field], str) or '\x00' in result[field]:
                raise ValueError('Invalid SSH text field.')
        elif isinstance(default, bool):
            if not isinstance(result[field], bool):
                raise ValueError('Invalid SSH switch.')
    result['host'] = hostname(result['host'].strip())
    result['sni'] = result['sni'].strip()
    if result['sni']:
        hostname(result['sni'])
    if result['proxy_host']:
        result['proxy_host'] = hostname(result['proxy_host'].strip())
    for field, minimum in (('port', 1), ('proxy_port', 1), ('local_port', 0)):
        if isinstance(result[field], (bool, float)):
            raise ValueError('Invalid port.')
        try:
            number = int(result[field])
        except (TypeError, ValueError):
            raise ValueError('Ports must be numbers.') from None
        if not minimum <= number <= 65535:
            raise ValueError('Ports must be between 1 and 65535 (local 0 selects a free port).')
        result[field] = number
    if result['routing'] not in ('socks', 'tun'):
        raise ValueError('Choose Local SOCKS5 or Whole-PC TCP routing.')
    result['label'] = ''.join(c for c in result['label'] if c.isprintable()).strip()[:80] or 'SSH TLS profile'
    if result['expires']:
        try:
            date.fromisoformat(result['expires'])
        except ValueError:
            raise ValueError('Expiry must use YYYY-MM-DD or be left empty.') from None
    pin = result['tls_pin'].replace(':', '').strip().lower()
    if pin and not re.fullmatch('[0-9a-f]{64}', pin):
        raise ValueError('TLS certificate pin must be its full SHA-256 fingerprint.')
    result['tls_pin'] = pin
    if result['host_key']:
        parts = result['host_key'].strip().split()
        if len(parts) != 2 or not parts[0].startswith(('ssh-', 'ecdsa-')):
            raise ValueError('SSH host key must contain its key type and base64 public key.')
        try:
            raw = base64.b64decode(parts[1], validate=True)
            parsed = paramiko.PKey.from_type_string(parts[0], raw)
            if parsed.asbytes() != raw:
                raise ValueError()
        except Exception:
            raise ValueError('Invalid SSH host public key.') from None
        result['host_key'] = ' '.join(parts)
    for field in ('payload_before', 'payload_after'):
        if len(result[field]) > 8192:
            raise ValueError('Each custom payload must be at most 8 KB.')
        render_payload(result[field], result)
    if not result['tls'] and result['payload_after']:
        raise ValueError('Payload after TLS requires TLS to be enabled.')
    if len(json.dumps(result).encode()) > LIMIT:
        raise ValueError('SSH profile is too large.')
    if credentials:
        if not result['username'].strip() or not result['password']:
            raise ValueError('Enter the account username and password supplied by your SSH provider.')
        if not result['host_key']:
            raise ValueError('Probe and explicitly trust the SSH host key before connecting.')
        if result['expires'] and date.fromisoformat(result['expires']) < date.today():
            raise ValueError('This saved SSH account has expired. Renew it with your provider.')
    return result


def render_payload(text, profile):
    values = {'host': profile['host'], 'port': str(profile['port']),
              'sni': profile.get('sni') or profile['host']}
    for key, value in values.items():
        text = text.replace('{' + key + '}', value)
    text = text.replace('[crlf]', '\r\n').replace('\\r\\n', '\r\n').replace('\\n', '\n')
    text = text.replace('\r\n', '\n').replace('\n', '\r\n')
    if text and not text.endswith('\r\n\r\n'):
        text = text.rstrip('\r\n') + '\r\n\r\n'
    try:
        data = text.encode('latin1')
    except UnicodeError:
        raise ValueError('HTTP payloads must use Latin-1/ASCII header characters.') from None
    if len(data) > 16384:
        raise ValueError('Expanded payload is too large.')
    return data


def http_prelude(stream, data):
    """Read exactly the HTTP header, preserving the following TLS/SSH bytes."""
    stream.sendall(data)
    header = bytearray()
    while not header.endswith(b'\r\n\r\n'):
        part = stream.recv(1)
        if not part:
            raise OSError('HTTP proxy or payload endpoint closed the connection.')
        header.extend(part)
        if len(header) > 16384:
            raise OSError('HTTP proxy response headers are too large.')
    line = bytes(header).split(b'\r\n', 1)[0]
    if not re.fullmatch(rb'HTTP/1\.[01] (?:2[0-9]{2}|101)(?: .*)?', line):
        raise OSError('HTTP proxy or custom payload did not establish a tunnel.')


def fingerprint(key):
    return 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')


def wire_key(key):
    return key.get_name() + ' ' + key.get_base64()


def close_stream(stream):
    if stream is not None:
        try:
            stream.close()
        except (OSError, EOFError):
            pass


def open_stream(profile, inspect=False, register=lambda stream: None):
    """Plain socket -> optional HTTP CONNECT -> prelude -> TLS/SNI -> postlude."""
    host = profile['proxy_host'] or profile['host']
    port = profile['proxy_port'] if profile['proxy_host'] else profile['port']
    raw = socket.create_connection((host, port), timeout=10)
    register(raw)
    stream = raw
    info = {'upstream_ip': raw.getpeername()[0], 'tls_verified': not profile['tls'],
            'tls_fingerprint': '', 'tls_mode': 'No TLS'}
    try:
        if profile['proxy_host']:
            authority = ('[' + profile['host'] + ']' if ':' in profile['host'] else profile['host']) + ':' + str(profile['port'])
            headers = f'CONNECT {authority} HTTP/1.1\r\nHost: {authority}\r\n'
            if profile['proxy_user']:
                token = base64.b64encode((profile['proxy_user'] + ':' + profile['proxy_password']).encode()).decode()
                headers += 'Proxy-Authorization: Basic ' + token + '\r\n'
            http_prelude(stream, (headers + '\r\n').encode('ascii'))
        if profile['payload_before']:
            http_prelude(stream, render_payload(profile['payload_before'], profile))
        if profile['tls']:
            pin = profile['tls_pin']
            if pin or inspect:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            else:
                context = ssl.create_default_context(cadata=profile['ca_pem'] or None)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            stream = context.wrap_socket(stream, server_hostname=profile['sni'] or profile['host'])
            register(stream)
            actual = hashlib.sha256(stream.getpeercert(binary_form=True)).hexdigest()
            if pin and not hmac.compare_digest(pin, actual):
                raise ssl.SSLCertVerificationError('The TLS certificate does not match the saved SHA-256 pin.')
            info.update(tls_fingerprint=actual, tls_verified=bool(pin or not inspect),
                        tls_mode='Pinned certificate' if pin else ('Inspection only' if inspect else 'CA + hostname'))
        if profile['payload_after']:
            http_prelude(stream, render_payload(profile['payload_after'], profile))
        return stream, info
    except Exception:
        close_stream(stream)
        close_stream(raw)
        raise


def negotiate(profile, inspect=False, register=lambda resource: None):
    stream, info = open_stream(profile, inspect=inspect, register=register)
    transport = None
    try:
        transport = paramiko.Transport(stream)
        register(transport)
        transport.set_log_channel('netcroc.ssh')
        transport.banner_timeout = 10
        transport.auth_timeout = 10
        transport.start_client(timeout=10)
        key = transport.get_remote_server_key()
        info.update(host_key=wire_key(key), host_fingerprint=fingerprint(key))
        return transport, info
    except Exception:
        if transport:
            transport.close()
        close_stream(stream)
        raise


def probe(value, inspect=False):
    """Discover public identities only. Never sends a username or password."""
    profile = validate(value)
    transport, info = negotiate(profile, inspect=inspect)
    transport.close()
    return info


class ProfileStore:
    def __init__(self, folder):
        self.folder = Path(folder)

    def path(self, identifier):
        if not re.fullmatch('[0-9a-f]{32}', identifier):
            raise ValueError('Invalid SSH profile identifier.')
        return self.folder / (identifier + '.json')

    def save(self, value, identifier=None):
        profile = validate(value)
        identifier = identifier or uuid.uuid4().hex
        path = self.path(identifier)
        self.folder.mkdir(parents=True, exist_ok=True)
        # All connection parameters and payloads can contain sensitive account data.
        protected = base64.b64encode(crypt(json.dumps(profile).encode(), description='NetCroc SSH profile')).decode()
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'id': identifier, 'protected': protected}), encoding='utf-8')
        temporary.replace(path)
        return identifier

    def load(self, identifier):
        try:
            data = json.loads(self.path(identifier).read_text(encoding='utf-8'))
            profile = json.loads(crypt(base64.b64decode(data['protected'], validate=True), decrypt=True))
        except Exception:
            raise ValueError('Could not unlock this SSH profile for this Windows account.') from None
        return validate(profile)

    def profiles(self):
        result = []
        for path in self.folder.glob('*.json'):
            try:
                value = self.load(path.stem)
                result.append((path.stem, {k: value[k] for k in ('label', 'host', 'port', 'tls', 'expires', 'routing')}))
            except (OSError, ValueError):
                continue
        return sorted(result, key=lambda item: item[1]['label'].lower())

    def remove(self, identifier):
        self.path(identifier).unlink()

    def import_file(self, path):
        with Path(path).open('rb') as source:
            raw = source.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError('SSH profile is too large.')
        try:
            value = json.loads(raw.decode('utf-8-sig'))
        except (UnicodeError, ValueError):
            raise ValueError('Import a NetCroc SSH JSON profile, not an encrypted export from another app.') from None
        return self.save(value)


def receive_exact(stream, length):
    data = bytearray()
    while len(data) < length:
        part = stream.recv(length - len(data))
        if not part:
            raise OSError('Client closed the SOCKS request.')
        data.extend(part)
    return bytes(data)


class SocksServer:
    """RFC 1928 CONNECT, IPv4/IPv6/domain destinations; DNS stays on the SSH server."""
    def __init__(self, transport, port):
        self.transport = transport
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.resources = set()
        self.workers = set()
        self.capacity = threading.BoundedSemaphore(32)
        self.down = self.up = 0
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.listener.bind(('127.0.0.1', port))
            self.listener.listen(32)
            self.listener.settimeout(.25)
        except Exception:
            self.listener.close()
            raise
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    def _accept(self):
        while not self.stop_event.is_set():
            try:
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not self.capacity.acquire(blocking=False):
                client.close()
                continue
            worker = threading.Thread(target=self._serve, args=(client,), daemon=True)
            with self.lock:
                self.resources.add(client)
                self.workers.add(worker)
            worker.start()

    def _serve(self, client):
        channel = None
        connected = False
        try:
            client.settimeout(10)
            version, count = receive_exact(client, 2)
            methods = receive_exact(client, count)
            if version != 5 or 0 not in methods:
                client.sendall(b'\x05\xff')
                return
            client.sendall(b'\x05\x00')
            version, command, reserved, kind = receive_exact(client, 4)
            if version != 5 or reserved or command != 1:
                client.sendall(b'\x05\x07\x00\x01' + bytes(6))
                return
            if kind == 1:
                host = socket.inet_ntop(socket.AF_INET, receive_exact(client, 4))
            elif kind == 4:
                host = socket.inet_ntop(socket.AF_INET6, receive_exact(client, 16))
            elif kind == 3:
                length = receive_exact(client, 1)[0]
                host = receive_exact(client, length).decode('idna')
                hostname(host)
            else:
                client.sendall(b'\x05\x08\x00\x01' + bytes(6))
                return
            port = struct.unpack('!H', receive_exact(client, 2))[0]
            if not port:
                raise ValueError('Invalid destination port.')
            channel = self.transport.open_channel('direct-tcpip', (host, port), ('127.0.0.1', 0), timeout=10)
            if channel is None:
                raise OSError('SSH forwarding was refused.')
            with self.lock:
                self.resources.add(channel)
            client.sendall(b'\x05\x00\x00\x01' + bytes(6))
            connected = True
            client.settimeout(1)
            channel.settimeout(1)
            activity = [time.monotonic()]

            def pump(source, target, direction):
                try:
                    while not self.stop_event.is_set() and time.monotonic() - activity[0] < 120:
                        try:
                            data = source.recv(65536)
                        except socket.timeout:
                            continue
                        if not data:
                            break
                        target.sendall(data)
                        activity[0] = time.monotonic()
                        with self.lock:
                            if direction == 'down':
                                self.down += len(data)
                            else:
                                self.up += len(data)
                except (OSError, EOFError, paramiko.SSHException):
                    pass
                finally:
                    try:
                        target.shutdown(socket.SHUT_WR)
                    except (OSError, EOFError):
                        pass

            downstream = threading.Thread(target=pump, args=(channel, client, 'down'), daemon=True)
            downstream.start()
            pump(client, channel, 'up')
            while downstream.is_alive() and not self.stop_event.is_set():
                downstream.join(.2)
        except (OSError, ValueError, UnicodeError, paramiko.SSHException):
            if not connected:
                try:
                    client.sendall(b'\x05\x05\x00\x01' + bytes(6))
                except OSError:
                    pass
        finally:
            close_stream(client)
            close_stream(channel)
            with self.lock:
                self.resources.discard(client)
                self.resources.discard(channel)
                self.workers.discard(threading.current_thread())
            self.capacity.release()

    def stop(self):
        self.stop_event.set()
        close_stream(self.listener)
        with self.lock:
            for resource in list(self.resources):
                close_stream(resource)
            workers = list(self.workers)
        self.thread.join(timeout=1)
        deadline = time.monotonic() + 2
        for worker in workers:
            worker.join(timeout=max(0, deadline - time.monotonic()))


class Session:
    def __init__(self, routing=None):
        self.routing = routing
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.resources = []
        self.transport = self.socks = None
        self.status = 'Disconnected'
        self.info = {}
        self.started = 0
        self.profile_id = None

    def _register(self, resource):
        with self.lock:
            if self.cancel.is_set():
                resource.close()
                raise OSError('Connection cancelled.')
            self.resources.append(resource)

    def start(self, value, identifier=None):
        profile = validate(value, credentials=True)
        if profile['routing'] == 'tun':
            if not self.routing:
                raise ValueError('Install the optional routing core before using Whole-PC mode.')
            self.routing.preflight()
        self.profile_id = identifier
        self.status = 'Connecting'
        try:
            transport, info = negotiate(profile, register=self._register)
            if not hmac.compare_digest(info['host_key'], profile['host_key']):
                expected = profile['host_key'].split()
                key = paramiko.PKey.from_type_string(expected[0], base64.b64decode(expected[1]))
                raise paramiko.BadHostKeyException(profile['host'], transport.get_remote_server_key(), key)
            if self.cancel.is_set():
                raise OSError('Connection cancelled.')
            transport.auth_password(profile['username'], profile['password'], fallback=False)
            if not transport.is_authenticated():
                raise paramiko.AuthenticationException('SSH authentication failed.')
            transport.set_keepalive(20)
            self.transport = transport
            self.info = info
            self.socks = SocksServer(transport, profile['local_port'])
            if self.cancel.is_set():
                raise OSError('Connection cancelled.')
            if profile['routing'] == 'tun':
                self.routing.start(self.socks.port, [info['upstream_ip']])
            if self.cancel.is_set():
                raise OSError('Connection cancelled.')
            self.started = time.monotonic()
            self.status = 'Connected · ' + ('Whole-PC TCP' if profile['routing'] == 'tun' else 'Local SOCKS5')
            threading.Thread(target=self._watch, daemon=True).start()
            return self.snapshot()
        except Exception:
            self.stop()
            raise

    def _watch(self):
        while not self.cancel.wait(1):
            if not self.transport or not self.transport.is_active():
                self.stop('SSH server disconnected')
                break
            if self.routing and self.routing.active and not self.routing.healthy():
                self.stop('Routing process stopped')
                break

    def snapshot(self):
        with self.lock:
            return {'status': self.status, 'port': self.socks.port if self.socks else None,
                    'down': self.socks.down if self.socks else 0,
                    'up': self.socks.up if self.socks else 0,
                    'seconds': max(0, time.monotonic() - self.started) if self.started else 0,
                    'host_fingerprint': self.info.get('host_fingerprint', ''),
                    'tls_mode': self.info.get('tls_mode', '')}

    def stop(self, status='Disconnected'):
        self.status = status
        self.cancel.set()
        if self.routing:
            self.routing.stop()
        if self.socks:
            self.socks.stop()
        with self.lock:
            for resource in reversed(self.resources):
                close_stream(resource)
            self.resources.clear()
            self.status = status


def friendly_error(error):
    """Do not show backend tracebacks, payloads, passwords or proxy credentials."""
    if isinstance(error, paramiko.BadHostKeyException):
        return 'SSH host key changed or does not match the trusted key. Connection refused.'
    if isinstance(error, paramiko.AuthenticationException):
        return 'SSH login was refused. Check the exact username, password and account expiry.'
    if isinstance(error, ssl.SSLCertVerificationError):
        return 'TLS certificate validation failed. Verify SNI, CA trust or the expected certificate pin.'
    if isinstance(error, (ValueError, PermissionError, FileNotFoundError)):
        return str(error)
    return 'Connection failed (' + type(error).__name__ + '). Check the server, port, proxy and payload settings.'
