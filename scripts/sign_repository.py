"""Sign or verify the repository's single-file Ed25519 envelope using OpenSSL 3."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

import repository

SPKI_PREFIX = bytes.fromhex('302a300506032b6570032100')
ENVELOPE_FORMAT = 'fm1-repository-v1'
VALIDITY_DAYS = 14


def openssl(*args):
    return subprocess.run(['openssl', *args], check=True, stdout=subprocess.PIPE).stdout


def ed25519_spki(public_der):
    if not public_der.startswith(SPKI_PREFIX) or len(public_der) != len(SPKI_PREFIX) + 32:
        raise ValueError('An Ed25519 public key is required')
    return public_der


def stamp(value):
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def b64(value):
    return base64.b64encode(value).decode('ascii')


def unb64(value):
    raw = base64.b64decode(value, validate=True)
    if b64(raw) != value:
        raise ValueError('Expected standard padded base64')
    return raw


def read_json(raw):
    def object_pairs(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError('Duplicate JSON field')
        return result

    def invalid_constant(value):
        raise ValueError(f'Invalid JSON constant: {value}')

    return json.loads(raw.decode('utf-8'), object_pairs_hook=object_pairs, parse_constant=invalid_constant)


def sign(index, private_key, fingerprint, sequence, now):
    repository.validate(index)
    if type(sequence) is not int or not 1 <= sequence <= 2**53 - 1:
        raise ValueError('Sequence must be a positive JSON-safe integer')
    if not re.fullmatch(r'[0-9a-f]{64}', fingerprint):
        raise ValueError('Expected a lowercase SHA-256 public key fingerprint')
    public = ed25519_spki(openssl('pkey', '-in', str(private_key), '-pubout', '-outform', 'DER'))
    if hashlib.sha256(public).hexdigest() != fingerprint:
        raise ValueError('Signing key does not match the configured fingerprint')
    payload = json.dumps({
        'format': ENVELOPE_FORMAT,
        'sequence': sequence,
        'issuedAt': stamp(now),
        'expiresAt': stamp(now + timedelta(days=VALIDITY_DAYS)),
        'index': index,
    }, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    with tempfile.TemporaryDirectory() as directory:
        content = Path(directory) / 'payload'
        content.write_bytes(payload)
        signature = openssl('pkeyutl', '-sign', '-rawin', '-inkey', str(private_key), '-in', str(content))
    envelope = repository.encode({
        'format': ENVELOPE_FORMAT, 'publicKey': b64(public),
        'payload': b64(payload), 'signature': b64(signature),
    })
    if len(envelope) > repository.MAX_ENVELOPE_BYTES:
        raise ValueError('Signed repository exceeds the envelope size limit')
    return envelope


def verify(envelope, fingerprint, now, minimum_sequence=1):
    if len(envelope) > repository.MAX_ENVELOPE_BYTES:
        raise ValueError('Signed repository exceeds the envelope size limit')
    entry = read_json(envelope)
    if set(entry) != {'format', 'publicKey', 'payload', 'signature'} or entry['format'] != ENVELOPE_FORMAT:
        raise ValueError('Unsupported repository envelope')
    public = ed25519_spki(unb64(entry['publicKey']))
    if hashlib.sha256(public).hexdigest() != fingerprint:
        raise ValueError('Repository key does not match the pinned fingerprint')
    payload = unb64(entry['payload'])
    signature = unb64(entry['signature'])
    if len(signature) != 64 or len(payload) > repository.MAX_INDEX_BYTES + 1024:
        raise ValueError('Invalid repository signature or payload length')
    with tempfile.TemporaryDirectory() as directory:
        key, content, sig = (Path(directory) / name for name in ('public.der', 'payload', 'signature'))
        key.write_bytes(public)
        content.write_bytes(payload)
        sig.write_bytes(signature)
        openssl('pkeyutl', '-verify', '-rawin', '-pubin', '-keyform', 'DER', '-inkey', str(key),
                '-in', str(content), '-sigfile', str(sig))
    data = read_json(payload)
    if set(data) != {'format', 'sequence', 'issuedAt', 'expiresAt', 'index'} or data['format'] != ENVELOPE_FORMAT:
        raise ValueError('Unsupported signed repository format')
    sequence = data['sequence']
    if type(sequence) is not int or not max(1, minimum_sequence) <= sequence <= 2**53 - 1:
        raise ValueError('Invalid or replayed repository sequence')
    issued, expires = (repository.utc(data[key]) for key in ('issuedAt', 'expiresAt'))
    if issued > now + timedelta(minutes=5) or not now < expires <= issued + timedelta(days=VALIDITY_DAYS):
        raise ValueError('Repository snapshot expired or has invalid validity dates')
    if expires <= issued:
        raise ValueError('Invalid repository validity period')
    repository.validate(data['index'])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    signing = subcommands.add_parser('sign')
    signing.add_argument('entry', type=Path)
    signing.add_argument('--private-key', type=Path, help='PEM file or FM1_REPO_PRIVATE_KEY environment variable')
    signing.add_argument('--sequence', type=int, help='Override clock-based sequence for local builds')
    verifying = subcommands.add_parser('verify')
    verifying.add_argument('entry', type=Path)
    verifying.add_argument('--minimum-sequence', type=int, default=1)
    for command in (signing, verifying):
        command.add_argument('--fingerprint', default=os.environ.get('FM1_REPO_FINGERPRINT'))
    args = parser.parse_args()
    if not args.fingerprint:
        parser.error('Provide --fingerprint or FM1_REPO_FINGERPRINT')
    timestamp = time.time_ns() // 1_000_000
    now = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
    if args.command == 'verify':
        with args.entry.open('rb') as stream:
            data = verify(stream.read(repository.MAX_ENVELOPE_BYTES + 1), args.fingerprint, now, args.minimum_sequence)
        print(f"Verified {data['index']['repository']['id']} sequence {data['sequence']}")
        return

    index = repository.build_index()
    repository.export_legacy(index, check=True)
    sequence = timestamp if args.sequence is None else args.sequence
    with tempfile.TemporaryDirectory() as directory:
        key = args.private_key
        if key is None:
            private_pem = os.environ.pop('FM1_REPO_PRIVATE_KEY', '')
            if not private_pem:
                parser.error('Provide --private-key or FM1_REPO_PRIVATE_KEY')
            key = Path(directory) / 'private.pem'
            key.touch(mode=0o600)
            key.write_text(private_pem, encoding='utf-8')
        envelope = sign(index, key, args.fingerprint, sequence, now)
    verify(envelope, args.fingerprint, now, minimum_sequence=sequence)
    args.entry.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=args.entry.parent, delete=False) as temporary:
        temporary.write(envelope)
    Path(temporary.name).replace(args.entry)
    print(f"Signed {index['repository']['id']} sequence {sequence}")


if __name__ == '__main__':
    main()
