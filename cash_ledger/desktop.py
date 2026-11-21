"""Qt bindings for the ledger screen."""

from datetime import date, timedelta
from pathlib import Path
import sqlite3

from PySide6.QtCore import QByteArray, Property, QAbstractListModel, QLocale, QModelIndex, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .ledger import Ledger, MONETARY, ValidationError, WEIGHTS, weight_error

COLUMNS = (
    ("marker", "Пр.", "Маркер за продажба", "", 55),
    ("contract", "Д-р. Н.", "Номер на договор или етикет", "", 86),
    ("interest", "Л.", "Лихва", "+", 63),
    ("principal", "Г.", "Главница", "+", 69),
    ("gold", "Зл./гр.", "Злато, грамове", "", 73),
    ("newGold", "Н. Зл.", "Ново злато, грамове", "", 73),
    ("silver", "Ср./гр.", "Сребро, грамове", "", 73),
    ("newSilver", "Н. Ср.", "Ново сребро, грамове", "", 73),
    ("income", "П.", "Приход", "+", 83),
    ("cost", "Р.", "Разход", "−", 83),
    ("pledge", "Н-р Д.", "Номер на залог", "", 80),
    ("pledgeAmount", "С. З.", "Сума на залога", "−", 77),
    ("buyGold", "К. З.", "Купено злато", "−", 77),
    ("buySilver", "К. С.", "Купено сребро", "−", 77),
)
QML_COLUMNS = [{"key": key, "title": title, "label": label, "side": side, "width": width,
                "weight": key in WEIGHTS, "number": key in (*MONETARY, *WEIGHTS), "split": index in (8, 10, 12)}
               for index, (key, title, label, side, width) in enumerate(COLUMNS)]
STORE_ERROR = "Базата данни е недостъпна. "


def decimal_text(amount: int, *, grouping: bool = True) -> str:
    whole, cents = divmod(abs(amount), 100)
    integer = f"{whole:,}".replace(",", "\u00a0") if grouping else str(whole)
    return ("-" if amount < 0 else "") + f"{integer},{cents:02d}"


def money(amount: int, signed: bool = False) -> str:
    return ("+" if signed and amount > 0 else "") + decimal_text(amount) + " €"


def _screen_row(row):
    cells = []
    for column in QML_COLUMNS:
        key = column["key"]
        cell = row.get(key)
        text = ""
        note = ""
        price = ""
        calculation = ""
        if cell is not None:
            if key not in WEIGHTS or cell.value:
                text = decimal_text(cell.value) if column["number"] else cell.value
            note = cell.note
            if cell.unit_price is not None:
                price = money(cell.unit_price) + "/г"
                sale = row["interest"].value + row["principal"].value
                calculation = f"{money(sale)} ÷ {text} г = {price}"
        cells.append({"text": text, "note": note, "price": price, "calculation": calculation})
    return cells


class DailyRows(QAbstractListModel):
    Cells = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def roleNames(self):
        return {self.Cells: QByteArray(b"cells")}

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == self.Cells and index.isValid() and 0 <= index.row() < len(self._rows):
            return self._rows[index.row()]
        return None

    def replace(self, rows):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class LedgerWindow(QObject):
    changed = Signal()

    def __init__(self, database: Path, parent=None):
        super().__init__(parent)
        self._ledger = Ledger(database)
        self._day = date.today()
        self._rows = DailyRows(self)
        self._summary = {}
        self._totals = []
        self._widths = []
        self._opening = 0
        self._refresh()

    def _refresh(self):
        day = self._ledger.day(self._day)
        display = [_screen_row(row) for row in day.rows]
        self._totals = [decimal_text(day.totals[col["key"]]) if col["key"] in day.totals else ""
                        for col in QML_COLUMNS]
        font = QFont()
        font.setPixelSize(15)
        font.setBold(True)
        totals_metrics = QFontMetrics(font)
        weight_metrics = QFontMetrics(font)
        font.setBold(False)
        font.setPixelSize(13)
        text_metrics = QFontMetrics(font)
        font.setPixelSize(11)
        price_metrics = QFontMetrics(font)
        self._widths = [max(col["width"], totals_metrics.horizontalAdvance(self._totals[index]) + 20)
                        for index, col in enumerate(QML_COLUMNS)]
        for row in display:
            for index, cell in enumerate(row):
                value_metrics = weight_metrics if QML_COLUMNS[index]["weight"] else text_metrics
                self._widths[index] = max(self._widths[index],
                                          value_metrics.horizontalAdvance(cell["text"]) + 20,
                                          price_metrics.horizontalAdvance(cell["price"]) + 20)
        self._summary = {key: money(amount, key in ("incoming", "net"))
                         for key, amount in day.summary.items()}
        self._summary["outgoing"] = money(-day.summary["outgoing"])
        self._opening = self._ledger.opening_cash()
        self._rows.replace(display)
        self.changed.emit()

    @Property(QObject, constant=True)
    def rows(self):
        return self._rows

    @Property("QVariantList", constant=True)
    def columns(self):
        return QML_COLUMNS

    @Property("QVariantList", notify=changed)
    def widths(self):
        return self._widths

    @Property("QVariantList", notify=changed)
    def totals(self):
        return self._totals

    @Property("QVariantMap", notify=changed)
    def summary(self):
        return self._summary

    @Property(str, notify=changed)
    def dateText(self):
        return QLocale("bg_BG").toString(self._day, "d MMMM yyyy")

    @Property(str, notify=changed)
    def dateIso(self):
        return self._day.isoformat()

    @Property(bool, notify=changed)
    def isToday(self):
        return self._day == date.today()

    @Property(str, notify=changed)
    def openingText(self):
        return decimal_text(self._opening, grouping=False)

    @Slot(str, result=str)
    def setOpening(self, value):
        try:
            self._ledger.set_opening_cash(value)
            self._refresh()
        except ValidationError as error:
            return str(error)
        except sqlite3.Error as error:
            return STORE_ERROR + str(error)
        return ""

    @Slot(str, result=str)
    def goTo(self, value):
        try:
            target = date.fromisoformat(value)
        except ValueError:
            return "Въведи дата във формат ГГГГ-ММ-ДД."
        if target > date.today():
            return "Избери днешна или по-ранна дата."
        return self._select(target)

    @Slot(int, result=str)
    def shiftDay(self, days):
        try:
            target = self._day + timedelta(days=days)
        except OverflowError:
            return "Няма по-ранна дата."
        return self._select(min(target, date.today()))

    @Slot(result=str)
    def goToday(self):
        return self._select(date.today())

    def _select(self, target):
        previous = self._day
        self._day = target
        try:
            self._refresh()
        except sqlite3.Error as error:
            self._day = previous
            return STORE_ERROR + str(error)
        return ""

    @Slot("QVariantMap", result=str)
    def draftWeightError(self, fields):
        return weight_error(fields)

    @Slot("QVariantMap", result="QVariantMap")
    def saveDraft(self, fields):
        try:
            result = self._ledger.save(date.today(), fields)
        except ValidationError as error:
            return {"ok": False, "message": str(error)}
        except sqlite3.Error as error:
            return {"ok": False, "message": STORE_ERROR + str(error)}

        message = "Записана е 1 операция." if result.count == 1 else f"Записани са {result.count} операции."
        refresh_error = self.goToday()
        if refresh_error:
            message += " " + refresh_error
        return {"ok": True, "cleared": list(result.cleared), "pledge": result.next_pledge or "",
                "message": message}


def make_window(database: Path):
    QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    controller = LedgerWindow(database, engine)
    engine.setInitialProperties({"controller": controller})
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("Main.qml"))))
    return engine, controller
