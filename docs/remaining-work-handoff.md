# Integration TAK remaining work handoff

Date: 2026-10-10.
Recipient: the next implementation agent or engineer.
Repository: `opendefence/integration-tak`.
Branch: `feat/i0-foundation`.
Initial binary probe checkpoint: `67b94e2`. Later probe evidence is in [the current checkpoint](implementation-status.md).

The foundation and pure full-setup package builder are implemented.
The operator and REST delivery service are not implemented.
I1 is incomplete. I2 is partial. The integration is not release-ready.
Continue independent work when its inputs are available.
The user resumed binary probing on 2026-10-10.

## Start here

Read these files before changing code:

1. [Original implementation handoff](../integration-tak-implementation-handoff.md).
2. [Current checkpoint](implementation-status.md).
3. [Core contract decisions](core-contracts.md).
4. [I1 binary and static findings](i1-findings.md).
5. [Package builder](packages.md) and [certificate export](certificates.md).
6. [OpenAPI draft](../tak-package-api.openapi.json), version `1.0.0-draft.5`.

The original handoff and OpenAPI draft are local, untracked inputs.
Preserve them. A fresh clone needs separate copies.
The tracked `spikes/i1/` component probe preserves the original failure context and repaired test.
Do not include it in production images.

The revision-5 `tak-package-audit-and-redesign-plan.md` remains missing.
The two shared conversations are supporting sources, not a complete copy of that file:

