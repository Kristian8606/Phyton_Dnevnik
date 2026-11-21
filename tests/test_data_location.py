from contextlib import closing
from datetime import date
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.data_location import LEGACY_DIRECTORY_NAME, default_database
from cash_ledger.ledger import Ledger


class DataLocationTests(unittest.TestCase):
    def test_copies_live_legacy_database_once_into_renamed_folder(self):
        day = date(2026, 11, 21)
        with TemporaryDirectory() as temporary:
            parent = Path(temporary)
            old = parent / LEGACY_DIRECTORY_NAME / "cash-ledger.sqlite3"
            location = parent / "Dnevnik"
            Ledger(old)
            with closing(sqlite3.connect(old)) as connection:
                Ledger(old).save(day, {"income": "75"})
                new = default_database(location)
            self.assertEqual(new, location / "dnevnik.sqlite3")
            self.assertEqual(Ledger(new).day(day).summary["cash"], 7500)
            Ledger(new).save(day, {"income": "10"})
            self.assertEqual(default_database(location), new)
            self.assertEqual(Ledger(new).day(day).summary["cash"], 8500)
            self.assertEqual(Ledger(old).day(day).summary["cash"], 7500)

    def test_demo_keeps_its_own_database(self):
        day = date(2026, 11, 21)
        with TemporaryDirectory() as temporary:
            parent = Path(temporary)
            old_demo = parent / LEGACY_DIRECTORY_NAME / "cash-ledger-test-days.sqlite3"
            Ledger(old_demo).save(day, {"income": "12"})
            location = parent / "Dnevnik"
            new_demo = default_database(location, demo=True)
            self.assertEqual(new_demo, location / "dnevnik-test-days.sqlite3")
            self.assertEqual(Ledger(new_demo).day(day).summary["cash"], 1200)
            self.assertFalse(default_database(location).exists())
