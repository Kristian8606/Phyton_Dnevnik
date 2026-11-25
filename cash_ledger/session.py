"""Manage the sign-in window and open the journal only for a local session."""

from pathlib import Path
import sqlite3

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .accounts import AccountError, LocalAccounts
from .desktop import make_window
from .preferences import Preferences


class DesktopSession(QObject):
    formChanged = Signal()

    def __init__(self, data_directory: Path, database_for_session, *, demo=False, show_windows=True,
                 archive_directory: Path | None = None):
        super().__init__()
        self._accounts = LocalAccounts(data_directory / "access" / "accounts.sqlite3")
        self._has_users = self._accounts.has_users()
        self._preferences = Preferences(data_directory / "settings.ini", self)
        self._database_for_session = database_for_session
        self._demo = demo
        self._show_windows = show_windows
        self._archive_directory = archive_directory
        self._adding_user = False
        self._work_engine = None
        self._access_engine = QQmlApplicationEngine(self)

    def start(self) -> bool:
        if QQuickStyle.name() != "Basic":
            QQuickStyle.setStyle("Basic")
        self._access_engine.setInitialProperties({"session": self, "preferences": self._preferences})
        self._access_engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name("Access.qml"))))
        windows = self._access_engine.rootObjects()
        if not windows:
            return False
        if self._show_windows:
            windows[0].show()
        return True

    @Property(bool, notify=formChanged)
    def registering(self):
        return not self._has_users or self._adding_user

    @Property(bool, notify=formChanged)
    def addingUser(self):
        return self._adding_user

    @Property(bool, notify=formChanged)
    def administratorPasswordRequired(self):
        return self.registering and self._has_users

    @Property(bool, notify=formChanged)
    def canResetAdministrator(self):
        return self._has_users and self._work_engine is None

    @Slot(str, str, str, str, result=str)
    def submit(self, username, password, code, administrator_password=""):
        if self._work_engine is not None:
            return ""
        try:
            if self.registering:
                self._accounts.register(username, password, code, administrator_password=administrator_password)
                self._has_users = True
                if self._adding_user:
                    self.cancelRegistration()
                    return ""
                self.formChanged.emit()
            elif not self._accounts.authenticate(username, password):
                return "Грешно потребителско име или парола."
            administrator = self._accounts.is_administrator(username)
        except AccountError as exc:
            if not self._has_users:
                self._has_users = self._accounts.has_users()
                self.formChanged.emit()
            return str(exc)
        except (OSError, sqlite3.Error):
            return "Потребителските профили са недостъпни."

        try:
            database = self._database_for_session()

            def verify_administrator(name, secret):
                return self._accounts.authenticate(name, secret, administrator_only=True)

            engine, controller = make_window(
                database, demo=self._demo, preferences=self._preferences,
                session_enabled=True, visible=self._show_windows, active_username=username.strip(),
                archive_directory=self._archive_directory,
                is_administrator=administrator, verify_admin=verify_administrator,
            )
        except (OSError, sqlite3.Error) as exc:
            return f"Дневникът не можа да се отвори. {exc}"
        if not engine.rootObjects():
            return "Дневникът не можа да се отвори."
        self._work_engine = engine
        window = engine.rootObjects()[0]
        window.signOutRequested.connect(self.sign_out)
        self._access_engine.rootObjects()[0].hide()
        return ""

    @Slot(result=bool)
    def needsRecoveryCode(self):
        try:
            return not self._accounts.has_recovery_code()
        except (OSError, sqlite3.Error):
            return False

    @Slot(str, str, str, bool, result=str)
    def submitAdministratorRecovery(self, code, username, password, setup_code):
        if not self.canResetAdministrator:
            return "Отвори „Нулирай администратора“ от екрана за вход."
        try:
            if setup_code:
                self._accounts.configure_recovery_code(username, password, code)
            else:
                self._accounts.reset_administrator(code, username, password)
        except AccountError as exc:
            return str(exc)
        except (OSError, sqlite3.Error):
            return "Промяната не можа да се запише."
        return ""

    @Slot()
    def add_user(self):
        if self._adding_user or self._work_engine is not None:
            return
        self._adding_user = True
        self.formChanged.emit()

    @Slot()
    def cancelRegistration(self):
        if not self._adding_user:
            return
        self._adding_user = False
        self.formChanged.emit()

    @Slot()
    def sign_out(self):
        if self._work_engine is None:
            return
        self._access_engine.rootObjects()[0].show()
        engine, self._work_engine = self._work_engine, None
        self.formChanged.emit()
        engine.rootObjects()[0].close()
        engine.deleteLater()
