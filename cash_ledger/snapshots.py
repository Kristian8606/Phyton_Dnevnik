"""Write verified, standalone SQLite snapshots."""

from contextlib import closing
from pathlib import Path
import sqlite3
from stat import S_ISREG
from tempfile import TemporaryDirectory
from time import monotonic

from .i18n import localized
from .ledger import AUTOMATIC_ARCHIVE_NAME, BLOCKS


def backup_before_update(data_directory: Path, archive_directory: Path) -> Path | None:
    for database in (data_directory / "Dnevnik" / "dnevnik.sqlite3",
                     data_directory / "KasovDnevnik" / "cash-ledger.sqlite3"):
        try:
            mode = database.stat().st_mode
        except FileNotFoundError:
            continue
        if not S_ISREG(mode):
            raise OSError(localized("Файлът на дневника не е достъпен."))
        break
    else:
        return None

    target = archive_directory / AUTOMATIC_ARCHIVE_NAME
    replace_archive(database, target)
    return target


def replace_archive(database: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    uri = database.resolve(strict=True).as_uri()
    # Serialize automatic backups across the app and the installer.
    with closing(sqlite3.connect(uri + "?mode=rw", uri=True)) as lock:
        lock.execute("BEGIN IMMEDIATE")
        with TemporaryDirectory(prefix=".dnevnik-archive-", dir=target.parent) as staging:
            temporary = Path(staging) / "snapshot.sqlite3"
            deadline = monotonic() + 20

            def check_progress(status, _remaining, _total):
                if status in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) and monotonic() >= deadline:
                    raise TimeoutError(localized("Дневникът е зает и не може да се архивира."))

            with closing(sqlite3.connect(uri + "?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(temporary)) as snapshot:
                    source.backup(snapshot, pages=256, progress=check_progress)
                    snapshot.execute("PRAGMA journal_mode = DELETE")
                    version = snapshot.execute("PRAGMA user_version").fetchone()[0]
                    required = {"settings", *BLOCKS}
                    if version == 2:
                        required.add("revisions")
                    tables = {row[0] for row in snapshot.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")}
                    if (version not in (1, 2) or not required <= tables
                            or snapshot.execute("PRAGMA quick_check").fetchall() != [("ok",)]):
                        raise sqlite3.DatabaseError(localized("Копието на дневника не премина проверката."))
            temporary.replace(target)
