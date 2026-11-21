"""Launch the local desktop application."""

from argparse import ArgumentParser
from pathlib import Path
import sys

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QGuiApplication

from .desktop import make_window


def main() -> int:
    parser = ArgumentParser(description="Касов дневник")
    parser.add_argument("--database", type=Path, help="Използвай друг SQLite файл.")
    args = parser.parse_args()
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("KasovDnevnik")
    app.setApplicationDisplayName("Касов дневник")
    data_directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    engine, controller = make_window(args.database or data_directory / "cash-ledger.sqlite3")
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
