# Core integration contract decisions

The supplied Core CRDs establish the resource shapes and UserBinding ownership.
The tak-operator imports its Core resource models from `lib-opendefence-core==0.2.2+261011`,
resolved from the user-supplied Nexus `pypilocal` index and pinned by hash in `uv.lock`.
The package requires Cloudcoil 0.8, now resolved from PyPI.
Its `UserSpec.callsign` requires `^[a-z0-9]{3,30}$`, while the supplied CRD
snapshot only requires a nonempty string. An existing User with a callsign
outside the package pattern fails model validation during the tak-operator scan.
Check the installed CRD and existing User values against this package before deployment;
the tak-operator does not rewrite Core-owned callsigns.
They unblock schema-based resource readers and binding lifecycle design.
Production authorization, credential selection, and activation still need the contracts listed below.
Do not treat every Core boundary as missing, or infer credential approval from user approval alone.

## Supplied schema

Current source: [Core CRDs at `f34aef83`](https://github.com/opendefence/core/blob/f34aef83d5db838ad8d2f28ea2fa9af7147510e9/manifests/crds/crds.yaml).
This revision matches library version `0.2.2+261011` and includes `Integration`.
Run `task --yes core:crds` to install the six CRDs without the core-operator.
The local `task up` runs this step before it deploys the integration package.
API: `platform.opendefence.fi/v1alpha1`; each CRD serves and stores this version.

The earlier [opendefence_core_crds.yaml](../../opendefence_core_crds.yaml) remains a historical input.
Its SHA-256 is `105bede6c1dd9f77c9effb6d8525d5882822a6ca67c75f14f2f59f64f106a747`.
It contains five CRDs and five Core service-account/RBAC resources.
It does not contain `Integration`.

| Resource | Scope | Supplied contract |
| --- | --- | --- |
| `User` | Cluster | Required `spec.callsign`; optional `approvedAt`, `revokedAt`, `approvalCode`, direct `roleRefs`, and `groupRefs`. Status includes resolved roles/groups, `publicKey`, binding observations, and reconciliation conditions. |
| `Group` | Cluster | Required `spec.name` and `displayName`; optional `parentRef`, `managerRefs`, and `roleRefs`. Status resolves parent, managers, and roles by name and Kubernetes UID. |
| `Role` | Cluster | Required `spec.name` and `displayName`. No permission/action map is included. |
| `Invite` | Cluster | Required `spec.code`; group/role references, `useCount`, and `validUntil`. This is an enrollment resource, not a client-download grant. |
| `UserBinding` | Namespaced | Required `spec.userRef.name`. The integration creates one binding per User in its own namespace and writes the `Synced` condition when provisioning is complete. Core watches bindings; it does not admit or reconcile them. |
| `Integration` | Cluster | Required `spec.displayName` and `version`. Optional product information, text metadata, extra roles, and declared ingress/egress. The core-operator manages the declared extra Role resources. Network policy is stored but not enforced. |

All six CRDs expose a status subresource, generic conditions, and nullable `status.observedGeneration`.
The TAK package registers `Integration/integration-tak`.
It declares no extra roles because approved Users and projected `superadmin` already determine TAK permissions.
The Integration version follows this repository's package version.
The Integration status does not contain certificate identities, renewal state, or destination acknowledgements.
The tak-operator does not use Integration status to grant User access.
Reference inputs identify objects by resource name. Resolved User and Group references also carry Kubernetes UIDs.
The published model describes `User.status.roles` as direct resolved roles.
The project owner now defines these User status roles and memberships as the trusted integration projections.
Core must publish effective roles in `User.status.roles` before group-derived permissions can reach integrations.
The tak-operator uses the projected roles and does not calculate roles from `spec.roleRefs`.
It treats `user` as implied for each approved User.
It maps `superadmin` to TAK `ROLE_ADMIN`.
It maps other approved Users to TAK `ROLE_READONLY`.
One User identity owns one UserBinding and a TAK record for each accepted certificate.
Each record receives the role and groups from `User.status.roles` and `User.status.groups`.
Several certificate identities can use the same callsign during rollover.
The tak-operator selects records by User UID and exact certificate fingerprint.
Each certificate is identified by fingerprint and issuer plus serial.
Certificates do not grant a role or group membership.
The core-operator refuses deletion after `spec.approvedAt` is set.
Revoke an approved User with `spec.revokedAt`.
Keep the revoked User as a permanent revocation record.
The tak-operator requests removal of all accepted credentials for that User.
It also removes the User's TAK role and groups.
It keeps the UserBinding while the revoked User remains.
A native projector removes only the TAK record for a certificate that leaves the accepted set.
It keeps the other certificate records and their projected permissions.
It must not grant a role by callsign or certificate CN.
It requires `status.observedGeneration` to match the User generation before it requests a TAK role.
Tests can patch the User status through the CRD without a running core-operator.
The tak-operator does not mark a UserBinding ready until TAK confirms the complete credential and permission projection.
The `JniProjector` applies the native records through the tak-operator's JNI bridge.
It verifies roles, fingerprints, and all three native group lists after writes.
It leaves bindings unready with `EnforcementUnverified` until strict admission is verified.
The supplied RBAC belongs to the Core service account. It does not grant the TAK integration access.
The integration still needs its own resource and namespaced binding/status permissions.

## Remaining semantic contracts

| Contract | Established rule or supplied field | Decision still required |
| --- | --- | --- |
| Identity | Use an immutable User UUID in a canonical `urn:uuid:<uuid>` URI SAN. Treat the CN as display text. Keep callsign mutable and outside the certificate. The current CRD has no separate identity UUID field. | Confirm the persistent UUID source, restore behavior, and CSR validation. The API draft uses compact Base64URL paths; the CRD does not define that path encoding. |
| Effective access | Integrations trust `User.status.roles` and `User.status.groups`. Approved Users have the implied `user` role. The tak-operator maps `superadmin` to TAK admin. | Core must publish effective group-derived roles and memberships in User status. The current model descriptions still say direct roles and groups. Define freshness across related Group and Role changes. |
| User approval and revocation | `User.spec.approvedAt` marks user approval; `revokedAt` marks user revocation. | Define trusted writers and the current authorization/freshness rule. User approval does not identify an approved certificate purpose or generation. |
| Credential inventory | Core owns approval, purpose, validity, history, and revocation. The new handoff proposes one Core-owned User annotation with a versioned array of accepted public records. The integration provisionally reads `platform.opendefence.fi/accepted-credentials`. Each record has a leaf SHA-256, serial, issuer ID, and validity times. | Confirm the annotation key and wire schema. Supply purpose, predecessor, deadline, and compromised or superseded states. `User.status.publicKey` cannot supply this inventory. |
| Integration certificate identity | Installing an integration authorizes one instance. `Integration` is now cluster-scoped. The certificate handoff proposes a separate identity and Core-owned public credential status, but this release has no such fields. Do not create a service User or UserBinding for it. | Define the identity SAN, named credential requests, connection purposes, credential status ownership, and destination acknowledgements. Core or the issuer must send an authenticated renewal notice. Keep the old keypair until all destinations acknowledge the replacement. TAK needs the current installed-identity inventory for 8443 and 8089. |
| Key delivery | A ZIP contains exactly one approved exportable keypair. Main and TAK-only credentials can both be accepted by TAK. | Define permission to reuse an exportable main key. Define restart-safe TAK-only issuance for CSR-held main keys. Approval must constrain automatic renewal. |
| Namespace access | Bindings belong in the integration namespace. TAK-only material remains separate from main user material under the handoff. | Name credential namespaces, Secret references/readers, retention, cleanup, and access after revocation. The CRDs and Core RBAC do not supply this contract. Do not rely on cross-namespace owner references. |
| UserBinding readiness | Scope, integration spec/status ownership, `spec.userRef.name`, and `Synced` are now specified. Status has generic conditions and `observedGeneration`. | Agree how readiness binds the current User UID, permission/credential revision, and applied messaging/API revisions. Binding generation alone does not cover changes to referenced objects. |
| Activation observation | Exact approved successor use triggers Core's mapped predecessor revocation. No manual acknowledgement or download event is sufficient. | Supply a trusted evidence interface, purpose/generation fields, durable event identity, idempotency, freshness, and recovery scan. These CRDs contain no activation record. |
| HTTP authority | Verified mTLS identity and fresh Core authorization protect self-service delivery. Admin alone cannot extract another user's key. | Define trusted header names, certificate-generation identity, freshness/deadlines, spoofed-header removal, and direct-service access controls. |
| UI | Use the Core session and navigation model. | Supply the module-federation, user-management, and session contracts. Keep fixtures separate from upstream acceptance. |

### Readiness limits

The supplied `UserBinding.spec` refers to a User by name only.
A User replacement, group move, role edit, or credential change can leave that binding spec unchanged.
Do not treat a matching binding `observedGeneration` as proof that those inputs are current.
Define the applied-state contract before reporting production readiness; do not invent new CRD status fields locally.

`User.status.bindings` records binding name, namespace, UID, and a `synced` boolean.
It does not carry the desired permission/credential revision, server applied revisions, or an authorization deadline.
That summary alone cannot authorize downloads or establish current strict server enforcement.

## Prototype evidence

The local Core prototype was inspected at revision `5278b09e9776020b48ccba17f51d7d93e4378d2c`.
The supplied CRDs now provide the schema reference; the older prototype is historical evidence.
Its success check did not establish that a condition described the latest desired revision.
Do not copy prototype runtime assumptions into the production implementation.

## Next integration slice

Use the shared package for readers of User and namespaced UserBinding resources.
Read projected roles and groups from User status.
Preserve the distinction between direct references, resolved references, and effective permissions.
Keep Invite redemption in Core and use integration-specific RBAC.
Test optional or missing status and replacement of a referenced object with a new UID.
This schema work does not need a guessed credential API.
Runtime implementation remains subject to the I2 model gate and its corresponding semantic contracts.

## Independent implementation slice

The [pure package renderer](packages.md) is implemented without these adapters.
Use explicit in-process inputs and fixture credentials.
Do not label fixture inputs as the Core API.
Keep construction pure and bounded.
Validate certificate/key pairing and archive paths.
Build XML with an XML library.
Use `cryptography` for PKCS#12 and its Java truststore serializer.
Keep the stable internal filenames independent of callsign and credential generation.
Keep credential-update delivery disabled until client compatibility evidence exists.

This slice does not enable production downloads.
Readiness still requires current authority and verified application of the full approved credential set.
Issuance, operator reconciliation, live grants, and activation reporting require the corresponding contracts above.
I2 remains partial until the required adapters and workloads are implemented.
