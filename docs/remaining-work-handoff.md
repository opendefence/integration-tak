# Integration TAK remaining work handoff

Date: 2026-10-10.
Recipient: the next implementation agent or engineer.
Repository: `opendefence/integration-tak`.
Branch: `feat/i0-foundation`.
Baseline checkpoint: `0eb51aded9a8c338425ba7d21648cc2012298f70`.

The foundation and pure full-setup package builder are implemented.
The operator and REST delivery service are not implemented.
I1 is incomplete. I2 is partial. The integration is not release-ready.
Continue independent work when its inputs are available.
Keep binary probing deferred until the user explicitly resumes it.

## Start here

Read these files before changing code:

1. [Original implementation handoff](../integration-tak-implementation-handoff.md).
2. [Current checkpoint](implementation-status.md).
3. [Core contract decisions](core-contracts.md).
4. [I1 static findings and probe failure](i1-findings.md).
5. [Package builder](packages.md) and [certificate export](certificates.md).
6. [OpenAPI draft](../tak-package-api.openapi.json), version `1.0.0-draft.5`.

The original handoff and OpenAPI draft are local, untracked inputs.
Preserve them. A fresh clone needs separate copies.
The unfinished `spikes/i1/` files are also untracked.
Preserve their failure record and do not include them in production images.

The revision-5 `tak-package-audit-and-redesign-plan.md` remains missing.
The two shared conversations are supporting sources, not a complete copy of that file:

