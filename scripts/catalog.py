"""Build/check local catalogs. No publisher requests and no firmware downloads."""
import argparse
from datetime import datetime
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema/catalog.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def validate(catalog):
    VALIDATOR.validate(catalog)
    ids = [entry["id"] for entry in catalog["firmwares"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate firmware ID within a catalog")


def combine(catalogs):
    entries = []
    dates = []
    for catalog in catalogs:
        validate(catalog)
        # This repository writes ISO UTC timestamps; the Android importer also accepts Hub dates.
        stamp = datetime.fromisoformat(catalog["updated"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Component updated must include its timezone")
        dates.append((stamp, catalog["updated"]))
        entries.extend(catalog["firmwares"])
        if catalog.get("stock"):
            raise ValueError("Stock aggregation is not implemented; do not silently discard it")
    if not dates:
        raise ValueError("At least one component catalog is required")
    result = {"updated": max(dates)[1], "firmwares": sorted(entries, key=lambda item: item["id"])}
    validate(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check without writing catalog.json")
    args = parser.parse_args()
    paths = sorted((ROOT / "catalogs").glob("*.json"))
    combined = combine([json.loads(path.read_text()) for path in paths])
    target = ROOT / "catalog.json"
    if args.check:
        existing = json.loads(target.read_text())
        validate(existing)
        if existing != combined:
            raise ValueError("catalog.json differs from its components; run python3 scripts/catalog.py")
    else:
        target.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n")
    print(f"Validated {len(paths)} component catalog(s), {len(combined['firmwares'])} firmware(s)")


if __name__ == "__main__":
    main()
