# TAK Server remaining changes handoff

Date: 2026-10-10. Target repository: `opendefence/tak-server`.

Package the tested single-Pod server layout and finish the adopted strict fingerprint extension.
The current server binary accepts an unapproved, CA-valid certificate with an approved user's UUID.
The new policy fixes this decision in isolation. TAK does not call it yet.
Do not advertise strict authentication or production readiness until the live acceptance checks pass.

## Checkpoints and authority

| Worktree | Branch and checkpoint | State |
| --- | --- | --- |
| `../tak-server` | `implementation/t0-foundation`, `a38531b` | T1 runtime decisions complete. T2 packaging has not started. |
| `../tak-server-strict-fingerprint` | `feat/strict-fingerprint`, `7f1e42c`, based on `65b0173` | Tested Java policy and tests only. No TAK entry point uses it. |
| This integration repository | `feat/i0-foundation`, `6503b83` before this handoff | I1 open; pure I2 package builder complete; production operator/API absent. |

The server user selected **one Pod with separate config, messaging, and API containers**.
An optional plugin container can share that Pod.
This later decision supersedes the original server handoff's separate-Pod constraint.
Keep the integration JNI/operator process in a separate Pod.
See the committed [server checkpoint](../../tak-server/docs/implementation-status.md) and [T1 follow-up](../../tak-server/docs/t1-single-pod-findings.md).

The integration user explicitly adopted the strict fingerprint change:
"We are not getting a fixed server build anytime soon so continue with strict fingerprint proposal".
Do not request that adoption decision again.
The server checkpoint's unmodified-binary baseline remains valid for packaging experiments.
The adopted authentication extension is a specific exception for the final server.
It does not approve unrelated XML persistence patches.
Update the server checkpoint to record this exception when the branches are integrated.

This handoff consolidates the remaining server scope from both workstreams.
Keep the [original server handoff](../../tak-server/tak-server-implementation-handoff.md) for its detailed requirements and stage protocol, subject to the later decisions above.
That input is untracked. The companion `tak-server-kubernetes-migration-plan.md` is still missing.
Sibling links require these local checkouts; provide their files or equivalent commit references to a remote recipient.

## Ownership and release inputs

| Owner | Responsibility |
| --- | --- |
| TAK server | Image, source/build provenance, strict authentication enforcement, trusted management interface, runtime state, reusable Kustomize base, standalone overlays, server acceptance tests. |
| Integration | Core-to-TAK projection, separate JNI process, projection readback, selected observer/guard, client ZIP API, grants, and UI. Consume the server base; do not copy it. |
| Core | Immutable identity, effective permissions, approved credential inventory, purpose/generation mapping, issuance, durable activation evidence, and predecessor revocation. |

The integration can create a dedicated mTLS certificate for its access to TAK's port 8443 REST API.
Its operator registers that certificate as a trusted administrator through JNI.
TAK must also trust the certificate for TLS client authentication.
The installed integration's certificate identity is trusted because an administrator applied its Zarf package.
Do not require a second approval.
Strict mode must bind the presented certificate to that installed identity before the REST API can use it.
Other installed integrations may need port 8443 or 8089.
Core's `Integration` CRD must define how status reports each integration's own mTLS certificate serial.
The schema in library `0.2.2+261011` has no certificate fields yet.
It must define identity, issuer, rotation, removal, and freshness checks.
A serial alone is not a global certificate identity.
Keep the private key in an integration-owned Secret and outside the delivery API Pod.

Use the current candidate only as a recorded baseline:

| Item | Recorded value |
| --- | --- |
| TAK / Java / Ignite | `5.8-RELEASE-84` / Temurin `17.0.20.1+1` / `2.18.0` |
| Image runtime tested | ARM64; Python `3.12.3` |
| Server source baseline | `beaab168e70187dbdc4eadeca77d4939413df6b5` |
| PR #136 adapter reference | `025355ba9f76bf6c41187897f4a5fcac93b82afb` |
| Experimental image | `localhost/tak-server:t1-5.8.84-pr136` |
| Image manifest | `sha256:a3c022ec0806378523ed86dc9949599fb3b5331cf4deb78293dd4ee9efd9fffe` |
| `UserManager.jar` SHA-256 | `4ad7adcb9a09156d7122bfb2d4ddf3fd6705fb612f4d521335a5e08b449d24f6` |
| `takserver.war` SHA-256 | `64309513e45ba1e92084d457cd787b35d1c570ab918a11fd1ce1e5bdd4d6f26c` |

