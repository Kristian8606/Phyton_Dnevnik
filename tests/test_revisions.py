from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from unittest.mock import patch

from cash_ledger.ledger import Ledger, ValidationError


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

    def test_closing_preserves_cash_and_history_across_multiple_same_day_periods(self):
        end = date(2026, 11, 25)
        morning = end - timedelta(days=1)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.sqlite3"
            ledger = Ledger(path)
            ledger.save(morning, {"income": "1225", "contract": "0404", "interest": "5", "principal": "0"})
            ledger.save(end, {"cost": "55"})
            report = ledger.revision_snapshot(end)
            self.assertEqual(report.operation_count, 3)
            backup = ledger.close_revision(report)
            self.assertTrue(backup.is_file())
            self.assertEqual(len(Ledger(backup).day(morning).rows), 1)
            self.assertEqual(ledger.day(end).rows, [])
            self.assertEqual(ledger.day(end).carried_cash, 117500)
            self.assertEqual(ledger.revision_totals(end)["income"], 0)
            self.assertEqual(ledger.find_number("0404"), [])
            self.assertEqual(ledger.cash_by_day(end)[0].movement, 0)
            with self.assertRaises(ValidationError):
                ledger.save(morning, {"income": "1"})

            ledger.save(end, {"income": "25"})
            second = ledger.revision_snapshot(end)
            self.assertEqual(second.totals["closing"], 120000)
            ledger.close_revision(second)
            reopened = Ledger(path)
            self.assertEqual([row.totals["closing"] for row in reopened.revision_history()], [120000, 117500])
            self.assertEqual(reopened.day(end).carried_cash, 120000)
            self.assertEqual(reopened.day(end + timedelta(days=1)).carried_cash, 120000)

    def test_automatic_backup_prefers_the_program_folder_and_falls_back_if_unavailable(self):
        end = date(2026, 11, 25)
        with TemporaryDirectory() as temporary:
            parent = Path(temporary)
            program_archives = parent / "program" / "Архиви"
            data = parent / "data"
            journal = Ledger(data / "ledger.sqlite3", archive_directory=program_archives)
            journal.save(end, {"income": "100"})
            backup = journal.close_revision(journal.revision_snapshot(end))
            self.assertEqual(backup.parent, program_archives)
            self.assertTrue(backup.is_file())

            unavailable = parent / "unavailable"
            unavailable.touch()
            journal = Ledger(data / "ledger.sqlite3", archive_directory=unavailable)
            journal.save(end, {"income": "10"})
            backup = journal.close_revision(journal.revision_snapshot(end))
            self.assertEqual(backup.parent, data / "Архиви")
            self.assertTrue(backup.is_file())

    def test_stale_preview_and_failed_backup_leave_the_journal_intact(self):
        end = date(2026, 11, 25)
        with TemporaryDirectory() as temporary:
            ledger = Ledger(Path(temporary) / "ledger.sqlite3")
            ledger.save(end, {"income": "100"})
            saved = ledger.revision_snapshot(end)
            ledger.save(end, {"cost": "20"})
            with self.assertRaises(ValidationError):
                ledger.close_revision(saved)
            current = ledger.revision_snapshot(end)
            with patch.object(ledger, "backup", side_effect=OSError("backup failure")):
                with self.assertRaises(OSError):
                    ledger.close_revision(current)
            self.assertEqual(ledger.revision_history(), [])
            self.assertEqual(ledger.revision_snapshot(end), current)

    def test_restore_old_archive_migrates_and_restores_modern_revision_history(self):
        end = date(2026, 11, 25)
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            ledger = Ledger(directory / "ledger.sqlite3")
            ledger.save(end, {"income": "50"})
            old_archive = directory / "old.sqlite3"
            ledger.backup(old_archive)
            with closing(sqlite3.connect(old_archive)) as db, db:
                db.execute("DROP TABLE revisions")
                db.execute("PRAGMA user_version = 1")
            ledger.close_revision(ledger.revision_snapshot(end))
            current_archive = directory / "current.sqlite3"
            ledger.backup(current_archive)
            ledger.restore(old_archive)
            self.assertEqual(ledger.revision_history(), [])
            self.assertEqual(ledger.day(end).summary["cash"], 5000)
            ledger.restore(current_archive)
            self.assertEqual(ledger.day(end).rows, [])
            self.assertEqual(ledger.day(end).carried_cash, 5000)
            self.assertEqual(len(ledger.revision_history()), 1)
