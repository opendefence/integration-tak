# Integration TAK remaining work handoff

Date: 2026-10-11.
Recipient: the next implementation agent or engineer.
Repository: `opendefence/integration-tak`.
Branch: `feat/i0-foundation`.
Initial binary probe checkpoint: `67b94e2`. Later probe evidence is in [the current checkpoint](implementation-status.md).

The foundation and pure full-setup package builder are implemented.
The seven REST operations, Secret-backed grants and UserBinding reconciliation are implemented.
Production Core authorization and strict TAK JNI adapters remain unavailable.
Core CRD resource readers now use `lib-opendefence-core==0.2.2+261011` from Nexus;
the installed CRD and existing User callsigns must satisfy its narrower callsign pattern.
See [API and operator](api-operator.md) for behavior and adapter contracts.
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
6. [Tracked OpenAPI draft](package-api.openapi.json), version `1.0.0-draft.5`.

The original handoff and OpenAPI draft remain local, untracked inputs.
Preserve them. The tracked OpenAPI copy supports tests in fresh clones.
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
Use the [TAK image change handoff](tak-server-change-handoff.md) only for changes that require a different TAK image.
Their local paths may be unavailable on another host.
Obtain the source files before relying on their contracts.

## Integrated strict authentication ownership

The user assigned integrated strict authentication to the `tak-operator` on 2026-10-11.
This repository owns that work unless it requires changes to the TAK image.
This section is the authoritative work list. It supersedes the broader server assignments in earlier handoffs.
Core still owns User authority, credential approval, and predecessor revocation.
Standalone TAK keeps legacy certificate authentication.

The native projector already writes one TAK record per accepted certificate.
It verifies native records and requests CoT session removal.
These operations do not prove strict admission. `JniProjector` still returns no strict receipt.
Keep `Synced=False` until fresh authority and verified enforcement agree.

- [ ] Resolve the [Core contracts](core-contracts.md). Define immutable UUID, URI SAN, display CN, credential purpose and generation, issuer/serial, fingerprint, deadlines, permission revisions, and restore behavior.
- [ ] Reconcile each User's complete accepted set. Apply the User's roles and groups to every certificate record. Serialize JNI mutations. Verify uncertain writes before retry. Remove one certificate without removing the other records or permissions.
- [ ] Own the trusted strict-policy writer and readback adapter. Use the existing 8443 REST service and the integration's trusted administrator mTLS identity. Do not add another listener or bootstrap credential. Request an image interface only if the existing interfaces cannot perform the required operation.
- [ ] Bind immutable readback to the requested complete set, deadline, and conditional revision in both messaging and API JVMs. Handle conflicts, partial application, limit errors, and uncertain writes. A successful JNI write alone is insufficient.
- [ ] Own the 60-second authority lease. Renew only after confirming the complete Core projection is current. Invalidate on authority loss. Test expiry, invalidation, restart, and recovery in both JVMs. Never renew an expired nonempty projection to restore stale approvals.
- [ ] Consume the installed `Integration` identity inventory when Core defines its missing certificate fields. Zarf installation is authorization. Match integration identity and issuer plus serial, with the exact leaf when available. Apply the required 8443 and 8089 access. Remove access on removal or credential change. Do not create a service User or a second approval step.
- [ ] Verify the versioned image capability and active enforcement mode. Match the unchanged vendor artifacts and extension version. Resolve the current policy's exact-CN account model against Core's UUID URI SAN and native per-certificate records. Check its limits of 1,024 accounts, 32 fingerprints per account, and 256 characters per identifier. Do not encode sets in TAK's scalar fingerprint field.
- [ ] Prove denial before the first CoT is routed and before protected HTTP access. Cover caches, tokens, enabled alternate transports, existing connections, and resumed TLS sessions. Measure the revocation bound. CoT removal after authentication cannot establish admission safety.
- [ ] Own completed-authentication observation and recovery after reconnect or restart. Bind evidence to the exact connection, UUID, leaf fingerprint, approval revision, and time. Reject stale, unrelated, revoked, and superseded evidence. Request an image signal only if existing APIs cannot provide this proof.
- [ ] Report activation durably to Core with idempotent events and recovery scans. Keep main and TAK-only activation independent. Downloads and manual acknowledgement are not activation. Do not require a CoT message or HTTP application transaction. Planned overlap has no default forced-cutover timer.
- [ ] Run the coupled live acceptance on one final image, extension, JNI JAR, and deployment tuple. Include approved main and TAK-only leaves, a denied third CA-valid same-UUID leaf, single-leaf revocation, authority loss, restart, and sessions. Keep I1 and production readiness open until these checks pass.