The final patched image will have new checksums.
Build the schema, management interface, WAR, and `UserManager.jar` together.
Publish one tested compatibility tuple.
Integration's I0 image still contains a different 5.8.69 JAR; it must be repinned before compatibility acceptance.

Matching TAK 5.8.84 application source remains missing. Its location was requested.
The previously inspected public source at `5187abd46d827d37cfc5708805eced197a837e49` is based on 5.7.14.
It is not a matching source bundle. Do not silently substitute it or change the target release.
Packaging work can continue while the source input is obtained.

## 1. Package the selected topology and storage

Implement one versioned Kustomize base with standalone and integrated overlays.
Use ordinary OCI builds and a slim Java 17 runtime.
Align startup Python tooling with the image's Python 3.12 environment.
Do not copy integration's Python 3.14 setting into the server without changing and testing its runtime.

1. Package the tested startup adapter in the image. The experimental fixture mounts it from a ConfigMap.
2. Use one configuration-service owner and non-overlapping replacement. A singleton StatefulSet is a suitable controller. Keep the lifetime lock regardless of controller.
3. Keep `/opt/tak/data/CoreConfig_config.xml` as the PVC authority. Keep `/opt/tak/CoreConfig.xml` and `/opt/tak/data/CoreConfig.xml` as its compatibility links in the config container.
4. Reuse `scripts/coreconfig.py`: lock, read or seed, merge owned attributes, validate with the selected release's XSD, back up, publish atomically, then start the JVM while retaining the lock.
5. Seed follower CoreConfigs from that validated authority after the merge. Give each follower private writable runtime files. Runtime configuration flows through Ignite.
6. Isolate file-auth by role. Messaging owns persistent file-auth. Give API a private copy and private backup directory. The current live fixture still shares this file.
7. Put authoritative backups on persistent storage. Tighten file-auth and backup permissions; the inspected fixture used mode `0644`.
8. Preserve administrator-managed federation trust and initialize it only when absent. Inventory mission, content, audit, and other writes before changing mounts or making the root filesystem read-only.

Follow the [storage design](../../tak-server/docs/coreconfig-kubernetes-design.md).
Document `coreconfig.MANAGED` and the deployment-owned replacement of the LDAP element.
Preserve administrator peers, groups, policy, extra listeners, and federation trust attributes.
An extra listener requires separate Service and NetworkPolicy exposure.
Rendered XML and backups contain secrets; keep them out of ConfigMaps and Git.
Keep persistent file-auth accounts, fingerprints, roles, and groups under the user-management service; do not regenerate them from deployment templates.

A completed init container cannot retain the JVM lifetime lock or repeat the merge after a container restart.
Do not add a whole-file watcher or force-save JNI loop.
The tested topology already persists the selected admin edits without either mechanism.

RWO is not a writer lock. The experimental `Recreate` Deployment does not prevent every manual-deletion overlap.
RWOP can serve several containers in one Pod if the selected CSI driver supports it.
Only local-path RWO was tested. Do not claim movable storage or node-failure recovery from this result.

## 2. Wire strict fingerprint authentication into TAK

Start from [the implemented policy and test instructions](../../tak-server-strict-fingerprint/extensions/strict-fingerprint/README.md).
Integrate commit `7f1e42c` with the later packaging checkpoint without discarding either branch's changes.

`StrictFingerprintPolicy` holds an immutable projection in one JVM.
It atomically replaces one account's complete approved set using a current revision token.
It checks the exact account CN, leaf SHA-256, leaf validity, and explicit approval deadline.
It rejects CA leaves and ambiguous CNs. Empty, missing, expired, or invalidated approval denies access.
Restart creates an empty projection and a new revision.
TLS chain and client-certificate usage validation remain the caller's responsibility.

