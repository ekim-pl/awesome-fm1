# Awesome FM-1 firmware repository

Awesome FM-1 keeps reviewed firmware metadata in Git. GitHub Actions checks pull requests, prepares publisher updates and publishes catalog snapshots through GitHub Releases and GitHub Pages. Firmware files stay at the listed publisher URLs. Each project keeps its own release history so reviews can distinguish a new release, a replacement download and a withdrawal.

## Contribute a project or release

Open the **Suggest a firmware project** issue form with the publisher URL, or open a PR against `projects/<project-id>.json`. Use the [repository schema](../schema/repository.schema.json) and a [reviewed example](../projects/sloop.json). Keep project IDs stable. An FM-1 package product code identifies a package family and can occur in more than one project.

Add each release with a stable ID, a display version, a channel and one or more artifacts. Record the exact package URL, size, SHA-256, identity, upstream provenance and evidence. Choose the recommended release and artifact explicitly. A project can have an empty release list and a null recommendation. Preserve known publication times and leave unknown dates absent.

Use `legacyChip: "unknown"` until there is hardware evidence for the exact hash. The labels `old` and `new` retain their current FM-1 Flasher meanings. An importer reports package inspection and starts each new hash at unknown compatibility. Hardware reports should record the hash, device and chip, procedure and observed result.

For a withdrawal, add the hash, reason and UTC `withdrawnAt` in the project's `withdrawals` list. Clear or replace its recommendation and set the project's `updated` timestamp. Use `available: false` when a known release can no longer be downloaded, including an older version on a reused mutable URL. This allows clients to distinguish availability from a withdrawal.

