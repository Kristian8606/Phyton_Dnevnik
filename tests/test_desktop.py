import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, QPointF, Qt, qInstallMessageHandler
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from cash_ledger.desktop import make_window
from cash_ledger.demo import prepare_demo
from cash_ledger.ledger import Ledger
from cash_ledger.snapshots import AUTOMATIC_ARCHIVE_NAME, backup_before_update
from cash_ledger.table_print import _print_table, _printer


def visual_item(root: QQuickItem, name: str) -> QQuickItem | None:
    if root.objectName() == name:
        return root
    return next((found for item in root.childItems() if (found := visual_item(item, name))), None)


class DesktopTests(unittest.TestCase):
    def test_settings_theme_persists_and_archive_actions_are_available(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            engine, controller = make_window(database)
            try:
                window: QQuickWindow = engine.rootObjects()[0]
                app.processEvents()

                def click(name):
                    control = visual_item(window.contentItem(), name)
                    self.assertIsNotNone(control, name)
                    point = control.mapToScene(QPointF(control.width() / 2, control.height() / 2))
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                     point.toPoint())
                    app.processEvents()

                def open_theme_menu():
                    click("settingsButton")
                    settings = window.findChild(QObject, "settingsMenu")
                    self.assertIsNotNone(settings)
                    self.assertTrue(settings.property("opened"))
                    QTest.keyClick(window, Qt.Key.Key_Down)
                    QTest.keyClick(window, Qt.Key.Key_Right)
                    QTest.qWait(60)
                    theme = window.findChild(QObject, "themeMenu")
                    self.assertIsNotNone(theme)
                    self.assertTrue(theme.property("opened"))

                open_theme_menu()
                click("theme_dark")
                self.assertTrue(window.property("dark"))
                open_theme_menu()
                self.assertTrue(visual_item(window.contentItem(), "theme_dark").property("checked"))
                click("theme_light")
                self.assertFalse(window.property("dark"))
                open_theme_menu()
                click("theme_dark")

                click("settingsButton")
                QTest.keyClick(window, Qt.Key.Key_Down)
                QTest.keyClick(window, Qt.Key.Key_Down)
                QTest.keyClick(window, Qt.Key.Key_Right)
                QTest.qWait(60)
                archive = window.findChild(QObject, "archiveMenu")
                self.assertIsNotNone(archive)
                self.assertTrue(archive.property("opened"))
                for name in ("createArchiveMenuItem", "restoreArchiveMenuItem"):
                    self.assertIsNotNone(visual_item(window.contentItem(), name))
            finally:
                engine.rootObjects()[0].close()

            reopened, controller = make_window(database)
            try:
                self.assertTrue(reopened.rootObjects()[0].property("dark"))
            finally:
                reopened.rootObjects()[0].close()

    def test_revision_tab_shows_the_current_cash_and_preserves_the_draft(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            Ledger(database).save(date.today(), {"income": "1225"})
            engine, controller = make_window(database)
            window = engine.rootObjects()[0]
            try:
                app.processEvents()
                root = window.contentItem()
                tabs = visual_item(root, "navigationTabs")
                self.assertIsNotNone(tabs)
                self.assertEqual(tabs.property("currentIndex"), 0)
                draft = visual_item(root, "entry_income")
                draft.setProperty("text", "50")

                def click(name):
                    item = visual_item(root, name)
                    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                     point.toPoint())
                    app.processEvents()

                click("revisionsTab")
                self.assertTrue(window.property("showingRevisions"))
                self.assertEqual(tabs.property("currentIndex"), 1)
                closing = visual_item(root, "revision_closing")
                self.assertEqual(closing.property("value") + " €", controller.summary["cash"])
                click("operationsTab")
                self.assertFalse(window.property("showingRevisions"))
                self.assertEqual(tabs.property("currentIndex"), 0)
                self.assertEqual(draft.property("text"), "50")
                visual_item(root, "operationsTab").forceActiveFocus()
                QTest.keyClick(window, Qt.Key.Key_Right)
                self.assertEqual(tabs.property("currentIndex"), 1)
                self.assertEqual(closing.property("value") + " €", controller.summary["cash"])
            finally:
                window.close()

    def test_administrator_authorizes_a_new_period_for_the_signed_in_operator(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            store = Ledger(database)
            store.save(date.today(), {"income": "1225"})
            engine, controller = make_window(
                database, session_enabled=True, active_username="operator",
                verify_admin=lambda username, password: (username, password) == ("admin", "test-secret")
            )
            window = engine.rootObjects()[0]
            try:
                app.processEvents()
                root = window.contentItem()
                def click(name):
                    item = visual_item(root, name)
                    self.assertIsNotNone(item, name)
                    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                     point.toPoint())
                    app.processEvents()

                click("revisionsTab")
                button = visual_item(root, "closeRevisionButton")
                self.assertEqual(button.property("text"), "Нов период")
                self.assertTrue(button.property("visible"))
                self.assertFalse(controller.isAdministrator)
                click("closeRevisionButton")
                username = visual_item(root, "revisionUsername")
                self.assertIsNotNone(username)
                password = visual_item(root, "revisionPassword")
                for name, secret in (("друг", "test-secret"), ("admin", "wrong"), ("", "test-secret")):
                    username.setProperty("text", name)
                    password.setProperty("text", secret)
                    click("confirmCloseRevision")
                    self.assertEqual(len(store.day(date.today()).rows), 1)
                    self.assertEqual(store.revision_history(), [])
                username.setProperty("text", "admin")
                password.setProperty("text", "test-secret")
                click("confirmCloseRevision")

                self.assertEqual(store.day(date.today()).rows, [])
                self.assertEqual(store.day(date.today()).carried_cash, 122500)
                self.assertEqual(len(window.property("revisionReport")["history"]), 1)
                self.assertIn("Резервно копие", window.property("revisionFeedback"))
                self.assertFalse(visual_item(root, "closeRevisionButton").property("enabled"))
                click("operationsTab")
                self.assertEqual(controller.summary["carried"], "1\u00a0225,00 €")
            finally:
                window.close()

    def test_save_remains_below_the_table_without_the_cash_summary(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            data = directory / "Local"
            database = data / "Dnevnik" / "dnevnik.sqlite3"
            archives = directory / "Архиви"
            engine, controller = make_window(database, archive_directory=archives)
            try:
                window: QQuickWindow = engine.rootObjects()[0]
                window.resize(1350, 650)
                app.processEvents()
                root = window.contentItem()
                field = visual_item(root, "entry_income")
                button = visual_item(root, "saveOperationButton")
                self.assertIsNotNone(button)
                self.assertIsNone(visual_item(root, "cashReportButton"))
                labels = [item.property("text") for item in window.findChildren(QObject)]
                for label in ("Постъпления", "Плащания", "Движение за деня"):
                    self.assertNotIn(label, labels)
                point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
                self.assertGreater(point.y(), field.mapToScene(QPointF(0, field.height())).y())
                field.setProperty("text", "25")
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                 point.toPoint())
                backup = archives / AUTOMATIC_ARCHIVE_NAME
                self.assertTrue(backup.is_file())
                self.assertEqual(Ledger(backup).day(date.today()).summary["cash"], 2500)
                ledger = Ledger(database)
                operation_id = ledger.day(date.today()).operation_ids[0]["cash_movements"]
                self.assertTrue(controller.openEdit("cash_movements", str(operation_id))["ok"])
                self.assertTrue(controller.saveEdit({"income": "35"})["ok"])
                self.assertEqual(Ledger(backup).day(date.today()).summary["cash"], 3500)
                ledger.save(date.today(), {"income": "10"})
                self.assertEqual(backup_before_update(data, archives), backup)
                self.assertEqual(Ledger(backup).day(date.today()).summary["cash"], 4500)
                self.assertEqual(list(archives.iterdir()), [backup])

                with patch("cash_ledger.desktop.replace_archive", side_effect=OSError):
                    result = controller.saveDraft({"income": "10"})
                self.assertTrue(result["ok"])
                self.assertTrue(result["warning"])
                self.assertEqual(ledger.day(date.today()).summary["cash"], 5500)
                self.assertEqual(Ledger(backup).day(date.today()).summary["cash"], 4500)
                self.assertEqual(list(archives.iterdir()), [backup])

                window.findChild(QObject, "restoreArchiveMenuItem").triggered.emit()
                app.processEvents()
                self.assertEqual(visual_item(root, "restoreArchiveName").property("text"), backup.name)
                confirm = visual_item(root, "confirmRestoreArchive")
                position = confirm.mapToScene(QPointF(confirm.width() / 2, confirm.height() / 2))
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                 position.toPoint())
                self.assertEqual(ledger.day(date.today()).summary["cash"], 4500)

            finally:
                if engine.rootObjects():
                    engine.rootObjects()[0].close()

    def test_print_tab_uses_today_or_an_inclusive_date_range(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            database = directory / "ledger.sqlite3"
            today = date.today()
            previous = today - timedelta(days=1)
            ledger = Ledger(database)
            ledger.save(previous - timedelta(days=1), {"income": "400"})
            ledger.save(previous, {"income": "125 първи ден"})
            ledger.save(today, {"income": "60 днес", "contract": "124", "interest": "10",
                                "principal": "20", "pledge": "500", "pledgeAmount": "5"})
            engine, controller = make_window(database)
            window = engine.rootObjects()[0]
            try:
                app.processEvents()
                root = window.contentItem()

                def click(name):
                    item = visual_item(root, name)
                    self.assertIsNotNone(item, name)
                    self.assertTrue(item.property("visible"), name)
                    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                     point.toPoint())
                    app.processEvents()

                draft = visual_item(root, "entry_income")
                draft.setProperty("text", "12")
                click("printTab")
                self.assertFalse(visual_item(root, "saveOperationButton").property("visible"))
                self.assertIsNone(visual_item(root, "exportOperationsPdfButton"))
                self.assertTrue(visual_item(root, "printTodayOption").property("checked"))
                with patch("cash_ledger.desktop.print_table", return_value=False):
                    click("printOperationsButton")
                    self.assertTrue(visual_item(root, "printScreen").property("visible"))
                with patch("cash_ledger.desktop.print_table", return_value=True) as print_table:
                    click("printOperationsButton")
                    columns, rows, overview = print_table.call_args.args
                    self.assertEqual(columns[0].heading, "Пр.")
                    self.assertEqual(len(rows), 1)
                    self.assertIn(("60,00", "", "днес"), rows[0])
                    self.assertEqual(dict(overview), {
                        "Дата": today.strftime("%d.%m.%Y"), "Каса": "610,00 €",
                        "Печалба": "10,00 €", "Откуп": "20,00 €", "Залози": "5,00 €", "Лихви": "10,00 €",
                    })

                    self.assertTrue(visual_item(root, "saveOperationButton").property("visible"))
                    self.assertEqual(draft.property("text"), "12")
                    click("printTab")
                    click("printPeriodOption")
                    click("printFirstDate")
                    if previous.month != today.month:
                        click("calendarPreviousMonth")
                    click("calendar_day_" + previous.isoformat())
                    click("printOperationsButton")
                    columns, rows, overview = print_table.call_args.args
                    self.assertEqual(columns[0].heading, "Дата")
                    self.assertEqual(len(rows), 2)
                    self.assertEqual([row[0][0] for row in rows],
                                     [previous.strftime("%d.%m.%Y"), today.strftime("%d.%m.%Y")])
                    self.assertIn(("125,00", "", "първи ден"), rows[0])
                    self.assertNotIn("Пренос в началото", dict(overview))
                    self.assertEqual(dict(overview)["Каса"], "610,00 €")
                    self.assertEqual(controller.dateIso, today.isoformat())
                    self.assertFalse(visual_item(root, "printScreen").property("visible"))

                click("printTab")
                self.assertTrue(visual_item(root, "printTodayOption").property("checked"))
                target = directory / "таблица.pdf"
                invalid = controller.printOperations(today.isoformat(), previous.isoformat())
                self.assertFalse(invalid["ok"])
                printer = _printer()
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setOutputFileName(str(target))
                _print_table(printer, columns, rows, overview)
                self.assertTrue(target.read_bytes().startswith(b"%PDF-"))
            finally:
                window.close()

    def test_number_search_opens_and_highlights_the_correct_block(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            prior = date.today() - timedelta(days=2)
            ledger = Ledger(database)
            ledger.save(prior, {"contract": "42", "interest": "5", "principal": "20",
                                "pledge": "00040", "pledgeAmount": "25"})
            ledger.save(prior, {"contract": "43", "interest": "5", "principal": "30",
                                "pledge": "00041", "pledgeAmount": "30"})
            engine, controller = make_window(database)
            try:
                window: QQuickWindow = engine.rootObjects()[0]
                window.resize(1380, 650)
                app.processEvents()

                def item(name):
                    result = visual_item(window.contentItem(), name)
                    self.assertIsNotNone(result, name)
                    return result

                def click(control):
                    point = control.mapToScene(QPointF(control.width() / 2, control.height() / 2)).toPoint()
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
                    app.processEvents()

                click(item("findNumberButton"))
                search = item("findNumberInput")
                search.setProperty("text", "00041")
                search.forceActiveFocus()
                QTest.keyClick(window, Qt.Key.Key_Return)
                QTest.qWait(50)
                click(item("findNumberResult_0"))
                self.assertEqual(controller.dateIso, prior.isoformat())
                self.assertTrue(item("saved_1_pledge").property("isSearchMatch"))
                self.assertFalse(item("saved_1_contract").property("isSearchMatch"))
                self.assertFalse(item("saved_0_pledge").property("isSearchMatch"))
            finally:
                if engine.rootObjects():
                    engine.rootObjects()[0].close()

    def test_calendar_selects_leap_day_and_disallows_future_dates(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            ledger = Ledger(database)
            ledger.save(date(2024, 2, 29), {"income": "25"})
            ledger.save(date(2021, 3, 10), {"income": "8"})
            engine, controller = make_window(database)
            try:
                window: QQuickWindow = engine.rootObjects()[0]
                window.resize(760, 520)
                app.processEvents()

                def item(name):
                    result = visual_item(window.contentItem(), name)
                    self.assertIsNotNone(result, name)
                    return result

                def click(control):
                    point = control.mapToScene(QPointF(control.width() / 2, control.height() / 2)).toPoint()
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
                    app.processEvents()

                self.assertEqual(controller.goTo("2024-09-30"), "")
                balance = item("balanceCard")
                balance_top = balance.mapToScene(QPointF())
                for name in ("findNumberButton", "datePickerButton"):
                    control = item(name)
                    upper_left = control.mapToScene(QPointF())
                    lower_right = control.mapToScene(QPointF(control.width(), control.height()))
                    self.assertGreaterEqual(upper_left.x(), balance_top.x())
                    self.assertLessEqual(lower_right.x(), balance_top.x() + balance.width())
                    self.assertLessEqual(lower_right.y(), balance_top.y())

                self.assertEqual(controller.goTo("2024-02-12"), "")
                click(item("datePickerButton"))
                self.assertTrue(item("calendarActivityDot_2024-02-29").property("visible"))
                self.assertFalse(item("calendarActivityDot_2024-02-28").property("visible"))
                click(item("calendar_day_2024-02-29"))
                self.assertEqual(controller.dateIso, "2024-02-29")
                self.assertEqual(controller.summary["cash"], "33,00 €")
                self.assertIn("2021-03-10", controller.calendarDaysWithOperations(2021, 2))

                self.assertEqual(controller.goTo("2024-01-19"), "")
                click(item("datePickerButton"))
                click(item("calendarPreviousMonth"))
                click(item("calendar_day_2023-12-31"))
                self.assertEqual(controller.dateIso, "2023-12-31")

                controller.goToday()
                click(item("datePickerButton"))
                tomorrow = (date.today() + timedelta(days=1)).isoformat()
                self.assertFalse(item("calendar_day_" + tomorrow).property("enabled"))
                self.assertFalse(item("calendarNextMonth").property("enabled"))
            finally:
                if engine.rootObjects():
                    engine.rootObjects()[0].close()

    def test_demo_calendar_opens_selected_day_and_shows_carried_cash(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "test-days.sqlite3"
            today = date.today()
            prepare_demo(database, today)
            engine, controller = make_window(database, demo=True)
            try:
                window: QQuickWindow = engine.rootObjects()[0]
                app.processEvents()
                self.assertIn("Тестови дни", window.title())
                carried = visual_item(window.contentItem(), "carriedCash")
                self.assertEqual(carried.property("text"), "1\u00a0227,00 €")

                def click(item):
                    self.assertIsNotNone(item)
                    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
                    app.processEvents()

                root = window.contentItem()
                click(visual_item(root, "datePickerButton"))
                selected = today - timedelta(days=2)
                if selected.month != today.month:
                    click(visual_item(root, "calendarPreviousMonth"))
                click(visual_item(root, "calendar_day_" + selected.isoformat()))
                self.assertEqual(controller.dateIso, selected.isoformat())
                self.assertEqual(carried.property("text"), "1\u00a0115,00 €")
                self.assertEqual(controller.summary["cash"], "1\u00a0185,00 €")
            finally:
                if engine.rootObjects():
                    engine.rootObjects()[0].close()

    def test_quick_entry_validation_and_persistence(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            messages = []
            handler = qInstallMessageHandler(lambda mode, context, message: messages.append(message))
            engine, controller = make_window(database)
            try:
                self.assertEqual(len(engine.rootObjects()), 1, messages)
                window: QQuickWindow = engine.rootObjects()[0]
                app.processEvents()
                def field(key):
                    item = visual_item(window.contentItem(), "entry_" + key)
                    self.assertIsNotNone(item)
                    return item

                for key, text in {"marker": "1", "contract": "00041",
                                  "interest": "40", "principal": "100",
                                  "gold": "5 Пръстен", "newGold": "2"}.items():
                    field(key).setProperty("text", text)
                warning = visual_item(window.contentItem(), "weightWarning")
                self.assertIn("само един грамаж", warning.property("text"))
                field("newGold").forceActiveFocus()
                QTest.keyClick(window, Qt.Key.Key_Return)
                self.assertFalse(Ledger(database).day(date.today()).rows)
                field("newGold").setProperty("text", "")
                self.assertEqual(warning.property("text"), "")
                field("marker").setProperty("text", "")
                self.assertIn("само при продажба", warning.property("text"))
                field("marker").setProperty("text", "1")
                self.assertEqual(warning.property("text"), "")
                field("gold").forceActiveFocus()
                QTest.keyClick(window, Qt.Key.Key_Return)
                self.assertEqual(field("gold").property("text"), "")
                self.assertTrue(field("marker").property("activeFocus"))
                self.assertEqual(controller.summary["cash"], "140,00 €")
                snapshot = Ledger(database).day(date.today())
                self.assertEqual(snapshot.rows[0]["gold"].unit_price, 2800)
                self.assertEqual(snapshot.rows[0]["contract"].value, "00041")
                self.assertFalse([message for message in messages if "Main.qml:" in message], messages)
            finally:
                if engine.rootObjects():
                    engine.rootObjects()[0].close()
                qInstallMessageHandler(handler)


    def test_clicking_saved_weight_edits_only_its_operation(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            store = Ledger(database)
            today = date.today()
            store.save(today, {"marker": "1", "contract": "00041", "interest": "40",
                               "principal": "100", "gold": "5 Пръстен", "cost": "10"})
            engine, controller = make_window(database)
            try:
                window: QQuickWindow = engine.rootObjects()[0]
                window.resize(1350, 650)
                app.processEvents()
                saved = visual_item(window.contentItem(), "saved_0_gold")
                self.assertIsNotNone(saved)
                point = saved.mapToScene(QPointF(12, saved.height() / 2)).toPoint()
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                 point)
                app.processEvents()
                editor = visual_item(window.contentItem(), "edit_gold")
                self.assertIsNotNone(editor)
                self.assertEqual(editor.property("text"), "5,00 Пръстен")
                marker = visual_item(window.contentItem(), "edit_marker")
                marker.setProperty("text", "")
                warning = visual_item(window.contentItem(), "editWeightWarning")
                self.assertIsNotNone(warning)
                self.assertIn("само при продажба", warning.property("text"))
                editor.forceActiveFocus()
                QTest.keyClick(window, Qt.Key.Key_Return)
                self.assertEqual(Ledger(database).day(today).rows[0]["marker"].value, "--||--")
                self.assertEqual(editor.property("text"), "5,00 Пръстен")
                marker.setProperty("text", "1")
                editor.setProperty("text", "4 Пръстен")
                editor.forceActiveFocus()
                QTest.keyClick(window, Qt.Key.Key_Return)
                app.processEvents()
                view = Ledger(database).day(today)
                self.assertEqual(view.rows[0]["gold"].unit_price, 3500)
                self.assertEqual(view.rows[0]["cost"].value, 1000)
                self.assertEqual(controller.summary["cash"], "130,00 €")
            finally:
                if engine.rootObjects():
                    engine.rootObjects()[0].close()
