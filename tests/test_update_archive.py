from contextlib import closing
from datetime import date
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.ledger import Ledger
from cash_ledger.snapshots import AUTOMATIC_ARCHIVE_NAME, backup_before_update


class UpdateArchiveTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.data = self.root / "Local"
        self.archives = self.root / "Програма" / "Архиви"
        self.source = self.data / "Dnevnik" / "dnevnik.sqlite3"

    def test_no_database_leaves_the_existing_archive_alone(self):
        self.archives.mkdir(parents=True)
        existing = self.archives / AUTOMATIC_ARCHIVE_NAME
        existing.write_bytes(b"previous archive")
        self.assertIsNone(backup_before_update(self.data, self.archives))
        self.assertEqual(existing.read_bytes(), b"previous archive")

    def test_replaces_the_same_archive_including_committed_wal_data(self):
        ledger = Ledger(self.source)
        day = date.today()
        with closing(sqlite3.connect(self.source)) as writer:
            writer.execute("PRAGMA journal_mode = WAL")
            writer.execute("PRAGMA wal_autocheckpoint = 0")
            ledger.save(day, {"income": "125"})
            backup = backup_before_update(self.data, self.archives)
            self.assertEqual(backup, self.archives / AUTOMATIC_ARCHIVE_NAME)
            self.assertEqual(Ledger(backup).day(day).summary["cash"], 12500)
            with writer:
                writer.execute(
                    "INSERT INTO cash_movements(day, income, income_note, cost_note) VALUES (?, ?, '', '')",
                    (day.isoformat(), 2500),
                )
            self.assertTrue(self.source.with_suffix(".sqlite3-wal").is_file())
            self.assertEqual(backup_before_update(self.data, self.archives), backup)
            self.assertEqual(Ledger(backup).day(day).summary["cash"], 15000)
            self.assertEqual(list(self.archives.iterdir()), [backup])

    def test_reads_legacy_database_and_preserves_existing_backup_on_failure(self):
        legacy = self.data / "KasovDnevnik" / "cash-ledger.sqlite3"
        Ledger(legacy).save(date.today(), {"income": "83"})
        backup = backup_before_update(self.data, self.archives)
        self.assertEqual(Ledger(backup).day(date.today()).summary["cash"], 8300)
        previous = backup.read_bytes()
        self.source.parent.mkdir()
        self.source.write_bytes(b"invalid SQLite input")
        with self.assertRaises(sqlite3.DatabaseError):
            backup_before_update(self.data, self.archives)
        self.assertEqual(backup.read_bytes(), previous)
        self.assertEqual(list(self.archives.iterdir()), [backup])