The container suite passed 46 assertions with eight distinct signed leaves.
This is policy evidence, not TAK enforcement evidence.
See [saved results and limits](evidence/i1-strict-policy.txt).

Complete these coupled changes:

1. Add an explicit strict file-auth mode to the schema and startup validation. Invalid or unavailable strict state must not select legacy behavior. Keep legacy behavior explicitly separate.
2. Expose a trusted management operation for a UUID's complete approved leaf set, approval deadline, and conditional revision. Add immutable readback and explicit conflict/failure results. Restrict the writer to the agreed management authority.
3. Distribute the projection to both messaging and API JVMs. Sharing a Pod does not share Java memory. Return applied revisions from each process; local write success does not prove remote enforcement.
4. Bind permission and credential readback to the requested projection. Retain roles and groups when replacing credentials or removing one leaf. Resolve uncertain writes by readback before retrying.
5. Reject stale updates, stale authority, unavailable authority, missing state, and restart state. The current policy requires its owner to call `invalidate()` on authority failure; it cannot detect transport loss itself. Define and test that owner and freshness bound.
6. Enforce after validated TLS identity and before every role, group, token, cache, LDAP, or anonymous grant in strict mode. Audit all enabled certificate entry points. Explicitly disable unsupported paths until tested, including alternate transports if enabled.
7. Make messaging denial stop the first CoT before routing. A caught exception followed by asynchronous channel close is insufficient. Make HTTP denial cover cached principals and existing sessions as well as new TLS connections.
8. Define enforcement for existing connections and resumed TLS sessions. Measure the revocation bound. A policy decision made before a concurrent removal is not cancelled by the current policy object.
9. Version the schema, management capability, implementation, and artifact tuple together. Expose enough capability information for integration to reject an incompatible server.

Do not encode a list in the legacy scalar fingerprint field or alternate registrations as a substitute.
The tak-operator uses one native TAK record for each accepted certificate.
Several records can have the same callsign and receive one User's projected permissions.
Remove only the native record for a revoked certificate.
Preserve the other certificate identities for that User.
The strict policy must not require one native account per User UUID.
The current policy limits are 1,024 accounts, 32 fingerprints per account, and 256 account characters.
Validate those limits against the intended deployment and expose limit failures clearly.
Exact account strings do not settle Core's UUID encoding contract.
Random server revisions are neither Core generations nor durable activation events.

Keep the optional disconnect guard decision open.
A guard after authentication cannot establish rejection before the first authorized message.
The strict admission checks are required independently of that decision.

## 3. Expose trustworthy authentication evidence

Coordinate the minimal server interface with the integration observer.
First inspect whether the chosen release already exposes a usable completed-authentication signal.
If it does not, add a supported server signal or query as part of the authentication work.

The [lifecycle inspection](evidence/i1-auth-lifecycle.txt) found that `ConnectionInfo` receives the peer leaf before TAK authentication completes.
It has no authentication-status field, and its handler is transient.
TLS success, connection metadata, or subscription presence alone does not prove completed TAK authentication.

Evidence must bind a positive result to the exact connection, UUID, leaf fingerprint, applied approval revision, and observation time.
Do not require a CoT message or HTTP application transaction to activate a successor.
Test short-lived connections, stale observations, revoked/superseded leaves, restart, reconnect, and resumption.
Provide an authenticated current-state query or equivalent recovery path for missed notifications.

Integration owns the observer process and durable reporting to Core.
Core owns purpose/generation interpretation and automatic revocation of the exact mapped predecessor.
Main and TAK-only activation remain independent.
A download or manual acknowledgement is not activation. Planned overlap has no default forced-cutover timer.
Do not implement a second Core identity or issuance system inside TAK.

The [contact-handler probe](evidence/i1-binary-probe.txt) also proves that later CoT overwrites a contact-map callsign edit.
Do not claim the current contact API makes a callsign durable.
Any server contact update must bind the CoT UID to an authenticated connection and preserve the UUID, certificate, roles, and groups.
Client preference delivery and a `client-update-required` outcome belong to integration; no server identity rename is needed.

## 4. Finish recovery and optional roles

