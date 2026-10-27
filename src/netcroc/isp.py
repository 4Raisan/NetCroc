"""Small HTTPS lookup of the public exit network; never infer an ISP from an SSID."""
import json
import re
import urllib.request

URL = 'https://ipwho.is/?fields=success,message,connection'


def identify(value):
    if not isinstance(value, dict) or value.get('success') is not True:
        raise ValueError('Provider lookup unavailable. Keep your manual selection.')
    connection = value.get('connection', {})
    if not isinstance(connection, dict):
        raise ValueError('Invalid provider response.')
    provider = str(connection.get('isp') or connection.get('org') or '')
    provider = ''.join(c for c in provider if c.isprintable())[:160]
    text = re.sub(r'[^a-z0-9]+', ' ', provider.casefold())
    name = None
    for label, aliases in (
        ('Hutch', ('hutch', 'hutchison')), ('Mobitel', ('mobitel',)),
        ('Dialog', ('dialog',)), ('Airtel', ('airtel', 'bharti')),
        ('SLT', ('sri lanka telecom', 'srilanka telecom', 'slt'))):
        if any(re.search(r'\b'+re.escape(alias)+r'\b', text) for alias in aliases):
            name = label
            break
    return {'isp': name, 'provider': provider or 'Unknown provider'}


def lookup():
    request = urllib.request.Request(URL, headers={'User-Agent': 'NetCroc/0.4'})
    with urllib.request.urlopen(request, timeout=8) as response:
        raw = response.read(16385)
    if len(raw) > 16384:
        raise ValueError('Provider response was too large.')
    return identify(json.loads(raw))


def exit_location():
    request = urllib.request.Request('https://ipwho.is/?fields=success,country,country_code,connection', headers={'User-Agent':'NetCroc/0.4'})
    with urllib.request.urlopen(request, timeout=8) as response: raw=response.read(16385)
    if len(raw)>16384: raise ValueError('Exit response was too large.')
    value=json.loads(raw); provider=identify(value)
    country=value.get('country')
    if not isinstance(country,str) or not country.strip():raise ValueError('Exit country unavailable.')
    return dict(country=''.join(c for c in country if c.isprintable())[:80],provider=provider['provider'])
