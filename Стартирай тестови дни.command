#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
exec "$PWD/.venv/bin/python" -m cash_ledger --demo