Regenerate the checked-in legacy outputs and run CI locally.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python scripts/repository.py
.venv/bin/python scripts/repository.py --check
.venv/bin/python -m unittest discover -s tests -v
```

`catalogs/*.json` and `catalog.json` are generated. They expose one recommended artifact per project and omit projects with no active recommendation. Older clients use these unsigned exports. Withdrawal enforcement for previously saved versions requires a signed-repository client. The Firmware Hub remains a separate app source and `third-party/` remains a separate discovery feed.

## Prepare publisher updates

Run `.venv/bin/python scripts/import_publishers.py` or pass a configured project ID such as `shrub`. Starting from up-to-date legacy exports, the importer updates the project records and regenerates both exports together after successful validation. The reviewed records are the input for the next run.

- **SHRUB** reads the build metadata and installer, inspects the package and verifies that the build metadata stayed stable across the download. When a new release replaces the bytes at the same URL, the previous artifact stays in history with availability disabled.
- **SLOOP and ChoralRoot** share a GitHub Releases importer, configured in [publishers.json](../config/publishers.json). It checks the reviewed tag on the most recent release page, selects the exact configured asset name and considers releases published after the reviewed tag. ChoralRoot's tag filter excludes SMK-37 releases. New binaries are inspected locally even if GitHub supplies a digest. A stable recommendation stays on the stable channel. For a historical backfill or a recommendation outside the visible page, add the reviewed records manually.
- If an upstream release changes bytes under a known version, the package identity changes, or a configured publisher fails its checks, the run exits with an error and keeps the current catalog. Run one project by ID to prepare independent updates.

The **Prepare publisher catalog updates** workflow runs daily and accepts a project ID on manual runs. It saves a `publisher-updates.patch` artifact. Set the repository Actions variable `FM1_UPDATE_PRS=true` and allow Actions to create pull requests if you want the workflow to open a review PR. GitHub requires someone with write access to approve CI runs on PRs opened with the default workflow token. [GitHub token behavior](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs)

## Publish a signed repository

Set the `github-pages` environment to allow deployments from `main`. For the website, configure Pages to deploy with GitHub Actions. Create an Ed25519 key outside the checkout and record its SHA-256 fingerprint over the DER SubjectPublicKeyInfo.

```sh
umask 077
openssl genpkey -algorithm Ed25519 -out /secure/path/fm1-repository.pem
openssl pkey -in /secure/path/fm1-repository.pem -pubout -outform DER \
  | openssl dgst -sha256 -r
```

Add the PEM as the `FM1_REPO_PRIVATE_KEY` secret in the `github-pages` environment. Add the lowercase 64-character fingerprint as repository variable `FM1_REPO_FINGERPRINT` and set `FM1_REPO_SIGNING_ENABLED=true`. Keep a secure backup of the private key and protect changes to the main branch and publication workflow. Forks can configure their own [repository ID and homepage](../config/repository.json), Pages deployment and signing key. Update the fork's CODEOWNERS if using required owner reviews.

Run the **GitHub Pages** workflow from `main`. With signing enabled, the build produces one signed `entry.json`. One job publishes it to GitHub Releases with the generated legacy `catalog.json`, under a stable `catalog-<sequence>` tag pointing to the source commit. The release becomes Latest after its assets upload. A separate job publishes the same signed entry at `repo/v1/entry.json` on Pages, alongside the standalone index at `repo/v1/index.json`. The release job can succeed independently of Pages deployment.

Subscribers can use the [Latest release entry](https://github.com/ekim-pl/awesome-fm1/releases/latest/download/entry.json) or a URL for a specific catalog tag. Reserve GitHub's repository-wide Latest slot for catalog releases. Older clients can use the [legacy release asset](https://github.com/ekim-pl/awesome-fm1/releases/latest/download/catalog.json) or the existing catalog URLs. Signed clients keep their last verified snapshot if refresh fails.

The workflow signs reviewed data from `main` on production builds, including its weekly renewal schedule. To retry after a failure, rerun all jobs or start a new run from `main` so publication uses a fresh snapshot. Share the key fingerprint independently or bundle it in a trusted app release.

For a local smoke test, use a disposable Ed25519 key and run these commands. Set `FM1_REPO_FINGERPRINT` to its fingerprint.

```sh
.venv/bin/python scripts/build_site.py
.venv/bin/python scripts/repository.py --check --index _site/repo/v1/index.json
.venv/bin/python scripts/sign_repository.py sign _site/repo/v1/entry.json \
  --private-key /secure/path/test-repository.pem
.venv/bin/python scripts/sign_repository.py verify _site/repo/v1/entry.json
```

If a signing key changes, clients need a separately trusted new fingerprint. Built-in sources get it with an app release. Custom sources require explicit re-enrollment. A fresh deployment or a fork cannot authorize its own change of key.

## Signed entry wire format

The endpoint serves UTF-8 JSON with four fields. Duplicate JSON keys and unsupported formats are invalid.

| Field | Encoding |
| --- | --- |
| `format` | The string `fm1-repository-v1` |
| `publicKey` | Standard padded Base64 of the DER Ed25519 SubjectPublicKeyInfo |
| `payload` | Standard padded Base64 of the exact UTF-8 payload bytes |
| `signature` | Standard padded Base64 of the 64-byte Ed25519 signature over the decoded payload bytes |

The decoded payload contains `format` with the same value, `sequence`, `issuedAt`, `expiresAt` and `index`. The `index` object conforms to the repository schema and is signed directly. A single response carries the signature and index, so a cached response cannot combine files from different deployments. Verify the bytes as supplied. Pretty printing or canonicalizing before verification changes the signed input.

The signed entry is capped at 3 MiB. The decoded payload is capped at 2 MiB plus 1 KiB, and the standalone index build is capped at 2 MiB. Timestamps use `YYYY-MM-DDTHH:MM:SSZ`. Reject issue times more than five minutes ahead and expiry at or before the current time. Expiry must be after issue and no more than 14 days later.

`sequence` is a positive integer no greater than 2^53 − 1. Production signs serially from the head of `main` using the signing time in UTC epoch milliseconds. A client should persist the highest accepted sequence and the SHA-256 of the accepted payload bytes with the pinned key. Accept the same sequence again only for the same payload. Use a newer sequence to publish a reviewed revert. A verified signature authenticates repository metadata. A firmware file still has to match the artifact hash, identity and package checks, and compatibility remains an independent decision.
