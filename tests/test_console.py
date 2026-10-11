"""Verify CLI metadata and imports without Java."""

import subprocess  # nosec B404 - Runs the current interpreter for CLI isolation checks.
import sys
from importlib.metadata import version

import pytest

from opendefence_integration_tak import __version__


@pytest.mark.parametrize("arguments", [[], ["--help"], ["--version"], ["api", "--help"], ["operator", "--help"]])
def test_cli_without_java(arguments: list[str]) -> None:
    script = """
import importlib.abc
import sys

class RejectJava(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'jnius', 'jnius_config'}:
            raise AssertionError('CLI attempted to load Java')

sys.meta_path.insert(0, RejectJava())
import opendefence_integration_tak
import opendefence_integration_tak.certificates
import opendefence_integration_tak.packages
import opendefence_integration_tak.api
import opendefence_integration_tak.operator
import runpy
runpy.run_module('opendefence_integration_tak', run_name='__main__')
"""
    result = subprocess.run(  # nosec B603 - Current interpreter and fixed test script/arguments; no shell.
        [sys.executable, "-c", script, *arguments], capture_output=True, text=True, timeout=10, check=True
    )
    expected = (
        __version__
        if "--version" in arguments
        else "OpenDefence TAK integration"
        if not arguments or arguments == ["--help"]
        else "--namespace"
    )
    assert expected in result.stdout
    assert not result.stderr


def test_distribution_version() -> None:
    assert version("opendefence_integration_tak") == __version__
