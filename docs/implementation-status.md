# Integration TAK implementation status

## Stage and model

I0 is code-complete and locally verified on ARM64.
The integration is not release-ready.
Pause before I1, which requires `gpt-6-astra` / `xhigh`.
I0 used the user-confirmed `gpt-6.1-sol` / `medium` setting.
Confirmation: "Switched; resume I0".
The session cannot verify model runtime metadata or switch the active model.

## Checkpoint and sources

- Branch: `feat/i0-foundation`.
- Implementation HEAD: `b8113f6`. This checkpoint is saved in a later documentation commit.
- Completed commits: `a339af8` (tooling), `b8113f6` (separate images and CI).
- Unfinished implementation files: none. Supplied handoff and OpenAPI files remain untracked.
- Prototype tooling: `b332e527c7dedf5e3f0a972b792c7d697dcace6b`.
- Reviewed shared CI actions: `1786399bf62c2b691f1e8fb9dcfc7a0be72a2846`.
- OpenAPI input: `1.0.0-draft.5`; seven operations under `/integrations/tak/api/v1`.
- Server handoff: `../tak-server/tak-server-implementation-handoff.md`.
- Missing inputs: `tak-package-audit-and-redesign-plan.md` revision 5 and `rasenmaeher-core-architecture-handoff(1).md`.

Ponytail full and Caveman were restored before I0.
Local skill SHA-256 values:

- Ponytail: `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2`.
- Caveman: `0bf09a0a9a017d004a81d4b693e5a2d830e1a28230a5885df773e1ed9c0571cc`.

The handoff pins source revisions `9b58c1ffb790c075ca32e70a89cf1d80588f4abf` and
`2e08b9177c07bb7249a8a2d1a6758e5db281d002`, respectively.
Installed source revisions remain unverified.
Ponytail review and audit instructions were loaded from plugin version `5.1.0`.
Ponytail review found no remaining defects in the completed slices.
The final cumulative audit remains an I5 task.

## Decisions and checks

Keep JNI dependencies in the operator extra.
Pin PyJNIus `1.7.0` because `1.8.0` has no Linux artifact.
Use the standard-library CLI for bootstrap help and version output.
Do not copy prototype Core resource models or server deployments.
The images print help by default; neither workload is implemented yet.
Publishing and Snyk remain disabled until their repository variables enable them.

- `uv run --locked pytest`: 4 tests passed on macOS Python 3.14.7; 100% package coverage.
- `podman build --target api-test -t localhost/odintegration-tak-api:test .` and `podman run --rm localhost/odintegration-tak-api:test`: passed on Linux Python 3.14.8; 4 tests; 100% package coverage.
- `uv run --locked prek run --all-files`: passed, including Ruff, strict Pyrefly, Bandit, secret scan and lockfile validation.
- `uv build --no-sources`: built the source distribution and `odintegration_tak-0.1.0-py3-none-any.whl`.
- Wheel inspection: correct `odintegration_tak` modules and CLI entrypoint.
- `podman build --target api` and `podman build --target operator`: passed.
- Help and version checks: passed in both runtime images as UID 10001.
- `docker/check_runtime.py`: API boundary and actual operator JNI call passed. See `docs/evidence/i0-api-runtime.txt` and `docs/evidence/i0-operator-runtime.txt`.
- Commit hooks: pre-commit and conventional-commit checks passed.
- Not run: GitHub/ARC workflows, AMD64 runtime, live TAK authentication, Kind deployment, or client device tests.

## Runtime tuple and owned resources

The I0 native check uses prototype TAK `5.8-RELEASE-69`, Java `17.0.20.1+1`,
PyJNIus `1.7.0` and Linux Python `3.14.8`.
This check does not prove remote server compatibility.
The server project's 5.8.84 candidate remains unverified for this integration.
The final server image and Kubernetes base contract are pending.

- JAR source: `ghcr.io/pvarki/tak-server:5.8.69-260913-slimignite-pr136@sha256:5d250adfdb835e9bfafcce294736041d4fbd32c1ffde7b803f17e28bf2f85a09`.
- JAR SHA-256: `329c3831d0550bef309a7c77ff29c3b398279f973bc9789e0db5c26817ac39c7`.
- API image: `localhost/odintegration-tak-api:i0`, digest `sha256:07f4cf351aa5ad57737b75233be0ccaf0cfee03623c98cb1ba189697963930a7`.
- Operator image: `localhost/odintegration-tak-operator:i0`, digest `sha256:85bf49cce45ec1b1ad5997b176fda29ac36363da5a7faadcf46e9e2a257fcb63`.
- Test image: `localhost/odintegration-tak-api:test`, digest `sha256:3a1b624c6784c941e91c4f3f80a7aeb9c156fe28987298010bb600b2c9a6a43d`.

All base-image indexes are pinned in `Dockerfile`.
Their indexes include AMD64 and ARM64; only ARM64 was run locally.
Owned resources are these local images and temporary build containers.
Smoke containers used `--rm` and have exited.
Existing Podman containers were inspected and preserved.
No Kind context or namespace was selected.
No Kubernetes resources, PVCs or registry publications were changed.

## Next action

Confirm the I1 model setting before starting I1.
Obtain the missing companion documents and agreed Core contracts.
Obtain the server project's pinned image/JAR/base contract.
Then run the exact-binary authentication, callsign and rotation spikes.
Do not invent production Core resource schemas or weaken the approved-fingerprint requirement.
