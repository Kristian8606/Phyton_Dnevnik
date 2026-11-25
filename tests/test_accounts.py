from contextlib import closing
from hashlib import pbkdf2_hmac
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cash_ledger.accounts import AccountError, LocalAccounts


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.path = self.directory / "accounts.sqlite3"
        self.accounts = LocalAccounts(self.path)

    def test_registration_requires_the_four_character_code(self):
        with self.assertRaisesRegex(AccountError, "Кодът"):
            self.accounts.register("Касиер", "test-pass", "0")
        self.assertFalse(self.accounts.has_users())
        self.accounts.register("Касиер", "test-pass", "0000")
        reopened = LocalAccounts(self.path)
        self.assertTrue(reopened.authenticate("  КАСИЕР  ", "test-pass"))
        self.assertFalse(reopened.authenticate("Касиер", "0000"))

    def test_first_registration_cannot_be_reused_and_passwords_are_salted(self):
        self.accounts.register("първи", "sample-password", "0000")
        with self.assertRaises(AccountError):
            self.accounts.register("втори", "sample-password", "0000")
        with self.assertRaisesRegex(AccountError, "вече"):
            self.accounts.register("ПЪРВИ", "other", "0000", administrator_password="sample-password")
        self.accounts.register("втори", "sample-password", "0000", administrator_password="sample-password")
        self.assertTrue(self.accounts.authenticate("втори", "sample-password"))
        self.assertTrue(self.accounts.is_administrator("ПЪРВИ"))
        self.assertFalse(self.accounts.is_administrator("втори"))
        self.assertTrue(self.accounts.authenticate("ПЪРВИ", "sample-password", administrator_only=True))
        self.assertFalse(self.accounts.authenticate("втори", "sample-password", administrator_only=True))
        self._remove_role_table_to_simulate_the_previous_version()
        reopened = LocalAccounts(self.path)
        self.assertTrue(reopened.is_administrator("първи"))
        self.assertFalse(reopened.is_administrator("втори"))
        db = sqlite3.connect(self.path)
        try:
            hashes = db.execute("SELECT salt, password_hash FROM accounts").fetchall()
        finally:
            db.close()
        self.assertNotEqual(hashes[0][0], hashes[1][0])
        self.assertNotEqual(hashes[0][1], hashes[1][1])
        self.assertNotIn(b"sample-password", self.path.read_bytes())

    def test_recovery_keeps_the_code_until_the_administrator_chooses_a_new_one(self):
        self.accounts.register("Админ", "old-password", "0000")
        self.accounts.register("Служител", "staff-password", "0000", administrator_password="old-password")
        with self.assertRaises(AccountError):
            self.accounts.set_recovery_code("Служител", "staff-password", "957321624")
        with self.assertRaisesRegex(AccountError, "девет"):
            self.accounts.set_recovery_code("Админ", "old-password", "957301624")
        self.accounts.set_recovery_code("Админ", "old-password", "957321624")
        self.assertNotIn(b"957321624", self.path.read_bytes())

        reopened = LocalAccounts(self.path)
        self.assertTrue(reopened.has_numeric_recovery_code())
        with self.assertRaises(AccountError):
            reopened.reset_administrator("123456789", "Нов", "new-password")
        with self.assertRaisesRegex(AccountError, "вече"):
            reopened.reset_administrator("957321624", "Служител", "new-password", "849627531")
        self.assertTrue(reopened.authenticate("Админ", "old-password", administrator_only=True))

        reopened.reset_administrator("957321624", "Нов", "new-password")
        self.assertFalse(reopened.authenticate("Админ", "old-password"))
        self.assertTrue(reopened.authenticate("Нов", "new-password", administrator_only=True))
        self.assertTrue(reopened.authenticate("Служител", "staff-password"))
        self.assertFalse(reopened.is_administrator("Служител"))

        reopened.reset_administrator("957321624", "НОВ", "different-password", "849627531")
        self.assertTrue(reopened.authenticate("Нов", "different-password", administrator_only=True))
        with self.assertRaises(AccountError):
            reopened.reset_administrator("957321624", "Трети", "third-password")
        reopened.reset_administrator("849627531", "Трети", "third-password")
        self.assertTrue(reopened.is_administrator("Трети"))

    def test_recovery_accepts_a_legacy_code_and_pauses_after_repeated_failures(self):
        self.accounts.register("Админ", "old-password", "0000")
        with self.assertRaisesRegex(AccountError, "създаден"):
            self.accounts.reset_administrator("957321624", "Админ", "new-password")
        salt = bytes(16)
        legacy_code = "D9345463F486AD2CE335B5782A65ACC0"
        code_hash = pbkdf2_hmac("sha256", legacy_code.encode(), salt, 600_000)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DROP TABLE administrator_recovery")
            db.execute("""
                CREATE TABLE administrator_recovery (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    salt BLOB NOT NULL,
                    code_hash BLOB NOT NULL
                )
            """)
            db.execute("INSERT INTO administrator_recovery VALUES (1, ?, ?)", (salt, code_hash))

        accounts = LocalAccounts(self.path)
        self.assertFalse(accounts.has_numeric_recovery_code())
        with patch("cash_ledger.accounts.time", return_value=100):
            for _ in range(5):
                with self.assertRaisesRegex(AccountError, "грешен"):
                    accounts.reset_administrator("957321624", "Нов", "new-password")
            with self.assertRaisesRegex(AccountError, "секунди"):
                LocalAccounts(self.path).reset_administrator(legacy_code, "Нов", "new-password")
        with patch("cash_ledger.accounts.time", return_value=161):
            accounts.reset_administrator(legacy_code.lower(), "Нов", "new-password", "849627531")
        self.assertTrue(accounts.has_numeric_recovery_code())
        self.assertTrue(accounts.is_administrator("Нов"))

    def _remove_role_table_to_simulate_the_previous_version(self):
        db = sqlite3.connect(self.path)
        try:
            db.execute("DROP TABLE administrator")
        finally:
            db.close()
