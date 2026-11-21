"""Launch the local desktop application."""

from argparse import ArgumentParser, SUPPRESS
from datetime import date
from pathlib import Path
import sqlite3
import sys

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QSslSocket

from .data_location import default_database
from .desktop import make_window
from .demo import prepare_demo
from . import __version__


def main() -> int:
    parser = ArgumentParser(description="Дневник")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--check-startup", action="store_true", help=SUPPRESS)
    database_options = parser.add_mutually_exclusive_group()
    database_options.add_argument("--database", type=Path, help="Използвай друг SQLite файл.")
    database_options.add_argument("--demo", action="store_true", help="Отвори отделна база с тестови дни.")
    args = parser.parse_args()
    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("Dnevnik")
    app.setApplicationDisplayName("Дневник")
    app.setApplicationVersion(__version__)
    data_directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    try:
        database = args.database or default_database(data_directory, demo=args.demo)
    except (OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Записите не можаха да се прехвърлят. {exc}\n")
    if args.demo:
        data_directory.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(database.with_suffix(".seed.lock")))
        if not lock.tryLock(5000):
            parser.exit(1, "Подготовката на тестовите дни вече е стартирана.\n")
        try:
            prepare_demo(database, date.today())
        finally:
            lock.unlock()
    engine, controller = make_window(database, demo=args.demo)
    if not engine.rootObjects():
        return 1
    if args.check_startup:
        app.processEvents()
        if sys.platform == "win32" and not QSslSocket.supportsSsl():
            return 1
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
