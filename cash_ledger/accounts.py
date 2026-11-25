"""Local user accounts for the shared journal."""

from contextlib import closing
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from pathlib import Path
from secrets import token_bytes
import sqlite3
from time import time
from unicodedata import normalize


REGISTRATION_CODE = "0000"
PBKDF2_ITERATIONS = 600_000
MAX_USERNAME_LENGTH = 64
MAX_PASSWORD_LENGTH = 512
RECOVERY_ATTEMPTS = 5
RECOVERY_PAUSE_SECONDS = 60


class AccountError(ValueError):
    pass


def _username_key(username: str) -> str:
    return normalize("NFKC", username.strip()).casefold()


def _account_credentials(username: str, password: str) -> tuple[str, bytes, bytes]:
    key = _username_key(username)
    if not key or len(key) > MAX_USERNAME_LENGTH:
        raise AccountError("Въведи потребителско име до 64 знака.")
    if not password.strip() or len(password) > MAX_PASSWORD_LENGTH:
        raise AccountError("Въведи парола.")
    salt = token_bytes(16)
    return key, salt, _password_hash(password, salt)


def _password_hash(password: str, salt: bytes) -> bytes:
    return pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)


def _matches(record, password: str) -> bool:
    if not password or len(password) > MAX_PASSWORD_LENGTH:
        return False
    salt, expected = record if record else (bytes(16), bytes(32))
    return compare_digest(_password_hash(password, salt), expected) and record is not None


def _store_recovery_code(db: sqlite3.Connection, code: str):
    if len(code) != 9 or any(digit not in "123456789" for digit in code):
        raise AccountError("Въведи код от девет цифри, всяка от 1 до 9.")
    salt = token_bytes(16)
    db.execute("""
        INSERT OR REPLACE INTO administrator_recovery (singleton, salt, code_hash, is_numeric)
        VALUES (1, ?, ?, 1)
    """, (salt, _password_hash(code, salt)))


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
            db.execute("""
                CREATE TABLE IF NOT EXISTS administrator_recovery (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    salt BLOB NOT NULL,
                    code_hash BLOB NOT NULL,
                    is_numeric INTEGER NOT NULL DEFAULT 0,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    retry_after INTEGER NOT NULL DEFAULT 0
                )
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(administrator_recovery)")}
            for column in ("is_numeric", "failed_attempts", "retry_after"):
                if column not in columns:
                    db.execute(f"ALTER TABLE administrator_recovery ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")

    def has_users(self) -> bool:
        with closing(sqlite3.connect(self._path)) as db:
            return db.execute("SELECT 1 FROM accounts LIMIT 1").fetchone() is not None

    def register(self, username: str, password: str, code: str, *, administrator_password: str = ""):
        if code.strip() != REGISTRATION_CODE:
            raise AccountError("Кодът за регистрация е грешен.")
        key, salt, password_hash = _account_credentials(username, password)
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

    def has_numeric_recovery_code(self) -> bool:
        with closing(sqlite3.connect(self._path)) as db:
            return db.execute("SELECT 1 FROM administrator_recovery WHERE is_numeric = 1").fetchone() is not None

    def set_recovery_code(self, username: str, password: str, code: str):
        with closing(sqlite3.connect(self._path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            credentials = db.execute("""
                SELECT salt, password_hash FROM accounts JOIN administrator USING (username_key)
                WHERE username_key = ?
            """, (_username_key(username),)).fetchone()
            if not _matches(credentials, password):
                raise AccountError("Въведи правилната парола на администратора.")
            _store_recovery_code(db, code.strip())

    def reset_administrator(self, code: str, username: str, password: str, new_code: str = ""):
        with closing(sqlite3.connect(self._path)) as db, db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN IMMEDIATE")
            recovery = db.execute("""
                SELECT salt, code_hash, is_numeric, failed_attempts, retry_after FROM administrator_recovery
            """).fetchone()
            if recovery is None:
                raise AccountError("Още няма създаден код за възстановяване.")
            salt, code_hash, is_numeric, failures, retry_after = recovery
            now = int(time())
            if now < retry_after:
                raise AccountError(f"Опитай отново след {retry_after - now} секунди.")
            if retry_after:
                failures = 0
            candidate = code.strip() if is_numeric else "".join(code[:128].split()).replace("-", "").upper()
            if len(code) > 128 or not _matches((salt, code_hash), candidate):
                failures += 1
                retry_after = now + RECOVERY_PAUSE_SECONDS if failures >= RECOVERY_ATTEMPTS else 0
                db.execute("UPDATE administrator_recovery SET failed_attempts = ?, retry_after = ?",
                           (failures, retry_after))
                db.commit()
                raise AccountError("Кодът за възстановяване е грешен.")
            administrator = db.execute("SELECT username_key FROM administrator").fetchone()
            if administrator is None:
                raise AccountError("Няма администраторски профил за възстановяване.")
            key, salt, password_hash = _account_credentials(username, password)
            old_key = administrator[0]
            if key == old_key:
                db.execute("UPDATE accounts SET salt = ?, password_hash = ? WHERE username_key = ?",
                           (salt, password_hash, key))
            else:
                try:
                    db.execute("INSERT INTO accounts VALUES (?, ?, ?)", (key, salt, password_hash))
                except sqlite3.IntegrityError as exc:
                    raise AccountError("Това потребителско име вече е регистрирано.") from exc
                db.execute("UPDATE administrator SET username_key = ? WHERE singleton = 1", (key,))
                db.execute("DELETE FROM accounts WHERE username_key = ?", (old_key,))
            if new_code.strip():
                _store_recovery_code(db, new_code.strip())
            else:
                db.execute("UPDATE administrator_recovery SET failed_attempts = 0, retry_after = 0")

    def is_administrator(self, username: str) -> bool:
        with closing(sqlite3.connect(self._path)) as db:
            return db.execute(
                "SELECT 1 FROM administrator WHERE username_key = ?", (_username_key(username),)
            ).fetchone() is not None

    def authenticate(self, username: str, password: str, *, administrator_only: bool = False) -> bool:
        with closing(sqlite3.connect(self._path)) as db:
            record = db.execute("""
                SELECT salt, password_hash FROM accounts
                WHERE username_key = :username AND
                    (NOT :administrator_only OR username_key = (SELECT username_key FROM administrator))
            """, {"username": _username_key(username), "administrator_only": administrator_only}).fetchone()
        return _matches(record, password)