- [TAK package and server discussion](https://chatgpt.com/share/6aca5977-77e0-83eb-8d24-6162f8327167).
- [Core architecture discussion](https://chatgpt.com/share/6ac980bb-d5dc-83eb-82ab-31ae4dded1ee).

The Core working handoff is at `/Users/rambo/Downloads/rasenmaeher-core-architecture-handoff.md`.
The server handoff is at `../tak-server/tak-server-implementation-handoff.md`.
Their local paths may be unavailable on another host.
Obtain the source files before relying on their contracts.

## Completed work and evidence

| Work | Result |
| --- | --- |
| I0 foundation | Python 3.14, locked uv, prek hooks, strict typing, CI, wheel, and separate API/operator image targets. |
| Certificate export, `b835793` | Bounded PEM inputs, leaf CN and key checks, one exportable keypair, Java truststore entries, and separate private-key encryption policy. |
| Full setup, `0f9d9db` | ATAK, ATAK Mini, iTAK, WinTAK, and TAK Tracker ZIPs. XML escaping, stable internal filenames, and fresh outer filenames. |
| Checkpoint, `0eb51ad` | Sanitized test logs, image digests, scope limits, and remaining dependencies. |

The separate Java test image passed 116 tests with no skips and 100% package coverage.
RSA and EC tests exercised actual keytool import, read, entry types, and certificate export.
The JVM-free image and local environment passed 114 tests and skipped two keytool checks.
Those checks passed in the separate Java image.
Lint, typing, security hooks, lockfile checks, wheel build, and API import checks passed.
See `docs/evidence/i2-*.txt` for saved results.

These results establish package construction and Java container compatibility.
They do not establish real client import, approved-set authentication, rotation, or production delivery.
The runtime images still print CLI help by default.
The exact tested image digests and runtime versions are in the current checkpoint.

## Binary probing and possible safety blocks

The user reports Daybreak access.
That access is user-provided context. It was not independently verified in this session.
Do not assume it changes the active session's safety checks, tool permissions, or sandbox limits.
Binary probing may remain unavailable despite that access.

The last explicit binary instruction was: "Skip the binary probing for now."
This handoff request does not resume those probes.
No safety or automatic approval rejection was recorded in this session.
The attempted I1 component probe stopped at Java compilation.
It used invalid `Role.ROLE_USER` and `ConnectionType.STREAMING` enum names.
Four generated certificate chains verified, but no authentication or contact assertion ran.
Do not describe that compilation failure as a safety rejection.

If a future safety or approval check blocks a probe:

1. Stop the rejected action. Do not bypass the check or repeat it through another tool to evade the restriction.
2. Record the action, check type, stated reason, runtime tuple, and sanitized error.
3. Separate a policy rejection from missing permissions, missing tools, and a compile or runtime failure.
4. Report the blocked action and its reason to the user. Do not claim Daybreak guarantees execution.
5. Continue permitted work that does not depend on the rejected action.
6. Leave the affected acceptance checks open. Record who must supply the missing evidence.

If agent execution remains unavailable, a maintainer can provide permitted evidence from an authorized test environment.
Request logs, exact image/JAR checksums, test inputs, assertions, and outcomes.
Do not request private keys, live tokens, or kubeconfigs.
Review supplied evidence against the acceptance checks below.
Static inspection, mocks, fixture issuance, and Java keytool results do not replace live TAK authentication evidence.
If suitable evidence cannot be obtained, retain the release blocker.

## I1 binary acceptance work

Resume only after explicit user instruction and the I1 model gate.
Use `gpt-6-astra` / `xhigh`.
Obtain the final server image and Kubernetes base contract before claiming integration compatibility.
The inspected 5.8.84 candidate is recorded in [I1 findings](i1-findings.md#candidate-runtime).
The I0 JNI image uses a different 5.8.69 JAR.
Do not combine results from these versions into one accepted runtime tuple.

Complete these checks against the agreed binary and deployment:

- Repair the component fixture against the actual enum signatures. Retain the original failed reproduction.
- Prove that approved main and TAK-only certificates authenticate to the same UUID account with the desired permissions.
- Prove that a third CA-valid certificate with the same UUID, outside the approved set, is rejected before access is granted.
- Verify roles and groups after writes, uncertain writes, restart, and reconciliation.
- Test callsign updates across contact state, incoming CoT, reconnect, restart, live subscription, and peer display.
- Bind any contact UID to authenticated connection evidence. Do not infer it from callsign or UUID.
- Prove that a callsign edit preserves certificate material and permissions.
- Prove exact successor observation on an established authenticated connection. Reject stale, unrelated, revoked, and superseded evidence.
- Test raw CoT and HTTPS, new connections, existing connections, and resumed TLS sessions during revocation.

Static 5.8.84 inspection found a fingerprint-or-identifier authentication path.
The scalar fingerprint field does not establish a strict set of approved certificates.
Alternating registrations or encoding a list in that field is not an acceptable implementation.
The proposed strict approved-fingerprint server extension is not adopted.
Obtain an explicit design/adoption decision and implement any adopted change in the server project.
Update its schema, management interface, implementation, and pinned JAR together.
The optional disconnect guard decision remains open.
A post-authentication disconnect does not prove rejection before the first CoT message.

## Core contracts required for I2

Obtain versioned contracts or shared conformance implementations for these boundaries:

| Boundary | Required decision |
| --- | --- |
| Identity | Persistent immutable UUID source, public/CN encoding, normalization, restore behavior, and initial CSR flow. |
| Effective permissions | Group ancestry, role union, revisions, freshness, and changes caused by group moves or role edits. |
| Credential inventory | Approved generations, purpose, issuer/serial, SHA-256 fingerprint, validity, predecessor mapping, and superseded/compromised states. |
| Issuance and export | Permission to reuse a main key, TAK-only issuance for client-held main keys, renewal approval, and restart recovery. |
| Kubernetes ownership | Credential namespaces, permitted Secret readers, retention, UserBinding writers, observed revisions, and readiness. |
| HTTP authority | Verified mTLS identity, trusted headers, spoofed-header removal, authorization deadlines, and direct-service access controls. |
| Activation reporting | Trusted writer, completed authentication evidence, exact purpose/generation, durable event identity, idempotency, and recovery scan. |

Do not copy prototype CRDs into production or treat fixture inputs as an agreed Core API.
Keep the API free of issuance and JNI.
Core owns credential approval, inventory, and predecessor revocation.

## Remaining I2 implementation

After the corresponding contracts and server decisions are available:

1. Implement restart-safe credential selection and approved issuance through Core's lifecycle.
2. Implement the TAK projection operator. Use one JVM per process, serialized mutations, and readback after uncertain writes.
3. Reconcile the full approved credential set, roles, groups, and callsign presentation without recreating the UUID account.
4. Implement authenticated successor observation with an explicit process owner and persistent Core reporting.
5. Implement all seven operations in the supplied OpenAPI draft under `/integrations/tak/api/v1`.
6. Implement protected self-service routes and certificate-free token redemption with compatible TLS routing.
7. Add Secret-backed reusable grants, exact generation/profile/variant binding, current authorization checks, expiry, and deletion.
8. Add meaningful tests for denial, stale state, retryable failures, concurrency, and recovery.

GET requests must not create accounts, keys, or certificates.
An admin role alone must not permit extraction of another user's key.
Grants use a random public ID and a separate 256-bit token. Store only the token hash.
Grants normally expire after five minutes, or sooner when authority or credentials expire.
An old grant must not select a new credential generation.
Use `201` and `Location` for ready grant creation, `409` for unavailable inputs, and retryable `503` for infrastructure failure.
Public invalid, expired, or revoked grants return a uniform `404`.
Sensitive responses use `no-store`. Build links from a configured public origin.
Do not log tokens or restore live grants from backups.

Main and TAK-only activation flows are independent.
Qualifying authenticated successor use triggers Core's revocation of its mapped predecessor automatically.
A download, manual acknowledgement, or required CoT/HTTPS transaction is not activation.
Planned overlap has no default forced-cutover timer.
Never delete the shared UUID account to revoke one certificate.

## Later validation and delivery

I3 requires `gpt-6-astra` / `high` for live authorization, grant races, multi-certificate acceptance, rotation, and persistence review.
Escalate unresolved binary/design behavior through I1 at `xhigh`.
I4 requires `gpt-6.1-sol` / `high` for concrete fixes, UI adapters/fixtures, client tests, and operational docs.
I5 requires `gpt-6-astra` / `high` for a fresh cumulative Ponytail review/audit and acceptance review.
I6 requires `gpt-6.1-sol` / `medium` for final handover. Add no features in I6.
Follow the original handoff's exact model gate protocol before each transition.

Complete these external and operational checks:

- Obtain the versioned server base and add only integration overlays here.
- Test in a dedicated Kind context or assigned namespace. Preserve unrelated workloads and PVCs.
- Test restart/recovery, pending revocation, current authorization, and grant invalidation after restore.
- Verify AMD64 and ARM64 images and the configured GitHub/ARC workflows before enabling publication.
- Verify real client/version/import combinations for each advertised profile.
- Keep credential-update support disabled until same-name replacement updates the existing connection on tested clients.
- Validate preferences-only callsign refresh. Preserve local client overrides during credential refresh.
- Keep iTAK callsign manual until a supported preference is proven. Keep IPv6 disabled until its connection format is validated.
- Do not emit `disablePreferenceItem_locationCallsign=true` without the deferred client validation.
- Build the UI API client and fixture states when backend contracts permit. Keep Core session/navigation/module-federation dependencies visible.

## Resume procedure

Restore Ponytail full and Caveman from their actual skill files.
Use Simplified Technical English for persisted documentation.
Run Ponytail review before each coherent local commit.
Keep the final cumulative audit at I5.

Inspect Git and test-environment state before mutation.
Preserve the three untracked input/probe locations described above.
Consult the configured PyCharm Python environment before any Python toolchain command.
Use repository hooks and relevant tests. Save only sanitized evidence.
Do not push, publish, or deploy without the session's authorization.

For the next I2 session, first obtain the missing Core contracts and select the smallest agreed implementation slice.
If those inputs remain unavailable, report the specific dependency and preserve this checkpoint.
For binary work, first obtain explicit resumption and complete the I1 gate.
If safety checks prevent probing, use the evidence procedure above and retain all affected release blockers.