Use explicit Ignite discovery and the selected shared server Pod address.
Give the external JNI client a distinct profile such as `t1-jni`.
Do not reuse prototype helpers that advertise the client as `messaging`; they can affect TAK's locality test.
Keep discovery available before full readiness and restrict network access to required participants.

Implement finite automatic failure detection and recovery with visible failure status.
Use a non-mutating remote-service operation for readiness.
Listening sockets and old marker files do not prove RPC health.
`/proc/net/tcp` is especially misleading when containers share a network namespace.
Document whether recovery replaces one container or coordinates the server Pod.

T1 observed remote API and CoT recovery after full Pod replacement and a messaging-only container restart.
A separate PyJNIus 1.7.0 process recovered `getUserList()` after two Pod IP changes in 18.574 and 42.316 seconds from rollout requests, with no client Pod restart.
These times are observations, not an SLA or a total RPC timeout guarantee.
Ignite removes continuous queries and remote event listeners after reconnect.
The integration observer must resubscribe and rescan authenticated state; that behavior is untested.

If plugins are supported, package the optional XML-preserving launcher from PR #136.
See [report 006](../../tak-server/bugreports/006-pluginmanager-forces-localhost/HANDOFF.md).
It starts Ignite from the loaded XML before Spring and uses reflection to set `PluginService.ignite`.
It changes the external entry point, not TAK class bytes.
Build it against the exact selected release and fail clearly when incompatible.
Shared networking alone does not fix the plugin manager's localhost override.
Startup and three plugin API registrations passed; existing plugin-process recovery and third-party callbacks remain untested.
Keep retention as a long-running JAR unless a supported one-shot mode is proven.

## 5. Close persistence risks without overstating the evidence

Retain the existing [numbered reports](../../tak-server/bugreports/README.md).
Do not reopen solved packaging questions as mandatory application patches.

| Report | Current finding | Remaining server action |
| --- | --- | --- |
| 001: admin edits lost | Reproduced with different role IPs. Selected shared-Pod saves and restart preservation passed. | Package and retest the selected layout. Keep the upstream report; no locality-method patch is currently required. |
| 002: Ignite reconnect stalls | Separate-Pod failure reproduced; root cause unresolved. Shared-Pod and external JNI recovery passed in the fixture. | Prove bounded automatic detection/recovery and observer restoration on the final image. |
| 003: extra XML writers | Shared-file deployment risk. Private follower CoreConfigs passed. | Keep private files; complete API file-auth and backup isolation. |
| 004: unsafe XML publication | Java truncates the live target and copies a backup beside the supplied path. A symlink backup landed outside the PVC. Crash loss was not reproduced. | Fix persistent backup placement in packaging. Fault-test interruption and concurrent reads. Atomic Java publication is a separate, unapproved application change. |
| 005: hidden file-auth save errors | Bytecode publishes a control update before save and catches save exceptions with only debug logging. Ordinary registration/restart passed. | Inject failure at the persistent messaging owner and separately at API's private copy. Record RPC result, memory, disk, restart, and retry. Decide durable-success semantics from evidence. |
| 006: plugin localhost override | Same affected class in 5.8.69 and 5.8.84. Optional launcher startup passed. | Package the pinned launcher if supported; test recovery. Keep the upstream supported-initialization fix separate. |

For report 004, a possible source fix writes a temporary file on the canonical target's filesystem, flushes it, and atomically replaces the target while preserving compatibility links and a persistent backup.
Before seeking approval, specify symlink handling, permissions, backup ordering, and crash guarantees, and preserve the failing test.
For report 005, do not claim an observed successful HTTP response after a failed durable save: fault injection has not established that case.
If packaging cannot satisfy required durability, present the smallest concrete application patch and its evidence for a separate decision.
The strict-authentication adoption does not settle either persistence change.

## 6. Finish identities, migration, standalone use, and cleanup

