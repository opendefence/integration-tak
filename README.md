# OpenDefence TAK integration

This repository contains the `opendefence_integration_tak` project.
The project contains a client package builder, seven delivery API routes, Secret-backed grants and a UserBinding operator.
The tak-operator uses JNI to apply User roles and groups to each accepted certificate identity in TAK Server.
Production Core authorization and strict TAK projection adapters remain unavailable.
See [API and operator](docs/api-operator.md) for entry points, behavior and exact remaining boundaries.
The OpenDefence stack Kustomization at `k8s/stack` composes these workloads with
the sibling `../tak-server/k8s/overlays/integrated` and creates the TAK Server Pod resources.
See `docs/implementation-status.md` for stage gates and blockers.
See [remaining work handoff](docs/remaining-work-handoff.md) to continue implementation, including possible binary-probe safety blocks.
The `tak-operator` owns integrated strict authentication. See the [remaining work list](docs/remaining-work-handoff.md#integrated-strict-authentication-ownership).
Use the [TAK image handoff](docs/tak-server-change-handoff.md) for gaps that require image changes.
See [package construction](docs/packages.md) and [PKCS#12 export](docs/certificates.md) for the available Python functions.

## Development

Check out `tak-server` beside this repository.
Install Kind, Zarf, kubectl, and Docker or Podman.
Run `task --yes up` with Task 3.53 or newer to start the local Kind cluster and registries.
The task installs the base operators, local TAK database and identities.
It installs the six Core CRDs from a pinned Core revision without starting the core-operator.
The local Zarf flavor issues `tak-integration-admin` for the operator.
It builds and loads the three images, deploys this repository's Zarf package, and checks authenticated TAK HTTPS.
The task uses remote Taskfiles from `opendefence/base` and `opendefence/core`.
Task asks you to trust the remote source on first use if you omit `--yes`.

Use Python 3.14 and uv.
Run `uv sync --locked` to install the development environment without JNI.
This fetches the pinned Core resource model package from the Nexus `pypilocal` index.
Run `uv run --locked prek install` to install the Git hooks.
Run `uv run --locked prek run --all-files` to check the files.
Run `uv run --locked pytest` to test the package.
Run the separate `package-test` image to require Java compatibility checks.
Run `uv build --no-sources` to build the distributions.
Run `uv run --locked opendefence-integration-tak --help` to inspect the CLI.

Install the operator extra only in an environment with Java 17 and JNI headers.
Use `uv sync --locked --extra operator` in that environment.
Package imports, help and version output must not start a JVM.

The package builder exports already-issued material.
It does not authorize delivery or create accounts, keys, or certificates.
Credential-update delivery remains disabled until client tests establish a supported method.

## Kubernetes package

Run this command to check the local package:

```sh
zarf dev lint . --flavor local-dev \
  --set TAK_IMAGE=localhost/tak-server:local \
  --set API_IMAGE=localhost/opendefence-integration-tak-api:i2-http-operator \
  --set OPERATOR_IMAGE=localhost/opendefence-integration-tak-operator:i2-jni
```
Run `task --yes core:crds` to install the `platform.opendefence.fi/v1alpha1` Core CRDs before a manual deployment.
This task does not start the core-operator or change simulated User projections.
Core owns these shared CRDs. The integration package does not include them.
The package registers the cluster-scoped `Integration/integration-tak` resource.
It declares product information and intended network access.
It declares no extra roles; the tak-operator still trusts User role and group projections.
The Core library is pinned to `0.2.2+261011`.
This Integration schema has no certificate or renewal fields yet.
The local task builds and loads the images into Kind.
Run this command to redeploy the local package after its prerequisites are ready:

```sh
zarf dev deploy --connected --flavor local-dev --components integration-local-dev,tak-schema,tak-grants,tak-server \
  --create-set TAK_IMAGE=localhost/tak-server:local \
  --create-set API_IMAGE=localhost/opendefence-integration-tak-api:i2-http-operator \
  --create-set OPERATOR_IMAGE=localhost/opendefence-integration-tak-operator:i2-jni \
  --deploy-set-variables PUBLIC_ORIGIN=https://local-dev.opendefence.fi \
  --deploy-set-variables TAK_SERVER_ADDRESS=tak.localtest.me
```

The package deploys the schema Job, grants Job, and TAK Server after the integration workloads.
It builds the TAK resources from the sibling `tak-server` checkout.
Run `zarf package create . --flavor local-dev` with the three `--set` image values from the lint command to build a local archive.
Set `PUBLIC_ORIGIN` and `TAK_SERVER_ADDRESS` with `--set-variables` when you deploy that archive.

Both flavors contain the API, tak-operator, and TAK Server images and the relevant overlays.
Image selection is fixed when the package is created.
The package uses the normal TAK Server container image. It does not contain another Zarf package.
Set `PUBLIC_ORIGIN` and `TAK_SERVER_ADDRESS` before deployment.
Set `TAK_IMAGE`, `API_IMAGE`, and `OPERATOR_IMAGE` when you create a production package.
Use a published TAK Server image digest for `TAK_IMAGE`.
Provide the TAK database, passwords, and identities in `integration-tak` before deployment.
For an offline deployment, initialize Zarf before deployment so it can load the bundled images into its registry.
Connected deployments require access to the original image registries.
Do not use this package for production authentication until the Core adapters and strict TAK server checks pass.

## Source foundation

Tooling is adapted from `pvarki/python-tak-operator` at
`b332e527c7dedf5e3f0a972b792c7d697dcace6b`.
The implementation is greenfield.
Core resource models come from the versioned `lib-opendefence-core` package.
The prototype's server deployments are not copied.

## Images

Run `podman build --target api -t localhost/opendefence-integration-tak-api:i2-http-operator .` to build the API.
Run `podman build --target operator --build-arg TAKSERVER_IMAGE=localhost/tak-server:release-92 -t localhost/opendefence-integration-tak-operator:i2-jni .` to build the current operator runtime.
Both images currently print help by default.
Both images run as UID 10001.
The API image contains no Java runtime or JNI dependency.
The default operator image contains Java 17 and the published TAK 5.8.69 `UserManager.jar`.
This JAR is an I0 test input. The sibling release-92 image is available locally but is not published.
Use `--build-arg TAKSERVER_IMAGE=localhost/tak-server:release-92` to build an operator with that JAR.
Pass `--jar-sha256 0fe547c2f4ce05d06a2e9724e0c2837eab0a0ba5be398390bb974b2385ce6f14`
to `docker/check_runtime.py operator` when you check the release-92 image.
The server project must publish an agreed image digest and finish strict authentication before I1 can finish.

Run `podman build --target api-test -t localhost/opendefence-integration-tak-api:test .` to build the container test environment.
Run `podman run --rm localhost/opendefence-integration-tak-api:test` to test it.
Use this command to check each runtime image:

```sh
podman run --rm -i --entrypoint python localhost/opendefence-integration-tak-api:i2-http-operator - api < docker/check_runtime.py
podman run --rm -i --entrypoint python localhost/opendefence-integration-tak-operator:i2-jni - operator --jar-sha256 0fe547c2f4ce05d06a2e9724e0c2837eab0a0ba5be398390bb974b2385ce6f14 < docker/check_runtime.py
```

The operator check starts one JVM and calls a class from the actual JAR.
It does not connect to TAK or prove certificate authorization.

## CI

The shared CI actions are pinned to `pvarki/config-ci-library` revision
`1786399bf62c2b691f1e8fb9dcfc7a0be72a2846`.
Checks run on pull requests and pushes to `main`.
The shared Python setup installs all extras, so its job requires a JDK.
The image job tests the API environment and both runtime targets.

The Zarf build job runs on native AMD64 and ARM64 hosted runners.
Set these repository variables before running the package jobs:

| Variable | Value |
| --- | --- |
| `TAK_SERVER_IMAGE` | Published TAK Server container reference with an `@sha256:` digest. The image must support both architectures. |
| `PUBLISH_ENABLED` | Set to `true` to publish images and Zarf packages after all checks pass. |

The build fails if the TAK Server image reference is missing or malformed.
CI reads the image's `org.opencontainers.image.revision` label.
This label must contain the full 40-character source commit from `opendefence/tak-server`.
CI checks out that commit to use the matching integrated overlays.
The tak-operator build reads `UserManager.jar` from the same TAK Server image that the package contains.
The runtime check compares the JAR hash with that source image before packaging.
CI archives contain the exact locally built API and tak-operator images, read through an OCI image archive.
The build uploads the production archives as `zarf-amd64` and `zarf-arm64` workflow artifacts.
CI rejects archives whose rendered manifests include `platform.opendefence.fi` CRDs.
The `local-dev` flavor is linted but is not published.

Publishing uses `arc-runner-set` and the shared image publisher.
Keep `PUBLISH_ENABLED` unset until registry setup and runtime acceptance are complete.
The publisher requires Docker CLI access and native AMD64 and ARM64 BuildKit services.
The services must be reachable at `buildkit-amd64.buildkit.svc.cluster.local:1234`
and `buildkit-arm64.buildkit.svc.cluster.local:1234`.
Mount readable `ca.crt`, `tls.crt` and `tls.key` files at `/etc/buildkit/tls` on the runner.
The shared action configures remote Buildx and validates these runner inputs.
Use the repository's `GITHUB_TOKEN` for GHCR.
No registry credentials are copied from the prototype.

Zarf publication follows the sibling `base` workflow.
The job downloads the checked archives and signs them with the GitHub OIDC identity.
It publishes them to `ghcr.io/<owner>/integration-tak` with the shared image publisher's tag rules:

| Event | Tags |
| --- | --- |
| Pull request N from this repository | `VERSION-prN-DATE`, `VERSION-prN`, and `N-merge`. |
| Push or manual run on `main` | `VERSION-DATE`, `VERSION`, `VERSION-local`, `main`, and `latest`. |
| Manual run on another branch | The branch name with `/` replaced by `-`, then OCI tag normalization. |

`DATE` is the UTC build time in `YYYYMMDDTHHMM` format.
The `VERSION-local` alias contains the production flavor, as do the other published tags.
Fork pull requests build artifacts but cannot publish or use the publishing runners.
The publish job updates the AMD64 and ARM64 entries in each OCI index in sequence.
The image publisher also receives the package's version tag so connected deployments can pull matching image tags.

Snyk is disabled unless `SNYK_ENABLED` is `true`.
Set `SNYK_ORG` and the `SNYK_TOKEN` secret before enabling it.
