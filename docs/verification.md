# Initial SHRUB evidence

Observed on 2026-11-14; this is a point-in-time observation, not a promise that a mutable URL will keep serving these bytes.

- Publisher page: <https://shrub.audio/>.
- Download explicitly linked by the publisher installer: <https://shrub.audio/editor/firmware/SHRUB.fwsc>.
- Download checked again at 2026-11-14T20:05:43Z; identical to the previously tested bytes.
- Size: 615868 bytes.
- SHA-256: `73b4a369e73a66e45c3c14468f336f0c20f801c0da8dea52005996d7751b8537`.
- Embedded identity: `FM-1_901`. DUELL also used this identity in the observed Hub catalog; it is not a unique project key.
- <https://shrub.audio/editor/build.json> reported firmware `1.01`, editor date `2026-11-14`, commit `7474c93`. The metadata and binary are separate resources, not an atomic signed release.
- The site's home page labels SHRUB beta and identifies its copyright holder as Xfer Inc.
- Android parser test `FirmwarePackageTest.validatesRealOfficialPackagesWhenProvided` passed at 2026-11-14T19:48:14Z with this package supplied through `FM1_TEST_PACKAGES` (one test, zero failures, zero skips).

That parser test checked package structure, processor, CRCs, identity and the presence of firmware/update-loader payloads. It calculated the expected hash from the downloaded bytes; it is not an independent publisher signature verification. The catalog now pins that observed hash.

No hardware flashing, old/new flash compatibility or round-trip update test was performed. `chip` therefore remains `unknown`. No binary is stored in this repository.
