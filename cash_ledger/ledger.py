"""Validation, exact arithmetic and SQLite storage for the desktop journal."""

from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import date, datetime
import errno
from itertools import zip_longest
import os
from pathlib import Path
import re
import sqlite3
from typing import Mapping

SALE = "--||--"
SALE_MARKERS = (SALE, "1", "-")
WEIGHTS = ("gold", "newGold", "silver", "newSilver")
CONTRACT_FIELDS = ("marker", "contract", "interest", "principal", *WEIGHTS)
CASH_FIELDS = ("income", "cost")
PLEDGE_FIELDS = ("pledge", "pledgeAmount")
PURCHASE_FIELDS = ("buyGold", "buySilver")
BLOCKS = {
    "contracts": (CONTRACT_FIELDS, (
        "marker", "contract_no", "interest", "principal", "weight_kind", "weight", "weight_note",
    )),
    "cash_movements": (CASH_FIELDS, ("income", "cost", "income_note", "cost_note")),
    "pledges": (PLEDGE_FIELDS, ("pledge_no", "amount")),
    "purchases": (PURCHASE_FIELDS, ("gold", "silver", "gold_note", "silver_note")),
}
MONETARY = ("interest", "principal", "income", "cost", "pledgeAmount", *PURCHASE_FIELDS)
WEIGHT_ERROR = "Един етикет допуска само един грамаж. Остави едно попълнено поле."
WEIGHT_WITHOUT_SALE = "Грамаж се допуска само при продажба. Въведи „1“ в „Пр.“ или изчисти грамажа."
MONEY_FIELDS = {
    "interest": "Лихва",
    "principal": "Главница",
    "income": "Приход",
    "cost": "Разход",
    "pledgeAmount": "Сума на залога",
    "buyGold": "Купено злато",
    "buySilver": "Купено сребро",
    "gold": "Злато",
    "newGold": "Ново злато",
    "silver": "Сребро",
    "newSilver": "Ново сребро",
}
DECIMAL = re.compile(r"([0-9]{1,12})(?:[,.]([0-9]{1,2}))?(?:\s+(.+))?", re.DOTALL)
NUMBER = re.compile(r"[0-9]{1,24}")
SEARCH_LIMIT = 100

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    opening_cash INTEGER NOT NULL
);
INSERT OR IGNORE INTO settings VALUES (1, 0);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    marker TEXT NOT NULL,
    contract_no TEXT NOT NULL,
    interest INTEGER NOT NULL CHECK (interest >= 0),
    principal INTEGER NOT NULL CHECK (principal >= 0),
    weight_kind TEXT,
    weight INTEGER,
    weight_note TEXT NOT NULL,
    CHECK ((weight_kind IS NULL AND weight IS NULL) OR
           (weight_kind IS NOT NULL AND weight_kind IN ('gold','newGold','silver','newSilver')
            AND weight IS NOT NULL AND weight >= 0))
);
CREATE INDEX IF NOT EXISTS contracts_by_day ON contracts(day, id);
CREATE UNIQUE INDEX IF NOT EXISTS unique_redemption
    ON contracts(day, contract_no) WHERE marker = '';

