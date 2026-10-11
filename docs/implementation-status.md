# Integration TAK implementation status

## Stage and model

I0 is code-complete and locally verified on ARM64.
I1 is incomplete. The 5.8.84 component probe proves an approved-set failure.
The current sibling candidate is TAK 5.8.92. Its strict admission hooks are installed, but the policy is not connected to authentication.
I2 includes the package builder, seven REST operations, Secret-backed grants and UserBinding reconciliation.
The operator now starts one TAKCL JVM and checks the remote user manager on each scan.
It can register a dedicated `integration-tak-admin` certificate through JNI and verify the stored fingerprint and role.
The local 5.8.92 operator image passed the native JNI runtime check.
The current Kind namespace has a ready `tak-ignite` Service and TAK Server StatefulSet.
The operator registered `integration-tak-admin` through JNI, and its certificate authenticated to the 8443 REST API.
Strict projection and Core authorization remain unavailable. UserBinding readiness stays false.
The stack Kustomization composes the sibling TAK Server integrated overlay with the
integration workloads. Separate entry points render the schema and grants Jobs.
`kubectl kustomize` rendered the stack and both namespaced Jobs using the sibling checkout.
The integration Zarf package now deploys the TAK schema, grants and server components.
The Zarf package has `local-dev` and `production` manifest flavors.
Both flavors built as ARM64 archives and passed lint and manifest inspection with explicit variables.
The local archive deployed to `kind-opendefence-dev` after the Core CRDs were installed.
Both deployments became Available. The API returned `503 authority-unavailable`, as expected.
An added Secret key survived an archive upgrade under the same Secret UID. The test key was removed.
The live operator created a UserBinding with `Synced=False` and `AuthorityUnavailable`.
A callsign edit changed its input revision without setting `Synced=True`.
Kubernetes removed the binding after the test User was deleted.
Service-account checks allowed the API to get and update the named grant Secret.
They denied Secret lists and access to `private-registry`.
The operator could list Users and update binding status. It could not get Secrets or create Users.
The package bundles the TAK image. Local Kind uses loaded images for connected development deployment.
Production needs reachable API and operator images and explicit deploy variables.
Production Core authority and strict TAK projection adapters remain unavailable. Defaults return `503` or `Synced=False`.
Core CRD shapes and UserBinding ownership are supplied. The operator uses
`lib-opendefence-core==0.2.1+261010` models from the user-supplied Nexus index.
Production authorization and credential adapters still need semantic contracts.
The release-92 operator image also passed a native JNI check, a Kind binding lifecycle check, and live administrator registration.
The integration is not release-ready.

| Gate | Required setting | Confirmation |
| --- | --- | --- |
| I0 | `gpt-6.1-sol` / `medium` | User: "Switched; resume I0" |
| I1 | `gpt-6-astra` / `xhigh` | User: "Switched; resume I1" |
| I2 | `gpt-6.1-sol` / `high` | User: "Switched; resume I2" |

The session cannot verify model runtime metadata or switch the active model.
The earlier I1 continuation explicitly confirmed Astra / XHigh.
The user reports that Daybreak Blue ran the earlier probing tests. That provenance is not independently verified.
I2 is active after the user's fresh "Switched; resume I2" confirmation.
That confirmation satisfies the transition required at `f8bed37`.
I1 remains a release blocker; do not enter I3 yet.
The completed I2 application slice and remaining adapters are described in [API and operator](api-operator.md).

## Checkpoint and sources