The `tak-server` repository owns its shipped Java policy, admission hooks, and binary compatibility checks.
Keep that source there because it is part of the image.
Use the [image handoff](tak-server-change-handoff.md) for a reproduced gap that needs image code.
Continue integration work when existing interfaces suffice.

## Completed work and evidence

| Work | Result |
| --- | --- |
| I0 foundation | Python 3.14, locked uv, prek hooks, strict typing, CI, wheel, and separate API/operator image targets. |
| Certificate export, `b835793` | Bounded PEM inputs, leaf CN and key checks, one exportable keypair, Java truststore entries, and separate private-key encryption policy. |
| Full setup, `0f9d9db` | ATAK, ATAK Mini, iTAK, WinTAK, and TAK Tracker ZIPs. XML escaping, stable internal filenames, and fresh outer filenames. |
| Checkpoint, `0eb51ad` | Sanitized test logs, image digests, scope limits, and remaining dependencies. |
| Binary component probe, `67b94e2` | Actual 5.8.84 WAR classes prove the unapproved same-UUID certificate receives the configured role and groups. |
| Strict fingerprint policy, server commit `7f1e42c` | Initial independent policy passed 46 container assertions. The current 5.8.92 image has admission hooks; trusted updates and both-JVM readback remain open. |
| API/operator slice, `3739c08` | Seven HTTP routes, bounded Secret-backed grants, schema-based Core readers, UserBinding ownership, separate workload commands and scoped integration manifests. Production authority and strict JNI adapters remain unavailable. |

The latest API/operator image passed 265 tests with no skips and 96.57% coverage with branches enabled.
Both runtime targets passed their boundary checks; the operator JNI check retains the I0 5.8.69 tuple.
Hooks, distributions and local Kustomize rendering passed. No cluster resources were applied.
See [API/operator evidence](evidence/i2-api-operator.txt) for the current proof and limits.
The earlier package-only results below remain historical evidence.

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
- Prove through live TLS that each accepted certificate identity receives the User's projected permissions.
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
The initial policy commit `7f1e42c` was merged into the server workstream.
Read the current [image extension contract](../../tak-server/extensions/strict-fingerprint/README.md).
The pinned 5.8.92 image has admission hooks and local negative checks.
It has no trusted update interface or verified readback across both JVMs.
The integrated deployment still selects legacy authentication.
See `docs/evidence/i1-strict-policy.txt` for the historical isolated results.
The later server plan supersedes a matching-source prerequisite: changes use external launchers/runtime injection against unchanged pinned vendor artifacts.
Public source at `5187abd46d827d37cfc5708805eced197a837e49` is based on 5.7.14 and is not a substitute.
Complete the integration-owned strict work list above.
Request only required image changes through the image handoff.

## Core contracts required for I2

The supplied CRDs establish cluster-scoped User, Group, Role, and Invite resources and namespaced UserBindings.
Integrations create their own bindings, refer to Users through `spec.userRef.name`, and write `Synced`; Core observes them.
Resource shapes and binding ownership no longer need to be invented or recovered from the prototype.
The schema does not supply a multi-generation credential inventory or durable activation interface.

Obtain versioned contracts or shared conformance implementations for these boundaries:

