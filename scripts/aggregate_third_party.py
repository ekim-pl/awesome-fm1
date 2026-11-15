#!/usr/bin/env python3
"""Aggregate FM-1 projects into a TheFirmwareHub-shaped catalog. Python 3.10+."""

import argparse
import copy
import hashlib
import html
import json
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

COLLECTION = "https://raw.githubusercontent.com/2bbb/fm1-firmware-collection/main/catalog/firmwares.json"
AROUM = "https://raw.githubusercontent.com/aroum/fm1-custom-fw/main/README.md"
HUB = "https://thefirmwarehub.com/catalog.json"
HUB_BASE = "https://thefirmwarehub.com/"
GITHUB_URL = re.compile(r"https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^\s)<>]*)?", re.I)
FIELDS = """id kind name author repo ident what editor play added loader cheat install
card color vintage ambient fmhub stars talk lic starsDay site version date published
pkg product size sha256 release tag srcref mirror beta hid chip base dinghy dinghyv source""".split()
URL_FIELDS = "source editor play loader cheat install card talk site pkg release mirror".split()


def repo_name(value):
    """Canonical GitHub identity; branch, release, query and fragment are irrelevant."""
    if not isinstance(value, str):
        raise ValueError("Repository must be a string")
    value = value.strip()
    if value.startswith("git@github.com:"):
        value = value[len("git@github.com:"):]
    elif "://" in value:
        parts = urlsplit(value)
        if parts.hostname != "github.com" or parts.scheme not in ("http", "https", "ssh", "git"):
            raise ValueError(f"Not a GitHub repository: {value}")
        value = "/".join(parts.path.strip("/").split("/")[:2])
    value = re.sub(r"\.git$", "", value.strip("/"), flags=re.I)
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError(f"Invalid repository: {value}")
    return value.lower()


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Fetcher:
    """Cache all requests for 24h, including catalog access and redirect checks."""

    def __init__(self, directory, offline=False):
        self.directory = Path(directory)
        self.offline = offline

    def get(self, url, redirect_only=False):
        path = self.directory / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if path.exists() and (self.offline or time.time() - path.stat().st_mtime < 86400):
            return json.loads(path.read_text(encoding="utf-8"))
        if self.offline:
            raise ValueError(f"Missing offline cache for {url}; run online first")
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 fm1-catalog/1.0"})
        try:
            with urlopen(request, timeout=45) as response:
                result = {"url": response.url, "status": response.status,
                          "text": "" if redirect_only else response.read().decode("utf-8")}
        except HTTPError as error:
            if not redirect_only or error.code not in (404, 410):
                raise
            result = {"url": url, "status": error.code, "text": ""}
        atomic_write(path, json.dumps(result, ensure_ascii=False))
        return result


def plain_text(text):
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return " ".join(html.unescape(text).replace("**", "").replace("`", "").replace(r"\|", "|").split())


def parse_aroum(text):
    section = re.search(r"^## 1\. Custom[^\n]*\n(.*?)(?=^## 2\. )", text, re.M | re.S)
    if section is None:
        raise ValueError("Cannot find aroum firmware section; README structure changed")
    entries, skipped = [], []
    heading = ""
    # shortcut: upstream currently uses single-line table rows; reject an empty parse on layout changes.
    for line in section[1].splitlines():
        if line.startswith("###"):
            heading = line.lstrip("# ")
        if not re.match(r"\|\s*\d+\s*\|", line):
            continue
        columns = re.split(r"(?<!\\)\|", line)
        if len(columns) < 4:
            raise ValueError("Malformed aroum firmware table row")
        info, description = columns[2:4]
        title_match = re.search(r"\*\*(.*?)\*\*", info)
        title = plain_text(title_match[1] if title_match else info.split("<br>")[0])
        name, _, author = title.partition(" by ")
        # Only the project's links column: references in its description can name unrelated repos.
        repos = sorted({repo_name(url) for url in GITHUB_URL.findall(info)})
        if not repos:
            skipped.append(title)
        for repo in repos:
            entries.append({"repo": repo, "name": name, "author": author or None,
                            "what": plain_text(description), "section": heading})
    if not entries:
        raise ValueError("No firmware repositories found in aroum README")
    return entries, skipped


