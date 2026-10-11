# Delivery API and binding operator

This I2 slice implements the seven HTTP operations and integration-owned UserBindings.
It does not connect production Core authorization or the strict TAK management extension.
The supplied CRDs define resource shapes, but not these semantic interfaces.
Default HTTP authority returns `503 authority-unavailable`.
Default projection writes `Synced=False`, reason `AuthorityUnavailable`.
No account or credential is created by these defaults.

## Entry points

Run the workloads in separate processes and containers:

```sh
opendefence-integration-tak api --namespace integration-tak --public-origin https://your-installation.example
opendefence-integration-tak operator --namespace integration-tak
```

The API listens on port 8080. It contains no JNI or Java runtime.
Kubernetes configuration comes from the service account or the selected kubeconfig.
In-cluster requests re-read the projected service-account token before each request.
Missing or empty projected tokens fail without sending the initial token as a fallback.
Kubeconfig authentication remains owned by Cloudcoil.
The operator extra remains separate and pins PyJNIus to `1.7.0`.
Imports and help/version commands do not start a JVM.
The operator starts one TAKCL JVM when its workload starts.
It checks the remote user manager during each scan.
It registers an optional dedicated administrator certificate through JNI.
The operator still reports `Synced=False` because strict projection and Core authority are unavailable.
Build the current local operator image with the selected TAK 5.8.92 server image:

```sh
podman build --target operator --build-arg TAKSERVER_IMAGE=localhost/tak-server:release-92 -t localhost/opendefence-integration-tak-operator:i2-jni .
```

Use the selected server image and JAR as one tested tuple.
The Dockerfile default still points to the older 5.8.69 artifact.
Do not use the legacy scalar fingerprint operation as a substitute for strict projection.

## HTTP contract

[The tracked OpenAPI draft](package-api.openapi.json) is a copy of the supplied `1.0.0-draft.5` contract.
Source SHA-256: `d7c9b7ba88e1560c0dfac3d28760167e3003611f0bb86d5c215edc351ceb34aa`.
Formatting may differ. The original local input remains unchanged.
Its old package name and server-version references are historical; the current package is `opendefence_integration_tak`.

