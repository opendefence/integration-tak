"""Inspect the integration without starting a JVM."""

import argparse
import asyncio

from opendefence_integration_tak import __version__
from opendefence_integration_tak.operator import run_operator
from opendefence_integration_tak.runtime import serve_api


def main() -> None:
    """Inspect the package or start one separate workload."""
    parser = argparse.ArgumentParser(description="OpenDefence TAK integration.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command")
    api = commands.add_parser("api", help="Run the JVM-free delivery API")
    api.add_argument("--namespace", required=True, help="Integration namespace containing the grant Secret")
    api.add_argument(
        "--public-origin", required=True, help="HTTPS origin used for download URLs and browser mutation checks"
    )
    operator = commands.add_parser("operator", help="Reconcile integration-owned UserBindings")
    operator.add_argument("--namespace", required=True, help="Integration namespace for UserBindings")
    args = parser.parse_args()
    if args.command == "api":
        asyncio.run(serve_api(args.namespace, args.public_origin))
    elif args.command == "operator":
        run_operator(args.namespace)
    else:
        parser.print_help()
