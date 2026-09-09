"""Interactive vault administration; secrets are never command-line arguments."""

import argparse
import getpass
import sys
import warnings
from uuid import UUID

from pydantic import SecretStr

from wisetodo.tools.credentials import ToolCredentialError, ToolCredentials


def main() -> None:
    parser = argparse.ArgumentParser(description="WiseTodo tool credential vault")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("add")
    delete = commands.add_parser("delete")
    delete.add_argument("reference", type=UUID)
    args = parser.parse_args()
    try:
        vault = ToolCredentials()
        if args.action == "add":
            # Never fall back to echoed stdin when a terminal is unavailable.
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                value = getpass.getpass("Bearer token (hidden): ")
            print(vault.save(SecretStr(value)))
        else:
            vault.delete(args.reference)
            print("Credential deleted; remove its reference from configuration.")
    except (ToolCredentialError, getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        print("Credential operation failed or cancelled; no secret was printed.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
