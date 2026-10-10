"""Verify CLI metadata and imports without Java."""

import subprocess
import sys
from importlib.metadata import version

import pytest

from odintegration_tak import __version__


@pytest.mark.parametrize("arguments", [[], ["--help"], ["--version"]])
def test_cli_without_java(arguments: list[str]) -> None:
    script = """
import importlib.abc
import sys

class RejectJava(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'jnius', 'jnius_config'}:
            raise AssertionError('CLI attempted to load Java')

sys.meta_path.insert(0, RejectJava())
import odintegration_tak
from odintegration_tak.console import main
main()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, *arguments], capture_output=True, text=True, timeout=10, check=True
    )
    expected = __version__ if "--version" in arguments else "foundation only"
    assert expected in result.stdout
    assert not result.stderr


def test_distribution_version() -> None:
    assert version("odintegration_tak") == __version__