def firmware_rows(data, source):
    if not isinstance(data, dict) or not isinstance(data.get("firmwares"), list) or not data["firmwares"]:
        raise ValueError(f"{source}: expected a nonempty firmwares array")
    for row in data["firmwares"]:
        if not isinstance(row, dict):
            raise ValueError(f"{source}: firmware must be an object")
        repo_name(row.get("repo"))
    return data["firmwares"]


def hub_entry(row):
    entry = copy.deepcopy(row)
    for field in URL_FIELDS:
        if entry.get(field):
            entry[field] = urljoin(HUB_BASE, entry[field])
    return entry


def aggregate(collection, hub, aroum, skipped, resolutions, updated):
    rows = firmware_rows(collection, "2bbb")
    hub_rows = firmware_rows(hub, "TheFirmwareHub")
    groups = {}
    for row in rows:
        key = repo_name(row["repo"])
        groups.setdefault(key, {"collection": [], "aroum": [], "aliases": []})["collection"].append(row)
    for row in aroum:
        original = row["repo"]
        resolution = resolutions.get(original, {})
        key = repo_name(resolution["url"]) if resolution.get("status") == 200 else original
        group = groups.setdefault(key, {"collection": [], "aroum": [], "aliases": []})
        group["aroum"].append(row)
        if original != key and original not in group["aliases"]:
            group["aliases"].append(original)
    hubs = {}
    for row in hub_rows:
        hubs.setdefault(repo_name(row["repo"]), []).append(hub_entry(row))

    entries = []
    for repo, group in sorted(groups.items()):
        source = group["collection"][0] if group["collection"] else {}
        curated = group["aroum"][0] if group["aroum"] else {}
        variants = hubs.get(repo, [])
        embedded = source.get("hub") or {}
        entry = dict.fromkeys(FIELDS)
        entry.update(variants[0] if variants else hub_entry(embedded))
        entry["repo"] = repo
        entry["id"] = entry.get("id") or "github-" + repo.replace("/", "__")
        entry["name"] = entry.get("name") or curated.get("name") or repo.split("/")[1]
        entry["author"] = entry.get("author") or curated.get("author") or repo.split("/")[0]
        entry["what"] = entry.get("what") or source.get("description") or curated.get("what")
        entry["source"] = entry.get("source") or "https://github.com/" + repo
        entry["site"] = entry.get("site") or "https://github.com/" + repo
        entry["lic"] = entry.get("lic") or source.get("license")
        if entry.get("stars") is None:
            entry["stars"] = source.get("stars")
        # A repository can publish binaries for several devices. Do not guess a flashable package.
        sources = ([COLLECTION] if group["collection"] else []) + ([AROUM] if group["aroum"] else [])
        if variants or embedded:
            sources.append(HUB)
        entry["catalog_meta"] = {
            "sources": sources,
            "aliases": group["aliases"],
            "aroum": group["aroum"],
            "collection": group["collection"],
        }
        resolution = resolutions.get(repo)
        if resolution:
            entry["catalog_meta"]["repository_http_status"] = resolution["status"]
        if len(variants) > 1:
            entry["variants"] = variants
        entries.append(entry)

    ids = [entry["id"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("Conflicting firmware IDs; refusing to write an ambiguous catalog")
    return {
        "license": hub.get("license"),
        "updated": updated,
        "firmwares": entries,
        "aggregation": {
            "sources": [COLLECTION, AROUM],
            "enrichment": HUB,
            "hub_updated": hub.get("updated"),
            "license_scope": "The top-level license is The Firmware Hub's attribution and applies to its list. "
                             "Additional metadata retains its upstream terms; firmware licenses are in lic.",
            "aroum_scope": "Section 1, project links column only; includes platforms, games and binary patchers.",
            "deduplication": "Case-insensitive GitHub owner/repo; redirects for aroum repos absent from 2bbb. "
                             "Forks remain separate; Hub variants are preserved under variants.",
            "counts": {"collection_rows": len(rows), "aroum_rows": len(aroum),
                       "aroum_repositories": len({r['repo'] for r in aroum}),
                       "unique_repositories": len(entries),
                       "merged_rows": len(rows) + len(aroum) - len(entries),
                       "redirect_aliases": sum(len(g["aliases"]) for g in groups.values()),
                       "added_from_aroum": sum(not g["collection"] for g in groups.values())},
            "aroum_without_git_repository": skipped,
            "unavailable_repositories": [repo for repo, value in resolutions.items() if value["status"] != 200],
        },
    }


def clean_catalog(catalog, hub, exclude_hub=False, unique_code=False, unique_names=False):
    """Filter the generated snapshot; equal HEAD means equal default-branch commit only."""
    rows = catalog["firmwares"]
    hub_repos = {repo_name(r["repo"]) for r in firmware_rows(hub, "TheFirmwareHub")}
    for field in ("stars", "talk"):
        hub_repos.update(repo_name(repo) for repo in hub.get("smk37", {}).get(field, {}))
    stock_source = hub.get("stock", {}).get("source")
    if stock_source and urlsplit(stock_source).hostname == "github.com":
        hub_repos.add(repo_name(stock_source))

    def head(row):
        records = row.get("catalog_meta", {}).get("collection", [])
        return records[0].get("head") if records else None

    hub_heads = {head(r) for r in rows if r["repo"] in hub_repos and head(r)}
    removed, remaining = [], []
    for row in rows:
        reason = None
        identities = {row["repo"], *row.get("catalog_meta", {}).get("aliases", [])}
        if exclude_hub and identities & hub_repos:
            reason = "thefirmwarehub_repository"
        elif exclude_hub and unique_code and head(row) and head(row) in hub_heads:
            reason = "same_head_as_thefirmwarehub_repository"
        if reason:
            removed.append({"repo": row["repo"], "reason": reason})
        else:
            remaining.append(row)

    if unique_code:
        groups = {}
        for row in remaining:
            key = ("head", head(row)) if head(row) else ("repo", row["repo"])
            groups.setdefault(key, []).append(row)
        remaining = []
        for group in groups.values():
            parents = {repo_name(c["fork_of"]) for r in group
                       for c in r["catalog_meta"]["collection"] if c.get("fork_of")}
            preferred = sorted(group, key=lambda r: (
                -(r["repo"] in parents),
                -bool(r["catalog_meta"]["aroum"]),
                -(r.get("stars") or 0), r["repo"]))[0]
            remaining.append(preferred)
            for row in group:
                if row is not preferred:
                    removed.append({"repo": row["repo"], "reason": "same_head",
                                    "kept": preferred["repo"], "head": head(row)})
    if unique_names:
        groups = {}
        for row in remaining:
            name = " ".join((row.get("name") or "").casefold().split())
            groups.setdefault(name or row["repo"], []).append(row)
        remaining = []
        for group in groups.values():
            parents = {repo_name(c["fork_of"]) for r in group
                       for c in r["catalog_meta"]["collection"] if c.get("fork_of")}
            preferred = sorted(group, key=lambda r: (
                -(r["repo"] in parents), -bool(r["catalog_meta"]["aroum"]),
                -(r.get("stars") or 0), r["repo"]))[0]
            remaining.append(preferred)
            removed.extend({"repo": r["repo"], "reason": "same_name",
                            "kept": preferred["repo"], "name": r["name"]}
                           for r in group if r is not preferred)
    catalog["firmwares"] = sorted(remaining, key=lambda r: r["repo"])
    catalog["aggregation"]["cleanup"] = {
        "exclude_hub": exclude_hub, "unique_code": unique_code, "unique_names": unique_names,
        "rule": "Identical default-branch HEAD in the source snapshot; other branches and release assets are not compared.",
        "removed": removed,
    }
    catalog["aggregation"]["counts"]["before_cleanup"] = len(rows)
    catalog["aggregation"]["counts"]["removed_by_cleanup"] = len(removed)
    catalog["aggregation"]["counts"]["unique_repositories"] = len(remaining)
    return catalog


def add_projects_without_git(catalog, hub, readme, exclude_hub):
    section = re.search(r"^## 1\. Custom[^\n]*\n(.*?)(?=^## 2\. )", readme, re.M | re.S)
    if not section:
        raise ValueError("Cannot find aroum firmware section")
    hub_names = {r['name'].casefold() for r in firmware_rows(hub, 'TheFirmwareHub') if r.get('name')}
    existing = {r['name'].casefold() for r in catalog['firmwares'] if r.get('name')}
    added = []
    for line in section[1].splitlines():
        if not re.match(r"\|\s*\d+\s*\|", line):
            continue
        columns = re.split(r"(?<!\\)\|", line)
        if len(columns) < 4 or GITHUB_URL.search(columns[2]):
            continue
        info, description = columns[2:4]
        match = re.search(r"\*\*(.*?)\*\*", info)
        if not match:
            continue
        title = plain_text(match[1])
        name, _, author = title.partition(' by ')
        key = name.casefold()
        if exclude_hub and key in hub_names:
            continue
        if key in existing and key not in {'grus', 'jazzy'}:
            continue
        links = re.findall(r'\[([^\]]+)\]\((https?://[^)]+)\)', info)
        entry = dict.fromkeys(FIELDS)
        entry.update(id='aroum-' + hashlib.sha256(title.encode()).hexdigest()[:16],
                     name=name, author=author or None, what=plain_text(description),
                     site=links[0][1] if links else None, source=links[0][1] if links else None,
                     catalog_meta={'sources': [AROUM], 'aliases': [], 'collection': [],
                                   'aroum': [{'title': title, 'links': links}],
                                   'note': 'No Git repository linked in the source.'})
        catalog['firmwares'].append(entry)
        existing.add(key)
        added.append(title)
    catalog['aggregation']['added_without_git'] = added
    catalog['aggregation']['counts']['added_without_git'] = len(added)
    catalog['aggregation']['counts']['total_firmwares'] = len(catalog['firmwares'])
    catalog['aggregation']['aroum_without_git_repository'] = []
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("catalog.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/fm1-catalog"))
    parser.add_argument("--offline", action="store_true", help="Use cached inputs without network access")
    parser.add_argument("--exclude-hub", action="store_true", help="Exclude repositories listed by TheFirmwareHub")
    parser.add_argument("--unique-code", action="store_true", help="Keep one project per identical source HEAD")
    parser.add_argument("--unique-names", action="store_true", help="Keep one entry per case-insensitive name, even for distinct projects")
    args = parser.parse_args()
    fetch = Fetcher(args.cache_dir, args.offline)
    try:
        collection = json.loads(fetch.get(COLLECTION)["text"])
        hub = json.loads(fetch.get(HUB)["text"])
        readme = fetch.get(AROUM)["text"]
        aroum, skipped = parse_aroum(readme)
        known = {repo_name(row["repo"]) for row in firmware_rows(collection, "2bbb")}
        resolutions = {}
        for repo in sorted({row["repo"] for row in aroum} - known):
            resolutions[repo] = fetch.get("https://github.com/" + repo, redirect_only=True)
        catalog = aggregate(collection, hub, aroum, skipped, resolutions,
                            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        if args.exclude_hub or args.unique_code or args.unique_names:
            clean_catalog(catalog, hub, args.exclude_hub, args.unique_code, args.unique_names)
        add_projects_without_git(catalog, hub, readme, args.exclude_hub)
        atomic_write(args.output, json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    except (OSError, URLError, ValueError, TypeError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(catalog["aggregation"]["counts"], indent=2))
    print(f"Written: {args.output}")
    for repo in catalog["aggregation"]["unavailable_repositories"]:
        print(f"WARNING: repository unavailable; retained source entry: {repo}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
