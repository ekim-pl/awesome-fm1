"""Build a versioned firmware index and the existing app catalog exports."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator

import catalog

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'schema/repository.schema.json').read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=Draft202012Validator.FORMAT_CHECKER)
MAX_INDEX_BYTES = 2 * 1024 * 1024
MAX_ENVELOPE_BYTES = 3 * 1024 * 1024


def read(path):
    return json.loads(path.read_bytes())


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def utc(value):
    if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value):
        raise ValueError(f'Expected a UTC timestamp in YYYY-MM-DDTHH:MM:SSZ form: {value!r}')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def https(address):
    parts = urlsplit(address)
    if (not address.startswith('https://') or not parts.hostname
            or parts.username is not None or parts.port not in (None, 443) or parts.fragment
            or any(ord(char) <= 32 or char == '\\' for char in address)):
        raise ValueError(f'Invalid HTTPS URL: {address!r}')
    return parts


def check_github_url(address, repo, tag):
    parts = https(address)
    prefix = f'/{repo}/releases/download/{tag}/'
    path = unquote(parts.path)
    name = path[len(prefix):]
    if (parts.hostname != 'github.com' or parts.query
            or not path.startswith(prefix) or '/' in name or '\\' in name
            or not name.lower().endswith('.fwsc') or len(name) <= len('.fwsc')
            or any(segment in ('.', '..') for segment in path.split('/'))):
        raise ValueError(f'Unexpected release asset URL for {repo}@{tag}: {address!r}')
    return name


def recommended(project):
    choice = project['recommended']
    if choice is None:
        return None
    for release in project['releases']:
        if release['id'] == choice['release']:
            for artifact in release['artifacts']:
                if artifact['id'] == choice['artifact']:
                    return release, artifact
    raise ValueError(f"{project['id']}: recommended artifact does not exist")


def unique(values, label):
    seen = set()
    for value in values:
        if value in seen:
            raise ValueError(f'Duplicate {label}: {value}')
        seen.add(value)
    return seen


def validate(index):
    VALIDATOR.validate(index)
    utc(index['updated'])
    https(index['repository']['homepage'])
    unique((project['id'] for project in index['projects']), 'project ID')
    for project in index['projects']:
        utc(project['updated'])
        for address in project['links'].values():
            https(address)
        unique((release['id'] for release in project['releases']), 'release ID')
        withdrawals = project.get('withdrawals', [])
        withdrawn = unique((row['sha256'] for row in withdrawals), 'withdrawn hash')
        for row in withdrawals:
            utc(row['withdrawnAt'])
        for release in project['releases']:
            if 'publishedAt' in release:
                utc(release['publishedAt'])
            unique((artifact['id'] for artifact in release['artifacts']), 'artifact ID')
            for artifact in release['artifacts']:
                https(artifact['url'])
                if 'inspection' in artifact:
                    utc(artifact['inspection']['checkedAt'])
                upstream = artifact['upstream']
                if upstream['type'] == 'github-release':
                    check_github_url(artifact['url'], upstream['repository'], upstream['tag'])
        choice = recommended(project)
        if choice and (not choice[1]['available'] or choice[1]['sha256'] in withdrawn):
            raise ValueError(f"{project['id']}: recommended artifact is unavailable or withdrawn")
    if len(encode(index)) > MAX_INDEX_BYTES:
        raise ValueError('Index exceeds the repository size limit')


def build_index(root=ROOT):
    projects = []
    for path in sorted((root / 'projects').glob('*.json')):
        project = read(path)
        if project['id'] != path.stem:
            raise ValueError(f'{path.name}: filename must match the project ID')
        projects.append(project)
    updated = max(
        (stamp for project in projects for stamp in
         [project['updated'], *(row['withdrawnAt'] for row in project.get('withdrawals', []))]),
        default='1970-01-01T00:00:00Z',
    )
    index = {'schemaVersion': 1, 'repository': read(root / 'config/repository.json'),
             'updated': updated, 'projects': projects}
    validate(index)
    return index


def legacy_component(project):
    choice = recommended(project)
    if not choice:
        return {'updated': project['updated'], 'firmwares': []}

    release, artifact = choice
    github = artifact['upstream']['type'] == 'github-release'
    upstream = artifact['upstream'] if github else {}
    kind = project['categories']
    row = {
        'id': project['id'], 'name': project['name'], 'author': project['author'],
        'kind': kind[0] if len(kind) == 1 else kind,
        'what': project['summary'], 'version': release['version'],
        **{key: project['links'][key] for key in ('site', 'card', 'editor', 'install')
           if key in project['links']},
        'repo': upstream.get('repository'), 'tag': upstream.get('tag'), 'asset': upstream.get('assetId'),
        'pkg': artifact['url'], 'product': artifact['product'], 'size': artifact['size'],
        'sha256': artifact['sha256'], 'chip': artifact['legacyChip'], 'beta': release['channel'] == 'beta',
    }
    if 'publishedAt' in release:
        row['published'] = release['publishedAt']
    return {'updated': project['updated'], 'firmwares': [row]}


def export_legacy(index, check=False, root=ROOT):
    components = {project['id']: legacy_component(project) for project in index['projects']}
    combined = catalog.combine(list(components.values())) if components else {
        'updated': index['updated'], 'firmwares': [],
    }
    expected = {root / 'catalogs' / f'{key}.json': value for key, value in components.items()}
    expected[root / 'catalog.json'] = combined
    obsolete = set((root / 'catalogs').glob('*.json')) - expected.keys()
    if obsolete:
        raise ValueError(f'Remove obsolete generated catalog files: {sorted(str(path) for path in obsolete)}')
    for path, value in expected.items():
        if check:
            if not path.is_file() or read(path) != value:
                raise ValueError(f'{path.name} is out of date; run python scripts/repository.py')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encode(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate reviewed records and existing exports')
    parser.add_argument('--index', type=Path, help='Also write the unsigned repository index to this path')
    args = parser.parse_args()
    index = build_index()
    export_legacy(index, check=args.check)
    if args.index:
        args.index.parent.mkdir(parents=True, exist_ok=True)
        args.index.write_bytes(encode(index))
    print(f"Validated {len(index['projects'])} repository project(s)")


if __name__ == '__main__':
    main()
