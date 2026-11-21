from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.ledger import Ledger, ValidationError, weight_error


DAY = date(2026, 11, 21)
NEXT_DAY = date(2026, 11, 22)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        temp = self.enterContext(TemporaryDirectory())
        self.database = Path(temp) / "ledger.sqlite3"
        self.ledger = Ledger(self.database)

    def test_confirmed_day_survives_reopening(self):
        self.ledger.save(DAY - timedelta(days=1), {"income": "1000,00"})
        self.ledger.save(DAY, {"contract": "102", "interest": "15", "principal": "80"})
        self.ledger.save(DAY, {"marker": "1", "contract": "103", "interest": "20",
                               "principal": "100", "gold": "5 Златен пръстен"})
        result = self.ledger.save(DAY, {"income": "30", "cost": "10", "pledge": "090",
                                        "pledgeAmount": "70", "buyGold": "25", "buySilver": "12"})
        self.assertEqual(result.next_pledge, "91")
        view = Ledger(self.database).day(DAY)
        self.assertEqual(
            view.summary,
            {"cash": 112800, "profit": 3500, "interest": 1500, "redemption": 8000,
             "pledges": 7000, "incoming": 24500, "outgoing": 11700, "net": 12800},
        )
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(view.rows[0]["pledge"].value, "090")
        self.assertEqual(view.rows[1]["marker"].value, "--||--")
        self.assertEqual(view.rows[1]["gold"].note, "Златен пръстен")
        self.assertEqual(view.rows[1]["gold"].unit_price, 2400)

    def test_history_has_daily_totals_and_cumulative_cash(self):
        self.ledger.save(DAY - timedelta(days=1), {"cost": "5,50"})
        self.ledger.save(DAY, {"income": "10,75"})
        self.ledger.save(NEXT_DAY, {"cost": "2,25"})
        self.assertEqual(self.ledger.day(DAY).summary["cash"], 525)
        following = self.ledger.day(NEXT_DAY)
        self.assertEqual(following.summary["cash"], 300)
        self.assertEqual(following.summary["incoming"], 0)
        self.assertEqual(following.rows[0]["cost"].value, 225)

    def test_search_spans_days_blocks_and_literal_identifier_fragments(self):
        self.ledger.save(DAY, {"marker": "1", "contract": "00123", "interest": "5", "principal": "15"})
        self.ledger.save(NEXT_DAY, {"contract": "01234", "interest": "1", "principal": "2",
                                    "pledge": "З-00123", "pledgeAmount": "12"})
        matches = self.ledger.find_number(" 00123 ")
        self.assertEqual([(hit.kind, hit.number, hit.day, hit.amount) for hit in matches], [
            ("sale", "00123", DAY, 2000), ("pledge", "З-00123", NEXT_DAY, 1200),
        ])
        self.assertEqual(self.ledger.find_number("з-001")[0].block, "pledges")
        self.assertEqual(self.ledger.find_number("1234")[0].block, "contracts")
        self.assertEqual(self.ledger.find_number("%"), [])
        self.assertEqual(self.ledger.find_number(" "), [])

    def test_second_weight_is_rejected_without_saving_another_block(self):
        keys = ("gold", "newGold", "silver", "newSilver")
        for index, first in enumerate(keys):
            for second in keys[index + 1:]:
                with self.subTest(first=first, second=second):
                    fields = {"marker": "1", "contract": "104", "interest": "40",
                              "principal": "100", first: "5", second: "2", "income": "1"}
                    self.assertTrue(weight_error(fields))
                    with self.assertRaises(ValidationError):
                        self.ledger.save(DAY, fields)
        self.assertFalse(self.ledger.day(DAY).rows)

    def test_each_weight_has_its_own_sale_price_and_other_cells_are_empty(self):
        keys = ("gold", "newGold", "silver", "newSilver")
        for index, key in enumerate(keys):
            self.ledger.save(DAY, {"marker": "1", "contract": str(200 + index),
                                   "interest": "40", "principal": "100", key: "5"})
        for key, row in zip(keys, self.ledger.day(DAY).rows):
            self.assertEqual(row[key].unit_price, 2800)
            self.assertFalse(any(other in row for other in keys if other != key))

    def test_weight_requires_an_actual_sale_marker(self):
        draft = {"contract": "200", "interest": "40", "principal": "100", "silver": "5"}
        for marker in ("", "бележка"):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(ValidationError, "само при продажба"):
                    self.ledger.save(DAY, draft | {"marker": marker})
        self.assertFalse(self.ledger.day(DAY).rows)
        self.ledger.save(DAY, draft | {"marker": "-"})
        self.assertEqual(self.ledger.day(DAY).rows[0]["marker"].value, "--||--")

    def test_incomplete_or_duplicate_record_does_not_change_other_blocks(self):
        self.ledger.save(DAY, {"contract": "200", "interest": "1", "principal": "1"})
        with self.assertRaises(ValidationError):
            self.ledger.save(DAY, {"contract": "200", "interest": "2",
                                   "principal": "2", "buyGold": "10"})
        with self.assertRaises(ValidationError):
            self.ledger.save(DAY, {"pledgeAmount": "5", "cost": "3"})
        self.assertEqual(self.ledger.day(DAY).summary["cash"], 200)

    def test_next_pledge_number_alone_does_not_block_other_entries(self):
        self.ledger.save(DAY, {"pledge": "0002", "income": "12.50 доставка"})
        view = self.ledger.day(DAY)
        self.assertEqual(view.summary["cash"], 1250)
        self.assertEqual(view.rows[0]["income"].note, "доставка")
        self.assertNotIn("pledge", view.rows[0])
