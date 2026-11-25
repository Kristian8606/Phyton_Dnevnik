"""Launch the local desktop application."""

from argparse import ArgumentParser, SUPPRESS
from datetime import date
from pathlib import Path
from secrets import token_urlsafe
import sqlite3
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QSslSocket

from . import __version__
from .data_location import default_database, program_archive_directory
from .demo import prepare_demo
from .session import DesktopSession


def check_startup(app: QGuiApplication) -> int:
    if sys.platform == "win32" and not QSslSocket.supportsSsl():
        return 1
    with TemporaryDirectory() as temporary:
        directory = Path(temporary)
        session = DesktopSession(directory, lambda: directory / "test.sqlite3", show_windows=False)
        if not session.start():
            return 1
        session.beginRegistration("administrator")
        if session.submit("startup-test", token_urlsafe(16), "4826"):
            return 1
        app.processEvents()
    return 0


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
    if args.check_startup:
        return check_startup(app)

    data_directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))

    def open_database():
        database = args.database or default_database(data_directory, demo=args.demo)
        if args.demo:
            data_directory.mkdir(parents=True, exist_ok=True)
            lock = QLockFile(str(database.with_suffix(".seed.lock")))
            if not lock.tryLock(5000):
                raise OSError("Подготовката на тестовите дни вече е стартирала.")
            try:
                prepare_demo(database, date.today())
            finally:
                lock.unlock()
        return database

    try:
        session = DesktopSession(
            data_directory, open_database, demo=args.demo, archive_directory=program_archive_directory(),
        )
    except (OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Профилите са недостъпни. {exc}\n")
    if not session.start():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
