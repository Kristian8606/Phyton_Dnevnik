import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtCore import QObject, QPointF, Qt, qInstallMessageHandler
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from cash_ledger.desktop import make_window
from cash_ledger.demo import prepare_demo
from cash_ledger.ledger import Ledger


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

    def test_save_shares_the_receipts_bar_and_writes_the_entry(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "ledger.sqlite3"
            engine, controller = make_window(database)
            try:
                window: QQuickWindow = engine.rootObjects()[0]
                window.resize(1350, 650)
                app.processEvents()
                root = window.contentItem()
                field = visual_item(root, "entry_income")
                button = visual_item(root, "saveOperationButton")
                receipts = visual_item(root, "receiptsLabel")
                self.assertIsNotNone(button)
                self.assertIsNotNone(receipts)
                point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
                line = receipts.mapToScene(QPointF(0, receipts.height() / 2))
                self.assertAlmostEqual(point.y(), line.y(), delta=2)
                field.setProperty("text", "25")
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                 point.toPoint())
                self.assertEqual(Ledger(database).day(date.today()).summary["cash"], 2500)
                self.assertEqual(controller.summary["incoming"], "+25,00 €")
            finally:
                if engine.rootObjects():
                    engine.rootObjects()[0].close()

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
            Ledger(database).save(date(2024, 2, 29), {"income": "25"})
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
                click(item("calendar_day_2024-02-29"))
                self.assertEqual(controller.dateIso, "2024-02-29")
                self.assertEqual(controller.summary["cash"], "25,00 €")

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

    def test_demo_report_opens_selected_day_and_shows_carried_cash(self):
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

                click(visual_item(window.contentItem(), "cashReportButton"))
                selected = (today - timedelta(days=2)).isoformat()
                click(visual_item(window.contentItem(), "report_day_" + selected))
                self.assertEqual(controller.dateIso, selected)
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
