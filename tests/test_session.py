from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from cash_ledger.ledger import Ledger
from cash_ledger.session import DesktopSession


class SessionTests(unittest.TestCase):
    def test_registration_sign_out_and_login_gate_the_same_existing_journal(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        directory = Path(self.enterContext(TemporaryDirectory()))
        database = directory / "ledger.sqlite3"
        Ledger(database).save(date.today(), {"income": "25"})
        opens = []

        def database_for_session():
            opens.append(database)
            return database

        session = DesktopSession(directory, database_for_session)
        self.assertTrue(session.start())
        gate = session._access_engine.rootObjects()[0]

        def field(name):
            result = gate.findChild(QObject, name)
            self.assertIsNotNone(result, name)
            return result

        def submit(username, password, verification=""):
            field("loginUsername").setProperty("text", username)
            field("loginPassword").setProperty("text", password)
            field("registrationCode").setProperty("text", verification)
            button = field("accountSubmitButton")
            point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
            QTest.mouseClick(gate, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point.toPoint())
            app.processEvents()

        try:
            app.processEvents()
            self.assertEqual(opens, [])
            submit("Касиер", "test-secret", "1234")
            self.assertEqual(opens, [])
            self.assertIn("Кодът", field("loginError").property("text"))
            submit("Касиер", "test-secret", "0000")
            self.assertEqual(opens, [database])
            self.assertFalse(gate.isVisible())

            session.add_user()
            self.assertTrue(gate.isVisible())
            submit("Втори", "different-pass", "0000")
            self.assertFalse(gate.isVisible())
            self.assertEqual(opens, [database])

            session.sign_out()
            app.processEvents()
            self.assertTrue(gate.isVisible())
            self.assertFalse(field("registrationCode").property("visible"))
            submit("Касиер", "wrong")
            self.assertEqual(opens, [database])
            submit("Втори", "different-pass")
            self.assertEqual(opens, [database, database])
            self.assertEqual(Ledger(database).day(date.today()).summary["cash"], 2500)
        finally:
            session.sign_out()
            gate.close()
            app.processEvents()
