# PKCS#12 export

`opendefence_integration_tak.certificates` exports existing material.
It does not generate keys, issue certificates, or approve access.
The authoritative adapter must supply the expected User UUID and an explicit verification time.
The exporter matches this UUID to one canonical `urn:uuid:<uuid>` URI SAN in the leaf.
It does not use the display CN as an identity key.
The exporter requires a matching RSA or EC private key and a currently valid leaf.
It checks the supplied leaf-first chain's issuer signatures and CA basic constraints.
These checks do not replace Core approval or full TLS certificate validation.

Use `ClientCredential` for the already-issued PEM chain, unencrypted PEM key, export password, and expected User UUID.
Use `client_keystore(credential, now=verification_time)` to export one keypair.
Use `public_credential(certificates)` to check the public record against the issued leaf and its issuing CA.
The record contains the leaf SHA-256, serial, issuer key ID, and validity times.
The provisional issuer ID is `issuer-sha256:` followed by the SHA-256 of the issuing CA subject DER and public key DER.
Core must publish the accepted record; an integration must not treat issuance alone as approval.
The provisional User annotation key is `platform.opendefence.fi/accepted-credentials`.
Use `accepted_credential_records(raw, now=verification_time)` to read its version 1 JSON value.
The parser rejects empty, duplicate, malformed, and unsupported records.
It removes expired and not-yet-valid records from the returned set.
The export has alias `client`.
It uses PBESv2 SHA-256/AES-256, a SHA-256 MAC, and 600,000 KDF rounds.
Passwords must contain 6 to 128 printable ASCII characters.
The caller must supply a suitable password; the exporter never derives it from callsign.

Use `ca_truststore(pem_bundle)` for the client CA trust bundle.
The caller must include the required CoT, HTTPS, and deployment trust anchors.
The exporter excludes certificates without a CA basic constraint and removes duplicate CA certificates.
It rejects a bundle with no CA certificates.
Each alias uses the certificate's full SHA-256 fingerprint.
It uses `serialize_java_truststore` to create Java `trustedCertEntry` values.
The public compatibility format uses PBESv1 SHA-1/3-key Triple-DES, a SHA-1 MAC, and 50,000 KDF rounds.
Its password is `public`.
This compatibility policy never protects a client private key.

Certificate PEM inputs are limited to 1 MiB and 32 certificates each.
Private-key PEM inputs are limited to 16 KiB.
Sensitive inputs do not appear in dataclass representations.

## Verification

Run `uv run --locked pytest` for Python checks.
The Java check is skipped in this command unless `--require-keytool` is supplied.
Run these commands for the mandatory Java 17 checks:

```sh
podman build --target package-test -t localhost/opendefence-integration-tak-package:test .
podman run --rm localhost/opendefence-integration-tak-package:test
```

The separate test image contains the pinned JDK.
The test checks RSA and EC exports, entry types, aliases, the leaf-first chain, exported certificate bytes, and actual keytool re-import.
A missing keytool fails the required check.
CI runs this check explicitly.
The API runtime contains no JDK or JVM.
Client device compatibility remains unverified.

The serializer follows the [cryptography PKCS#12 documentation](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/serialization/#pkcs12).
The public-store format is preserved from `pvarki/python-tak-rmapi` revision `2c5526046a1fd62e821392484a1b833d42bb91fd`.