1. Consume issuer-managed or supplied Secrets for server identities and passwords. Prefer the tested native cert-manager JKS output; retain conversion only for an input that needs it.
2. Keep RSA CoT/JWT identity separate from HTTPS identity. Preserve the target release's RS256 requirement. Keep CoT client trust, federation trust, and outbound Java HTTPS trust separate. Public JRE roots must not automatically authorize CoT clients.
3. Activate each key/certificate/password generation coherently. Verify the actually served certificate. Use reload only where proven; otherwise use tested coordinated replacement. HTTPS renewal must preserve CoT/JWT identity and federation trust.
4. Move local CA issuance to cert-manager or external PKI. Ordinary TAK Pods must not mount the CA signing key. Import existing identities before enabling automatic issuance. Preserve fingerprints and PVCs.
5. Replace `firstrun.done` with a versioned SchemaManager Job and database-side exclusion. Separate migration privileges from application credentials. Prove fresh, no-op, upgrade, concurrent, interrupted, and retried runs. Verify whether `takdb_base.sql` is still required before deleting it.
6. Provide standalone Kind and existing-cluster overlays using the same base. They must work without Core, RMAPI, Core CRDs, the integration operator, or a sibling checkout. Reuse existing CNPG/cert-manager in integrated installs.
7. Provide a narrow supported admin bootstrap Job and prove standalone client CoT. If strict mode is enabled, populate its trusted approval state explicitly; do not add an implicit admin bypass.
8. Expose CoT/federation as appropriate TCP services. Keep TAK `/Marti` routing/authentication separate from integration `/integrations/tak/api/v1`. Do not assume arbitrary prefix rewriting or identity headers preserve client-certificate authentication.
9. Remove `firstrun_rm.sh`, `kw_product_init`, RM manifest/host-file/bootstrap code, obsolete user wrappers, and duplicate shell ZIP delivery after native replacements pass. Replace Compose build/deploy orchestration. Remove obsolete Azure Container Apps and DevSpace paths.
10. Make APK/update content an optional pinned artifact or content service. Preserve historical LFS objects. Test install, restart, and upgrade with internet egress blocked.
11. Supply coordinated backup and restore for database, XML, file-auth, federation trust, application content, and identities. Removing workloads must retain data by default. Integration separately excludes live grants from restore.

## 7. Finish CI and deliver the server contract

Preserve imported Git history, intended branches/tags, and reachable LFS objects.
After separately authorized publication, verify an independent destination clone.
Track GitHub issues, PRs, releases, settings, secrets, and registry artifacts separately; Git copying does not migrate them.

Complete the [CI migration](../../tak-server/docs/ci-migration.md).
Keep actions pinned and PR jobs non-publishing.
Use `arc-runner-set`, native AMD64/ARM64 BuildKit services, and runner TLS files at `/etc/buildkit/tls/{ca.crt,tls.crt,tls.key}`.
Replace Compose checks with disposable Kubernetes validation of the exact candidate image.
Keep `TAK_PUBLISH_ENABLED` unset until runtime and runner acceptance pass.
The target registry is `ghcr.io/opendefence/tak-server`. No Snyk placeholder is needed.
No push or publication is authorized by this handoff alone.

Deliver these versioned inputs to integration:

- Image digest, TAK/JRE/Ignite versions, source and build provenance, WAR/JAR checksums, and strict-mode/schema/management capability versions.
- One reusable deployment base with its pinned reference, supported overlays, Services/ports, Secret keys, mounts, role profiles, and network requirements.
- Complete-set update/readback contract, conflicts, freshness deadlines, applied revisions per process, and authenticated observation contract.
- Readiness operation, total operation/recovery bounds, restart order, certificate renewal, backup/restore, and upgrade procedures.
- Supported architectures, storage drivers/failure domains, optional roles, sanitized acceptance evidence, and explicit remaining limits.

## Acceptance still required

Use the final image, base, schema, and management JAR together.
Save exact inputs, checksums, assertions, outcomes, and limits without credentials or raw configuration.

