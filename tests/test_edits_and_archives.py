from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.ledger import Ledger, ValidationError


DAY = date(2026, 11, 21)


class EditAndArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.path = self.directory / "ledger.sqlite3"
        self.store = Ledger(self.path)

    def make_sale(self):
        self.store.save(DAY, {"marker": "1", "contract": "0041", "interest": "40",
                              "principal": "100", "gold": "5 Пръстен", "cost": "7"})
        view = self.store.day(DAY)
        return view.operation_ids[0]["contracts"], view.operation_ids[0]["cash_movements"]

    def test_edit_a_sale_and_only_its_price_changes_after_reopening(self):
        sale, cash = self.make_sale()
        initial = self.store.read_operation(DAY, "contracts", sale)
        self.store.edit(DAY, "contracts", sale, {
            "marker": "1", "contract": "0041", "interest": "40",
            "principal": "100", "gold": "4 Пръстен",
        }, initial)
        view = Ledger(self.path).day(DAY)
        self.assertEqual(view.rows[0]["gold"].unit_price, 3500)
        self.assertEqual(view.rows[0]["gold"].note, "Пръстен")
        self.assertEqual(view.rows[0]["cost"].value, 700)
        self.assertEqual(view.summary["cash"], 13300)
        self.assertEqual(view.operation_ids, [{"contracts": sale, "cash_movements": cash}])

    def test_edits_target_independent_blocks_and_update_later_balance(self):
        self.store.save(DAY, {"income": "25", "pledge": "123", "pledgeAmount": "10", "buySilver": "4"})
        ids = self.store.day(DAY).operation_ids[0]
        for group, update in (
            ("cash_movements", {"cost": "2 Куриер"}),
            ("pledges", {"pledge": "0003", "pledgeAmount": "8"}),
            ("purchases", {"buyGold": "3"}),
        ):
            record_id = ids[group]
            original = self.store.read_operation(DAY, group, record_id)
            self.store.edit(DAY, group, record_id, update, original)
        day = self.store.day(DAY)
        self.assertEqual(day.operation_ids[0], ids)
        self.assertEqual(day.rows[0]["cost"].note, "Куриер")
        self.assertEqual(day.rows[0]["pledge"].value, "0003")
        self.assertEqual(day.rows[0]["buyGold"].value, 300)
        self.assertEqual(self.store.day(DAY + timedelta(days=1)).summary["cash"], -1300)

    def test_edit_rejects_invalid_or_stale_data(self):
        sale, _ = self.make_sale()
        initial = self.store.read_operation(DAY, "contracts", sale)
        valid = {"marker": "1", "contract": "0041", "interest": "40", "principal": "100", "gold": "4"}
        with self.assertRaises(ValidationError):
            self.store.edit(DAY, "contracts", sale, valid | {"silver": "2"}, initial)
        self.store.edit(DAY, "contracts", sale, valid, initial)
        with self.assertRaises(ValidationError):
            self.store.edit(DAY, "contracts", sale, valid | {"gold": "3"}, initial)
        self.assertEqual(self.store.day(DAY).rows[0]["gold"].value, 400)

    def test_clearing_sale_marker_requires_clearing_weight(self):
        sale, _ = self.make_sale()
        initial = self.store.read_operation(DAY, "contracts", sale)
        draft = {"marker": "", "contract": "0041", "interest": "40", "principal": "100"}
        with self.assertRaisesRegex(ValidationError, "само при продажба"):
            self.store.edit(DAY, "contracts", sale, draft | {"gold": "5 Пръстен"}, initial)
        self.assertEqual(self.store.read_operation(DAY, "contracts", sale), initial)
        self.store.edit(DAY, "contracts", sale, draft, initial)
        view = self.store.day(DAY)
        self.assertNotIn("gold", view.rows[0])
        self.assertEqual(view.summary["interest"], 4000)
        self.assertEqual(view.summary["redemption"], 10000)
        self.assertEqual(view.summary["cash"], 13300)

    def test_restore_keeps_safety_copy_and_refuses_unrelated_database(self):
        self.make_sale()
        archive = self.directory / "my-copy.sqlite3"
        self.store.backup(archive)
        with self.assertRaises(FileExistsError):
            self.store.backup(archive)
        self.store.save(DAY, {"income": "42"})
        unrelated = self.directory / "unrelated.sqlite3"
        with closing(sqlite3.connect(unrelated)) as db, db:
            db.execute("PRAGMA user_version = 1")
            db.execute("CREATE TABLE unrelated(x)")
        with self.assertRaises(ValidationError):
            self.store.restore(unrelated)
        self.assertEqual(self.store.day(DAY).summary["cash"], 17500)
        safety = self.store.restore(archive)
        self.assertEqual(Ledger(safety).day(DAY).summary["cash"], 17500)
        self.assertEqual(Ledger(self.path).day(DAY).summary["cash"], 13300)
        self.assertEqual(Ledger(archive).day(DAY).summary["cash"], 13300)

    def test_backup_and_restore_cannot_overwrite_the_active_database_directly(self):
        self.make_sale()
        with self.assertRaises(FileExistsError):
            self.store.backup(self.path)
        with self.assertRaises(ValidationError):
            self.store.restore(self.path)
        self.assertEqual(self.store.day(DAY).summary["cash"], 13300)