- Branch: `feat/i0-foundation`.
- Implementation HEAD before this checkpoint: `96df3cf`.
- I0 commits: `a339af8` (tooling), `b8113f6` (images and CI), `d351aad` (checkpoint).
- I1 commits: `4477bf6` (static findings), `67b94e2` (binary component probe), `27c7b97` (CoT overwrite).
- Server policy: `7f1e42c`, merged into the main server workstream by `fc07196`. The separate worktree `../tak-server-strict-fingerprint` remains a historical checkpoint.
- Current server plan: `fe005ee`, `../tak-server/docs/implementation-plan.md`. Required behavior changes use external launchers/runtime injection against unchanged vendor artifacts; fresh TAK source is no longer a prerequisite. The latest sibling commit checked was `fe13b7d`. It fixes local Zarf restart behavior. The preceding `738df0c` sets the LDAP interval to 60 seconds. Neither commit completes strict authentication.
- Server packaging: `61a8273` adds the integrated overlay and Zarf inputs. The integrated overlay still uses legacy authentication.
- I2 commits: `b835793` (PKCS#12 export), `0f9d9db` (client archives), `3739c08` (HTTP routes, grants and binding reconciliation).
- Integration deployment commits: `a98e6a2` (server overlay), `1b9359d` (Zarf manifest package), `2b030a4` (live deployment fix).
- Binary probe: `spikes/i1/`; tracked and complete for the current 5.8.84 artifacts.
- Supplied handoff and OpenAPI files remain untracked and unchanged.
- Prototype tooling: `b332e527c7dedf5e3f0a972b792c7d697dcace6b`.
- Reviewed shared CI actions: `1786399bf62c2b691f1e8fb9dcfc7a0be72a2846`.
- Package-format source: `pvarki/python-tak-rmapi` at `2c5526046a1fd62e821392484a1b833d42bb91fd`.
- OpenAPI input: `1.0.0-draft.5`; seven operations under `/integrations/tak/api/v1`.
- Server handoff: `../tak-server/tak-server-implementation-handoff.md`.
- Core handoff: `/Users/rambo/Downloads/rasenmaeher-core-architecture-handoff.md`, dated 2026-10-10.
- Core CRDs: user-supplied `../opendefence_core_crds.yaml`, `platform.opendefence.fi/v1alpha1`; five CRDs plus Core RBAC. The snapshot hash and remaining semantic gaps are in [Core contracts](core-contracts.md).
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

The user renamed the Python distribution/import package to `opendefence_integration_tak`.
The CLI is `opendefence-integration-tak`.
These names supersede the supplied handoff and OpenAPI draft's earlier names.
Historical image tags and saved evidence below retain the names used in those runs.
Rename verification passed: 114 local tests with two Java checks skipped; all 116 tests in the Java container, with 100% coverage.
The wheel/source build, wheel contents, new CLI/module help and version, and all repository checks passed.
Both renamed ARM64 runtime images passed help/version and `docker/check_runtime.py`, including the native operator JNI call.
The old import and CLI were absent after `uv sync --locked`. No compatibility aliases were added.
Hosted CI and AMD64 were not rerun for the rename.

Keep JNI dependencies in the operator extra. Keep PyJNIus pinned to `1.7.0`.
The images print help by default. Separate `api` and `operator` commands now start the workload processes.
Production authority and JNI projection adapters are not enabled.
Publishing and Snyk remain disabled until their repository variables enable them.
Use the shared Core models; do not copy prototype models or server deployments.

The package builder accepts explicit inputs and already-issued material.
It builds full setup for ATAK, ATAK Mini, iTAK, WinTAK, and TAK Tracker.
At this earlier checkpoint, it bound the certificate CN to the User UUID and validated key pairing.
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
The pure package checkpoint did not rebuild that image. The later API/operator checkpoint below verifies both targets.
At that checkpoint, GitHub/ARC workflows, AMD64 runtime, live TAK authentication, Kind deployment, and client devices were unchecked.

I1 inspected candidate 5.8.84 schemas and bytecode.
Its X509 path matches a stored fingerprint or account identifier.
The repaired component probe executed the actual WAR classes with four unique certificates.
Main, TAK-only, and unapproved same-UUID certificates all received `ROLE_READONLY` and `fixture` groups.
The result was identical with either approved fixture fingerprint stored.
A different UUID received only the anonymous fallback.
The contact-map update preserved the fixture certificate, account, role, and group list.
The extended probe passed once with the same pinned WAR and JDK.
The actual contact handler replaced `DESIRED` with the parsed CoT callsign `CLIENT-NEXT`.
Certificate bytes and account permissions remained unchanged. The fixture has no subscriptions.
See `evidence/i1-binary-probe.txt`.
Static lifecycle inspection shows that `ConnectionInfo` receives the peer certificate before TAK authentication completes.
It has no authentication-status field. `X509AuthCodec.onConnect` calls authentication without requiring CoT.
See `evidence/i1-auth-lifecycle.txt`. Remote activation observation remains unproven.
For this continuation, the saved `RESULT` lines match the raw probe output exactly.
All applicable repository checks passed. Ponytail review found no defects in the probe and evidence changes.
Python package tests were not rerun because this continuation changes no product Python code.
Live TLS, network CoT, rotation, restart, session resumption, and client compatibility remain unchecked.

The user adopted the strict fingerprint server change and declined waiting for a fixed server build.
The independent Java policy now passes 46 container assertions. Server repository checks passed.
It supports atomic accepted-set updates, immutable revision readback, exact CN/fingerprint checks, and explicit approval deadlines.
Missing state, expiry, restart, and explicit invalidation deny access. The caller must detect authority failure.
The policy is not connected to TAK authentication yet. See `evidence/i1-strict-policy.txt`.
The inspected public source is 5.7.14; its version does not match the tested binary.
The later server plan supersedes the missing-source prerequisite with external injection against pinned vendor artifacts.
Strict enforcement still requires verified hooks in both JVMs and a versioned management capability.

## API/operator checkpoint, `3739c08`

The fresh user confirmation resumed I2 at `gpt-6.1-sol` / `high`; model metadata remains user-provided.
Seven HTTP operations, a bounded Secret CAS store, typed Core readers, owned UserBindings and separate CLI workloads are implemented.
The integration manifests include only its workloads, scoped RBAC and an internal Service.
The production adapters and public ingress remain open. Defaults deny delivery and leave bindings unsynced.
See [API and operator](api-operator.md) for the internal seams and exact remaining inputs.

- Final ARM64 Java container: **265 passed, no skips; 96.57% coverage with branches enabled**. One upstream Starlette/AnyIO deprecation warning.
- Local macOS run before the final routing change: 263 passed, two keytool checks skipped; 96.56% coverage. Final Java tests include that change and both keytool checks.
- All-file prek checks and commit hooks passed, including strict Pyrefly, Bandit, secret scan and lockfile checks.
- API and operator builds passed. API boundary check and operator native JNI check passed with no network.
- API help/version and operator subcommand help passed. Wheel and source distribution builds passed.
- `kubectl kustomize k8s/integration` and `git diff --check` passed. No resources were applied.
- Inline Ponytail review covered ownership, secret delivery, freshness, CAS races, token rotation and restore. Readiness validation, receipt expiry and routing defects were fixed. No remaining defects were found within this implemented application slice; the production gaps remain blockers.
- Sanitized evidence: [I2 API/operator checks](evidence/i2-api-operator.txt). The cumulative audit remains I5 work.

The subsequent Core model migration replaces local v1alpha1 resource classes with
`lib-opendefence-core==0.2.1+261010` from the Nexus `pypilocal` index.
It also resolves the library's required Cloudcoil 0.8 from PyPI and keeps the
grant-store Secret model local. The lock pins the library wheel SHA-256.
The Java container passed 265 tests with no skips (96.42% coverage with branches enabled);
the focused local operator suite passed 19 tests. All-file prek checks, including
Pyrefly, Bandit and lock validation, passed. Both ARM64 runtime images built;
the API import boundary and native operator JNI checks passed without network.
The package enforces a callsign pattern absent from the supplied CRD snapshot;
see [Core contracts](core-contracts.md) before cluster deployment.

Image tags use `i2-http-operator`, all `linux/arm64`:

| Image | Manifest digest |
| --- | --- |
| `localhost/opendefence-integration-tak-package` | `sha256:4007f35e04f4c5ab69ed3b846f6cc7eea35805a858fb0ac871e0a517e14d9a0f` |
| `localhost/opendefence-integration-tak-api` | `sha256:f66f3e821d098080414d990338429bacf64f8b4a0f116de0e00ebad9eb1fcc08` |
| `localhost/opendefence-integration-tak-operator` | `sha256:61cbc39ed290cb39a2a706957d351436cd61f8dc9ddc7d898d714db026a4a121` |

The operator native check still uses the I0 TAK 5.8.69 JAR and Temurin `17.0.20.1+1`, with PyJNIus `1.7.0`.
It does not establish final 5.8.84 server compatibility or strict enforcement.
No cluster context was selected. Shared server work, Kubernetes resources, PVCs and registry state were preserved.
Both supplied untracked inputs remain unchanged. No tokens, credential material or kubeconfigs were saved as evidence.

## Runtime tuple and owned resources

The I0 native check used TAK `5.8-RELEASE-69`, Java `17.0.20.1+1`,
PyJNIus `1.7.0`, and Linux Python `3.14.8`.
This check does not prove remote server compatibility.
The former 5.8.84 candidate is component-verified but remains live integration-unverified.
Its checksums are in `docs/i1-findings.md`.
The sibling image built at `36bdeb8` supplied the 5.8.84 `UserManager.jar` for an operator smoke image.
That JAR has SHA-256 `4ad7adcb9a09156d7122bfb2d4ddf3fd6705fb612f4d521335a5e08b449d24f6`.
A native JNI `User` round-trip passed. The rebuilt operator became Available in Kind.
The server image ID is `bfe5accbb8085dff86d7598f29f7529fea50831f0c3b8f995d226f63dfc57fbb`.
The operator image ID is `8abe4dc1eed1aa911a8e2cc37fcc160f075675a8058929baa748af26f997af12`.
These checks do not prove strict admission or production projection.
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
Owned resources are these images, temporary build containers, and the separate strict-fingerprint server worktree.
Smoke containers used `--rm` and have exited.
Unrelated Podman state was preserved.
The test context at this earlier checkpoint was `kind-opendefence-dev`, namespace `integration-tak`.
The five supplied Core CRDs and the Zarf local package were installed there.
The package runs the API and operator images built from this checkout.
The operator used the 5.8.92 smoke image. No test User or UserBinding remained.
No PVCs or registry publications changed at that checkpoint.
Temporary I1 evidence remains in `/private/tmp/integration-tak-i1/`.
Temporary I2 test and build logs remain in `/private/tmp/integration-tak-*-i2.log`.
No fixture keys, certificates, or ZIPs were saved as evidence.

## TAK 5.8.92 candidate check

The sibling checkout at `6c8aa1c` selected `5.8-RELEASE-92`.
The operator build used `localhost/tak-server:release-92` at manifest
`sha256:12ecb27b054b05ce612bbd5b16d84e2544bad4c3e33d78b2edf57265e9ad78d2`.
The current local tag at `fe13b7d` has manifest
`sha256:3a052e1e03f3dc88cf10b3fc67df2fd86260f1acd7410c201a5d6b2719555318`.
The new image retains the same TAK 5.8.92 WAR and `UserManager.jar` hashes.
The image supplies `UserManager.jar` with SHA-256
`0fe547c2f4ce05d06a2e9724e0c2837eab0a0ba5be398390bb974b2385ce6f14`.
See the [sibling release record](../../tak-server/docs/release-92-candidate.md) for its server checks.

The operator built with `--build-arg TAKSERVER_IMAGE=localhost/tak-server:release-92`.
The local image is `localhost/opendefence-integration-tak-operator:tak-5.8.92-smoke`, image ID
`78afd77c3473a8df427d0d639da765148f78822ddf86815a913ded075e7414b6`.
`docker/check_runtime.py operator --jar-sha256 0fe547c2f4ce05d06a2e9724e0c2837eab0a0ba5be398390bb974b2385ce6f14`
passed inside that image. It checked the JAR hash, Python runtime boundary, Java 17, and one native JNI call.
The checker also passed without the override against the existing 5.8.69 operator image.

The release-92 operator became Available in `kind-opendefence-dev` with zero restarts.
The rollout used `kubectl set image`; the Zarf package was not rebuilt.
A test User produced a UserBinding with `Synced=False` and `AuthorityUnavailable`.
Kubernetes removed the binding after the User was deleted.
The test left no User or UserBinding.
The Dockerfile default still selects the published 5.8.69 server image.
The sibling release-92 runtime image is local and unpublished, so builds must supply it with `TAKSERVER_IMAGE`.
This check does not prove strict authentication or production projection.
The stack, schema, and grants Kustomizations render against sibling commit `fe13b7d`.
The stack has 21 resources and sets `LDAP_UPDATE_INTERVAL=60` and `TAK_AUTH_MODE=legacy`.
No server resource from this render was applied to a cluster.

## 2026-10-11 local server and administrator mTLS

The integration package deployed the TAK schema Job, grants Job, and singleton StatefulSet to `kind-opendefence-dev`.
The schema, grants, and bootstrap Jobs completed. The TAK Server and both integration Deployments became Ready.
The `tak-ignite` Service provides the operator's JNI management connection.
The local Zarf flavor issued `tak-integration-admin` through cert-manager and `public-issuer`.
The operator mounted the certificate, key, and CA bundle. The key file has mode `0440` and group `10001`.
The delivery API Pod did not mount the key.
The operator registered the certificate as `integration-tak-admin` through JNI.
`task --yes smoke` returned HTTP 200 from TAK's 8443 REST API with both the probe and integration identities.
The integration request verified the server name and CA and listed `integration-tak-admin`.
A request without a client certificate received no HTTP response.
The operator logged temporary management errors while TAK restarted. The errors stopped after TAK became Ready.
These checks do not prove strict admission, Core authorization, or safe administrator certificate rotation.
The local certificate is for the disposable test cluster. Production must supply an identity from a CA trusted by TAK.
Production renewal needs a notification from Core or the issuer before the operator changes TAK's administrator fingerprint.
The notification must bind the installed integration, issuer, new fingerprint, and Secret revision.

## 2026-10-11 certificate identity assumptions

The package exporter now checks the canonical User UUID URI SAN instead of treating the CN as an identity key.
Its test certificates use a display CN with a stable short tag. Callsign remains separate.
Delivery compares the approved public record with the exported leaf's SHA-256, serial, issuing CA key ID, and validity.
The provisional issuer ID is `issuer-sha256:` plus the SHA-256 of the issuing CA subject DER and public key DER.
The selected User annotation key, IntegrationManifest schema, and integration SAN profile remain open.
The current local administrator bootstrap does not use an IntegrationManifest.
The operator provisionally reads `platform.opendefence.fi/accepted-credentials` as a version 1 JSON set.
It includes that annotation in the input revision and passes current public records to the projector.
Missing or malformed metadata keeps UserBinding readiness false. The production projector remains unavailable.
The operator passes an empty set when metadata is invalid or the User is unapproved or revoked.
It keeps the last verified public credential set in `integration.opendefence.fi/applied-credentials` on the UserBinding.
The projector receives that prior set after a restart. A malformed record requires TAK readback before it is replaced.
No live TAK deprovisioning is claimed.

## Next action

Implement the production `Authority` and `Projector` adapters when versioned Core semantics and strict server capabilities are available.
The seven routes, typed Core readers, binding lifecycle, bounded Secret store and separate CLI workloads are implemented.
Their fixture-backed tests do not establish production authorization or server enforcement.
Keep the API JVM-free and the JNI bridge inside the operator process.
Add trusted ingress and server-base composition only against the supplied final contracts.

Use the [remaining work handoff](remaining-work-handoff.md) to resume implementation.
It records the user-reported Daybreak Blue probe execution and the remaining dependencies.

Use the supplied Core CRDs for resource shapes and integration-owned UserBindings.
Obtain the remaining contracts for credential inventory, approval, effective permissions,
binding readiness revisions, credential namespace access, HTTP authority, and authenticated activation reporting.
Then connect production credential, authority and strict JNI adapters to the implemented operator and seven REST operations.
Obtain the missing redesign file and final server base contract.
Keep credential-update delivery disabled until real client tests establish a supported method.
Keep production readiness blocked on current authority and full approved-set enforcement.
The strict approved-fingerprint design is adopted. Do not ask for that approval again.
Use the current server plan for external injection of the tested policy into authentication and management.
Version the extension configuration and management capability with the pinned, unchanged vendor artifacts.
Prove projection delivery to messaging and API before claiming readiness.
Live-test the adopted server mechanism before completing I1.
Do not mark I1 complete or weaken its approved-fingerprint requirement.
