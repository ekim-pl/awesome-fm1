# Awesome FM-1

![Awesome FM-1 logo and icon](assets/branding/branding-board.png)

[![Catalog CI](https://github.com/ekim-pl/awesome-fm1/actions/workflows/catalog-ci.yml/badge.svg)](https://github.com/ekim-pl/awesome-fm1/actions/workflows/catalog-ci.yml)
[![Website build](https://github.com/ekim-pl/awesome-fm1/actions/workflows/pages.yml/badge.svg)](https://github.com/ekim-pl/awesome-fm1/actions/workflows/pages.yml)
[![Project website](https://img.shields.io/badge/website-awesome--fm1-blue)](https://ekim-pl.github.io/awesome-fm1/en/)

A community-maintained directory of firmware for the **M-VAVE FM-1**. Discover projects, find their original publishers, and help keep firmware sources accurate and accessible.

A companion project to [FM-1 Flasher](https://github.com/ekim-pl/android-fm1-flasher), the experimental Android firmware browser and USB MIDI flasher. The app supports built-in and custom firmware catalogs. Visit the [FM-1 Flasher website](https://ekim-pl.github.io/android-fm1-flasher/) for app documentation.

Awesome FM-1 brings together publisher download links, project repositories, release information, and documented compatibility evidence in a consistent catalog. We welcome contributions from firmware authors, musicians, developers, and anyone who discovers a useful FM-1 project.

Awesome FM-1 is independent and is not affiliated with the creators of the listed projects. We encourage you to visit their project pages and support their work.

**Know a firmware project we should include? Open a pull request with its package URL or project repository URL.** A link and a short description are enough to start a review; a complete catalog entry is welcome too.

This repository stores metadata, not firmware binaries. Packages remain hosted by their publishers. Inclusion identifies a source; it does not certify a firmware package or establish hardware compatibility.

## Explore

- [Firmware directory](#firmware-directory) · [Use the catalogs](#use-the-catalogs)
- [Contributing](#contributing) · [Format and maintenance](#format-and-maintenance)
- [Project website](#project-website) · [Attribution](#attribution)

## Firmware directory

| Project | Description | Publisher | Verification |
| --- | --- | --- | --- |
| [SHRUB](https://shrub.audio/) | Wavetable synthesizer with a browser editor | Xfer Inc. | Package structure checked; hardware compatibility unknown. See [verification evidence](docs/verification.md). |
| [SLOOP](https://github.com/isod89/sloop-fm1) | Groovebox firmware | isod89 | Package identity and hash recorded; hardware compatibility unknown. See [verification evidence](docs/sloop-verification.md). |
| [ChoralRoot](https://github.com/Quixotic7/ChoralRootFM1) | Chord instrument firmware | Quixotic7 | Package identity and hash recorded; hardware compatibility unknown. See [verification evidence](docs/choralroot-verification.md). |

## Use the catalogs

Choose the combined catalog for a single endpoint, or subscribe to individual publisher catalogs:

- [catalog.json](catalog.json): the combined catalog, generated from reviewed records under `projects/`. Recommended single endpoint: <https://raw.githubusercontent.com/ekim-pl/awesome-fm1/main/catalog.json>.
- [catalogs/shrub.json](catalogs/shrub.json): a standalone publisher catalog in the same format. Alternative endpoint: <https://raw.githubusercontent.com/ekim-pl/awesome-fm1/main/catalogs/shrub.json>.
- [catalogs/sloop.json](catalogs/sloop.json): the standalone SLOOP catalog. Endpoint: <https://raw.githubusercontent.com/ekim-pl/awesome-fm1/main/catalogs/sloop.json>.
- [catalogs/choralroot.json](catalogs/choralroot.json): the standalone ChoralRoot catalog. Endpoint: <https://raw.githubusercontent.com/ekim-pl/awesome-fm1/main/catalogs/choralroot.json>.

Use the combined catalog **or** selected individual catalogs. Subscribing to both creates overlapping offers; clients must not merge projects by name or device identity.

Once signed publishing is configured, GitHub Releases provides the [latest signed snapshot](https://github.com/ekim-pl/awesome-fm1/releases/latest/download/entry.json) for clients that support repository signatures. Each catalog release also includes the generated `catalog.json` for legacy clients. See the [repository guide](docs/firmware-repository.md#publish-a-signed-repository) for setup and verification.

FM-1 Flasher includes The Firmware Hub and Awesome FM-1 as built-in sources (Hub enabled and Awesome FM-1 disabled by default), and supports custom JSON catalog subscriptions. The `third-party` discovery feed is separate and is not compatible with the app’s catalog importer.

SHRUB is currently listed with `chip: "unknown"`. Its package passed the Android app's structural parser, but installation, subsequent updates, and old/new flash compatibility have not been tested. FM-1 Flasher normally blocks installation when compatibility is unknown; its separate force option requires explicit confirmation.

## Third-party discovery catalog

[third-party/catalog.json](third-party/catalog.json) is an automatically refreshed discovery list, separate from the reviewed firmware directory above. Candidate projects come from [2bbb's firmware collection](https://github.com/2bbb/fm1-firmware-collection) and the firmware section of [aroum's directory](https://github.com/aroum/fm1-custom-fw).

The main [catalog.json](catalog.json) is generated only from reviewed project records under `projects/`. Its builder never reads `third-party/`, so this discovery list cannot add entries to or change the main catalog. The entries above are separately reviewed entries in the main catalog. This separation is checked by the catalog tests.

Entries are unreviewed and may describe other devices, tools, unavailable projects or works in progress. Missing metadata remains null. It does **not** satisfy the installation catalog schema; do not use it by itself to authorize downloads or flashing.

### Access the third-party feed

The raw discovery list is available at <https://raw.githubusercontent.com/ekim-pl/awesome-fm1/main/third-party/catalog.json>. FM-1 Flasher cannot import it as a custom JSON catalog: its parser requires a valid `sha256` and `product` for every entry, and the discovery list includes entries without them. To explore a project in the app, add its GitHub repository or a direct package URL as a separate source when supported; see the [FM-1 Flasher source documentation](https://github.com/ekim-pl/android-fm1-flasher#catalog-providers-and-authentication).

The [daily workflow](.github/workflows/third-party.yml) updates the file and commits changes to `main`; it can also be started manually. Locally, run:

```sh
python3 scripts/aggregate_third_party.py --output third-party/catalog.json --exclude-hub --unique-code --unique-names
```

The cache under `.cache/fm1-catalog` limits repeated Hub catalog requests to once per 24 hours; retain it across runs as required by the Hub's terms. `--offline` uses cached inputs. The workflow preserves the cache between runs. The file is also published at `https://ekim-pl.github.io/awesome-fm1/third-party/catalog.json` with Pages.

## Project website

The GitHub Pages website is available in [English](https://ekim-pl.github.io/awesome-fm1/en/), [Polish](https://ekim-pl.github.io/awesome-fm1/pl/) and [Simplified Chinese](https://ekim-pl.github.io/awesome-fm1/zh-CN/).

Build locally with `python3 scripts/build_site.py`; output goes to `_site/`. Translations are in [website/locales.json](website/locales.json), with shared styling in [website/style.css](website/style.css). The website introduces the project and contribution guidelines without listing individual firmware projects; `catalog.json` remains available as a separate endpoint. The [Pages workflow](.github/workflows/pages.yml) checks PR builds and deploys pushes to `main`. GitHub Pages must use **GitHub Actions** as its source.

## Contributing

Open a **Suggest a firmware project** issue with the publisher link, or submit a pull request. Maintainers can help with the catalog details.

### Submit a firmware source

1. Fork this repository and create a branch for your contribution.
2. Choose either submission path below.
3. Open a pull request describing the project and linking to its original publisher. Keep each PR focused on one project or a closely related update.
4. Respond to review questions and make any requested corrections. Maintainers review provenance, metadata, and available evidence before adding a source to the published catalog.

**URL-only submission:** add a short Markdown file under `submissions/`, for example `submissions/my-firmware.md`, using the template below. The directory can be created with your first submission. These files are review proposals and are not imported by the catalog builder. Maintainers can help turn an accepted proposal into a catalog entry; missing package details must be resolved before publication.

```markdown
# Firmware source proposal

- Project name:
- Short description:
- Author / publisher:
- Project website:
- Package URL and/or repository URL:
- Release / version (if known):
- FM-1 compatibility evidence (or "unknown"):
- Your relationship to the project (author, user, or other):
- Additional notes (beta status, license, installation docs, etc.):
```

Provide at least one publicly accessible HTTPS package or repository URL. A repository URL is sufficient for proposing a project, even if it does not yet publish a downloadable package. Clearly label projects without installable releases. Do not commit firmware binaries.

**Complete catalog submission:** add or update a reviewed record in `projects/`, using [projects/shrub.json](projects/shrub.json) and the [repository schema](schema/repository.schema.json) as references. Include verification notes in `docs/` when introducing a package or changing its hash or compatibility claims. Regenerate the legacy exports and run the checks below before opening your PR.

### Catalog entry requirements

Keep the project ID stable and record its publisher, description and links. For an installable release, include the exact publisher asset URL, SHA-256, byte size, observed FM-1 product ID, release channel and verification evidence. For GitHub assets include the owner/repository, release tag and numeric asset ID. Use `legacyChip: "unknown"` until there is hardware evidence for the exact package.

A hash records which bytes were reviewed. Distinguish package inspection from hardware installation evidence. See the [repository guide](docs/firmware-repository.md#contribute-a-project-or-release) for recommended releases, availability and withdrawals.

### Project guidelines

- **Link to the original source.** Prefer the author's website, repository, and release assets. Explain any alternate host and its relationship to the publisher.
- **Respect authors and distribution rights.** Preserve attribution and relevant license information. A public download link does not grant permission to redistribute the package.
- **Make claims reviewable.** Link supporting release notes or documentation. Mark uncertain details as unknown and disclose beta status and known limitations.
- **Keep updates traceable.** Explain changed URLs, versions, hashes, and compatibility claims. Never replace an expected hash simply to make a failed download pass.
- **Avoid duplicates and promotional copy.** Check existing entries first. Describe what a project does in neutral, useful language.
- **Collaborate respectfully.** Discuss evidence and technical details constructively. Harassment, impersonation, and knowingly misleading submissions are not acceptable.
- **Report stale or incorrect entries.** Open an issue or a focused correction PR with the affected entry, source URL, and evidence. Maintainers may defer or remove entries whose provenance or accuracy cannot be established.

## Format and maintenance

Edit the reviewed records under `projects/`. GitHub Actions checks the records, prepares candidate publisher updates and publishes the [versioned repository](docs/firmware-repository.md). The separate [FM-1 Flasher integration plan](docs/android-fm1-flasher-repository-plan.md) covers signed subscriptions and migration of existing app data.

Run these commands before submitting a change.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/repository.py
.venv/bin/python scripts/repository.py --check
.venv/bin/python -m unittest discover -s tests -v
```

The [legacy catalog schema](schema/catalog.schema.json) still applies to the generated `catalog.json` and `catalogs/*.json` exports used by current flasher builds. The Hub's package rules remain specific to that source. [Hub catalog terms](https://thefirmwarehub.com/kb/#catalog)

## Attribution

Catalog format reference: [The Firmware Hub](https://thefirmwarehub.com/). The reviewed installation catalog does not copy the Hub catalog; the separate discovery catalog includes attribution and upstream-derived metadata. Firmware, artwork and publisher descriptions remain their authors' work. Listing a download URL does not grant permission to redistribute its binary. No license is asserted here for third-party firmware.
