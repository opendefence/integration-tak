# I1 partial findings

## Status and scope

I1 is incomplete.
The user confirmed `gpt-6-astra` / `xhigh` with "Switched; resume I1".
The host cannot verify the active model metadata.
The user resumed binary probing and confirmed the I1 gate on 2026-10-10.
The latest user message confirms Astra / XHigh and reports that Daybreak Blue ran the earlier probing tests.
This is user-reported provenance. The host cannot verify either runtime setting.
The 5.8.84 component probe now compiles and passes its assertions.
It proves that the current binary fails the strict approved-set requirement.
No production authentication, Core adapter, or server deployment has changed.

## Companion sources

The local Core handoff is `/Users/rambo/Downloads/rasenmaeher-core-architecture-handoff.md`.
It is dated 2026-10-10 and has status "Working architecture handoff".
Its SHA-256 is `33a41720b2255535570a1cc782cd8ca29b13ab97cccb1da580c19926487992be`.
The supplied filename differs from the integration handoff's `(1)` filename.
This copy explicitly leaves the contracts below open.

The user supplied two additional sources:

- [TAK package and server design discussion](https://chatgpt.com/share/6aca5977-77e0-83eb-8d24-6162f8327167).
- [Core architecture discussion](https://chatgpt.com/share/6ac980bb-d5dc-83eb-82ab-31ae4dded1ee).

Both conversations were read through their public HTML.
The TAK discussion confirms independent main and TAK-only activation flows.
It also distinguishes observation from the optional disconnect guard.
Its generated summary mentions explicit confirmation, but the later detailed instructions require automatic confirmation from authenticated successor use.
The integration handoff retains that later requirement.

The revision-5 redesign document remains unavailable as a file.
The shared conversation links it through a sandbox path in the originating session.
The shared HTML does not include the full document.
Conversation excerpts are supporting evidence, not a verified copy of revision 5.
The local OpenAPI input remains `1.0.0-draft.5`.

## Candidate runtime

The server repository's T0 checkpoint identifies this candidate.
It is an investigation input, not the final integration runtime contract.
The I0 Dockerfile still uses its recorded 5.8.69 JAR.

| Item | Value |
| --- | --- |
| Server source baseline | `beaab168e70187dbdc4eadeca77d4939413df6b5` |
| Local image | `localhost/tak-server:baseline-5.8.84-beaab168` |
| Image manifest | `sha256:f0521e15dacfa1d03f5d9b46da3f236c2bfe8c01c89194ff491b403f39209bfa` |
| TAK version | `5.8-RELEASE-84` |
| Server JRE | Temurin `17.0.20.1+1`, from the server T0 record |
| Architecture | ARM64 |
| `UserManager.jar` SHA-256 | `4ad7adcb9a09156d7122bfb2d4ddf3fd6705fb612f4d521335a5e08b449d24f6` |
| `takserver.war` SHA-256 | `64309513e45ba1e92084d457cd787b35d1c570ab918a11fd1ce1e5bdd4d6f26c` |
| Inspection JDK image | `eclipse-temurin:17-jdk-noble@sha256:fb79620c3f6ee8f1c7530a8dc4fd49e3b410bcef037694ad4858a1553bac4170` |

The artifacts were extracted from the local image.
The JAR checksum matches the server checkpoint.
No TAK service was started for this investigation.
No Kind context or namespace was selected.
The server project's existing cluster was left unchanged.

## Authentication evidence

`UserAuthenticationFile.xsd` exposes one scalar fingerprint per User.
The actual WAR's `X509Authenticator.auth(User, Input)` loops through file users.
Bytecode offsets 646 through 684 match either the stored fingerprint or the identifier.
Offsets 687 through 712 assign the matched user's role.
Offsets 975 through 982 assign its groups when the group cache is disabled.

This is static evidence of a CN/account fallback.
It supports the inference that changing the scalar fingerprint alone cannot restrict a shared UUID to two approved certificates.
It does not prove an end-to-end TLS/CoT result.
The optional certificate-revocation lookup rejects a known revoked record.
An absent record continues through the inspected code; this is not a positive approved-set check.
No suitable existing approved-set mechanism has been proven.

The component reproduction is in `spikes/i1/`.
It uses the actual WAR classes and generates certificates in container tmpfs.
The first run failed because `Role.ROLE_USER` and `ConnectionType.STREAMING` do not exist in 5.8.84.
Container `javap` inspection identified `Role.ROLE_READONLY` and `ConnectionType.CORE` as the exact binary values.
The repaired probe passed with a pinned Java 17 JDK and no network.

The main, TAK-only, and unapproved certificates had unique fingerprints and the same UUID CN.
The fixture alternated the stored scalar fingerprint between main and TAK-only.
All three same-UUID certificates received `ROLE_READONLY` and both `fixture` group directions.
The different-UUID certificate did not receive `ROLE_READONLY`.
It received the binary's `ROLE_ANONYMOUS` and `__ANON__` group fallback.
The process returned exit status 0 after all assertions.
See `docs/evidence/i1-binary-probe.txt` for the sanitized result matrix.

The experimental server image `localhost/tak-server:t1-5.8.84-pr136` contains the same tested WAR and `UserManager.jar` checksums.
The component result therefore applies to its Java artifacts.
This does not replace a live TAK TLS and CoT authentication test.

The user adopted the following repair on 2026-10-10 and asked to proceed without waiting for a fixed server build.
This change belongs in the server project:

1. Add an explicit strict file-auth mode with a set of approved leaf SHA-256 fingerprints per UUID.
2. Check both the certificate's UUID and its exact fingerprint before assigning roles or groups.
3. Reject an empty, missing, expired, or unavailable approval projection.
4. Apply the check before alternate token/group-cache paths can grant access.
5. Replace each UUID's accepted set atomically and expose readback of its applied revision.
6. Preserve one UUID account and its permissions when one certificate is removed.
7. Apply the same policy to messaging and API authentication paths.

Keep the legacy scalar representation separate from the new strict mode.
Do not encode a list inside the scalar value.
The server change must update the schema, management interface, implementation, and pinned JAR together.
Proceed with the custom server change. Adoption is settled; production enforcement is not implemented.

The first implementation slice is committed in the server repository at `7f1e42c`, branch `feat/strict-fingerprint`.
Its separate worktree is `../tak-server-strict-fingerprint`.
`extensions/strict-fingerprint/` contains the Java policy, a container test, and the remaining wiring plan.
The policy checks exact certificate CN and SHA-256, leaf validity, and approval expiry.
It provides immutable readback and atomic updates that reject stale revisions, including revisions from before restart.
Empty, missing, expired, or explicitly invalidated projections deny access.
The owner must signal authority failure; the policy has no Core availability monitor.
The final container run passed 46 assertions, including two approved same-UUID leaves and rejection of the third.
See [policy conformance evidence](evidence/i1-strict-policy.txt).

This policy is not wired into the 5.8.84 authentication classes.
The matching source bundle is still missing; the local server repository contains distribution artifacts.
Public source HEAD `5187abd46d827d37cfc5708805eced197a837e49` merges `upstream/5.7-RELEASE-14`.
The `5.8*` tag query returned no matches. Do not substitute that source for the tested binary.
The source location was requested. The existing server worktree and shared test cluster were preserved.
Next, wire the policy into the schema, trusted management path, and every supported certificate authentication path.
Cover cached HTTP identities, token/group-cache grants, and denial before message routing.
Then build the server and management JAR together and run live acceptance tests.

Residual risks remain explicit.
A stale approval projection can retain access after a Core change.
Core and the server must agree freshness and failure behavior.
Existing connections and TLS resumption require separate enforcement tests.
A post-authentication disconnect guard cannot establish rejection before the first CoT message.
The guard decision remains open; no decision to omit it has been made.

## Callsign evidence

| Surface | Current evidence | Implementation consequence |
| --- | --- | --- |
| Package preferences | The pure full-setup builder emits the current desired callsign where the client format is known | Real client import and override behavior remain untested. |
| Contact table | The component probe changed `CLIENT` to `DESIRED` through `DistributedContactManager.updateContact` | The actual binary can replace the contact record by UID in process. Live remote execution is untested. |
| Next CoT contact | The extended component probe calls `SubmissionService.processContactMessage` with parsed CoT. It replaces `DESIRED` with `CLIENT-NEXT` and the fixture endpoint | Incoming contact data can overwrite the desired name. Network delivery remains untested. |
| Live subscription | No update established by the inspected contact method | Do not advertise immediate subscription rename. |
| Peer display | Not tested | Do not advertise immediate peer rename. |
| Reconnect and restart | Not tested | Keep the acceptance checks open. |

Use `client-update-required` when a durable supported refresh is unavailable.
A preferences-only update still needs package and client validation.
Do not emit `disablePreferenceItem_locationCallsign=true`.
Do not infer the CoT UID from a UUID or callsign.
Bind it to the authenticated connection before any contact mutation.
The component probe preserved the fixture certificate bytes, UUID account, role, and group list after the edit and CoT overwrite.
It invokes the private contact handler through reflection, without server initialization, routing, or UID authentication.
The fixture has no subscription. It does not prove preservation of an existing subscription.
This does not prove durable client or peer presentation behavior.

## Rotation evidence

The actual remote `ConnectionInfo` class contains the peer certificate and connection ID.
That makes it a candidate input for exact-fingerprint observation.
Presence of a certificate in this object does not prove completed authentication.
Container bytecode inspection now establishes the ordering for the Netty TLS path.
After TLS success, the handler creates `ConnectionInfo` and copies the peer leaf before it creates the authentication codec.
The codec starts with `AuthStatus.NEW`.
`X509AuthCodec.onConnect` calls `doTlsAuth`, which stores the result from `X509Authenticator.authenticate`.
This path does not require a CoT application message to call the authenticator.
The serialized `ConnectionInfo` has no authentication status; its handler reference is transient.
See [the static lifecycle trace](evidence/i1-auth-lifecycle.txt) for exact classes and bytecode offsets.
The observer must use established, authenticated connection evidence.
Do not approve an observer that treats a peer certificate or subscription record alone as activation evidence.
Its Core status writer, replay rules, and persistence contract remain open.

Core owns predecessor revocation for both credential purposes.
An observation must identify the exact approved successor and its mapped predecessor.
Main and TAK-only transitions proceed independently.
Downloads, OCSP requests, and arbitrary CoT claims do not activate a successor.
No observer, rotation, reconnection, or session-resumption test ran in I1.

## Local evidence and resumption

Temporary evidence is under `/private/tmp/integration-tak-i1/`:

- `5.8.84/`: extracted artifacts, unpacked WAR, and `javap -p -c` output.
- `probe.log`: the original certificate checks and compilation failure.
- `probe-final.log` and `probe-pinned.log`: successful repaired runs with raw process logs.
- `probe-contact.log`: successful extended contact-handler probe with the same pinned runtime.
- `auth-lifecycle-javap.txt` and `handshake-javap.txt`: static connection/authentication lifecycle inspection.
- `shared-redesign.html` and `shared-core.html`: fetched public conversations.
- `shared-*-messages.txt`: extracted text used for the source review.

These temporary files are not durable release evidence.
They contain generated or fetched investigation data and are not committed.
The sanitized component result is committed at `docs/evidence/i1-binary-probe.txt`.
All probe containers used `--rm`.
The attempted reproduction ran with `--network none` and a temporary filesystem.
Its generated private keys disappeared with that container.
No keys, tokens, or kubeconfigs are in the repository changes.

The component probe is complete for the current 5.8.84 artifacts.
Complete live authentication tests after the adopted strict approved-set design is wired into the agreed server base.
I1 cannot be marked complete until the approved-fingerprint mechanism and required Core contracts are established.
