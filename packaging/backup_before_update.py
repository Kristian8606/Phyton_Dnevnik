"""Entry point embedded in the Windows installer."""

from argparse import ArgumentParser
from pathlib import Path
import sqlite3
import sys

from cash_ledger.snapshots import backup_before_update


def main() -> int:
    parser = ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("archives", type=Path)
    arguments = parser.parse_args()
    try:
        backup_before_update(arguments.data, arguments.archives)
    except (OSError, sqlite3.Error) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
