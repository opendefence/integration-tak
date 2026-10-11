# Client package construction

`opendefence_integration_tak.packages.build_package` builds an in-memory full-setup ZIP.
It requires explicit connection settings, one existing exportable credential, the trust PEM bundle, and an aware verification time.
It does not read Kubernetes, start Java, write files, or provision resources.
Core authorization and verified TAK acceptance remain the caller's responsibility.
No HTTP delivery service is enabled by this slice.

Use `PackageSettings` for the deployment ID, User UUID, host, callsign, and port.
Deployment IDs must be lowercase DNS labels.
Hosts must be DNS names or IPv4 addresses.
The default TLS CoT port is 8089.
IPv6 connection syntax is disabled until client validation establishes the format.
Callsigns may contain 1 to 128 valid XML characters without controls.
The XML library escapes callsigns and passwords.
Callsigns never select archive paths or certificate material.

The credential's expected User UUID must equal `PackageSettings.user_id`.
The exporter checks the canonical `urn:uuid:<uuid>` URI SAN in the leaf.
The CN is display text and does not authorize the package.
The renderer does not choose Core's UUID storage source.
The adapter must bind all inputs to the authorized User and credential generation.

## Profile formats

These profiles use essential connection settings from the pinned legacy source.
No profile has device validation in this repository.
ATAK and ATAK Mini have the same essential setup contents.
Optional maps, toolbars, branding, and unrelated preferences are omitted.

| Profile | Certificate preference fields | Callsign field |
| --- | --- | --- |
| `atak` | Indexed connection fields and global defaults | `com.atakmap.app_preferences.locationCallsign` |
| `atak-mini` | Indexed connection fields and global defaults | `com.atakmap.app_preferences.locationCallsign` |
| `itak` | Global defaults only | No proven preference; change callsign on the client |
| `wintak` | Global defaults only | `com.atakmap.app_preferences.locationCallsign` |
| `tak-tracker` | Indexed connection fields | `gov.tak.taktracker_preferences.callsign` |

The iTAK manifest preserves the legacy omission of `onReceiveImport`.
Other profiles set `onReceiveImport=true`.
All profiles set `onReceiveDelete=false`.
The renderer never emits `disablePreferenceItem_locationCallsign=true`.
It does not set team or role preferences.

## Archive layout

Each ZIP contains these four files:

- `MANIFEST/manifest.xml`.
- `{deployment}_{uuid_hex}_{profile}-ca.p12`.
- `{deployment}_{uuid_hex}_{profile}-client.p12`.
- `server.pref`.

The manifest lists both PKCS#12 files before `server.pref`.
Preferences refer to the client import directory as `cert/{filename}`.
The archive itself preserves the legacy root-level PKCS#12 layout.
Internal filenames depend only on deployment, UUID, and profile.
Callsign, serial, fingerprint, and generation changes preserve those names.
Every build has a fresh manifest UID and outer ZIP filename.
The returned `RenderedPackage` hides ZIP bytes from its representation.

The ZIP contains a private key and the import password in preferences.
Treat the entire ZIP as private material.
PKCS#12 encryption does not provide a second authorization boundary for this ZIP.
The caller must use authenticated or valid grant delivery and `no-store` responses.

Use the [certificate exporter](certificates.md) to inspect material limits and encryption formats.
Caller-supplied archive paths and template directories are not supported.
The fixed layout and bounded inputs bound memory use.

## Verification and remaining gates

Python tests inspect every profile's manifest, preference references, XML escaping, and PKCS#12 content.
Tests also cover unsafe paths, invalid connection fields, different-user credentials, stable rotation names, and deployment/profile isolation.
The separate Java test image requires actual keytool import, read, and certificate export for RSA and EC credentials.
Use the commands in [PKCS#12 export](certificates.md#verification).

Stable filenames do not prove that a real client replaces an existing connection credential.
Credential-update packages are not implemented or advertised as supported.
Full setup is separate from a future validated update method.
A full setup may apply its callsign preference; it is not an automatic rotation update that preserves an existing local override.
Preferences-only updates and durable client refresh remain unverified.
No immediate live subscription or peer rename is established.

The format source is `pvarki/python-tak-rmapi` revision `2c5526046a1fd62e821392484a1b833d42bb91fd`.
Core adapters, approved-fingerprint enforcement, and real client import tests remain release gates.
