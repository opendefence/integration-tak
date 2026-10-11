# TAK image change handoff

Updated: 2026-10-11. Target repository: `opendefence/tak-server`.

The `tak-operator` owns strict authentication for integrated stacks.
The user assigned that work to `integration-tak` unless it requires changes to the TAK image.
Use the [remaining work list](remaining-work-handoff.md#integrated-strict-authentication-ownership) for contracts, projection, freshness, sessions, observation, and acceptance.
This handoff replaces the earlier broad server assignment.
Do not wait for unrelated server work when existing interfaces suffice.

## Ownership

| Owner | Responsibility |
| --- | --- |
| `integration-tak` | `tak-operator` reconciliation, Core adapters, strict-policy writer and readback, authority lease renewal, installed integration identities, session handling, activation observation, durable reporting, and coupled live acceptance. |
| `tak-server` | Shipped Java policy and admission hooks, required in-image management or evidence interfaces, binary compatibility, image packaging, and native server deployment. |
| Core | Immutable User identity, effective permissions, credential approval and inventory, installed Integration schema, durable activation authority, and mapped predecessor revocation. |

The config, messaging, and API containers share one server Pod.
The `tak-operator` JNI process runs in a separate Pod in `integration-tak`.
Standalone TAK uses legacy authentication and has no Core approval projection.

## Current image boundary

The current candidate is TAK `5.8-RELEASE-92`.
The server workstream merged the initial strict policy from `7f1e42c`.
Its external agent installs pinned messaging and API hooks before TAK startup.
Missing or incompatible injection fails strict startup.
Local negative CoT and HTTP tests passed.
The API hook can admit the exact integration administrator leaf through the existing 8443 service.
Its issuer must be trusted. The `tak-operator` must register its TAK administrator role through JNI.

The running JVMs have no trusted complete-set update interface or verified readback yet.
The integrated overlay therefore still selects legacy mode.
Native certificate records and CoT disconnection do not establish strict admission.
Keep `Synced=False` and production readiness blocked until the coupled checks pass.
See the [extension contract](../../tak-server/extensions/strict-fingerprint/README.md) and [server checkpoint](../../tak-server/docs/implementation-status.md).

## When an image change is required

First test the required operation through the existing APIs and JNI interfaces.
Record the missing behavior and the exact binary tuple.
Request the smallest image change that resolves the gap:

- A trusted complete-set update/readback interface on 8443, if existing interfaces cannot reach the policy. Require conditional revisions, explicit deadlines, conflicts, limit errors, and acknowledgement from both JVMs. Use the existing administrator mTLS identity.
- An admission or session hook, if the `tak-operator` cannot enforce a required denial through existing interfaces. Deny before the first routed CoT or protected HTTP access. Keep missing, expired, invalidated, and restarted policy state closed.
- A policy change for the agreed Core identity model or installed integration inventory, if the existing exact-CN model cannot represent it safely.
- A completed-authentication signal and recovery query, if existing APIs cannot bind the exact connection, UUID, leaf fingerprint, approval revision, and time. `ConnectionInfo` alone is insufficient because peer metadata precedes authentication.
- A versioned capability check needed to verify the active enforcement mode, both applied revisions, and artifact compatibility.

Do not move the integration controller or Core authority into the TAK image.
Do not add a second management listener, bootstrap credential, or integration approval workflow.
Keep TAK's role and endpoint authorization after certificate admission.

## Image implementation and evidence

Keep the vendor WAR and JAR bytes unchanged.
Fresh server source is unavailable. Use external launchers or runtime injection.
Verify artifact hashes, hook signatures, and classloader paths against the selected release.
Reject unsupported injection before client traffic can enter.
Publish image provenance, vendor checksums, extension version, interface schemas, and failure behavior.
Test missing extensions, changed artifacts, and incompatible hooks.
The integration workstream must then verify the complete live behavior against that image.
Do not combine older 5.8.69 or 5.8.84 evidence with 5.8.92 into an accepted tuple.

## Other server work

Native storage, identities, migration, recovery, standalone operation, CI, and distribution cleanup stay in the [server implementation plan](../../tak-server/docs/implementation-plan.md).
The original [server handoff](../../tak-server/tak-server-implementation-handoff.md) remains an untracked input.
Its companion migration plan is still missing.
Keep the recorded single-Pod decision and persistent identity/data requirements.
The strict extension decision does not authorize the separate XML publication or file-auth error-handling patches in server reports 004 and 005.
Those reports still need fault evidence and a separate decision if packaging cannot satisfy durability.
Sibling links require local checkouts. Supply equivalent committed files to remote recipients.
