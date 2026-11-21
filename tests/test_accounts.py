from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.accounts import AccountError, LocalAccounts


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.path = self.directory / "accounts.sqlite3"
        self.accounts = LocalAccounts(self.path)

    def test_registration_requires_the_four_character_code(self):
        with self.assertRaisesRegex(AccountError, "Кодът"):
            self.accounts.register("Касиер", "test-pass", "0", first_only=True)
        self.assertFalse(self.accounts.has_users())
        self.accounts.register("Касиер", "test-pass", "0000", first_only=True)
        reopened = LocalAccounts(self.path)
        self.assertTrue(reopened.authenticate("  КАСИЕР  ", "test-pass"))
        self.assertFalse(reopened.authenticate("Касиер", "0000"))

    def test_first_registration_cannot_be_reused_and_passwords_are_salted(self):
        self.accounts.register("първи", "sample-password", "0000", first_only=True)
        with self.assertRaises(AccountError):
            self.accounts.register("втори", "sample-password", "0000", first_only=True)
        with self.assertRaisesRegex(AccountError, "вече"):
            self.accounts.register("ПЪРВИ", "other", "0000", first_only=False)
        self.accounts.register("втори", "sample-password", "0000", first_only=False)
        self.assertTrue(self.accounts.authenticate("втори", "sample-password"))
        db = sqlite3.connect(self.path)
        try:
            hashes = db.execute("SELECT salt, password_hash FROM accounts").fetchall()
        finally:
            db.close()
        self.assertNotEqual(hashes[0][0], hashes[1][0])
        self.assertNotEqual(hashes[0][1], hashes[1][1])
        self.assertNotIn(b"sample-password", self.path.read_bytes())
