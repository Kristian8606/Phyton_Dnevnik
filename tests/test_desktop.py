import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtCore import Qt, qInstallMessageHandler
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from cash_ledger.desktop import make_window
from cash_ledger.ledger import Ledger


def visual_item(root: QQuickItem, name: str) -> QQuickItem | None:
    if root.objectName() == name:
        return root
    return next((found for item in root.childItems() if (found := visual_item(item, name))), None)


class DesktopTests(unittest.TestCase):
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
