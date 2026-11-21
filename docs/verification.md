# SHRUB verification evidence

Observed on 2026-11-16; this is a point-in-time observation, not a promise that a mutable URL will keep serving these bytes.

- Publisher page: <https://shrub.audio/>.
- Download explicitly linked by the publisher installer: <https://shrub.audio/editor/firmware/SHRUB.fwsc>.
- Download checked at 2026-11-16T08:20:18Z.
- Size: 615816 bytes.
- SHA-256: `0097468bde8c0e863aca8648745d7213893d188319dad7e1e918bbfd71133e1e`.
- Embedded identity: `FM-1_901`. DUELL also used this identity in the observed Hub catalog; it is not a unique project key.
- <https://shrub.audio/editor/build.json> reported firmware `1.07`, date `2026-11-15`, commit `d9d1511`, with `dirty: false`. The metadata and binary are separate resources, not an atomic signed release.
- The site's home page labels SHRUB beta and identifies its copyright holder as Xfer Inc.
- Android parser test `FirmwarePackageTest.validatesRealOfficialPackagesWhenProvided` passed at 2026-11-14T19:48:14Z for the earlier 1.01 package (one test, zero failures, zero skips). The 1.07 package has not been run through that parser.

The earlier parser test checked package structure, processor, CRCs, identity and the presence of firmware/update-loader payloads. It calculated the expected hash from the downloaded bytes; it is not an independent publisher signature verification. The catalog pinned the observed 1.07 package hash at that time. The publisher's installer linked to a mutable package URL.

No hardware flashing, old/new flash compatibility or round-trip update test was performed. `chip` therefore remains `unknown`. No binary is stored in this repository.

## SHRUB 1.14 beta

- On 2026-11-18 at 17:06:54 UTC, the publisher importer observed firmware `1.14` at commit `8ea7b6d`. The clean build metadata matched before and after the package download. [Build metadata](https://shrub.audio/editor/build.json) · [Publisher installer](https://shrub.audio/editor/install)
- The package measured 689940 bytes and had SHA-256 `b8e874a92d3c05456303f68510c6ef182e996fad89f8750b5ff4fee02d7a7e3e`. The importer confirmed the `FM-1_901` identity and checked the file structure, processor marker, file ranges and CRCs.
- Hardware compatibility remains unknown. The publisher serves 1.14 from the same URL as 1.07, so the 1.07 artifact is marked unavailable.
