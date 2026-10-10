# Integration TAK implementation status

## Stage and model

I0 is code-complete and locally verified on ARM64.
I1 is incomplete. Binary probing is deferred by the user's explicit instruction.
I1 used the user-confirmed `gpt-6-astra` / `xhigh` setting.
Confirmation: "Switched; resume I1".
Deferral: "Skip the binary probing for now."
The integration is not release-ready.
The next independent coding slice is I2 package construction, which requires `gpt-6.1-sol` / `high`.
This slice does not close I1 or authorize production authentication.
I0 used the user-confirmed `gpt-6.1-sol` / `medium` setting.
The session cannot verify model runtime metadata or switch the active model.

## Checkpoint and sources

- Branch: `feat/i0-foundation`.
- Implementation HEAD before this checkpoint: `d351aad`.
- Completed commits: `a339af8` (tooling), `b8113f6` (separate images and CI), `d351aad` (I0 checkpoint).
- Unfinished implementation files: `spikes/i1/BinaryProbe.java` and `spikes/i1/probe.sh`; untracked and parked with their README.
- Supplied handoff and OpenAPI files remain untracked and unchanged.
- Prototype tooling: `b332e527c7dedf5e3f0a972b792c7d697dcace6b`.
- Reviewed shared CI actions: `1786399bf62c2b691f1e8fb9dcfc7a0be72a2846`.
- OpenAPI input: `1.0.0-draft.5`; seven operations under `/integrations/tak/api/v1`.
- Server handoff: `../tak-server/tak-server-implementation-handoff.md`.
- Core handoff read: `/Users/rambo/Downloads/rasenmaeher-core-architecture-handoff.md`, dated 2026-10-10.
- Additional sources: both user-supplied shared conversations. See `docs/i1-findings.md` for links and provenance.
- Missing file: `tak-package-audit-and-redesign-plan.md` revision 5. Its shared-conversation link does not provide the full file contents.
- Open Core contracts: `docs/core-contracts.md`.

Ponytail full and Caveman were restored before I0 and I1.
Local skill SHA-256 values:

- Ponytail: `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2`.
- Caveman: `0bf09a0a9a017d004a81d4b693e5a2d830e1a28230a5885df773e1ed9c0571cc`.

The handoff pins source revisions `9b58c1ffb790c075ca32e70a89cf1d80588f4abf` and
`2e08b9177c07bb7249a8a2d1a6758e5db281d002`, respectively.
Installed source revisions remain unverified.
Ponytail review and audit instructions were loaded from plugin version `5.1.0`.
Ponytail review found no remaining defects in the completed slices.
The final cumulative audit remains an I5 task.

I1 also used investigate-first to separate static evidence from runtime proof.
Ponytail review found no defects in the documentation slice.
It checked source provenance, evidence limits, and pending decisions.
The documentation hooks and `git diff --check` passed.
Package tests were not repeated because this slice changes documentation only.

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

I1 read the candidate 5.8.84 schemas and bytecode.
The inspected X509 path matches a stored fingerprint or account identifier.
The contact update path replaces a contact record; the CoT path can replace it again.
These are static findings. See `docs/i1-findings.md` for method offsets and limits.
The draft probe verified four fixture chains, then failed Java compilation.
No authentication or contact assertion ran.
No approved-set, rotation, restart, CoT, HTTPS, or client compatibility check passed in I1.
Binary work stopped when the user deferred it.

## Runtime tuple and owned resources

The I0 native check uses prototype TAK `5.8-RELEASE-69`, Java `17.0.20.1+1`,
PyJNIus `1.7.0` and Linux Python `3.14.8`.
This check does not prove remote server compatibility.
The server project's 5.8.84 candidate was inspected but remains runtime-unverified for this integration.
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
I1 added no images or persistent containers.
Temporary I1 evidence is in `/private/tmp/integration-tak-i1/`.
The candidate image/JAR/WAR checksums are in `docs/i1-findings.md`.
The probe container used no network and removed its fixture keys on exit.

## Next action

Keep binary probing deferred until the user requests it again.
Complete the I2 model gate before the independent package-renderer slice.
Keep production Core adapters and TAK acceptance readiness blocked.
Obtain the missing redesign file, versioned Core contracts, and final server base contract.
The proposed strict approved-fingerprint server change needs an adoption decision before implementation.
Return to I1 for the deferred binary and live authentication evidence.
Do not mark I1 complete or weaken the approved-fingerprint requirement.
