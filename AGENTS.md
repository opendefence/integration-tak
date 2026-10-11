# Agent instructions

- Use the `ponytail` skill for all coding work. Read its `SKILL.md` before editing code.
- Run `uv run --locked prek install` when you set up this repository. This installs the basic pre-commit checks.
- Run `uv run --locked prek run --all-files` regularly. Run it before pushing or creating a PR when those actions are authorized.
- Run `ponytail-audit` before every commit. Fix findings caused by the staged change before committing.
- Write all documentation in Simplified Technical English (STE). Use short, active sentences and consistent terms. Give one instruction per sentence. Preserve exact commands and identifiers.
- Name each operator explicitly in discussion and documentation. Use `core-operator` for the planned Core controller, `tak-operator` for this repository's controller, and `mediamtx-operator` for the MediaMTX controller.
- Keep `platform.opendefence.fi` CRDs out of Kustomize output, Zarf packages, and any future manifest emit path. Core owns these shared CRDs. Integration packages must not install or remove them.