- [TAK package and server discussion](https://chatgpt.com/share/6aca5977-77e0-83eb-8d24-6162f8327167).
- [Core architecture discussion](https://chatgpt.com/share/6ac980bb-d5dc-83eb-82ab-31ae4dded1ee).

The Core working handoff is at `/Users/rambo/Downloads/rasenmaeher-core-architecture-handoff.md`.
The user supplied [Core CRDs](../../opendefence_core_crds.yaml) for `platform.opendefence.fi/v1alpha1`.
See [Core contracts](core-contracts.md) for the snapshot hash, settled resource ownership, and remaining semantic gaps.
The server handoff is at `../tak-server/tak-server-implementation-handoff.md`.
Use the [consolidated server change handoff](tak-server-change-handoff.md) for the later single-Pod decision, adopted strict fingerprint extension, and all remaining server changes.
Their local paths may be unavailable on another host.
Obtain the source files before relying on their contracts.

## Completed work and evidence

| Work | Result |
| --- | --- |
| I0 foundation | Python 3.14, locked uv, prek hooks, strict typing, CI, wheel, and separate API/operator image targets. |
| Certificate export, `b835793` | Bounded PEM inputs, leaf CN and key checks, one exportable keypair, Java truststore entries, and separate private-key encryption policy. |
| Full setup, `0f9d9db` | ATAK, ATAK Mini, iTAK, WinTAK, and TAK Tracker ZIPs. XML escaping, stable internal filenames, and fresh outer filenames. |
| Checkpoint, `0eb51ad` | Sanitized test logs, image digests, scope limits, and remaining dependencies. |
| Binary component probe, `67b94e2` | Actual 5.8.84 WAR classes prove the unapproved same-UUID certificate receives the configured role and groups. |
| Strict fingerprint policy, server commit `7f1e42c` | Independent Java policy passes 46 container assertions. It is not wired into TAK authentication yet. |

The separate Java test image passed 116 tests with no skips and 100% package coverage.
RSA and EC tests exercised actual keytool import, read, entry types, and certificate export.
The JVM-free image and local environment passed 114 tests and skipped two keytool checks.
Those checks passed in the separate Java image.
Lint, typing, security hooks, lockfile checks, wheel build, and API import checks passed.
See `docs/evidence/i2-*.txt` for saved results.

These results establish package construction and Java container compatibility.
They do not establish real client import, rotation, or production delivery.
The binary probe establishes that the current file-auth path does not enforce the strict approved set.
The runtime images still print CLI help by default.
The exact tested image digests and runtime versions are in the current checkpoint.

## Binary probing and possible safety blocks

The user reports Daybreak access.
The latest user message says Daybreak Blue ran the earlier probing tests and confirms Astra / XHigh for this continuation.
That access is user-provided context. It was not independently verified in this session.
Do not assume it changes the active session's safety checks, tool permissions, or sandbox limits.
A future execution environment may still block a probe despite that access.

The user later instructed: "Try continuing the binary probing" and confirmed the I1 model gate.
One assistant response declined the defensive test based only on TAK's military context.
No tool or automatic approval system rejected the action.
The user clarified that certificate rejection is defensive authentication validation.
The probe then ran in an isolated container.

The initial probe failure was a Java compilation error.
It used invalid `Role.ROLE_USER` and `ConnectionType.STREAMING` enum names.
Container `javap` inspection identified the exact 5.8.84 values.
The repaired probe passed and saved sanitized evidence in `docs/evidence/i1-binary-probe.txt`.
The extended contact-handler probe also passed during the Astra / XHigh continuation.
It proves that parsed CoT can overwrite a contact-map rename while preserving the fixture certificate and permissions.
Static lifecycle inspection confirms that peer-certificate metadata precedes completed TAK authentication.
See `docs/evidence/i1-auth-lifecycle.txt`. A connection record alone is not sufficient successor activation evidence.
Do not describe the initial compilation failure as a safety rejection.

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

The user resumed this work and confirmed `gpt-6-astra` / `xhigh`.
Obtain the final server image and Kubernetes base contract before claiming integration compatibility.
The inspected 5.8.84 candidate is recorded in [I1 findings](i1-findings.md#candidate-runtime).
The I0 JNI image uses a different 5.8.69 JAR.
Do not combine results from these versions into one accepted runtime tuple.

Complete these checks against the agreed binary and deployment:

- Implement the adopted strict approved-fingerprint mechanism.
- Prove through live TLS that approved main and TAK-only certificates authenticate to the same UUID account with the desired permissions.
- Prove that a third CA-valid certificate with the same UUID, outside the approved set, is rejected before access is granted.
- Verify roles and groups after writes, uncertain writes, restart, and reconciliation.
- Extend the component callsign evidence to network CoT, reconnect, restart, live subscription, and peer display.
- Bind any contact UID to authenticated connection evidence. Do not infer it from callsign or UUID.
- Prove that a callsign edit preserves certificate material and permissions.
- Prove exact successor observation on an established authenticated connection. Reject stale, unrelated, revoked, and superseded evidence.
- Test raw CoT and HTTPS, new connections, existing connections, and resumed TLS sessions during revocation.

Static 5.8.84 inspection found a fingerprint-or-identifier authentication path.
The component probe confirmed that this path grants the configured role and groups to an unapproved same-UUID certificate.
The scalar fingerprint field does not establish a strict set of approved certificates.
Alternating registrations or encoding a list in that field is not an acceptable implementation.
The user adopted the strict approved-fingerprint server extension on 2026-10-10.
Do not request the adoption decision again. The user does not expect a fixed server build soon.
The initial policy implementation is on server branch `feat/strict-fingerprint`, commit `7f1e42c`.
Its separate local worktree is `../tak-server-strict-fingerprint`; the original server worktree has unrelated work.
Read `extensions/strict-fingerprint/README.md` there before continuing.
The policy is tested in isolation. It does not enforce authentication in the shipped server.
See `docs/evidence/i1-strict-policy.txt` for results and limits.
Matching TAK 5.8.84 source remains missing. Its location was requested.
Public source at `5187abd46d827d37cfc5708805eced197a837e49` is based on 5.7.14 and is not a substitute.
Connect the policy to the server schema, trusted management writer, and all supported certificate authentication paths.
Prove delivery to both messaging and API processes. Recheck cached HTTP identities and stop denied CoT before routing.
Update its schema, management interface, implementation, and pinned JAR together.
The optional disconnect guard decision remains open.
A post-authentication disconnect does not prove rejection before the first CoT message.

## Core contracts required for I2

The supplied CRDs establish cluster-scoped User, Group, Role, and Invite resources and namespaced UserBindings.
Integrations create their own bindings, refer to Users through `spec.userRef.name`, and write `Synced`; Core observes them.
Resource shapes and binding ownership no longer need to be invented or recovered from the prototype.
The schema does not supply a multi-generation credential inventory or durable activation interface.

Obtain versioned contracts or shared conformance implementations for these boundaries:

| Boundary | Required decision |
| --- | --- |
| Identity | Persistent immutable UUID source, public/CN encoding, normalization, restore behavior, and initial CSR flow. |
| Effective permissions | Group ancestry, role union, revisions, freshness, and changes caused by group moves or role edits. |
| Credential inventory | Approved generations, purpose, issuer/serial, SHA-256 fingerprint, validity, predecessor mapping, and superseded/compromised states. |
| Issuance and export | Permission to reuse a main key, TAK-only issuance for client-held main keys, renewal approval, and restart recovery. |
| Kubernetes ownership | Credential namespaces, permitted Secret readers, retention, applied revisions, and current readiness. UserBinding scope and integration writers are supplied. |
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
Preserve the two untracked input files described above.
Consult the configured PyCharm Python environment before any Python toolchain command.
Use repository hooks and relevant tests. Save only sanitized evidence.
Do not push, publish, or deploy without the session's authorization.

For the next I2 session, first obtain the missing Core contracts and select the smallest agreed implementation slice.
If those inputs remain unavailable, report the specific dependency and preserve this checkpoint.
Binary component work resumed at `67b94e2`; the current checkpoint includes the contact-handler extension.
Continue live binary work only against the agreed server mechanism and deployment tuple.
If safety checks prevent probing, use the evidence procedure above and retain all affected release blockers.
