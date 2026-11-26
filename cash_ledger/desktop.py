"""Qt bindings for the ledger screen."""

from datetime import date, timedelta
from pathlib import Path
import sqlite3

from PySide6.QtCore import QByteArray, Property, QAbstractListModel, QLocale, QModelIndex, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .i18n import language, localized
from .ledger import BLOCKS, Ledger, MONETARY, SEARCH_LIMIT, ValidationError, WEIGHTS, weight_error

from .preferences import Preferences
from .snapshots import replace_archive
from .table_print import PrintColumn, print_table
from .updates import WindowsUpdates

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
FIELD_BLOCKS = {key: block for block, (fields, _) in BLOCKS.items() for key in fields}
BLOCK_LABELS = {"contracts": "Договор или продажба", "cash_movements": "Приход / разход",
                "pledges": "Залог", "purchases": "Покупка"}
SEARCH_LABELS = {"sale": "Продажба", "contract": "Договор", "pledge": "Залог"}
QML_COLUMNS = [{"key": key, "title": title, "label": label, "side": side, "width": width,
                "block": FIELD_BLOCKS[key],
                "weight": key in WEIGHTS, "number": key in (*MONETARY, *WEIGHTS), "split": index in (8, 10, 12)}
               for index, (key, title, label, side, width) in enumerate(COLUMNS)]
STORE_ERROR = "Базата данни е недостъпна. "


def decimal_text(amount: int, *, grouping: bool = True) -> str:
    whole, cents = divmod(abs(amount), 100)
    integer = f"{whole:,}".replace(",", "\u00a0") if grouping else str(whole)
    return ("-" if amount < 0 else "") + f"{integer},{cents:02d}"


def money(amount: int, signed: bool = False) -> str:
    return ("+" if signed and amount > 0 else "") + decimal_text(amount) + " €"


