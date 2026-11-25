from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.ledger import Ledger


class RevisionTests(unittest.TestCase):
    def test_active_period_summary_keeps_exact_cash_and_separates_sold_weights(self):
        close = date(2026, 11, 25)
        earlier = close - timedelta(days=1)
        with TemporaryDirectory() as temporary:
            ledger = Ledger(Path(temporary) / "ledger.sqlite3")
            ledger.save(earlier, {"income": "1000", "cost": "20", "pledge": "222", "pledgeAmount": "50",
                                 "buyGold": "15", "buySilver": "5"})
            ledger.save(earlier, {"marker": "1", "contract": "123", "interest": "40", "principal": "100", "gold": "5"})
            ledger.save(close, {"marker": "1", "contract": "211", "interest": "12", "principal": "30", "newGold": "1,25"})
            ledger.save(close, {"marker": "1", "contract": "212", "interest": "8", "principal": "10", "silver": "2,50"})
            ledger.save(close, {"marker": "1", "contract": "213", "interest": "2", "principal": "5", "newSilver": "3,25"})
            ledger.save(close, {"contract": "214", "interest": "4", "principal": "10"})
            ledger.save(close + timedelta(days=1), {"income": "99"})
            self.assertEqual(ledger.revision_totals(close), {
                "profit": 6600, "sold_gold": 500, "sold_new_gold": 125, "sold_silver": 250,
                "sold_new_silver": 325, "income": 100000, "cost": 2000, "bought_gold": 1500,
                "bought_silver": 500, "closing": ledger.day(close).summary["cash"],
            })
            self.assertEqual(ledger.day(close).summary["cash"], 113100)
