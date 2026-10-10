# OpenDefence TAK integration

This repository contains the `opendefence_integration_tak` project.
The project contains a client package builder, seven delivery API routes, Secret-backed grants and a UserBinding operator.
Production Core authorization and strict TAK projection adapters remain unavailable.
See [API and operator](docs/api-operator.md) for entry points, behavior and exact remaining boundaries.
The OpenDefence stack Kustomization at `k8s/stack` composes these workloads with
the sibling `../tak-server/k8s/base` and creates the TAK Server Pod resources.
See `docs/implementation-status.md` for stage gates and blockers.
See [remaining work handoff](docs/remaining-work-handoff.md) to continue implementation, including possible binary-probe safety blocks.
See [server change handoff](docs/tak-server-change-handoff.md) for server packaging, strict authentication, and release acceptance work.
See [package construction](docs/packages.md) and [PKCS#12 export](docs/certificates.md) for the available Python functions.

## Development

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

## Source foundation

Tooling is adapted from `pvarki/python-tak-operator` at
`b332e527c7dedf5e3f0a972b792c7d697dcace6b`.
The implementation is greenfield.
Core resource models come from the versioned `lib-opendefence-core` package.
The prototype's server deployments are not copied.

## Images

Run `podman build --target api -t localhost/opendefence-integration-tak-api:i2-http-operator .` to build the API.
Run `podman build --target operator -t localhost/opendefence-integration-tak-operator:i2-http-operator .` to build the operator runtime.
Both images currently print help by default.
Both images run as UID 10001.
The API image contains no Java runtime or JNI dependency.
The operator image contains Java 17 and the pinned prototype `UserManager.jar`.
This JAR is an I0 test input, not the final server compatibility contract.
The server project must provide the agreed image digest and JAR checksum before I1 can finish.

Run `podman build --target api-test -t localhost/opendefence-integration-tak-api:test .` to build the container test environment.
Run `podman run --rm localhost/opendefence-integration-tak-api:test` to test it.
Use this command to check each runtime image:

```sh
podman run --rm -i --entrypoint python localhost/opendefence-integration-tak-api:i2-http-operator - api < docker/check_runtime.py
podman run --rm -i --entrypoint python localhost/opendefence-integration-tak-operator:i2-http-operator - operator < docker/check_runtime.py
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