| Boundary | Required decision |
| --- | --- |
| Identity | Persistent immutable User UUID source, canonical `urn:uuid:<uuid>` URI SAN, display CN, restore behavior, and initial CSR flow. |
| Effective permissions | Group ancestry, role union, revisions, freshness, and changes caused by group moves or role edits. |
| Credential inventory | Core-owned User annotation with approved generations, purpose, issuer/serial, SHA-256 fingerprint, validity, predecessor mapping, and superseded/compromised states. The integration provisionally reads `platform.opendefence.fi/accepted-credentials`; Core must confirm the key and schema. |
| Installed integration identity | The cluster-scoped `Integration` CRD now exists. The TAK package registers `integration-tak`. This schema does not yet include certificate identities, named credentials, connection purposes, or destination acknowledgements. Define those fields and the SAN, trust, rotation, removal, readiness, and freshness rules. Do not use a service User or UserBinding. Zarf installation is authorization; there is no second approval. TAK must apply the current inventory for 8443 and 8089. |
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
2. Complete the `tak-operator` strict projector and readback adapter. Keep one JVM per process, serialized mutations, and readback after uncertain writes.
3. Verify the full accepted credential set, roles, groups, and callsign presentation without recreating unrelated certificate records.
4. Implement authenticated successor observation with an explicit process owner and persistent Core reporting.
5. Connect the seven implemented operations to production Core authority and verified TAK projection readback.
6. Implement protected self-service routes and certificate-free token redemption with compatible TLS routing.
7. Verify the implemented Secret-backed grants against live Core authorization, ingress, replica races and the restore procedure.
8. Extend the fixture-backed denial, freshness, retries, recovery and binding replacement tests with live acceptance evidence.

GET requests must not create accounts, keys, or certificates.
An admin role alone must not permit extraction of another user's key.
Grants use a random public ID and a separate 256-bit token. Store only the token hash.
Grants normally expire after five minutes, or sooner when authority or credentials expire.
An old grant must not select a new credential generation.
Use `201` and `Location` for ready grant creation, `409` for unsupported updates, and retryable `503` for unavailable authority, projection, material or infrastructure.
Public invalid, expired, or revoked grants return a uniform `404`.
Sensitive responses use `no-store`. Build links from a configured public origin.
Do not log tokens or restore live grants from backups.

Main and TAK-only activation flows are independent.
Qualifying authenticated successor use triggers Core's revocation of its mapped predecessor automatically.
A download, manual acknowledgement, or required CoT/HTTPS transaction is not activation.
Planned overlap has no default forced-cutover timer.
Remove only the native record for the revoked certificate.
Keep the other certificate identities for that User.

## Later validation and delivery

I3 requires `gpt-6-astra` / `high` for live authorization, grant races, multi-certificate acceptance, rotation, and persistence review.
Escalate unresolved binary/design behavior through I1 at `xhigh`.
I4 requires `gpt-6.1-sol` / `high` for concrete fixes, UI adapters/fixtures, client tests, and operational docs.
I5 requires `gpt-6-astra` / `high` for a fresh cumulative Ponytail review/audit and acceptance review.
I6 requires `gpt-6.1-sol` / `medium` for final handover. Add no features in I6.
Follow the original handoff's exact model gate protocol before each transition.

Complete these external and operational checks:

- Promote the stack composition to a pinned server release once the sibling base and
  strict authentication are accepted. The local `k8s/stack` composition already
  includes the server base and this repo's operator ingress policy.
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

For the next I2 session, read the implemented application boundary in [API and operator](api-operator.md), then obtain the missing Core and server contracts for production adapters.
If those inputs remain unavailable, report the specific dependency and preserve this checkpoint.
Binary component work resumed at `67b94e2`; the current checkpoint includes the contact-handler extension.
Continue live binary work only against the agreed server mechanism and deployment tuple.
If safety checks prevent probing, use the evidence procedure above and retain all affected release blockers.
