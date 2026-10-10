# Core integration contract decisions

These decisions are required by the integration handoff.
They are not new Core CRDs or an approved wire contract.
The Core working handoff leaves them open.
Keep production adapters blocked until the relevant contract is versioned.

| Contract | Established rule | Decision still required |
| --- | --- | --- |
| Identity | Use an immutable UUID as the account key and certificate CN. Callsign is mutable. | Choose the persistent identity source, exact CN encoding, REST normalization, restore behavior, and initial CSR flow. The current API draft uses `metadata.uid` and compact Base64URL output. |
| Effective access | Membership flows upward to ancestors. Roles are the union of direct and effective-group grants. Manager status alone grants no permission. | Supply a shared implementation or versioned conformance contract. Define revision and freshness rules. Include changes caused by group moves and role edits. |
| Credential inventory | Core owns approval, purpose, validity, history, and revocation. Track SHA-256 and issuer plus serial. | Supply an authoritative inventory for all approved main and TAK-only generations. Bind each successor to its predecessor and approval deadline. Define compromised and superseded states. |
| Key delivery | A ZIP contains exactly one approved exportable keypair. Main and TAK-only credentials can both be accepted by TAK. | Define permission to reuse an exportable main key. Define restart-safe TAK-only issuance for CSR-held main keys. Approval must constrain automatic renewal. |
| Namespace access | TAK-only material is separate from main user material. | Name the namespaces and permitted Secret readers. Define references, retention, cleanup, and access after revocation. Do not rely on cross-namespace owner references. |
| UserBinding | The integration owns the TAK projection. Stale success does not establish readiness. | Agree spec/status writers, scope, identity reference, observed revision, and readiness conditions. Core's suggestion that integrations write their own status is not a final schema. |
| Activation observation | Exact approved successor use triggers Core's mapped predecessor revocation. No manual acknowledgement or download event is sufficient. | Define the trusted writer, authenticated connection evidence, purpose/generation fields, persistent event identity, idempotency, freshness, and recovery scan. |
| HTTP authority | Verified mTLS identity and fresh Core authorization protect self-service delivery. Admin alone cannot extract another user's key. | Define trusted header names, certificate-generation identity, freshness/deadlines, spoofed-header removal, and direct-service access controls. |
| UI | Use the Core session and navigation model. | Supply the module-federation, user-management, and session contracts. Keep fixtures separate from upstream acceptance. |

## Prototype evidence

The local Core prototype was inspected at revision `5278b09e9776020b48ccba17f51d7d93e4378d2c`.
Its `User` is cluster-scoped.
Its `UserBinding` is namespaced and refers to the User by object name.
Its integration writes a `Synced` condition.
Its current success check does not establish that the condition describes the latest desired revision.
It does not supply the required multi-generation credential inventory or trusted activation contract.
Do not copy these models into the greenfield production implementation.

## Independent implementation slice

The package renderer can be implemented before these adapters.
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
The I2 model gate still applies before package implementation starts.
