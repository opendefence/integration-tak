"""Inspect the integration without starting a JVM."""

import argparse

from odintegration_tak import __version__


def main() -> None:
    """Print bootstrap help or the package version."""
    parser = argparse.ArgumentParser(description="OpenDefence TAK integration (foundation only).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args()
    parser.print_help()
