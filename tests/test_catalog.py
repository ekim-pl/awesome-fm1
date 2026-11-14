import copy
import importlib.util
import json
from pathlib import Path
import unittest

from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("catalog", ROOT / "scripts/catalog.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads((ROOT / "catalogs/shrub.json").read_text())

    def test_same_product_is_not_a_duplicate_project(self):
        another = copy.deepcopy(self.sample)
        another["firmwares"][0]["id"] = "different-project"
        merged = catalog.combine([self.sample, another])
        self.assertEqual(2, len(merged["firmwares"]))

    def test_duplicate_project_ids_cannot_silently_overwrite(self):
        with self.assertRaises(ValueError):
            catalog.combine([self.sample, self.sample])

    def test_direct_download_needs_no_fake_github_repository(self):
        self.assertIsNone(self.sample["firmwares"][0]["repo"])
        catalog.validate(self.sample)

    def test_missing_or_invalid_hash_is_rejected(self):
        for replacement in [None, "not-a-hash"]:
            entry = self.sample["firmwares"][0]
            if replacement is None:
                entry.pop("sha256")
            else:
                entry["sha256"] = replacement
            with self.assertRaises(ValidationError):
                catalog.validate(self.sample)

    def test_unknown_upstream_fields_survive_aggregation(self):
        self.sample["firmwares"][0]["future-field"] = {"keep": True}
        self.assertEqual({"keep": True}, catalog.combine([self.sample])["firmwares"][0]["future-field"])

    def test_empty_full_catalog_is_valid(self):
        self.sample["firmwares"] = []
        self.assertEqual([], catalog.combine([self.sample])["firmwares"])

    def test_newest_component_time_is_used_without_fabricating_freshness(self):
        other = {"updated": "2026-11-15T00:00:00Z", "firmwares": []}
        self.assertEqual(other["updated"], catalog.combine([self.sample, other])["updated"])

    def test_defaults_leave_only_hub_enabled(self):
        sources = json.loads((ROOT / "config/app-source-presets.json").read_text())["sources"]
        self.assertEqual(["firmwarehub"], [s["id"] for s in sources if s["enabledByDefault"]])
        self.assertGreaterEqual(sources[0]["minRefreshHours"], 24)
        self.assertNotIn("thefirmwarehub.com", sources[0]["packageHosts"])


if __name__ == "__main__":
    unittest.main()
