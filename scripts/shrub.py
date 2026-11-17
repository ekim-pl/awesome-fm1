"""Prepare a reviewed SHRUB catalog update from the publisher's current package."""
import hashlib
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
BUILD = 'https://shrub.audio/editor/build.json'
INSTALL = 'https://shrub.audio/editor/install'
MAX_PACKAGE = 4 * 1024 * 1024


def check_url(url):
    parts = urlparse(url)
    if (parts.scheme != 'https' or parts.hostname != 'shrub.audio'
            or parts.username is not None or parts.port not in (None, 443)):
        raise ValueError('Unexpected publisher URL')


class PublisherRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit):
    check_url(url)
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0 AwesomeFM1 catalog updater'})
    with build_opener(PublisherRedirects()).open(request, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Publisher response exceeds size limit')
    return data


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href', '')
            if urlparse(href).path.lower().endswith('.fwsc'):
                self.urls.append(urljoin(INSTALL, href))


def crc(data):
    value = 0
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (0x1021 if value & 0x8000 else 0)) & 0xffff
    return value


def decrypt(data):
    key = 0xffff
    out = bytearray()
    for byte in data:
        out.append(byte ^ (key & 255))
        key = ((key << 1) ^ (0x1021 if key & 0x8000 else 0)) & 0xffff
    return bytes(out)


def inspect(raw):
    if not 960 <= len(raw) <= MAX_PACKAGE:
        raise ValueError('Invalid package size')
    product = ''.join(chr((raw[i * 48 + 47] - i - 1) & 255) for i in range(20) if raw[i * 48 + 47] != 0x7d)
    logical = b''.join(raw[i * 48:i * 48 + 47] for i in range(20)) + raw[960:]
    header = decrypt(logical[:64])
    num = lambda data: int.from_bytes(data, 'little')
    count = num(header[8:10])
    end = 64 + count * 80
    if (crc(header[2:]) != num(header[:2]) or header[16:64].rstrip(b'\0') != b'AC791N'
            or num(header[4:8]) != len(logical) or not 1 <= count <= 10 or end > 940
            or crc(logical[64:end]) != num(header[2:4])):
        raise ValueError('Invalid firmware header or file list')
    ranges, found = [], set()
    for i in range(count):
        entry = decrypt(logical[64 + 80*i:144 + 80*i])
        kind, offset, size, padded = num(entry[:2]), num(entry[8:12]), num(entry[12:16]), num(entry[16:20])
        name = entry[64:80].rstrip(b'\0')
        if (offset < 940 or padded < size or padded > MAX_PACKAGE or offset + size > len(logical)
                or (size and any(offset < stop and start < offset + size for start, stop in ranges))):
            raise ValueError('Invalid firmware file range')
        if size:
            ranges.append((offset, offset + size))
        if kind in (0, 100) and crc(logical[offset:offset + size]) != num(entry[4:6]):
            raise ValueError('Invalid firmware file CRC')
        if (name, kind) == (b'flash.bin', 0) and size >= 0x4000:
            if 'flash' in found:
                raise ValueError('Duplicate flash image')
            found.add('flash')
        if (name, kind) == (b'ota.bin', 100) and size:
            found.add('loader')
    if found != {'flash', 'loader'}:
        raise ValueError('Missing firmware image or loader')
    return product


def observe():
    before = json.loads(fetch(BUILD, 65536))
    version = before.get('firmware')
    if (not isinstance(version, str) or not version or before.get('dirty') is not False
            or not isinstance(before.get('date'), str) or not isinstance(before.get('commit'), str)
            or not before['date'] or not before['commit']):
        raise ValueError('Invalid or dirty publisher build metadata')
    links = Links()
    links.feed(fetch(INSTALL, 1024 * 1024).decode('utf-8'))
    if len(set(links.urls)) != 1:
        raise ValueError('Installer must identify exactly one package')
    url = links.urls[0]
    raw = fetch(url, MAX_PACKAGE)
    if json.loads(fetch(BUILD, 65536)) != before:
        raise ValueError('Publisher metadata changed during download')
    return before, url, raw


def main():
    path = ROOT / 'catalogs/shrub.json'
    catalog = json.loads(path.read_text())
    entry = next(item for item in catalog['firmwares'] if item['id'] == 'shrub')
    before, url, raw = observe()
    version = before['firmware']
    product = inspect(raw)
    if product != entry['product']:
        raise ValueError(f'Unexpected package identity: {product}')
    digest = hashlib.sha256(raw).hexdigest()
    changes = {'version': version, 'pkg': url, 'size': len(raw), 'sha256': digest}
    if all(entry.get(key) == value for key, value in changes.items()):
        print('SHRUB unchanged')
        return
    if version == entry['version'] and digest != entry['sha256']:
        raise ValueError('Package changed without a version change; investigate manually')
    if version != entry['version'] and digest == entry['sha256']:
        raise ValueError('Version changed but package bytes did not; investigate manually')
    for key, value in changes.items():
        if entry.get(key) != value:
            print(f'{key}: {entry.get(key)} -> {value}')
    entry.update(changes)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    catalog['updated'] = now
    evidence = ROOT / 'docs/verification.md'
    note = (f'\n## Update candidate {version} ({now})\n\n'
            f'- Installer: <{INSTALL}>; package: <{url}>.\n'
            f'- Size: {len(raw)} bytes; SHA-256: `{digest}`; identity: `{product}`.\n'
            f'- Build metadata: <{BUILD}>; date `{before.get("date")}`, commit `{before.get("commit")}`, dirty `{before.get("dirty")}`.\n'
            '- Package structure, processor, file ranges and CRCs checked locally. Metadata and package are separate resources, not a signed atomic release.\n'
            '- No hardware installation or compatibility test was performed; this hash identifies the observed bytes and is not a publisher signature.\n')
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    evidence.write_text(evidence.read_text() + note)
    print('Prepared candidate; review the catalog and verification evidence before publishing.')


if __name__ == '__main__':
    main()
