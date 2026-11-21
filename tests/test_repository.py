import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import import_publishers
import repository
import sign_repository


OBSERVED = '2026-11-18T00:00:00Z'


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.index = repository.build_index()

    def project(self, name):
        return next(row for row in self.index['projects'] if row['id'] == name)

    def test_migration_preserves_legacy_install_entries(self):
        repository.export_legacy(self.index, check=True)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            repository.export_legacy(self.index, root=root)
            for name in ('catalog.json', 'catalogs/choralroot.json', 'catalogs/shrub.json', 'catalogs/sloop.json'):
                self.assertEqual(repository.read(root / name), repository.read(repository.ROOT / name))

    def test_withdrawal_requires_explicit_recommendation_change(self):
        shrub = self.project('shrub')
        _, artifact = repository.recommended(shrub)
        shrub['withdrawals'] = [{'sha256': artifact['sha256'], 'reason': 'Example', 'withdrawnAt': OBSERVED}]
        with self.assertRaisesRegex(ValueError, 'withdrawn'):
            repository.validate(self.index)
        shrub['recommended'] = None
        repository.validate(self.index)
        self.assertEqual(repository.legacy_component(shrub)['firmwares'], [])

    def test_wrong_github_url_cannot_masquerade_as_release_asset(self):
        _, artifact = repository.recommended(self.project('sloop'))
        artifact['url'] = artifact['url'].replace('v2.8.5/', 'other-tag/')
        with self.assertRaisesRegex(ValueError, 'Unexpected release asset URL'):
            repository.validate(self.index)

    def test_shrub_reused_url_keeps_history_and_resets_compatibility(self):
        project = self.project('shrub')
        _, old = repository.recommended(project)
        old['legacyChip'] = 'new'
        with patch.object(import_publishers.shrub, 'observe', return_value=(
            {'firmware': '1.08', 'commit': 'new'}, old['url'], b'1' * 960,
        )), patch.object(import_publishers.shrub, 'inspect', return_value=old['product']):
            import_publishers.import_shrub(project, OBSERVED)
        release, current = repository.recommended(project)
        self.assertFalse(old['available'])
        self.assertEqual(old['legacyChip'], 'new')
        self.assertEqual(current['legacyChip'], 'unknown')
        self.assertEqual(release['version'], '1.08')
        repository.validate(self.index)

    def github_fixture(self):
        project = self.project('choralroot')
        _, current = repository.recommended(project)
        config = repository.read(repository.ROOT / 'config/publishers.json')['choralroot']
        repo = config['repository']
        package = b'a' * 960

        def release(tag, day, beta=False, url=None, sha256=None, size=960, asset_id=1234):
            name = config['assetTemplate'].format(version=tag[1:])
            return {
                'tag_name': tag, 'published_at': f'2026-11-{day}T00:00:00Z', 'draft': False,
                'prerelease': beta,
                'assets': [{'name': name, 'state': 'uploaded', 'id': asset_id, 'size': size,
                            'digest': f"sha256:{sha256 or hashlib.sha256(package).hexdigest()}",
                            'browser_download_url': url or f'https://github.com/{repo}/releases/download/{tag}/{name}'}],
            }

        anchor = release(current['upstream']['tag'], '12', url=current['url'], sha256=current['sha256'],
                         size=current['size'], asset_id=int(current['upstream']['assetId']))
        return project, config, current, package, release, anchor

    def test_choralroot_keeps_stable_and_excludes_smk37(self):
        project, config, current, package, release, anchor = self.github_fixture()
        beta = release('v0.42-rc1', '14', beta=True)
        smk37 = release('v0.42-smk37.1', '15')
        with patch.object(import_publishers, 'github_fetch', side_effect=[
            json.dumps([smk37, beta, anchor]).encode(), package,
        ]) as fetch, patch.object(import_publishers.shrub, 'inspect', return_value=current['product']):
            import_publishers.import_github(project, config, OBSERVED)
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual([row['id'] for row in project['releases']], ['v0.41', 'v0.42-rc1'])
        self.assertEqual(project['recommended']['release'], 'v0.41')
        repository.validate(self.index)

    def test_github_replaced_reviewed_bytes_fail(self):
        project, config, current, package, _, anchor = self.github_fixture()
        original = deepcopy(project)
        anchor['assets'][0].update(size=len(package), digest=f"sha256:{hashlib.sha256(package).hexdigest()}")
        with patch.object(import_publishers, 'github_fetch', side_effect=[
            json.dumps([anchor]).encode(), package,
        ]), patch.object(import_publishers.shrub, 'inspect', return_value=current['product']):
            with self.assertRaisesRegex(ValueError, 'Reviewed release asset changed'):
                import_publishers.import_github(project, config, OBSERVED)
        self.assertEqual(project, original)


class SigningTests(unittest.TestCase):
    def test_sign_and_reject_tamper_wrong_key_expiry_and_replay(self):
        now = datetime(2026, 11, 18, tzinfo=timezone.utc)
        index = repository.build_index()
        with TemporaryDirectory() as directory:
            private = Path(directory) / 'test.pem'
            sign_repository.openssl('genpkey', '-algorithm', 'Ed25519', '-out', str(private))
            public = sign_repository.openssl('pkey', '-in', str(private), '-pubout', '-outform', 'DER')
            pin = hashlib.sha256(public).hexdigest()
            signed = sign_repository.sign(index, private, pin, 100, now)

        self.assertEqual(sign_repository.verify(signed, pin, now)['index'], index)
        with self.assertRaisesRegex(ValueError, 'pinned fingerprint'):
            sign_repository.verify(signed, 'a' * 64, now)
        with self.assertRaisesRegex(ValueError, 'replayed'):
            sign_repository.verify(signed, pin, now, minimum_sequence=101)
        with self.assertRaisesRegex(ValueError, 'expired'):
            sign_repository.verify(signed, pin, now + timedelta(days=14))
        tampered = json.loads(signed)
        payload = base64.b64decode(tampered['payload']).replace(b'Awesome FM-1', b'Awesome FM-2')
        tampered['payload'] = base64.b64encode(payload).decode('ascii')
        with self.assertRaises(subprocess.CalledProcessError):
            sign_repository.verify(repository.encode(tampered), pin, now)


if __name__ == '__main__':
    unittest.main()
