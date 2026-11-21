from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.demo import prepare_demo
from cash_ledger.ledger import Ledger


TODAY = date(2026, 11, 21)


class CashCarryTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.demo = self.directory / "test-days.sqlite3"
        prepare_demo(self.demo, TODAY)
        self.ledger = Ledger(self.demo)

    def test_sample_days_and_reopening_preserve_user_corrections(self):
        dates = [TODAY - timedelta(days=ago) for ago in (3, 2, 1, 0)]
        self.assertEqual([self.ledger.day(day).summary["cash"] for day in dates],
                         [111500, 118500, 122700, 124200])
        self.assertEqual([self.ledger.day(day).carried_cash for day in dates],
                         [100000, 111500, 118500, 122700])

        sale_day = dates[1]
        sale = self.ledger.day(sale_day).operation_ids[0]["contracts"]
        original = self.ledger.read_operation(sale_day, "contracts", sale)
        self.ledger.edit(sale_day, "contracts", sale, dict(
            marker="1", contract="19001", interest="40", principal="120", gold="5 Златен пръстен"
        ), original)
        prepare_demo(self.demo, TODAY + timedelta(days=1))
        reopened = Ledger(self.demo)
        self.assertEqual([reopened.day(day).summary["cash"] for day in dates],
                         [111500, 120500, 124700, 126200])
        self.assertEqual([reopened.day(day).carried_cash for day in dates],
                         [100000, 111500, 120500, 124700])
        report = reopened.cash_by_day(TODAY)
        self.assertEqual([(line.day, line.carried, line.movement, line.closing) for line in report[-4:]], [
            (dates[0], 100000, 11500, 111500),
            (dates[1], 111500, 9000, 120500),
            (dates[2], 120500, 4200, 124700),
            (dates[3], 124700, 1500, 126200),
        ])
        self.assertFalse((self.directory / "cash-ledger.sqlite3").exists())

    def test_empty_day_carries_balance_without_a_movement(self):
        day = TODAY + timedelta(days=1)
        line = self.ledger.cash_by_day(day)[-1]
        self.assertEqual((line.day, line.carried, line.movement, line.closing),
                         (day, 124200, 0, 124200))
        self.assertEqual(self.ledger.day(day).carried_cash, 124200)
