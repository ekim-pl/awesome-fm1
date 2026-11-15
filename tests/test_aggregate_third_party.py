import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import importlib.util

spec = importlib.util.spec_from_file_location("aggregate_third_party", Path(__file__).resolve().parents[1] / "scripts/aggregate_third_party.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


README = """## 1. Custom & Alternative Firmwares
### 1.1. Sound
| # | Name | Description |
|---|---|---|
| 1 | **Synth by Alice**<br>[GitHub](https://github.com/Alice/Synth.git/tree/main) \\| [Releases](https://github.com/alice/synth/releases) | **FM** synth; based on [other](https://github.com/other/library). |
| 2 | **No repo**<br>[Website](https://example.com) | Closed source. |
## 2. Hardware
[Tool](https://github.com/other/tool)
"""


class CatalogTests(unittest.TestCase):
    def test_repository_identity(self):
        for value in ("Alice/Synth", "https://github.com/ALICE/Synth.git/",
                      "git@github.com:Alice/Synth.git", "ssh://git@github.com/Alice/Synth.git",
                      "https://github.com/alice/Synth/tree/main?x=1#readme"):
            self.assertEqual(catalog.repo_name(value), "alice/synth")
        for value in (None, "https://example.com/alice/synth", "alice", "alice/synth/main"):
            with self.assertRaises(ValueError):
                catalog.repo_name(value)

    def test_aroum_scope_and_repeated_links(self):
        rows, skipped = catalog.parse_aroum(README)
        self.assertEqual([r["repo"] for r in rows], ["alice/synth"])
        self.assertEqual(rows[0]["name"], "Synth")
        self.assertEqual(rows[0]["author"], "Alice")
        self.assertEqual(skipped, ["No repo"])
        without_trailing_pipes = "\n".join(line.rstrip(" |") for line in README.splitlines())
        self.assertEqual(catalog.parse_aroum(without_trailing_pipes), (rows, skipped))
        with self.assertRaises(ValueError):
            catalog.parse_aroum("# Different layout")

    def test_merge_redirects_forks_variants_and_unknowns(self):
        rows, skipped = catalog.parse_aroum(README)
        rows += [{"repo": "alice/old", "name": "Old"}, {"repo": "alice/missing", "name": "Missing"}]
        collection = {"firmwares": [
            {"repo": "Alice/Synth", "description": "Collection", "license": "MIT"},
            {"repo": "alice/SYNTH", "description": "Duplicate"},
            {"repo": "Bob/Synth", "fork_of": "Alice/Synth"},
        ]}
        hub = {"firmwares": [
            {"id": "synth", "repo": "Alice/Synth", "name": "Curated", "pkg": "fw/main.fwsc", "sha256": "abc"},
            {"id": "synth-bt", "repo": "alice/synth", "pkg": "fw/bt.fwsc", "sha256": "def"},
            {"id": "unrelated", "repo": "other/unrelated"},
        ]}
        resolutions = {"alice/old": {"status": 200, "url": "https://github.com/Alice/Synth"},
                       "alice/missing": {"status": 404, "url": "https://github.com/alice/missing"}}
        result = catalog.aggregate(collection, hub, rows, skipped, resolutions, "fixed")
        by_repo = {r["repo"]: r for r in result["firmwares"]}
        self.assertEqual(set(by_repo), {"alice/synth", "bob/synth", "alice/missing"})
        synth = by_repo["alice/synth"]
        self.assertEqual(synth["name"], "Curated")
        self.assertEqual(synth["pkg"], "https://thefirmwarehub.com/fw/main.fwsc")
        self.assertEqual(synth["sha256"], "abc")
        self.assertEqual(synth["variants"][1]["sha256"], "def")
        self.assertEqual(synth["catalog_meta"]["aliases"], ["alice/old"])
        self.assertEqual(len(synth["catalog_meta"]["collection"]), 2)
        self.assertEqual(synth["catalog_meta"]["sources"], [catalog.COLLECTION, catalog.AROUM, catalog.HUB])
        self.assertIsNone(by_repo["bob/synth"]["pkg"])
        self.assertIsNone(by_repo["alice/missing"]["version"])
        self.assertEqual(by_repo["alice/missing"]["catalog_meta"]["repository_http_status"], 404)
        self.assertEqual(hub["firmwares"][0]["pkg"], "fw/main.fwsc")

    def test_duplicate_ids_fail_instead_of_dropping_data(self):
        rows = [{"repo": "a/one", "hub": {"id": "same"}}, {"repo": "b/two", "hub": {"id": "same"}}]
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            catalog.aggregate({"firmwares": rows}, {"firmwares": [{"repo": "c/three"}]}, [], [], {}, "fixed")

    def test_cache_and_offline_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            fetch = catalog.Fetcher(directory)
            with patch.object(catalog, "urlopen") as request:
                response = request.return_value.__enter__.return_value
                response.url, response.status = catalog.HUB, 200
                response.read.return_value = b'{"firmwares": []}'
                first = fetch.get(catalog.HUB)
                self.assertEqual(fetch.get(catalog.HUB), first)
                self.assertEqual(catalog.Fetcher(directory, True).get(catalog.HUB), first)
                request.assert_called_once()
                with self.assertRaisesRegex(ValueError, "Missing offline cache"):
                    catalog.Fetcher(directory, True).get(catalog.AROUM)

    def test_cleanup_excludes_hub_and_identical_commits_but_not_names(self):
        def row(repo, head=None, parent=None):
            return {"repo": repo, "name": "Same name", "catalog_meta": {
                "aroum": [], "collection": [{"head": head, "fork_of": parent}]}}
        data = {"firmwares": [row("a/hub", "hubhead"), row("b/copy", "hubhead"),
                              row("c/original", "other"), row("d/fork", "other", "c/original"),
                              row("e/different", "different"), row("f/unknown"),
                              row("g/unknown"), row("h/smk"), row("i/stock")],
                "aggregation": {"counts": {}}}
        hub = {"firmwares": [{"repo": "a/hub"}], "smk37": {"stars": {"h/smk": 1}},
               "stock": {"source": "https://github.com/i/stock/blob/main/fw.fwsc"}}
        catalog.clean_catalog(data, hub, exclude_hub=True, unique_code=True)
        self.assertEqual([r["repo"] for r in data["firmwares"]],
                         ["c/original", "e/different", "f/unknown", "g/unknown"])
        self.assertEqual(data["aggregation"]["counts"]["removed_by_cleanup"], 5)
        self.assertEqual(len(data["aggregation"]["cleanup"]["removed"]), 5)

    def test_invalid_input_keeps_previous_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "catalog.json"
            output.write_text("previous catalog", encoding="utf-8")
            with patch("sys.argv", ["aggregate_catalog.py", "--output", str(output)]), \
                    patch.object(catalog.Fetcher, "get", return_value={"text": "invalid json"}), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(catalog.main(), 1)
            self.assertEqual(output.read_text(), "previous catalog")

    def test_unique_names_merges_distinct_projects_only_when_requested(self):
        def data():
            return {"firmwares": [
                {"repo": "a/one", "name": "  Same   Name ", "stars": 1,
                 "catalog_meta": {"collection": [], "aroum": []}},
                {"repo": "b/two", "name": "same name", "stars": 5,
                 "catalog_meta": {"collection": [], "aroum": []}},
            ], "aggregation": {"counts": {}}}
        hub = {"firmwares": [{"repo": "c/other"}]}
        original = data()
        catalog.clean_catalog(original, hub)
        self.assertEqual(len(original["firmwares"]), 2)
        result = data()
        catalog.clean_catalog(result, hub, unique_names=True)
        self.assertEqual([r["repo"] for r in result["firmwares"]], ["b/two"])
        self.assertEqual(result["aggregation"]["cleanup"]["removed"][0]["reason"], "same_name")

    def test_projects_without_git_preserve_explicit_name_exceptions(self):
        readme = """## 1. Custom
| 1 | **SHRUB by Steve** [Website](https://shrub.audio/) | Synth |
| 2 | **GRUS** [Discussion](https://example.org/grus) | Synth |
| 3 | **Clipper** [Website](https://example.org/clipper) | Synth |
## 2. Hardware
"""
        data = {"firmwares": [{"name": "grus", "repo": "a/grus"}], "aggregation": {"counts": {}}}
        hub = {"firmwares": [{"repo": "a/clipper", "name": "Clipper"}]}
        catalog.add_projects_without_git(data, hub, readme, True)
        self.assertEqual([r['name'] for r in data['firmwares']], ['grus', 'SHRUB', 'GRUS'])
        self.assertIsNone(data['firmwares'][1]['repo'])
        self.assertEqual(data['firmwares'][1]['site'], 'https://shrub.audio/')


if __name__ == "__main__":
    unittest.main()
