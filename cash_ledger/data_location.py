"""Select the local database and copy records from earlier installations."""

from contextlib import closing
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import QLockFile


# Historical folder name used only to locate data before the rename.
LEGACY_DIRECTORY_NAME = "KasovDnevnik"


def program_archive_directory() -> Path:
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parents[1] / "Архиви"
    executable = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        bundle = next((parent for parent in executable.parents if parent.suffix == ".app"), None)
        if bundle:
            return bundle.parent / "Дневник – Архиви"
    return executable.parent / "Архиви"


def default_database(directory: Path, *, demo: bool = False) -> Path:
    filename = "dnevnik-test-days.sqlite3" if demo else "dnevnik.sqlite3"
    database = directory / filename
    if database.exists():
        return database

    legacy_name = "cash-ledger-test-days.sqlite3" if demo else "cash-ledger.sqlite3"
    legacy = directory.with_name(LEGACY_DIRECTORY_NAME) / legacy_name
    if not legacy.is_file():
        return database

    directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(database.with_suffix(".migration.lock")))
    if not lock.tryLock(5000):
        raise OSError("Прехвърлянето на записите вече е стартирало.")
    try:
        if not database.exists():
            with TemporaryDirectory(dir=directory) as temporary:
                staged = Path(temporary) / filename
                with closing(sqlite3.connect(legacy.as_uri() + "?mode=ro", uri=True)) as source:
                    with closing(sqlite3.connect(staged)) as target:
                        source.backup(target)
                staged.replace(database)
    finally:
        lock.unlock()
    return database
