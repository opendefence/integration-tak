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
See [server change handoff](docs/tak-server-change-handoff.md) for server packaging, strict authentication, and release acceptance work.
See [package construction](docs/packages.md) and [PKCS#12 export](docs/certificates.md) for the available Python functions.

## Development

Check out `tak-server` beside this repository.
Install Kind, Zarf, kubectl, and Docker or Podman.
Run `task --yes up` with Task 3.53 or newer to start the local Kind cluster and registries.
The task installs the base operators, local TAK database and identities.
The local Zarf flavor issues `tak-integration-admin` for the operator.
It builds and loads the three images, deploys this repository's Zarf package, and checks authenticated TAK HTTPS.
The task uses the remote Taskfiles from `opendefence/base`.
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

Run `zarf dev lint . --flavor local-dev --set TAK_IMAGE=localhost/tak-server:local` to check the local package.
Install the `platform.opendefence.fi/v1alpha1` Core CRDs before you test operator reconciliation.
The local task builds and loads the images into Kind.
Run this command to redeploy the local package after its prerequisites are ready:

```sh
zarf dev deploy --connected --flavor local-dev --components integration-local-dev,tak-schema,tak-grants,tak-server \
  --create-set TAK_IMAGE=localhost/tak-server:local \
  --deploy-set-variables PUBLIC_ORIGIN=https://local-dev.opendefence.fi \
  --deploy-set-variables API_IMAGE=localhost/opendefence-integration-tak-api:i2-http-operator \
  --deploy-set-variables OPERATOR_IMAGE=localhost/opendefence-integration-tak-operator:i2-jni \
  --deploy-set-variables TAK_SERVER_ADDRESS=tak.localtest.me
```

The package deploys the schema Job, grants Job, and TAK Server after the integration workloads.
It builds the TAK resources from the sibling `tak-server` checkout.
Run `zarf package create . --flavor local-dev --set TAK_IMAGE=localhost/tak-server:local` to build a local archive.
Use `--set-variables` with the same values when you deploy that archive.

The `production` flavor also includes the TAK Server image and resources.
Set `PUBLIC_ORIGIN`, `API_IMAGE`, `OPERATOR_IMAGE`, and `TAK_SERVER_ADDRESS` before deployment.
Set `TAK_IMAGE` to a published image digest when you create a production package.
Provide the TAK database, passwords, and identities in `integration-tak` before deployment.
The cluster must be able to pull the API and operator images from its registry.
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

Publishing uses `arc-runner-set` and the shared publisher.
Keep `PUBLISH_ENABLED` unset until registry setup and runtime acceptance are complete.
The publisher requires Docker CLI access and native AMD64 and ARM64 BuildKit services.
The services must be reachable at `buildkit-amd64.buildkit.svc.cluster.local:1234`
and `buildkit-arm64.buildkit.svc.cluster.local:1234`.
Mount readable `ca.crt`, `tls.crt` and `tls.key` files at `/etc/buildkit/tls` on the runner.
The shared action configures remote Buildx and validates these runner inputs.
Use the repository's `GITHUB_TOKEN` for GHCR.
No registry credentials are copied from the prototype.

Snyk is disabled unless `SNYK_ENABLED` is `true`.
Set `SNYK_ORG` and the `SNYK_TOKEN` secret before enabling it.
