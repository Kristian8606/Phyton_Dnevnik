from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtCore import QObject, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from cash_ledger.accounts import LocalAccounts
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

        def submit(username, password, verification="", administrator_password=""):
            field("loginUsername").setProperty("text", username)
            field("loginPassword").setProperty("text", password)
            field("registrationCode").setProperty("text", verification)
            field("administratorPassword").setProperty("text", administrator_password)
            click("accountSubmitButton")

        def click(name):
            button = field(name)
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

            journal = session._work_engine.rootObjects()[0]
            self.assertEqual(journal.findChild(QObject, "activeUserLabel").property("text"), "Касиер")
            admin = journal.property("controller")
            self.assertTrue(admin.isAdministrator)
            self.assertIn("Грешна парола", admin.restoreArchive(QUrl.fromLocalFile(str(database)), "wrong")["message"])

            session.sign_out()
            app.processEvents()
            self.assertTrue(gate.isVisible())
            self.assertFalse(field("registrationCode").property("visible"))
            click("registrationButton")
            self.assertTrue(field("administratorPassword").property("visible"))
            submit("Втори", "different-pass", "0000", "wrong")
            self.assertEqual(opens, [database])
            self.assertIn("администратора", field("loginError").property("text"))
            submit("Втори", "different-pass", "0000", "test-secret")
            self.assertTrue(gate.isVisible())
            self.assertFalse(field("registrationCode").property("visible"))
            self.assertEqual(opens, [database])
            submit("Касиер", "wrong")
            self.assertEqual(opens, [database])
            submit("Втори", "different-pass")
            self.assertEqual(opens, [database, database])
            journal = session._work_engine.rootObjects()[0]
            self.assertEqual(journal.findChild(QObject, "activeUserLabel").property("text"), "Втори")
            member = journal.property("controller")
            self.assertFalse(member.isAdministrator)
            self.assertIn("Само администраторът", session.setRecoveryCode("test-secret", "957321624"))
            member.revisionReport()
            ledger = Ledger(database)
            for name, secret in (("Втори", "different-pass"), ("Втори", "test-secret"),
                                 ("Касиер", "wrong")):
                self.assertFalse(member.closeRevision(name, secret)["ok"])
                self.assertEqual(len(ledger.day(date.today()).rows), 1)
                self.assertEqual(ledger.revision_history(), [])

            result = member.closeRevision("Касиер", "test-secret")
            self.assertTrue(result["ok"], result)
            self.assertFalse(member.isAdministrator)
            self.assertEqual(journal.findChild(QObject, "activeUserLabel").property("text"), "Втори")
            self.assertEqual(opens, [database, database])
            result = member.restoreArchive(QUrl.fromLocalFile(str(database)), "test-secret")
            self.assertIn("Само администраторът", result["message"])
            self.assertEqual(ledger.day(date.today()).rows, [])
            self.assertEqual(ledger.day(date.today()).summary["cash"], 2500)
            self.assertEqual(len(ledger.revision_history()), 1)
        finally:
            session.sign_out()
            gate.close()
            app.processEvents()

    def test_forgotten_administrator_recovers_from_registration_with_personal_code(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        directory = Path(self.enterContext(TemporaryDirectory()))
        database = directory / "ledger.sqlite3"
        ledger = Ledger(database)
        ledger.save(date.today(), {"income": "125"})
        accounts = LocalAccounts(directory / "access" / "accounts.sqlite3")
        accounts.register("Админ", "forgotten-password", "0000")
        accounts.register("Служител", "employee-password", "0000", administrator_password="forgotten-password")

        session = DesktopSession(directory, lambda: database)
        self.assertTrue(session.start())
        gate = session._access_engine.rootObjects()[0]

        def item(window, name):
            result = window.findChild(QObject, name)
            self.assertIsNotNone(result, name)
            return result

        def click(window, name):
            button = item(window, name)
            self.assertTrue(button.property("visible"), name)
            point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
            QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point.toPoint())
            app.processEvents()

        try:
            self.assertEqual(session.submit("Админ", "forgotten-password", ""), "")
            journal = session._work_engine.rootObjects()[0]
            app.processEvents()
            password_field = item(journal, "recoverySettingsPassword")
            self.assertTrue(password_field.property("visible"))
            password_field.setProperty("text", "forgotten-password")
            item(journal, "chosenRecoveryCode").setProperty("text", "957321624")
            click(journal, "saveRecoveryCode")
            self.assertTrue(accounts.has_numeric_recovery_code())
            self.assertFalse(password_field.property("visible"))
            session.sign_out()
            app.processEvents()

            click(gate, "registrationButton")
            click(gate, "resetAdministratorButton")
            item(gate, "resetRecoveryCode").setProperty("text", "123456789")
            item(gate, "resetUsername").setProperty("text", "Нов админ")
            item(gate, "resetPassword").setProperty("text", "new-password")
            click(gate, "confirmAdministratorReset")
            self.assertIn("грешен", item(gate, "resetError").property("text"))
            item(gate, "resetRecoveryCode").setProperty("text", "957321624")
            item(gate, "resetNewRecoveryCode").setProperty("text", "849627531")
            click(gate, "confirmAdministratorReset")

            self.assertFalse(item(gate, "registrationCode").property("visible"))
            self.assertTrue(gate.isVisible())
            self.assertEqual(session.submit("Нов админ", "new-password", ""), "")
            journal = session._work_engine.rootObjects()[0]
            self.assertTrue(journal.property("controller").isAdministrator)
            self.assertFalse(item(journal, "chosenRecoveryCode").property("visible"))
            self.assertEqual(ledger.day(date.today()).summary["cash"], 12500)
            self.assertTrue(accounts.authenticate("Служител", "employee-password"))
        finally:
            session.sign_out()
            gate.close()
            app.processEvents()
