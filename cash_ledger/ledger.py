"""Validation, exact arithmetic and SQLite storage for the cash ledger."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from itertools import zip_longest
from pathlib import Path
import re
import sqlite3
from typing import Mapping

SALE = "--||--"
WEIGHTS = ("gold", "newGold", "silver", "newSilver")
CONTRACT_FIELDS = ("marker", "contract", "interest", "principal", *WEIGHTS)
CASH_FIELDS = ("income", "cost")
PLEDGE_FIELDS = ("pledge", "pledgeAmount")
PURCHASE_FIELDS = ("buyGold", "buySilver")
MONETARY = ("interest", "principal", "income", "cost", "pledgeAmount", *PURCHASE_FIELDS)
WEIGHT_ERROR = "Един етикет допуска само един грамаж. Остави едно попълнено поле."
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
DECIMAL = re.compile(r"(-?)([0-9]{1,12})(?:[,.]([0-9]{1,2}))?(?:\s+(.+))?", re.DOTALL)
NUMBER = re.compile(r"[0-9]{1,24}")

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

BALANCE_SQL = """
SELECT
    (SELECT opening_cash FROM settings WHERE singleton = 1)
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
    totals: dict[str, int]
    summary: dict[str, int]


@dataclass(frozen=True)
class SaveResult:
    cleared: tuple[str, ...]
    next_pledge: str | None
    count: int


def weight_error(fields: Mapping[str, str]) -> str:
    return WEIGHT_ERROR if sum(bool(fields.get(key, "").strip()) for key in WEIGHTS) > 1 else ""


def _decimal(text: str, name: str, *, note: bool = False, signed: bool = False) -> tuple[int, str]:
    match = DECIMAL.fullmatch(text)
    if not match or (match[1] and not signed) or (match[4] and not note):
        raise ValidationError(f"Въведи валидна стойност в „{name}“.")
    units = int(match[2]) * 100 + int((match[3] or "").ljust(2, "0"))
    return (-units if match[1] else units), (match[4] or "")


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
    if marker in ("1", "-"):
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


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                db.execute("PRAGMA journal_mode = WAL")
                db.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")
            elif version != 1:
                raise sqlite3.DatabaseError("Тази версия на базата данни изисква по-нова програма.")

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path)
        try:
            db.row_factory = sqlite3.Row
            with db:
                yield db
        finally:
            db.close()

    def opening_cash(self) -> int:
        with self._connection() as db:
            return db.execute("SELECT opening_cash FROM settings WHERE singleton = 1").fetchone()[0]

    def set_opening_cash(self, text: str) -> None:
        amount, _ = _decimal(text.strip(), "Начална каса", signed=True)
        with self._connection() as db:
            db.execute("UPDATE settings SET opening_cash = ? WHERE singleton = 1", (amount,))

    def save(self, day: date, fields: Mapping[str, str]) -> SaveResult:
        fields = {key: value.strip() for key, value in fields.items()}
        error = weight_error(fields)
        if error:
            raise ValidationError(error)

        iso = day.isoformat()
        contract = _contract(iso, fields)
        cash = _pair(iso, fields, CASH_FIELDS)
        pledge = _pledge(iso, fields)
        purchase = _pair(iso, fields, PURCHASE_FIELDS)
        records = (
            (contract, CONTRACT_FIELDS, "INSERT INTO contracts (day, marker, contract_no, interest, principal,"
             " weight_kind, weight, weight_note) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"),
            (cash, CASH_FIELDS, "INSERT INTO cash_movements (day, income, cost, income_note, cost_note)"
             " VALUES (?, ?, ?, ?, ?)"),
            (pledge, PLEDGE_FIELDS, "INSERT INTO pledges (day, pledge_no, amount) VALUES (?, ?, ?)"),
            (purchase, PURCHASE_FIELDS, "INSERT INTO purchases (day, gold, silver, gold_note, silver_note)"
             " VALUES (?, ?, ?, ?, ?)"),
        )
        if not any(record for record, _, _ in records):
            if fields.get("pledge"):
                raise ValidationError("Въведи сумата на залога.")
            raise ValidationError("Въведи поне една операция.")

        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if contract and not contract[1] and db.execute(
                "SELECT 1 FROM contracts WHERE day = ? AND contract_no = ?", (iso, contract[2])
            ).fetchone():
                raise ValidationError(f"Номер {contract[2]} вече е в таблицата за този ден.")
            for record, _, statement in records:
                if record is not None:
                    db.execute(statement, record)

        cleared = tuple(key for record, keys, _ in records if record is not None for key in keys)
        next_pledge = None
        if pledge:
            next_pledge = str(int(pledge[1]) + 1) if NUMBER.fullmatch(pledge[1]) else ""
        return SaveResult(cleared, next_pledge, sum(record is not None for record, _, _ in records))

    def day(self, day: date) -> DayLedger:
        iso = day.isoformat()
        with self._connection() as db:
            db.execute("BEGIN")
            contracts = [_contract_cells(row) for row in db.execute(
                "SELECT * FROM contracts WHERE day = ? ORDER BY id", (iso,)
            )]
            cash = [_pair_cells(row, CASH_FIELDS, CASH_FIELDS) for row in db.execute(
                "SELECT * FROM cash_movements WHERE day = ? ORDER BY id", (iso,)
            )]
            pledges = [{"pledge": Cell(row["pledge_no"]), "pledgeAmount": Cell(row["amount"])}
                       for row in db.execute("SELECT * FROM pledges WHERE day = ? ORDER BY id", (iso,))]
            purchases = [_pair_cells(row, ("gold", "silver"), PURCHASE_FIELDS) for row in db.execute(
                "SELECT * FROM purchases WHERE day = ? ORDER BY id", (iso,)
            )]
            balance = db.execute(BALANCE_SQL, {"day": iso}).fetchone()[0]

        rows = [{key: cell for block in blocks if block for key, cell in block.items()}
                for blocks in zip_longest(contracts, cash, pledges, purchases)]
        totals = {key: sum(row[key].value for row in rows if key in row) for key in MONETARY}
        unmarked = [row for row in contracts if not row["marker"].value]
        incoming = totals["interest"] + totals["principal"] + totals["income"]
        outgoing = totals["cost"] + totals["pledgeAmount"] + totals["buyGold"] + totals["buySilver"]
        return DayLedger(rows, totals, {
            "cash": balance,
            "profit": totals["interest"],
            "interest": sum(row["interest"].value for row in unmarked),
            "redemption": sum(row["principal"].value for row in unmarked),
            "pledges": totals["pledgeAmount"],
            "incoming": incoming,
            "outgoing": outgoing,
            "net": incoming - outgoing,
        })
