"""Prepare candidate release changes for review. Run from a clean branch."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

import repository
import shrub

ROOT = repository.ROOT
ASSET_HOSTS = {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}


def github_fetch(url, hosts, limit, accept):
    def check(address):
        if repository.https(address).hostname not in hosts:
            raise ValueError(f'Unexpected GitHub download host: {address!r}')

    class Redirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            check(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    check(url)
    request = Request(url, headers={'Accept': accept, 'User-Agent': 'AwesomeFM1 catalog updater'})
    with build_opener(Redirects()).open(request, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('GitHub response exceeds size limit')
    return data


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def inspect_artifact(raw, current, url, upstream, evidence, observed_at, mutable):
    product = shrub.inspect(raw)
    if product != current['product']:
        raise ValueError(f'Unexpected package identity: {product}')
    return {
        'id': current['id'], 'format': 'fwsc', 'url': url, 'size': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(), 'product': product, 'legacyChip': 'unknown',
        'upstream': upstream, 'mutable': mutable, 'available': True, 'evidence': evidence,
        'inspection': {'checkedAt': observed_at, 'method': 'fwsc-structure-crc'},
    }


def add_release(project, release):
    artifact, = release['artifacts']
    if any(artifact['sha256'] == row['sha256'] for old in project['releases'] for row in old['artifacts']):
        raise ValueError(f"{project['id']}: different release ID with previously reviewed bytes")
    if any(artifact['sha256'] == row['sha256'] for row in project.get('withdrawals', [])):
        raise ValueError(f"{project['id']}: candidate matches a withdrawn hash")
    if artifact['mutable']:
        for old in project['releases']:
            for row in old['artifacts']:
                if row['mutable'] and row['url'] == artifact['url']:
                    row['available'] = False
    project['releases'].append(release)
    project['updated'] = artifact['inspection']['checkedAt']


def select_release(project, release):
    artifact, = release['artifacts']
    project['recommended'] = {'release': release['id'], 'artifact': artifact['id']}


def verify_same_asset(previous, observed):
    for field in ('sha256', 'size', 'product', 'url'):
        if previous[field] != observed[field]:
            raise ValueError(f'Reviewed release asset changed ({field}); investigate manually')
    previous_upstream = previous['upstream']
    if previous_upstream.get('assetId') != observed['upstream'].get('assetId'):
        raise ValueError('Reviewed GitHub asset ID changed; investigate manually')
    if previous_upstream.get('commit', observed['upstream'].get('commit')) != observed['upstream'].get('commit'):
        raise ValueError('Reviewed publisher build commit changed; investigate manually')


def import_shrub(project, observed_at):
    release, current = repository.recommended(project)
    metadata, url, raw = shrub.observe()
    version = metadata['firmware']
    artifact = inspect_artifact(
        raw, current, url, {'type': 'direct', 'commit': metadata['commit']},
        [shrub.BUILD, shrub.INSTALL], observed_at, mutable=True,
    )
    for old in project['releases']:
        if old['id'] == version:
            previous, = (row for row in old['artifacts'] if row['id'] == current['id'])
            verify_same_asset(previous, artifact)
            if old['id'] != release['id']:
                raise ValueError('Publisher is serving an older reviewed SHRUB version')
            return
    new = {'id': version, 'version': version, 'channel': release['channel'], 'artifacts': [artifact]}
    add_release(project, new)
    select_release(project, new)


def import_github(project, config, observed_at):
    recommended, current = repository.recommended(project)
    repo = config['repository']
    if repo != current['upstream'].get('repository'):
        raise ValueError('Importer repository differs from reviewed project provenance')
    endpoint = f'https://api.github.com/repos/{repo}/releases?per_page=100'
    listing = json.loads(github_fetch(endpoint, {'api.github.com'}, 4 * 1024 * 1024,
                                     'application/vnd.github+json'))
    tag_pattern = re.compile(config.get('tagPattern', r'.+'))
    releases = {row['tag_name']: row for row in listing
                if not row['draft'] and row['published_at'] and tag_pattern.fullmatch(row['tag_name'])}
    anchor = current['upstream']['tag']
    if anchor not in releases:
        raise ValueError(f'{repo}: reviewed tag {anchor} missing from the recent release list')
    anchor_time = repository.utc(releases[anchor]['published_at'])
    reviewed = {row['id']: row for row in project['releases']}
    latest = None
    for tag, row in sorted(releases.items(), key=lambda pair: (pair[1]['published_at'], pair[0])):
        published = repository.utc(row['published_at'])
        if tag != anchor and published <= anchor_time:
            continue
        version = tag.removeprefix('v')
        name = config['assetTemplate'].format(version=version)
        matches = [asset for asset in row['assets'] if asset['name'] == name and asset['state'] == 'uploaded']
        if not matches and tag != anchor and tag not in reviewed:
            continue
        if len(matches) != 1:
            raise ValueError(f'{repo}@{tag}: expected exactly one asset named {name}')
        asset = matches[0]
        url = asset['browser_download_url']
        if repository.check_github_url(url, repo, tag) != name:
            raise ValueError('GitHub asset URL and configured filename differ')
        existing = reviewed.get(tag)
        digest = asset.get('digest')
        channel = 'beta' if row['prerelease'] else 'stable'
        if existing:
            previous, = (item for item in existing['artifacts'] if item['id'] == current['id'])
        if (not existing or digest != f"sha256:{previous['sha256']}" or asset['size'] != previous['size']
                or url != previous['url'] or str(asset['id']) != previous['upstream']['assetId']):
            raw = github_fetch(url, ASSET_HOSTS, shrub.MAX_PACKAGE, 'application/octet-stream')
            upstream = {'type': 'github-release', 'repository': repo, 'tag': tag, 'assetId': str(asset['id'])}
            evidence = [f'https://github.com/{repo}/releases/tag/{quote(tag, safe="")}']
            artifact = inspect_artifact(raw, current, url, upstream, evidence, observed_at, mutable=False)
            if len(raw) != asset['size'] or (digest and digest != f"sha256:{artifact['sha256']}"):
                raise ValueError('GitHub API metadata does not match downloaded bytes')
            if existing:
                verify_same_asset(previous, artifact)
        if existing:
            if existing['channel'] != channel:
                existing['channel'] = channel
                project['updated'] = observed_at
                if (tag != anchor and channel == 'stable' and len(existing['artifacts']) == 1
                        and previous['available'] and not any(
                            entry['sha256'] == previous['sha256'] for entry in project.get('withdrawals', []))):
                    latest = existing
            continue
        release = {'id': tag, 'version': version, 'channel': channel,
                   'publishedAt': row['published_at'], 'artifacts': [artifact]}
        add_release(project, release)
        if release['channel'] == 'stable' or recommended['channel'] == 'beta':
            latest = release
    if latest:
        select_release(project, latest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', nargs='*', help='Import only the given configured project IDs')
    args = parser.parse_args()
    index = repository.build_index()
    repository.export_legacy(index, check=True)
    config = repository.read(ROOT / 'config/publishers.json')
    unknown = set(args.project) - config.keys()
    if unknown:
        parser.error(f'No importer configured for {", ".join(sorted(unknown))}')
    selected = set(args.project or config)
    observed_at = utc_now()
    changed = []
    for project in index['projects']:
        if project['id'] not in selected:
            continue
        settings = config[project['id']]
        original = deepcopy(project)
        # A removed recommendation is an explicit curator decision. Leave it in place.
        if project['recommended'] is None:
            continue
        if settings['type'] == 'shrub':
            import_shrub(project, observed_at)
        elif settings['type'] == 'github-release':
            import_github(project, settings, observed_at)
        else:
            raise ValueError(f"Unknown importer type: {settings['type']}")
        if project != original:
            changed.append(project)
    if selected - {project['id'] for project in index['projects']}:
        raise ValueError('Publisher config refers to a missing project')
    index['updated'] = max([index['updated'], *(project['updated'] for project in changed)])
    repository.validate(index)
    for project in changed:
        path = ROOT / 'projects' / f"{project['id']}.json"
        path.write_bytes(repository.encode(project))
        print(f"Prepared update for {project['id']}")
    if changed:
        repository.export_legacy(index)
    else:
        print('No publisher updates')


if __name__ == '__main__':
    main()