def _screen_row(row, operation_ids):
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
                price = money(cell.unit_price) + localized("/г")
                sale = row["interest"].value + row["principal"].value
                calculation = f"{money(sale)} ÷ {text} {localized('г')} = {price}"
        cells.append({"text": text, "note": note, "price": price, "calculation": calculation,
                      "operationId": str(operation_ids.get(column["block"], ""))})
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

    def __init__(self, database: Path, parent=None, *, session_enabled=False,
                 is_administrator=False, verify_admin=None, archive_directory=None):
        super().__init__(parent)
        self._ledger = Ledger(database, archive_directory=archive_directory)
        self._session_enabled = session_enabled
        self._is_administrator = is_administrator
        self._verify_admin = verify_admin
        self._last_local_day = date.today()
        self._day = self._last_local_day
        self._rows = DailyRows(self)
        self._summary = {}
        self._widths = []
        self._editing = None
        self._operation_ids = []
        self._period_start = date.min
        self._revision_preview = None
        self._refresh()
        self._day_timer = QTimer(self)
        self._day_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._day_timer.timeout.connect(self._follow_local_day)
        self._day_timer.start(1000)

    def _follow_local_day(self):
        today = date.today()
        if today != self._last_local_day and not self._select(today):
            self._last_local_day = today

    def _refresh(self):
        self._period_start = self._ledger.current_period_start() or date.min
        self._day = max(self._day, self._period_start)
        day = self._ledger.day(self._day)
        self._operation_ids = day.operation_ids
        display = [_screen_row(row, ids) for row, ids in zip(day.rows, day.operation_ids)]
        font = QFont()
        font.setPixelSize(15)
        font.setBold(True)
        weight_metrics = QFontMetrics(font)
        font.setBold(False)
        font.setPixelSize(13)
        text_metrics = QFontMetrics(font)
        font.setPixelSize(11)
        price_metrics = QFontMetrics(font)
        self._widths = [col["width"] for col in QML_COLUMNS]
        for row in display:
            for index, cell in enumerate(row):
                value_metrics = weight_metrics if QML_COLUMNS[index]["weight"] else text_metrics
                self._widths[index] = max(self._widths[index],
                                          value_metrics.horizontalAdvance(cell["text"]) + 20,
                                          price_metrics.horizontalAdvance(cell["price"]) + 20)
        self._summary = {key: money(amount, key in ("incoming", "net"))
                         for key, amount in day.summary.items()}
        self._summary["carried"] = money(day.carried_cash)
        self._summary["outgoing"] = money(-day.summary["outgoing"])
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

    @Property("QVariantMap", notify=changed)
    def summary(self):
        return self._summary

    @Property(str, notify=changed)
    def dateText(self):
        return QLocale("en_GB" if language() == "en" else "bg_BG").toString(self._day, "d MMMM yyyy")

    @Slot()
    def refreshLanguage(self):
        self._select(self._day)

    @Property(str, notify=changed)
    def dateIso(self):
        return self._day.isoformat()

    @Property(str, notify=changed)
    def todayIso(self):
        return date.today().isoformat()

    @Property(str, notify=changed)
    def periodStartIso(self):
        return self._period_start.isoformat()

    @Property(bool, notify=changed)
    def isToday(self):
        return self._day == date.today()

    @Slot(int, int, result="QStringList")
    def calendarDaysWithOperations(self, year, month):
        try:
            first = date(year, month, 1).toordinal()
            # MonthGrid shows six weeks, including spillover into the next month.
            return self._ledger.operation_days(
                date.fromordinal(max(1, first - 6)),
                date.fromordinal(min(date.max.toordinal(), first + 41)),
            )
        except (ValueError, sqlite3.Error):
            return []

    @Slot(str, result=str)
    def goTo(self, value):
        try:
            target = date.fromisoformat(value)
        except ValueError:
            return localized("Въведи дата във формат ГГГГ-ММ-ДД.")
        if target > date.today():
            return localized("Избери днешна или по-ранна дата.")
        return self._select(target)

    @Slot(int, result=str)
    def shiftDay(self, days):
        try:
            target = self._day + timedelta(days=days)
        except OverflowError:
            return localized("Няма по-ранна дата.")
        return self._select(min(target, date.today()))

    @Slot(result=str)
    def goToday(self):
        return self._select(date.today())

    def _operation_table_for_print(self, first_iso, last_iso):
        try:
            first = date.fromisoformat(first_iso) if first_iso else date.today()
            last = date.fromisoformat(last_iso) if last_iso else first
        except ValueError as error:
            raise ValidationError(localized("Избери начална и крайна дата.")) from error
        if first > last:
            raise ValidationError(localized("Началната дата трябва да е преди или на крайната дата."))
        if last > date.today():
            raise ValidationError(localized("Избери днешна или по-ранна крайна дата."))
        selected, totals = self._ledger.operation_period(first, last)
        if not selected:
            raise ValidationError(localized("Няма записани операции за избраните дати."))

        columns = []
        if first != last:
            columns.append(PrintColumn(localized("Дата"), 88))
        columns.extend(PrintColumn(
            " ".join(part for part in (localized(column["title"]), column["side"]) if part),
            column["width"], column["number"],
        ) for column in QML_COLUMNS)
        rows = []
        for day, row in selected:
            cells = [(cell["text"], cell["price"], cell["note"]) for cell in _screen_row(row, {})]
            if first != last:
                cells.insert(0, (day.strftime("%d.%m.%Y"),))
            rows.append(cells)
        if first == last:
            period = (localized("Дата"), first.strftime("%d.%m.%Y"))
        else:
            period = (localized("Период"), f"{first:%d.%m.%Y} – {last:%d.%m.%Y}")
        overview = (
            period, (localized("Каса"), money(totals["cash"])), (localized("Печалба"), money(totals["profit"])),
            (localized("Откуп"), money(totals["redemption"])), (localized("Залози"), money(totals["pledges"])),
            (localized("Лихви"), money(totals["interest"])),
        )
        return columns, rows, overview

    @Slot(str, str, result="QVariantMap")
    def printOperations(self, first_iso, last_iso):
        try:
            columns, rows, overview = self._operation_table_for_print(first_iso, last_iso)
            printed = print_table(columns, rows, overview)
        except (ValidationError, OSError, sqlite3.Error) as error:
            return {"ok": False, "message": str(error)}
        return {"ok": True, "printed": printed,
                "message": localized("Таблицата е изпратена за печат.") if printed else ""}

    @Property(bool, constant=True)
    def isAdministrator(self):
        return self._is_administrator

    @Property(bool, constant=True)
    def canAuthorizePeriod(self):
        return self._verify_admin is not None

    @Slot(result="QVariantMap")
    def revisionReport(self):
        today = date.today()
        try:
            self._revision_preview = self._ledger.revision_snapshot(today)
            history = self._ledger.revision_history()
        except ValidationError as error:
            return {"ok": False, "message": str(error)}
        except sqlite3.Error as error:
            return {"ok": False, "message": localized(STORE_ERROR) + str(error)}
        return {
            "ok": True,
            "operationCount": self._revision_preview.operation_count,
            "carry": money(self._revision_preview.totals["closing"]),
            "row": {
                "date": today.strftime("%d.%m.%Y"),
                **{key: decimal_text(value) for key, value in self._revision_preview.totals.items()},
            },
            "history": [
                {"date": record.closed_at.strftime("%d.%m.%Y %H:%M"),
                 **{key: decimal_text(value) for key, value in record.totals.items()}}
                for record in history
            ],
        }

    @Slot(str, str, result="QVariantMap")
    def closeRevision(self, administrator_username, administrator_password):
        if self._verify_admin is None:
            return {"ok": False, "message": localized("За нов период е нужно потвърждение от администратор.")}
        if self._revision_preview is None or self._revision_preview.day != date.today():
            return {"ok": False, "message": localized("Отвори отново прегледа на ревизията.")}
        try:
            if not self._verify_admin(administrator_username, administrator_password):
                return {"ok": False, "message": localized("Въведи правилните име и парола на администратора.")}
            self._ledger.close_revision(self._revision_preview)
        except ValidationError as error:
            self._revision_preview = None
            return {"ok": False, "message": str(error)}
        except (OSError, sqlite3.Error) as error:
            return {"ok": False, "message": localized("Ревизията не е приключена. ") + str(error)}
        self._revision_preview = None
        self._editing = None
        refresh_error = self._select(date.today())
        message = localized("Ревизията е записана. Автоматичният архив е обновен.")
        return {"ok": True, "message": f"{message} {refresh_error}".strip()}

    @Slot(str, result="QVariantMap")
    def findNumber(self, query):
        try:
            matches = self._ledger.find_number(query)
        except sqlite3.Error as error:
            return {"ok": False, "message": localized(STORE_ERROR) + str(error)}
        return {"ok": True, "truncated": len(matches) > SEARCH_LIMIT, "matches": [
            {"block": match.block, "id": str(match.operation_id), "iso": match.day.isoformat(),
             "date": match.day.strftime("%d.%m.%Y"), "number": match.number,
             "label": localized(SEARCH_LABELS[match.kind]), "amount": money(match.amount)}
            for match in matches[:SEARCH_LIMIT]
        ]}

    @Slot(str, str, str, result="QVariantMap")
    def goToSearchMatch(self, iso, block, operation_id):
        error = self.goTo(iso)
        if error:
            return {"ok": False, "message": error}
        for index, ids in enumerate(self._operation_ids):
            if block in ids and str(ids[block]) == operation_id:
                field = "pledge" if block == "pledges" else "contract"
                column = next(i for i, spec in enumerate(QML_COLUMNS) if spec["key"] == field)
                return {"ok": True, "row": index, "column": column}
        return {"ok": False, "message": localized("Операцията вече не е налична. Обнови търсенето.")}

    def _select(self, target):
        previous = self._day
        self._day = target
        try:
            period_start = self._ledger.current_period_start()
            if period_start is not None and target < period_start:
                self._day = previous
                return localized("Датата е в приключен период. Обобщението е в „Ревизии“.")
            self._refresh()
        except sqlite3.Error as error:
            self._day = previous
            return localized(STORE_ERROR) + str(error)
        return ""

    @Slot("QVariantMap", result=str)
    def draftWeightError(self, fields):
        return weight_error(fields)

    @Slot(result=QUrl)
    def automaticArchive(self):
        try:
            archive = self._ledger.automatic_archive_path()
            return QUrl.fromLocalFile(str(archive)) if archive.is_file() else QUrl()
        except OSError:
            return QUrl()

    def _archive_saved_operations(self) -> str:
        try:
            replace_archive(self._ledger.path, self._ledger.automatic_archive_path())
        except (OSError, sqlite3.Error):
            return localized("Не можа да се създаде копие на базата след тази операция.")
        return ""

    @Slot("QVariantMap", result="QVariantMap")
    def saveDraft(self, fields):
        try:
            result = self._ledger.save(date.today(), fields)
        except ValidationError as error:
            return {"ok": False, "message": str(error)}
        except sqlite3.Error as error:
            return {"ok": False, "message": localized(STORE_ERROR) + str(error)}

        message = (localized("Записана е 1 операция.") if result.count == 1
                   else localized("Записани са {count} операции.").format(count=result.count))
        archive_error = self._archive_saved_operations()
        refresh_error = self.goToday()
        return {"ok": True, "cleared": list(result.cleared), "pledge": result.next_pledge or "",
                "message": " ".join(filter(None, (message, archive_error, refresh_error))),
                "warning": bool(archive_error or refresh_error)}

    @Slot(str, str, result="QVariantMap")
    def openEdit(self, block, operation_id):
        self._editing = None
        try:
            record_id = int(operation_id)
            cells = self._ledger.read_operation(self._day, block, record_id)
        except (ValueError, sqlite3.Error) as error:
            return {"ok": False, "message": str(error)}
        self._editing = (self._day, block, record_id, cells)
        fields = []
        for column in QML_COLUMNS:
            if column["block"] != block:
                continue
            cell = cells.get(column["key"])
            text = ""
            if cell is not None:
                text = decimal_text(cell.value, grouping=False) if column["number"] else cell.value
                if cell.note:
                    text += " " + cell.note
            fields.append({"key": column["key"], "label": localized(column["label"]),
                           "weight": column["weight"], "text": text})
        return {"ok": True, "fields": fields, "title": localized(BLOCK_LABELS[block]), "date": self.dateText}

    @Slot("QVariantMap", result="QVariantMap")
    def saveEdit(self, fields):
        if self._editing is None:
            return {"ok": False, "message": localized("Избери операция от таблицата.")}
        day, block, record_id, original = self._editing
        try:
            self._ledger.edit(day, block, record_id, fields, original)
        except ValidationError as error:
            return {"ok": False, "message": str(error)}
        except sqlite3.Error as error:
            return {"ok": False, "message": localized(STORE_ERROR) + str(error)}
        self._editing = None
        archive_error = self._archive_saved_operations()
        refresh_error = self._select(self._day)
        return {"ok": True, "warning": bool(archive_error or refresh_error),
                "message": " ".join(filter(None, (localized("Корекцията е записана."), archive_error, refresh_error)))}

    @Slot(result=QUrl)
    def archiveFolder(self):
        try:
            return QUrl.fromLocalFile(str(self._ledger.archive_directory()))
        except OSError:
            return QUrl()

    @Slot(QUrl, result="QVariantMap")
    def createArchive(self, url):
        if not url.isLocalFile():
            return {"ok": False, "message": localized("Избери локален файл за архива.")}
        try:
            self._ledger.backup(Path(url.toLocalFile()))
        except FileExistsError:
            return {"ok": False, "message": localized("Вече има файл с това име. Избери друго име.")}
        except (OSError, sqlite3.Error) as error:
            return {"ok": False, "message": localized("Архивът не е създаден. ") + str(error)}
        return {"ok": True, "message": localized("Архивът е създаден.")}

    @Slot(QUrl, str, str, result="QVariantMap")
    def restoreArchive(self, url, administrator_username, administrator_password):
        if self._session_enabled and self._verify_admin is None:
            return {"ok": False, "message": localized("За възстановяване е нужно потвърждение от администратор.")}
        if not url.isLocalFile():
            return {"ok": False, "message": localized("Избери локален архив.")}
        try:
            if self._session_enabled and not self._verify_admin(administrator_username, administrator_password):
                return {"ok": False, "message": localized("Въведи правилните име и парола на администратора.")}
            safety = self._ledger.restore(Path(url.toLocalFile()))
        except ValidationError as error:
            return {"ok": False, "message": str(error)}
        except (OSError, sqlite3.Error) as error:
            return {"ok": False, "message": localized("Възстановяването не е завършено. ") + str(error)}
        self._editing = None
        self._revision_preview = None
        try:
            self._refresh()
            refresh_error = ""
        except sqlite3.Error as error:
            refresh_error = localized(STORE_ERROR) + str(error)
        message = localized("Архивът е възстановен. Предишната база е запазена в {filename}.").format(filename=safety.name)
        return {"ok": True, "message": f"{message} {refresh_error}".strip()}

def make_window(database: Path, *, demo: bool = False, preferences: Preferences | None = None,
                session_enabled: bool = False, visible: bool = True,
                is_administrator: bool = False, verify_admin=None,
                active_username: str = "", archive_directory: Path | None = None):
    if QQuickStyle.name() != "Basic":
        QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    preferences = preferences or Preferences(database.parent / "settings.ini", engine)
    controller = LedgerWindow(
        database, engine, session_enabled=session_enabled,
        is_administrator=is_administrator, verify_admin=verify_admin,
        archive_directory=archive_directory,
    )
    preferences.languageChanged.connect(engine.retranslate)
    preferences.languageChanged.connect(controller.refreshLanguage)
    updates = WindowsUpdates(database.parent / "updates", engine)
    engine.setInitialProperties({
        "controller": controller,
        "preferences": preferences,
        "updates": updates,
        "testMode": demo,
        "sessionEnabled": session_enabled,
        "activeUsername": active_username,
        "visible": visible,
    })
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("Main.qml"))))
    return engine, controller