| Area | Required pass condition |
| --- | --- |
| Strict admission | Approved main and TAK-only leaves with one UUID receive the same intended permissions. A third CA-valid same-UUID leaf gets no CoT routing or protected HTTP access. |
| Projection lifecycle | Removing one leaf preserves the other and its account. Missing, expired, stale, invalidated, and restarted state denies. Concurrent/stale writes and uncertain outcomes preserve correct applied state in both JVMs. |
| Sessions and caches | New/existing/resumed TLS, HTTP principals/tokens/caches, and enabled alternate transports cannot bypass the approved set. Revocation meets the documented bound. |
| Authentication observation | Only completed authorized use of the exact successor qualifies. Reconnect resubscription and recovery scans reject stale, unrelated, revoked, and superseded evidence. |
| Install and persistence | Fresh/repeat standalone apply passes. Real admin edits survive container restart, full replacement, managed-input change, and supported upgrade. Invalid XML and competing owners preserve saved state. |
| Save failure | Private follower writes cannot overwrite authority. Persistent backups, interrupted owner saves, disk/permission failure, and file-auth failure have documented, tested outcomes. |
| Recovery | Messaging-only restart and full server replacement recover JNI, HTTPS, CoT, and any supported observer/plugin behavior within a stated bound, or report explicit failure. |
| TLS and schema | Coherent renewal changes the served identity as intended. Trust separation persists. Schema fresh/no-op/upgrade/concurrency/interruption/retry cases pass. |
| Storage and removal | Restore the coordinated state and verify identities/permissions. Test reattachment where promised. Uninstall retains data. State local-path limits. |
| Supported operation | AMD64 and ARM64, offline install/restart/upgrade, production NetworkPolicy enforcement, and supported retention/plugins pass. Test a real federation peer if federation is advertised. |
| Integration contract | Actual integration JNI uses the final JAR/base/image successfully. Core authority and both applied server revisions determine readiness. |

T1 already proved selected admin persistence, native JKS, RSA JWT verification, authenticated bidirectional CoT, basic JNI recovery, and plugin API availability.
The integration component probe proved the current authentication defect and CoT callsign overwrite.
Neither set of results replaces the remaining end-to-end checks above.
Local Kind networking does not establish production NetworkPolicy enforcement.

## Resume instructions and dependencies

Inspect both server worktrees before changing them. Preserve unrelated files and commits.
The original server checkout retains untracked `tak-server-implementation-handoff.md` and `bugreports/old/`.
Do not replace its worktree with the older policy branch.
Restore the required Ponytail full and Caveman skills, use STE documentation, review each coherent change, and keep local commits small.

Server T2 remains at its mandatory `gpt-6.1-sol` / `high` gate and requires confirmation under the original server protocol.
Integration's confirmed I1 Astra / XHigh setting does not waive that server transition.
Use T3 `gpt-6-astra` / `high` for live review, T4 `gpt-6.1-sol` / `high` for fixes, T5 `gpt-6-astra` / `high` for fresh cumulative review/audit, and T6 `gpt-6.1-sol` / `medium` for closure.
Escalate unresolved runtime/design behavior to T1 `gpt-6-astra` / `xhigh` and preserve the reproduction.
This documentation handoff does not start T2.

After the T2 gate, start with the tested Pod layout, private role files, persistent backups, and functional readiness.
Continue Secret inputs, migration Jobs, standalone operation, and CI in separate commits.
Obtain matching application source before wiring the strict policy into shipped TAK classes.
Keep any unrelated persistence patch decision separate.

The [Core contract list](core-contracts.md) is still open: UUID encoding/restore, effective permissions and freshness, approved credential inventory, issuance/export authority, namespace/Secret access, UserBinding writers/readiness, HTTP authority, and durable activation reporting.
Do not invent Core CRDs or label fixture inputs as an agreed API.
Finalize server transport/capability contracts with integration while Core supplies those semantics.

The shared test environment belongs to the server session: context `kind-tak-server-t0`, namespaces `tak-server-baseline` and `tak-server-t1`.
Inspect current state and coordinate its use before mutations. Preserve PVCs and identities.
Experimental fixtures and private logs are under ignored `outputs/t1/`; they are not a production deployment or a complete backup.
Use containers for Java compilation and specialist inspection. No local Java compiler is available.
The pinned container command is in the policy README above.

Earlier binary probes ran successfully. No tool or automatic approval system rejected them.
User-reported Daybreak Blue provenance is not independently verified.
If a future environment blocks a probe, record the exact reason and retain the affected acceptance check; do not bypass the restriction or describe an ordinary compile failure as a safety block.
See [the existing evidence procedure](remaining-work-handoff.md#binary-probing-and-possible-safety-blocks).
