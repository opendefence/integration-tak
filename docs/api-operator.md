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
The operator currently reconciles bindings without starting JNI.
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
Bytes already authorized or sent cannot be recalled.

Exclude the grant Secret from backups. Restore it as a new empty Secret.
The document binds its Kubernetes UID, so a recreated Secret ignores old grants.
Do not restore `grants.json` in place into the same Secret UID; that would restore deletion history incorrectly.
Normal Pod restarts and multiple API replicas retain the current shared document.
No private keys or ZIP bytes are stored in it.

## Binding lifecycle

Typed readers use `lib-opendefence-core==0.2.1+261010` for the supplied
`platform.opendefence.fi/v1alpha1` User, Group, Role and UserBinding shapes.
Only fields in that versioned model are interpreted as projection inputs; the models
do not turn Core status into an effective permission grant.
The package narrows callsigns beyond the supplied CRD snapshot; validate installed
Core CRDs and existing User objects against the pinned package before deploying.
The operator scans every ten seconds, with serial reconciliation and no fork.
One User incarnation gets one deterministic binding name derived from its Kubernetes UID.
The namespaced binding refers to `spec.userRef.name` and has a cluster-scoped User owner reference.
Recreating a User with the same name produces a different binding.
Kubernetes garbage collection owns removal of the old binding.

The operator preserves foreign bindings and unrelated status conditions.
It clears `Synced` before publishing changed input revisions.
Input revisions cover User identity/spec and relevant status, plus Group and Role identities/specs.
User binding observations are excluded to prevent feedback loops.
Projection failure, stale readback, authority failure, or a concurrent Core edit prevents `Synced=True`.
The operator re-reads Core resources before publishing a successful status.

Integration-owned annotations record User UID, input revision, applied revision and receipt deadline.
They use the `integration.opendefence.fi` prefix.
These annotations are an internal projection record, not a new Core CRD or an agreed Core authorization contract.
Binding `observedGeneration` alone cannot establish freshness of referenced resources.
Neither API delivery nor a production adapter may authorize from the `Synced` Boolean alone.
A Core outage can prevent status writes; the live authority boundary and receipt deadlines must still deny delivery.

## Remaining production adapters

The Python `Authority` and `Projector` interfaces are internal testable seams.
They do not define Core HTTP paths, identity headers, credential resources, or server wire schemas.
See [Core contracts](core-contracts.md) and [server changes](tak-server-change-handoff.md).

Implement these inputs when their versioned contracts are available:

1. Verified mTLS identity and fresh Core self-service authorization, including exact credential purpose, User approval/revocation, effective TAK entitlement and high-OPSEC delivery policy.
2. Approved multi-generation inventory, export permission and already-issued material. Core retains issuance, renewal approval and predecessor revocation ownership.
3. Strict management capability through one operator JVM, with serialized mutations, complete approved-set projection, uncertain-write readback and matching messaging/API receipts.
4. Durable completed-authentication observations for the exact approved successor. Rotation status remains Core-owned.
5. Trusted ingress routing, header stripping, direct-service isolation, and compatible TLS policy for protected and certificate-free routes.

## Kubernetes composition

`kubectl kustomize k8s/integration` renders the integration workloads, scoped RBAC,
the grant Secret and an internal Service. For an OpenDefence stack installation,
`kubectl kustomize k8s/stack` also includes the TAK Server base from a sibling
`../tak-server` checkout. This repository owns that composition and the operator's
Ignite ingress policy; TAK Server owns the reusable StatefulSet, Services, PVC,
bootstrap Job and server configuration.
The API and operator use separate service accounts and Deployments.
Both run without root, with a read-only root filesystem and a bounded temporary volume.
The operator uses one replica and Recreate updates.
API TCP probes establish process reachability only; they do not establish current user authorization or production TAK readiness.

Check out the versioned TAK Server repository beside this one. Provision the
database and required identity/password Secrets in `integration-tak` as described
in [its Kubernetes guide](../../tak-server/k8s/README.md). Create the namespace,
apply `k8s/stack/schema` and wait for `tak-schema-5-8-84` to complete, then grant
the runtime database role before applying `k8s/stack`. The schema Job is separate
so the installer can require its success before starting server Pods.
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
