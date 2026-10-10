# Integration TAK implementation status

## Stage and model

I0 is code-complete and locally verified on ARM64.
I1 is incomplete. The 5.8.84 component probe is complete and proves an approved-set failure.
I2 has a completed pure package slice. The operator and seven REST operations are not implemented.
Production Core adapters remain blocked on versioned contracts.
The integration is not release-ready.

| Gate | Required setting | Confirmation |
| --- | --- | --- |
| I0 | `gpt-6.1-sol` / `medium` | User: "Switched; resume I0" |
| I1 | `gpt-6-astra` / `xhigh` | User: "Switched; resume I1" |
| I2 | `gpt-6.1-sol` / `high` | User: "Switched; resume I2" |

The session cannot verify model runtime metadata or switch the active model.
I1 is the current escalation stage. I2 remains partial. Do not enter I3 yet.

## Checkpoint and sources

- Branch: `feat/i0-foundation`.
- Implementation HEAD before this checkpoint: `67b94e2`.
- I0 commits: `a339af8` (tooling), `b8113f6` (images and CI), `d351aad` (checkpoint).
- I1 commits: `4477bf6` (static findings), `67b94e2` (binary component probe).
- I2 commits: `b835793` (PKCS#12 export), `0f9d9db` (client archives).
- Binary probe: `spikes/i1/`; tracked and complete for the current 5.8.84 artifacts.
- Supplied handoff and OpenAPI files remain untracked and unchanged.
- Prototype tooling: `b332e527c7dedf5e3f0a972b792c7d697dcace6b`.
- Reviewed shared CI actions: `1786399bf62c2b691f1e8fb9dcfc7a0be72a2846`.
- Package-format source: `pvarki/python-tak-rmapi` at `2c5526046a1fd62e821392484a1b833d42bb91fd`.
- OpenAPI input: `1.0.0-draft.5`; seven operations under `/integrations/tak/api/v1`.
- Server handoff: `../tak-server/tak-server-implementation-handoff.md`.
- Core handoff: `/Users/rambo/Downloads/rasenmaeher-core-architecture-handoff.md`, dated 2026-10-10.
- Additional sources: both user-supplied shared conversations. See [I1 findings](i1-findings.md).
- Missing file: `tak-package-audit-and-redesign-plan.md` revision 5. The conversation link does not supply the full file.
- Open decisions: [Core contracts](core-contracts.md).

Ponytail full and Caveman were restored for I0, I1, and I2.
Local skill SHA-256 values:

- Ponytail: `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2`.
- Caveman: `0bf09a0a9a017d004a81d4b693e5a2d830e1a28230a5885df773e1ed9c0571cc`.

The handoff pins source revisions `9b58c1ffb790c075ca32e70a89cf1d80588f4abf` and
`2e08b9177c07bb7249a8a2d1a6758e5db281d002`, respectively.
Installed source revisions remain unverified.
Ponytail review instructions came from plugin version `5.1.0`.
Reviews found no remaining defects in each completed slice.
The final cumulative audit remains an I5 task.
I1 also used investigate-first to separate static evidence from runtime proof.

## Decisions and verification

Keep JNI dependencies in the operator extra. Keep PyJNIus pinned to `1.7.0`.
The images print help by default. Neither workload is enabled yet.
Publishing and Snyk remain disabled until their repository variables enable them.
Do not copy prototype Core models or server deployments.

The package builder accepts explicit inputs and already-issued material.
It builds full setup for ATAK, ATAK Mini, iTAK, WinTAK, and TAK Tracker.
It binds the expected certificate CN to the User UUID and validates key pairing.
It uses bounded inputs, XML construction, and stable internal certificate names.
Private keys use PBESv2 AES-256 with a SHA-256 MAC and 600,000 KDF rounds.
Public CA truststores preserve the specified Java compatibility format.
Java tests verify RSA and EC entry types, aliases, chains, passwords, import, and certificate export.
See [package construction](packages.md) and [PKCS#12 export](certificates.md).

- `uv run --locked pytest`: 114 passed, 2 keytool checks skipped on macOS Python 3.14.7; 100% package coverage.
- `podman build --target api-test -t localhost/odintegration-tak-api:test-i2 .` and its test run: 114 passed, 2 keytool checks skipped; 100% coverage. See `evidence/i2-api-test.txt`.
- `podman build --target package-test -t localhost/odintegration-tak-package:test .` and its test run: 116 passed, no skips; 100% coverage. Java 17 keytool is required. See `evidence/i2-package-test.txt`.
- `podman build --target api -t localhost/odintegration-tak-api:i2 .`: passed.
- API help, version, and `docker/check_runtime.py api`: passed. The installed builder imports without JVM, JNI, TAK artifacts, or build tools. See `evidence/i2-api-runtime.txt`.
- `uv run --locked prek run --all-files`: passed, including Ruff, strict Pyrefly, Bandit, secret scan, and lockfile validation.
- `uv build --no-sources`: built the source distribution and wheel. Wheel inspection confirmed both new modules and the CLI entrypoint. Tests and probe files are excluded.
- Code commit hooks and `git diff --check`: passed.

I0 separately verified the operator image and a real JNI call.
See `evidence/i0-operator-runtime.txt` and `evidence/i0-api-runtime.txt`.
That image was not rebuilt or retested in I2.
GitHub/ARC workflows, AMD64 runtime, live TAK authentication, Kind deployment, and client devices remain unchecked.

I1 inspected candidate 5.8.84 schemas and bytecode.
Its X509 path matches a stored fingerprint or account identifier.
The repaired component probe executed the actual WAR classes with four unique certificates.
Main, TAK-only, and unapproved same-UUID certificates all received `ROLE_READONLY` and `fixture` groups.
The result was identical with either approved fixture fingerprint stored.
A different UUID received only the anonymous fallback.
The contact-map update preserved the fixture certificate, account, role, and group list.
See `evidence/i1-binary-probe.txt`.
Live TLS, CoT, rotation, restart, session resumption, and client compatibility remain unchecked.

## Runtime tuple and owned resources

The I0 native check used TAK `5.8-RELEASE-69`, Java `17.0.20.1+1`,
PyJNIus `1.7.0`, and Linux Python `3.14.8`.
This check does not prove remote server compatibility.
Candidate 5.8.84 is component-verified but remains live integration-unverified.
Its checksums are in `docs/i1-findings.md`.
The final server image and Kubernetes base contract remain pending.
I2 package images use Linux Python `3.14.8` and cryptography `50.0.2` on ARM64.
The Java test image uses Temurin `17.0.20.1+1`. The API images contain no Java.

- I0 JAR source: `ghcr.io/pvarki/tak-server:5.8.69-260913-slimignite-pr136@sha256:5d250adfdb835e9bfafcce294736041d4fbd32c1ffde7b803f17e28bf2f85a09`.
- I0 JAR SHA-256: `329c3831d0550bef309a7c77ff29c3b398279f973bc9789e0db5c26817ac39c7`.
- I0 API image: `localhost/odintegration-tak-api:i0`, digest `sha256:07f4cf351aa5ad57737b75233be0ccaf0cfee03623c98cb1ba189697963930a7`.
- I0 operator image: `localhost/odintegration-tak-operator:i0`, digest `sha256:85bf49cce45ec1b1ad5997b176fda29ac36363da5a7faadcf46e9e2a257fcb63`.
- I0 test image: `localhost/odintegration-tak-api:test`, digest `sha256:3a1b624c6784c941e91c4f3f80a7aeb9c156fe28987298010bb600b2c9a6a43d`.
- I2 API image: `localhost/odintegration-tak-api:i2`, digest `sha256:9809640b756f7bb0d330a76090c7602d15c7caa60f451a2417818a317400f5e4`.
- I2 API test image: `localhost/odintegration-tak-api:test-i2`, digest `sha256:4c74196073f3f4d7feb359b7f8fc257999bea269a816cf7bf55e56d9af132c17`.
- I2 Java test image: `localhost/odintegration-tak-package:test`, digest `sha256:49d157dae47eb5382db37257c6d93ba37301a12c55ef08de3936ba9af8cfeae8`.
- I1 experimental server image: `localhost/tak-server:t1-5.8.84-pr136`, digest `sha256:a3c022ec0806378523ed86dc9949599fb3b5331cf4deb78293dd4ee9efd9fffe`.
- I1 JDK image: `eclipse-temurin:17-jdk-noble@sha256:fb79620c3f6ee8f1c7530a8dc4fd49e3b410bcef037694ad4858a1553bac4170`.

Base-image indexes are pinned in `Dockerfile` and include AMD64 and ARM64.
Only ARM64 was run locally.
Owned resources are these images and temporary build containers.
Smoke containers used `--rm` and have exited.
Unrelated Podman state was preserved.
No Kind context or namespace was selected.
No Kubernetes resources, PVCs, or registry publications were changed.
Temporary I1 evidence remains in `/private/tmp/integration-tak-i1/`.
Temporary I2 test and build logs remain in `/private/tmp/integration-tak-*-i2.log`.
No fixture keys, certificates, or ZIPs were saved as evidence.

## Next action

Use the [remaining work handoff](remaining-work-handoff.md) to resume implementation.
It includes the user-reported Daybreak access and the procedure for possible binary-probe safety blocks.

Obtain the versioned Core contracts for credential inventory, approval, effective permissions,
UserBinding ownership, namespace access, HTTP authority, and authenticated activation reporting.
Then implement the corresponding I2 adapters, operator, and seven REST operations.
Obtain the missing redesign file and final server base contract.
Keep credential-update delivery disabled until real client tests establish a supported method.
Keep production readiness blocked on current authority and full approved-set enforcement.
The proposed strict approved-fingerprint server change needs an adoption decision.
Implement and live-test the adopted server mechanism before completing I1.
Do not mark I1 complete or weaken its approved-fingerprint requirement.
