# OpenDefence TAK integration

This repository contains the `odintegration_tak` project.
The project is at the foundation stage.
The operator and delivery API are not implemented yet.
See `docs/implementation-status.md` for stage gates and blockers.

## Development

Use Python 3.14 and uv.
Run `uv sync --locked` to install the development environment without JNI.
Run `uv run --locked prek install` to install the Git hooks.
Run `uv run --locked prek run --all-files` to check the files.
Run `uv run --locked pytest` to test the package.
Run `uv build --no-sources` to build the distributions.
Run `uv run --locked odintegration-tak --help` to inspect the CLI.

Install the operator extra only in an environment with Java 17 and JNI headers.
Use `uv sync --locked --extra operator` in that environment.
Package imports, help and version output must not start a JVM.

## Source foundation

Tooling is adapted from `pvarki/python-tak-operator` at
`b332e527c7dedf5e3f0a972b792c7d697dcace6b`.
The implementation is greenfield.
The prototype's Core resource models and server deployments are not copied.