Routes use `/integrations/tak/api/v1`:

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/package-profiles` | Return the five implemented profiles after live authentication. |
| GET | `/users/{userId}/client-packages/{profileId}` | Return package readiness and metadata without provisioning. |
| GET | `/users/{userId}/client-packages/{profileId}/content` | Render one approved, already-issued keypair. |
| POST | `/users/{userId}/client-packages/{profileId}/download-grants` | Create a bounded, reusable download capability. |
| GET | `/download-grants/{grantId}` | Return owned metadata without the token or download URL. |
| DELETE | `/download-grants/{grantId}` | Delete an owned grant; absent grants are idempotent. |
| GET, HEAD | `/downloads/{grantId}/{fileName}` | Redeem an exact grant without requiring a browser certificate. |

UUID input accepts canonical text or canonical compact Base64URL. Responses use compact encoding.
The Core adapter must supply the agreed immutable identity. This normalization does not settle its storage source.
Only the authenticated user's package is accessible. An administrator header does not change ownership.
The application does not read identity headers. `Authority.authenticate` must implement the agreed trusted boundary.
Authentication and current policy checks run before conditional metadata responses.
Callsign changes alter metadata ETags, but preserve package input revisions.

Full packages use the existing bounded package builder.
Current authority and matching messaging/API strict revisions are required for readiness.
The exported leaf must match the approved generation's exact SHA-256 and expiration.
Rendering uses at most four worker threads per API process; saturation returns `429`.
Delivery rechecks current authorization and immutable inputs after rendering.
Sensitive responses use `no-store`, `no-referrer`, and `nosniff`.
Request access logging and proxy-header interpretation are disabled.
Unexpected adapter errors return a sanitized `503`; their messages and tracebacks are not logged.
Ingress and infrastructure logs must also exclude query values.

Credential-update variants remain disabled. Valid update selectors return `409 update-not-supported`.
Malformed selector combinations return `422`.
No profile is marked device-validated. No rotation confirmation is inferred from a download.

## Grants and storage

The installer creates `tak-download-grants`, an Opaque Secret in the integration namespace.
The API service account can get and update only this named Secret.
It cannot read credential Secrets or issuer keys with the supplied RBAC.

The Secret contains one bounded, versioned JSON document, encoded in `data[grants.json]`.
Each grant uses an independent random 128-bit ID and 256-bit token.
Only the SHA-256 token hash is stored. Raw tokens appear only in the creation response URL.
The lifetime is at most 300 seconds, capped by current authority, authorizing credential, and exported leaf deadlines.
Each document holds at most 256 grants, with at most eight active grants per User.
Creation removes expired entries. The document is capped at 600,000 decoded bytes.
Kubernetes `resourceVersion` compare-and-swap updates enforce bounds across replicas.
Conflicts retry four times, then return a retryable `503`.

Each grant binds the authorizing generation, delivered generation, profile and immutable material revision.
Redemption rechecks the authorizing generation, current policy, current strict projection, material, expiry and grant existence.
A default credential change invalidates an old grant; the API never substitutes the successor.
Full packages can render a fresh callsign without invalidating the grant.
Invalid, absent, expired, deleted and denied capabilities return uniform `404` responses.
Authority or storage outages return `503`.
GET and HEAD do not consume grants.
A final grant read prevents release after a deletion observed before that release decision.
The API rechecks authorization and package deadlines after the final storage read.
Bytes already authorized or sent cannot be recalled.

Exclude the grant Secret from backups. Restore it as a new empty Secret.
The document binds its Kubernetes UID, so a recreated Secret ignores old grants.
Do not restore `grants.json` in place into the same Secret UID; that would restore deletion history incorrectly.
Normal Pod restarts and multiple API replicas retain the current shared document.
No private keys or ZIP bytes are stored in it.

## Binding lifecycle

Typed readers use `lib-opendefence-core==0.2.2+261011` for the supplied
`platform.opendefence.fi/v1alpha1` User and UserBinding shapes.
Only fields in that versioned model are interpreted as projection inputs; the models
do not turn Core status into an effective permission grant.
The package narrows callsigns beyond the supplied CRD snapshot; validate installed
Core CRDs and existing User objects against the pinned package before deploying.
The tak-operator scans every ten seconds, with serial reconciliation and no fork.
If a Kubernetes request fails for one User, the tak-operator continues with the other Users.
It retries the failed User on the next scan.
One User incarnation gets one deterministic binding name derived from its Kubernetes UID.
The namespaced binding refers to `spec.userRef.name` and has a cluster-scoped User owner reference.
Recreating a User with the same name produces a different binding.
Kubernetes garbage collection owns removal of the old binding.

The tak-operator preserves foreign bindings and unrelated status conditions.
It clears `Synced` before publishing changed input revisions.
Input revisions cover User identity, spec, accepted certificates, and projected status.
They include the User generation and the generation observed by the core-operator.
User binding observations are excluded to prevent feedback loops.
The tak-operator reads roles and groups from `User.status` only.
The accepted certificates identify connections to that User.
Certificates do not grant TAK roles or group membership.
Projection failure, stale readback, authority failure, or a concurrent Core edit prevents `Synced=True`.
The tak-operator re-reads the User CR before publishing a successful status.

Integration-owned annotations record User UID, input revision, applied revision, public applied credentials, and receipt deadline.
They use the `integration.opendefence.fi` prefix.
These annotations are an internal projection record, not a new Core CRD or an agreed Core authorization contract.
Binding `observedGeneration` alone cannot establish freshness of referenced resources.
Neither API delivery nor a production adapter may authorize from the `Synced` Boolean alone.
A Core outage can prevent status writes; the live authority boundary and receipt deadlines must still deny delivery.

## Remaining production adapters

The Python `Authority` and `Projector` interfaces are internal testable seams.
They do not define Core HTTP paths, identity headers, credential resources, or server wire schemas.
See [Core contracts](core-contracts.md) and [server changes](tak-server-change-handoff.md).
The package exporter now checks the User UUID in the leaf URI SAN.
Delivery compares Core's selected public credential record with the certificate used for export.
The tak-operator reads the provisional accepted-credential User annotation and includes it in its input revision.
It passes only current, valid public records to a projector. Missing or malformed metadata leaves the UserBinding unready.
It passes an empty set when metadata is invalid or the User is unapproved, revoked, or deleting.
The projector uses this empty set to remove old access.
It passes the last verified applied records to the projector, including expired records.
It writes the new applied set only after a verified projection receipt.
It logs a malformed applied record and asks the projector to recover from TAK state.
It replaces the record only after verified readback.
It rejects a projection receipt that stays valid beyond the earliest accepted certificate expiry.
The `JniProjector` creates one native record for each accepted certificate.
Its identifier is `od-user-<User UID>-<leaf SHA-256>`.
The tak-operator reserves this identifier prefix for its records.
It converts the fingerprint to TAK's uppercase, colon-separated SHA-256 format.
It applies the User's TAK role and projected group names to every current record.
It replaces all group lists, including directional groups, with the projected state.
It removes records for credentials outside the accepted set.
It clears native records for unapproved, revoked, or stale User state.
It scans the reserved records after a restart to recover partial writes.
It rejects records with an unexpected fingerprint or a password.
Callsign changes do not change these identifiers or certificate records.
The current native file-auth model still permits identifier fallback during authentication.
Native readback therefore leaves `Synced=False` with `EnforcementUnverified`.
Strict admission and readback from both TAK JVMs remain separate verification work.

## CoT connection removal

The tak-operator uses the JNI connection lookup and removal code from
[python-tak-rmapi PR #155](https://github.com/pvarki/python-tak-rmapi/pull/155).
The source commit is `ed6a8f14656a03d4599aa923d1c7a5901cb0dde7`.
The port reads live subscriptions from each messaging node.
It reads the TLS certificate through `GroupManager.getUserByConnectionId`.
It selects connections by the exact SHA-256 fingerprint.
It calls `deleteSubscription` on the originating node.
Each service proxy has the legacy five-second RPC timeout.
A failed connection or node does not prevent attempts on the remaining connections and nodes.
The existing native registration calls still use the TAKCL user manager.
The five-second service timeout does not bound those calls or the full scan.

The tak-operator requests a session refresh after certificate, role, or group changes.
It attempts the kick even if a native registration write fails.
It retains failed kicks for retry when the native certificate record is already absent.
Unchanged successor certificates keep their sessions when a predecessor is removed.
After a tak-operator restart, each managed certificate gets one session refresh.
This refresh recovers permission changes whose native write completed before a crash.
An unchanged projection does not request another refresh in the same process.

The regular ten-second scan also checks reconnects.
It removes expired certificates and certificates without an exact native fingerprint registration.
An identity that TAK has not yet supplied is checked again on a later scan.
The scan runs after a Core scan failure as well.
Core owns credential revocation. This port has no separate issuer denylist.
A retained native registration is not evidence of current Core approval.
Failed Core reads or native writes can therefore delay revocation handling.

The legacy watcher also used subscription notifications and a separate supervised process.
This port uses the existing serial tak-operator loop.
It does not claim the legacy watcher's 17–85 ms timings.
Slow Core or JNI calls can extend the interval between connection scans.
The local legacy evidence is in
`~/devel/pvarki/docker-rasenmaeher-integration/support-reports/tak-cot-anonymous-fallback-20260913/evidence/guard-results.txt`.
That run used TAK 5.8-RELEASE-69 and one messaging node.
It closed 29 invalid reconnects and preserved two valid control connections.
All 29 early CoT messages arrived before disconnection.
The evidence covers TLS 1.2, TLS 1.3, resumed sessions, and watcher recovery.
It does not validate this port against TAK 5.8.92.
Unit tests cover the port's certificate selection, retries, permission refresh, and node routing.
Disconnection occurs after authentication. It does not establish strict admission.
UserBindings remain `Synced=False` with `EnforcementUnverified`.

## Production adapter inputs

Implement these inputs when their versioned contracts are available:

1. Verified mTLS identity and fresh Core self-service authorization, including exact credential purpose, User approval/revocation, effective TAK entitlement and high-OPSEC delivery policy.
2. Approved multi-generation inventory, export permission and already-issued material. Core retains issuance, renewal approval and predecessor revocation ownership.
3. Strict management capability through one operator JVM, with serialized mutations, complete approved-set projection, uncertain-write readback and matching messaging/API receipts.
4. Durable completed-authentication observations for the exact approved successor. Rotation status remains Core-owned.
5. Trusted ingress routing, header stripping, direct-service isolation, and compatible TLS policy for protected and certificate-free routes.

The integration operator uses a dedicated client certificate for TAK's port 8443 REST API.
The local Zarf flavor creates `tak-integration-admin` through cert-manager and `public-issuer`.
The local administrator bootstrap still uses its fixed CN. The integration identity SAN profile is not defined yet.
Supply `tak-integration-admin` in the integration namespace for a production deployment.
Use `integration-tak-admin` as the certificate CN.
Store `tls.crt`, `tls.key`, and `ca.crt` in the same Secret.
The operator mounts these files with group-only access to the private key.
The delivery API Pod does not mount this Secret.
The operator registers the certificate as an administrator through JNI and verifies the stored fingerprint and role.
It rejects a different fingerprint under the same CN to avoid replacing an existing administrator.
Ensure that TAK also trusts the certificate for TLS client authentication before using the REST API.
In strict mode, bind the certificate to the installed integration identity. The current TAK candidate pins its exact public leaf through `tak-integration-admin`; no second certificate approval is required.
Issue the certificate from a CA in TAK's client truststore.
Core or the certificate issuer must send an authenticated notice before the operator adopts a renewed certificate.
The notice must identify the installed integration, trusted issuer, new certificate fingerprint, and Secret revision.
The renewal flow must retain the old keypair until the operator verifies the new administrator fingerprint and a new 8443 mTLS request.
The operator must reject a notice that does not match the renewed Secret, trusted issuer, or installed integration.
Production still needs the notice transport, issuer trust, TAK trust activation, overlap, and failure rules before the operator can replace the pinned fingerprint.
The local operator polls the projected Secret. This poll does not implement the production renewal notice.
Run `task --yes smoke` to verify local TLS authentication and administrator access after bootstrap.
Keep this management identity separate from user credentials and the delivery API workload.

## Kubernetes composition

`kubectl kustomize k8s/integration` renders the integration workloads, scoped RBAC,
the grant Secret and an internal Service. For an OpenDefence stack installation,
`kubectl kustomize k8s/stack` also includes the TAK Server integrated overlay from a sibling
`../tak-server` checkout. This repository owns that composition; TAK Server owns the operator's
Ignite ingress policy, reusable StatefulSet, Services, PVC,
bootstrap Job and server configuration.
The API and operator use separate service accounts and Deployments.
Both run without root, with a read-only root filesystem and a bounded temporary volume.
The operator uses one replica and Recreate updates.
API TCP probes establish process reachability only; they do not establish current user authorization or production TAK readiness.

Check out the versioned TAK Server repository beside this one. Provision the
database and required identity/password Secrets in `integration-tak` as described
in [its Kubernetes guide](../../tak-server/k8s/README.md).
Run `task --yes up` for the local cluster and identities.
This repository's Zarf package waits for `tak-schema-5-8-92` and `tak-grants-5-8-92` before it starts TAK Server.
An installation overlay must pin accepted image digests, set the server address,
database endpoint, storage class and real public origin. The checked-in image tags
and settings are local candidates, not a deployable release.
There is no public Ingress or assumed Core ForwardAuth/header configuration.
The current server candidate stops startup in strict mode until its injection exists.
Do not deploy this composition as a production authentication release.

## Validation

Tests use generated RSA/EC material, an explicit fixture authority, ASGI requests and actual Cloudcoil clients over a Kubernetes HTTP fixture.
JSON responses are checked against the tracked OpenAPI schemas.
Tests cover denial, ETags after live authorization, ownership, exact leaf checks, origin validation, bounded rendering, grants, CAS retries, replica sharing, restore UID changes, stale projection, partial failures and binding replacement.
Runtime tests exercise Kubernetes discovery and both CLI workload entry points without a live cluster or JNI.
These tests establish application behavior, not production Core semantics or real TAK enforcement.
Use the separate `package-test` container for Java 17 keytool checks.