CREATE TABLE IF NOT EXISTS cash_movements (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    income INTEGER CHECK (income >= 0),
    cost INTEGER CHECK (cost >= 0),
    income_note TEXT NOT NULL,
    cost_note TEXT NOT NULL,
    CHECK (income IS NOT NULL OR cost IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS cash_by_day ON cash_movements(day, id);

CREATE TABLE IF NOT EXISTS pledges (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    pledge_no TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount >= 0)
);
CREATE INDEX IF NOT EXISTS pledges_by_day ON pledges(day, id);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    gold INTEGER CHECK (gold >= 0),
    silver INTEGER CHECK (silver >= 0),
    gold_note TEXT NOT NULL,
    silver_note TEXT NOT NULL,
    CHECK (gold IS NOT NULL OR silver IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS purchases_by_day ON purchases(day, id);
PRAGMA user_version = 1;
"""

REVISION_SCHEMA = """
CREATE TABLE IF NOT EXISTS revisions (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    closed_at TEXT NOT NULL,
    operation_count INTEGER NOT NULL CHECK (operation_count > 0),
    profit INTEGER NOT NULL,
    sold_gold INTEGER NOT NULL,
    sold_new_gold INTEGER NOT NULL,
    sold_silver INTEGER NOT NULL,
    sold_new_silver INTEGER NOT NULL,
    income INTEGER NOT NULL,
    cost INTEGER NOT NULL,
    bought_gold INTEGER NOT NULL,
    bought_silver INTEGER NOT NULL,
    closing INTEGER NOT NULL
)
"""
REVISION_FIELDS = (
    "profit", "sold_gold", "sold_new_gold", "sold_silver", "sold_new_silver",
    "income", "cost", "bought_gold", "bought_silver", "closing",
)

BALANCE_SQL = """
SELECT
    COALESCE((SELECT closing FROM revisions WHERE day <= :day ORDER BY id DESC LIMIT 1), 0)
    + COALESCE((SELECT SUM(interest + principal) FROM contracts WHERE day <= :day), 0)
    + COALESCE((SELECT SUM(COALESCE(income, 0) - COALESCE(cost, 0))
                FROM cash_movements WHERE day <= :day), 0)
    - COALESCE((SELECT SUM(amount) FROM pledges WHERE day <= :day), 0)
    - COALESCE((SELECT SUM(COALESCE(gold, 0) + COALESCE(silver, 0))
                FROM purchases WHERE day <= :day), 0)
"""


class ValidationError(ValueError):
    """A draft the cashier can correct before saving."""


@dataclass(frozen=True)
class Cell:
    value: str | int
    note: str = ""
    unit_price: int | None = None


@dataclass(frozen=True)
class DayLedger:
    rows: list[dict[str, Cell]]
    operation_ids: list[dict[str, int]]
    summary: dict[str, int]

    @property
    def carried_cash(self) -> int:
        return self.summary["cash"] - self.summary["net"]


@dataclass(frozen=True)
class CashDay:
    day: date
    carried: int
    movement: int
    closing: int


@dataclass(frozen=True)
class RevisionSnapshot:
    day: date
    totals: dict[str, int]
    operation_count: int
    previous_revision: int | None


@dataclass(frozen=True)
class ClosedRevision:
    closed_at: datetime
    totals: dict[str, int]


@dataclass(frozen=True)
class NumberMatch:
    block: str
    operation_id: int
    day: date
    number: str
    kind: str
    amount: int


@dataclass(frozen=True)
class SaveResult:
    cleared: tuple[str, ...]
    next_pledge: str | None
    count: int


def weight_error(fields: Mapping[str, str]) -> str:
    populated = sum(bool(fields.get(key, "").strip()) for key in WEIGHTS)
    if populated > 1:
        return WEIGHT_ERROR
    if populated and fields.get("marker", "").strip() not in SALE_MARKERS:
        return WEIGHT_WITHOUT_SALE
    return ""


def _decimal(text: str, name: str, *, note: bool = False) -> tuple[int, str]:
    match = DECIMAL.fullmatch(text)
    if not match or (match[3] and not note):
        raise ValidationError(f"Въведи валидна стойност в „{name}“.")
    units = int(match[1]) * 100 + int((match[2] or "").ljust(2, "0"))
    return units, (match[3] or "")


def _amount(fields: Mapping[str, str], key: str, *, note: bool = False) -> tuple[int | None, str]:
    return _decimal(fields[key], MONEY_FIELDS[key], note=note) if fields.get(key) else (None, "")


def _contract(day: str, fields: Mapping[str, str]) -> tuple | None:
    if not any(fields.get(key) for key in CONTRACT_FIELDS):
        return None
    number = fields.get("contract", "")
    if not NUMBER.fullmatch(number):
        raise ValidationError("Въведи номер на договор или етикет.")
    interest = _decimal(fields.get("interest", ""), MONEY_FIELDS["interest"])[0]
    principal = _decimal(fields.get("principal", ""), MONEY_FIELDS["principal"])[0]
    marker = fields.get("marker", "")
    if marker in SALE_MARKERS:
        marker = SALE
    kind = next((key for key in WEIGHTS if fields.get(key)), None)
    weight, note = _amount(fields, kind, note=True) if kind else (None, "")
    return day, marker, number, interest, principal, kind, weight, note


def _pair(day: str, fields: Mapping[str, str], keys: tuple[str, str]) -> tuple | None:
    if not any(fields.get(key) for key in keys):
        return None
    left, left_note = _amount(fields, keys[0], note=True)
    right, right_note = _amount(fields, keys[1], note=True)
    return day, left, right, left_note, right_note


def _pledge(day: str, fields: Mapping[str, str]) -> tuple | None:
    if not fields.get("pledgeAmount"):
        return None
    number = fields.get("pledge", "")
    if not number:
        raise ValidationError("Въведи номер на залог.")
    amount = _decimal(fields["pledgeAmount"], MONEY_FIELDS["pledgeAmount"])[0]
    return day, number, amount


def _contract_cells(record: sqlite3.Row) -> dict[str, Cell]:
    cells = {
        "marker": Cell(record["marker"]),
        "contract": Cell(record["contract_no"]),
        "interest": Cell(record["interest"]),
        "principal": Cell(record["principal"]),
    }
    weight = record["weight"]
    if record["weight_kind"] is not None:
        unit_price = None
        if record["marker"] == SALE and weight:
            total = record["interest"] + record["principal"]
            price, remainder = divmod(total * 100, weight)
            unit_price = price + (2 * remainder >= weight)
        cells[record["weight_kind"]] = Cell(weight, record["weight_note"], unit_price)
    return cells


def _pair_cells(record: sqlite3.Row, columns: tuple[str, str], keys: tuple[str, str]) -> dict[str, Cell]:
    return {
        key: Cell(record[column], record[column + "_note"])
        for column, key in zip(columns, keys)
        if record[column] is not None
    }


def _cells(block: str, record: sqlite3.Row) -> dict[str, Cell]:
    if block == "contracts":
        return _contract_cells(record)
    if block == "cash_movements":
        return _pair_cells(record, CASH_FIELDS, CASH_FIELDS)
    if block == "pledges":
        return {"pledge": Cell(record["pledge_no"]), "pledgeAmount": Cell(record["amount"])}
    return _pair_cells(record, ("gold", "silver"), PURCHASE_FIELDS)


def _draft_record(block: str, day: str, fields: Mapping[str, str]) -> tuple | None:
    if block == "contracts":
        return _contract(day, fields)
    if block == "pledges":
        return _pledge(day, fields)
    return _pair(day, fields, BLOCKS[block][0])


def _checked_fields(fields: Mapping[str, str]) -> dict[str, str]:
    clean = {key: value.strip() for key, value in fields.items()}
    if problem := weight_error(clean):
        raise ValidationError(problem)
    return clean


def _check_redemption(db: sqlite3.Connection, record: tuple, exclude: int | None = None) -> None:
    if not record[1] and db.execute(
        "SELECT 1 FROM contracts WHERE day = ? AND contract_no = ? AND id IS NOT ?",
        (record[0], record[2], exclude),
    ).fetchone():
        raise ValidationError(f"Номер {record[2]} вече е в таблицата за този ден.")


def _schema_signature(db: sqlite3.Connection) -> list[tuple]:
    return [tuple(row) for row in db.execute(
        "SELECT type, name, sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
    )]


def _convert_opening_cash(db: sqlite3.Connection) -> None:
    """Upgrade a v1 balance in place while keeping old archive schemas readable."""
    opening = db.execute("SELECT opening_cash FROM settings WHERE singleton = 1").fetchone()[0]
    if opening == 0:
        return
    first_day = db.execute(
        "SELECT min(first_day) FROM (" +
        " UNION ALL ".join(f"SELECT min(day) AS first_day FROM {block}" for block in BLOCKS) +
        ")"
    ).fetchone()[0]
    funding_day = (date.fromordinal(max(1, date.fromisoformat(first_day).toordinal() - 1))
                   if first_day else date.today())
    note = "Пренесено салдо от старата начална каса"
    if opening > 0:
        movement = (funding_day.isoformat(), opening, None, note, "")
    else:
        movement = (funding_day.isoformat(), None, -opening, "", note)
    db.execute(
        "INSERT INTO cash_movements (day, income, cost, income_note, cost_note) VALUES (?, ?, ?, ?, ?)",
        movement,
    )
    db.execute("UPDATE settings SET opening_cash = 0 WHERE singleton = 1")


def _latest_revision(db: sqlite3.Connection):
    return db.execute("SELECT id, day, closing FROM revisions ORDER BY id DESC LIMIT 1").fetchone()


def _require_current_period(db: sqlite3.Connection, day: str) -> None:
    latest = _latest_revision(db)
    if latest is not None and day < latest["day"]:
        raise ValidationError("Датата е в приключен период. Обобщението е в „Ревизии“.")


class Ledger:
    def __init__(self, path: Path, *, archive_directory: Path | None = None):
        self.path = path
        self._preferred_archive = archive_directory
        self._archive_fallback = path.parent / "Архиви" if archive_directory else path.parent
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                db.execute("PRAGMA journal_mode = WAL")
                db.executescript(
                    "BEGIN IMMEDIATE;\n" + SCHEMA + REVISION_SCHEMA + ";\nPRAGMA user_version = 2;\nCOMMIT;"
                )
            elif version not in (1, 2):
                raise sqlite3.DatabaseError("Тази версия на базата данни изисква по-нова програма.")
            elif version == 1 or db.execute("SELECT opening_cash FROM settings WHERE singleton = 1").fetchone()[0]:
                db.execute("BEGIN IMMEDIATE")
                db.execute(REVISION_SCHEMA)
                db.execute("PRAGMA user_version = 2")
                _convert_opening_cash(db)

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path)
        try:
            db.row_factory = sqlite3.Row
            with db:
                yield db
        finally:
            db.close()

    def save(self, day: date, fields: Mapping[str, str]) -> SaveResult:
        fields = _checked_fields(fields)
        iso = day.isoformat()
        records = {block: record for block in BLOCKS if (record := _draft_record(block, iso, fields))}
        if not records:
            if fields.get("pledge"):
                raise ValidationError("Въведи сумата на залога.")
            raise ValidationError("Въведи поне една операция.")

        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            _require_current_period(db, iso)
            if contract := records.get("contracts"):
                _check_redemption(db, contract)
            for block, record in records.items():
                columns = ", ".join(BLOCKS[block][1])
                placeholders = ", ".join("?" for _ in record)
                db.execute(f"INSERT INTO {block} (day, {columns}) VALUES ({placeholders})", record)

        cleared = tuple(key for block in records for key in BLOCKS[block][0])
        next_pledge = None
        if pledge := records.get("pledges"):
            next_pledge = str(int(pledge[1]) + 1) if NUMBER.fullmatch(pledge[1]) else ""
        return SaveResult(cleared, next_pledge, len(records))

    def _operation(self, db: sqlite3.Connection, day: date, block: str, operation_id: int) -> dict[str, Cell]:
        if block not in BLOCKS:
            raise ValidationError("Избери операция от таблицата.")
        row = db.execute(f"SELECT * FROM {block} WHERE day = ? AND id = ?",
                         (day.isoformat(), operation_id)).fetchone()
        if row is None:
            raise ValidationError("Операцията вече не е налична. Отвори датата отново.")
        return _cells(block, row)

    def read_operation(self, day: date, block: str, operation_id: int) -> dict[str, Cell]:
        with self._connection() as db:
            return self._operation(db, day, block, operation_id)

    def edit(self, day: date, block: str, operation_id: int,
             fields: Mapping[str, str], original: Mapping[str, Cell]) -> None:
        if block not in BLOCKS:
            raise ValidationError("Избери операция от таблицата.")
        values = _checked_fields({key: fields.get(key, "") for key in BLOCKS[block][0]})
        record = _draft_record(block, day.isoformat(), values)
        if record is None:
            raise ValidationError("Попълни данните на операцията.")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            _require_current_period(db, day.isoformat())
            if self._operation(db, day, block, operation_id) != original:
                raise ValidationError("Операцията е променена. Отвори я отново, за да видиш актуалните данни.")
            if block == "contracts":
                _check_redemption(db, record, operation_id)
            columns = ", ".join(f"{name} = ?" for name in BLOCKS[block][1])
            db.execute(f"UPDATE {block} SET {columns} WHERE id = ? AND day = ?",
                       (*record[1:], operation_id, record[0]))

    def archive_directory(self) -> Path:
        if self._preferred_archive is not None:
            try:
                self._preferred_archive.mkdir(mode=0o700, parents=True, exist_ok=True)
            except OSError:
                pass
            else:
                if os.access(self._preferred_archive, os.W_OK | os.X_OK):
                    return self._preferred_archive
        self._archive_fallback.mkdir(mode=0o700, parents=True, exist_ok=True)
        return self._archive_fallback

    def _safety_backup(self, action: str, when: datetime) -> Path:
        stamp = when.strftime("%Y%m%d-%H%M%S-%f")
        name = f"{self.path.stem}-before-{action}-{stamp}.sqlite3"
        directory = self.archive_directory()
        target = directory / name
        try:
            self.backup(target)
        except OSError as error:
            if directory == self._archive_fallback or error.errno not in (errno.EACCES, errno.EPERM, errno.EROFS):
                raise
            self._preferred_archive = None
            target = self.archive_directory() / name
            self.backup(target)
        return target

    def backup(self, target: Path) -> None:
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        try:
            with self._connection() as source, closing(sqlite3.connect(target)) as archive:
                source.backup(archive)
                archive.execute("PRAGMA journal_mode = DELETE")
        except BaseException:
            target.unlink(missing_ok=True)
            raise

    def restore(self, archive: Path) -> Path:
        if archive.samefile(self.path):
            raise ValidationError("Избери архивен файл на дневника.")
        with closing(sqlite3.connect(archive.resolve().as_uri() + "?mode=ro", uri=True)) as source:
            source.execute("PRAGMA trusted_schema = OFF")
            source.execute("BEGIN")
            with self._connection() as destination:
                version = source.execute("PRAGMA user_version").fetchone()[0]
                expected_schema = _schema_signature(destination)
                if version == 1:
                    expected_schema = [entry for entry in expected_schema if entry[1] != "revisions"]
                compatible = version in (1, 2) and _schema_signature(source) == expected_schema
                if not compatible or source.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValidationError("Файлът не е валиден архив на тази версия на дневника.")
                if source.execute("SELECT opening_cash FROM settings WHERE singleton = 1").fetchone() is None:
                    raise ValidationError("В архива липсват настройките на дневника.")
                destination.execute("BEGIN IMMEDIATE")
                safety = self._safety_backup("restore", datetime.now())
                for table in ("settings", *BLOCKS, "revisions"):
                    destination.execute(f"DELETE FROM {table}")
                    if table == "revisions" and version == 1:
                        continue
                    records = source.execute(f"SELECT * FROM {table}")
                    placeholders = ", ".join("?" for _ in records.description)
                    destination.executemany(f"INSERT INTO {table} VALUES ({placeholders})", records)
                _convert_opening_cash(destination)
        return safety

    @staticmethod
    def _revision_totals(db: sqlite3.Connection, day: date) -> dict[str, int]:
        params = {"day": day.isoformat(), "sale": SALE}
        totals = dict(db.execute("""
            WITH contracts_totals AS (
                SELECT COALESCE(SUM(interest), 0) AS profit,
                       COALESCE(SUM(weight) FILTER (WHERE marker = :sale AND weight_kind = 'gold'), 0) AS sold_gold,
                       COALESCE(SUM(weight) FILTER (WHERE marker = :sale AND weight_kind = 'newGold'), 0) AS sold_new_gold,
                       COALESCE(SUM(weight) FILTER (WHERE marker = :sale AND weight_kind = 'silver'), 0) AS sold_silver,
                       COALESCE(SUM(weight) FILTER (WHERE marker = :sale AND weight_kind = 'newSilver'), 0) AS sold_new_silver
                FROM contracts WHERE day <= :day
            ), cash_totals AS (
                SELECT COALESCE(SUM(income), 0) AS income, COALESCE(SUM(cost), 0) AS cost
                FROM cash_movements WHERE day <= :day
            ), purchase_totals AS (
                SELECT COALESCE(SUM(gold), 0) AS bought_gold, COALESCE(SUM(silver), 0) AS bought_silver
                FROM purchases WHERE day <= :day
            )
            SELECT * FROM contracts_totals CROSS JOIN cash_totals CROSS JOIN purchase_totals
        """, params).fetchone())
        totals["closing"] = db.execute(BALANCE_SQL, params).fetchone()[0]
        return totals

    def revision_totals(self, day: date) -> dict[str, int]:
        with self._connection() as db:
            db.execute("BEGIN")
            return self._revision_totals(db, day)

    def _revision_snapshot(self, db: sqlite3.Connection, day: date) -> RevisionSnapshot:
        iso = day.isoformat()
        _require_current_period(db, iso)
        latest = _latest_revision(db)
        count = sum(db.execute(f"SELECT COUNT(*) FROM {block} WHERE day <= ?", (iso,)).fetchone()[0]
                    for block in BLOCKS)
        return RevisionSnapshot(day, self._revision_totals(db, day), count, latest["id"] if latest else None)

    def revision_snapshot(self, day: date) -> RevisionSnapshot:
        with self._connection() as db:
            db.execute("BEGIN")
            return self._revision_snapshot(db, day)

    def revision_history(self) -> list[ClosedRevision]:
        with self._connection() as db:
            return [
                ClosedRevision(datetime.fromisoformat(row["closed_at"]), {key: row[key] for key in REVISION_FIELDS})
                for row in db.execute("SELECT * FROM revisions ORDER BY id DESC")
            ]

    def current_period_start(self) -> date | None:
        with self._connection() as db:
            latest = _latest_revision(db)
            return date.fromisoformat(latest["day"]) if latest else None

    def close_revision(self, preview: RevisionSnapshot) -> Path:
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = self._revision_snapshot(db, preview.day)
            if current != preview:
                raise ValidationError("Операциите са променени. Отвори отново прегледа на ревизията.")
            if not current.operation_count:
                raise ValidationError("Няма операции за приключване.")

            closed_at = datetime.now().astimezone()
            safety = self._safety_backup("revision", closed_at)

            labels = ", ".join(REVISION_FIELDS)
            placeholders = ", ".join("?" for _ in REVISION_FIELDS)
            db.execute(
                f"INSERT INTO revisions (day, closed_at, operation_count, {labels}) VALUES (?, ?, ?, {placeholders})",
                (current.day.isoformat(), closed_at.isoformat(timespec="seconds"), current.operation_count,
                 *(current.totals[key] for key in REVISION_FIELDS)),
            )
            for block in BLOCKS:
                db.execute(f"DELETE FROM {block} WHERE day <= ?", (current.day.isoformat(),))
        return safety

    def cash_by_day(self, last_day: date) -> list[CashDay]:
        end = last_day.toordinal()
        start = max(1, end - 6)
        history = []
        with self._connection() as db:
            db.execute("BEGIN")
            latest = _latest_revision(db)
            first = date.fromisoformat(latest["day"]).toordinal() if latest else 0
            start = max(start, first)
            prior = date.fromordinal(start - 1).isoformat() if start > 1 else ""
            carried = latest["closing"] if start == first else db.execute(BALANCE_SQL, {"day": prior}).fetchone()[0]
            for ordinal in range(start, end + 1):
                day = date.fromordinal(ordinal)
                closing = db.execute(BALANCE_SQL, {"day": day.isoformat()}).fetchone()[0]
                history.append(CashDay(day, carried, closing - carried, closing))
                carried = closing
        return history

    def operation_days(self, first: date, last: date) -> list[str]:
        with self._connection() as db:
            queries = " UNION ".join(
                f"SELECT day FROM {block} WHERE day BETWEEN :first AND :last" for block in BLOCKS
            )
            return [row["day"] for row in db.execute(
                queries + " ORDER BY day", {"first": first.isoformat(), "last": last.isoformat()}
            )]

    def find_number(self, query: str) -> list[NumberMatch]:
        needle = query.strip().casefold()
        if not needle:
            return []
        with self._connection() as db:
            db.create_function("casefold", 1, str.casefold, deterministic=True)
            matches = db.execute("""
                SELECT * FROM (
                    SELECT 'contracts' AS block, id, day, contract_no AS number,
                           CASE WHEN marker = :sale THEN 'sale' ELSE 'contract' END AS kind,
                           interest + principal AS amount
                    FROM contracts WHERE instr(contract_no, :needle) > 0
                    UNION ALL
                    SELECT 'pledges', id, day, pledge_no, 'pledge', amount
                    FROM pledges WHERE instr(casefold(pledge_no), :needle) > 0
                )
                ORDER BY (casefold(number) = :needle) DESC, day DESC, block, id DESC
                LIMIT :limit
            """, {"needle": needle, "sale": SALE, "limit": SEARCH_LIMIT + 1})
            return [NumberMatch(row["block"], row["id"], date.fromisoformat(row["day"]),
                                row["number"], row["kind"], row["amount"]) for row in matches]

    def day(self, day: date) -> DayLedger:
        iso = day.isoformat()
        with self._connection() as db:
            db.execute("BEGIN")
            records = {block: [(row["id"], _cells(block, row)) for row in db.execute(
                f"SELECT * FROM {block} WHERE day = ? ORDER BY id", (iso,)
            )] for block in BLOCKS}
            balance = db.execute(BALANCE_SQL, {"day": iso}).fetchone()[0]

        rows = []
        operation_ids = []
        for entries in zip_longest(*records.values()):
            blocks = {block: entry for block, entry in zip(records, entries) if entry is not None}
            operation_ids.append({block: entry[0] for block, entry in blocks.items()})
            rows.append({key: cell for _, cells in blocks.values() for key, cell in cells.items()})
        totals = {key: sum(row[key].value for row in rows if key in row) for key in MONETARY}
        unmarked = [row for _, row in records["contracts"] if not row["marker"].value]
        incoming = totals["interest"] + totals["principal"] + totals["income"]
        outgoing = totals["cost"] + totals["pledgeAmount"] + totals["buyGold"] + totals["buySilver"]
        return DayLedger(rows, operation_ids, {
            "cash": balance,
            "profit": totals["interest"],
            "interest": sum(row["interest"].value for row in unmarked),
            "redemption": sum(row["principal"].value for row in unmarked),
            "pledges": totals["pledgeAmount"],
            "incoming": incoming,
            "outgoing": outgoing,
            "net": incoming - outgoing,
        })
