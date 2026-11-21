from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.ledger import Ledger


DAY = date(2026, 11, 21)


class FundingTests(unittest.TestCase):
    def test_a_new_database_is_funded_by_ordinary_income(self):
        with TemporaryDirectory() as temporary:
            ledger = Ledger(Path(temporary) / "ledger.sqlite3")
            self.assertEqual(ledger.day(DAY).summary["cash"], 0)
            ledger.save(DAY, {"income": "1225 Зареждане"})
            self.assertEqual(ledger.day(DAY).summary["cash"], 122500)
            self.assertEqual(ledger.day(DAY + timedelta(days=1)).carried_cash, 122500)

    def test_legacy_opening_becomes_income_once_and_preserves_daily_carry(self):
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            Ledger(database).save(DAY, {"cost": "50"})
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("UPDATE settings SET opening_cash = 122500 WHERE singleton = 1")
            first = Ledger(database)
            prior = DAY - timedelta(days=1)
            self.assertEqual(first.day(prior).summary["incoming"], 122500)
            self.assertEqual(first.day(DAY).carried_cash, 122500)
            self.assertEqual(first.day(DAY).summary["cash"], 117500)
            self.assertEqual(first.day(DAY).summary["net"], -5000)
            reopened = Ledger(database)
            self.assertEqual(len(reopened.day(prior).rows), 1)
            self.assertEqual(reopened.day(DAY).summary["cash"], 117500)

    def test_restoring_legacy_archive_preserves_the_balance_as_a_movement(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = directory / "old.sqlite3"
            Ledger(original).save(DAY, {"income": "40"})
            with closing(sqlite3.connect(original)) as connection, connection:
                connection.execute("UPDATE settings SET opening_cash = -1000 WHERE singleton = 1")
            target = Ledger(directory / "current.sqlite3")
            target.restore(original)
            prior = target.day(DAY - timedelta(days=1))
            self.assertEqual(prior.summary["outgoing"], 1000)
            self.assertEqual(target.day(DAY).summary["cash"], 3000)
