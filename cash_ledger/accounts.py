"""Local user accounts for the shared journal."""

from contextlib import closing
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from pathlib import Path
from secrets import token_bytes
import sqlite3
from unicodedata import normalize


REGISTRATION_CODE = "0000"
PBKDF2_ITERATIONS = 600_000
MAX_USERNAME_LENGTH = 64
MAX_PASSWORD_LENGTH = 512


class AccountError(ValueError):
    pass


def _username_key(username: str) -> str:
    return normalize("NFKC", username.strip()).casefold()


def _password_hash(password: str, salt: bytes) -> bytes:
    return pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)


def _matches(record, password: str) -> bool:
    if not password or len(password) > MAX_PASSWORD_LENGTH:
        return False
    salt, expected = record if record else (bytes(16), bytes(32))
    return compare_digest(_password_hash(password, salt), expected) and record is not None


class LocalAccounts:
    def __init__(self, path: Path):
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    username_key TEXT PRIMARY KEY,
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS administrator (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    username_key TEXT NOT NULL REFERENCES accounts(username_key)
                )
            """)
            db.execute("""
                INSERT OR IGNORE INTO administrator
                SELECT 1, username_key FROM accounts ORDER BY rowid LIMIT 1
            """)

    def has_users(self) -> bool:
        with closing(sqlite3.connect(self._path)) as db:
            return db.execute("SELECT 1 FROM accounts LIMIT 1").fetchone() is not None

    def register(self, username: str, password: str, code: str, *, administrator_password: str = ""):
        if code.strip() != REGISTRATION_CODE:
            raise AccountError("Кодът за регистрация е грешен.")
        key = _username_key(username)
        if not key or len(key) > MAX_USERNAME_LENGTH:
            raise AccountError("Въведи потребителско име до 64 знака.")
        if not password.strip() or len(password) > MAX_PASSWORD_LENGTH:
            raise AccountError("Въведи парола.")
        salt = token_bytes(16)
        password_hash = _password_hash(password, salt)
        with closing(sqlite3.connect(self._path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            administrator = db.execute("""
                SELECT salt, password_hash FROM accounts JOIN administrator USING (username_key)
            """).fetchone()
            if administrator is not None and not _matches(administrator, administrator_password):
                raise AccountError("Въведи правилната парола на администратора.")
            try:
                db.execute("INSERT INTO accounts VALUES (?, ?, ?)", (key, salt, password_hash))
            except sqlite3.IntegrityError as exc:
                raise AccountError("Това потребителско име вече е регистрирано.") from exc
            if administrator is None:
                db.execute("INSERT INTO administrator VALUES (1, ?)", (key,))

    def is_administrator(self, username: str) -> bool:
        with closing(sqlite3.connect(self._path)) as db:
            return db.execute(
                "SELECT 1 FROM administrator WHERE username_key = ?", (_username_key(username),)
            ).fetchone() is not None

    def authenticate(self, username: str, password: str) -> bool:
        with closing(sqlite3.connect(self._path)) as db:
            record = db.execute(
                "SELECT salt, password_hash FROM accounts WHERE username_key = ?", (_username_key(username),)
            ).fetchone()
        return _matches(record, password)
