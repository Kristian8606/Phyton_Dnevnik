"""Preferences for the desktop interface."""

from pathlib import Path

from PySide6.QtCore import QObject, Property, QSettings, Signal, Slot

from . import __version__


THEMES = ("system", "light", "dark")


class Preferences(QObject):
    themeChanged = Signal()

    def __init__(self, location: Path, parent=None):
        super().__init__(parent)
        self._settings = QSettings(str(location), QSettings.Format.IniFormat)
        theme = self._settings.value("appearance/theme", "system", type=str)
        self._theme = theme if theme in THEMES else "system"

    @Property(str, constant=True)
    def version(self):
        return __version__

    @Property(str, notify=themeChanged)
    def theme(self):
        return self._theme

    @Slot(str, result=str)
    def setTheme(self, theme):
        if theme not in THEMES or theme == self._theme:
            return ""
        self._settings.setValue("appearance/theme", theme)
        self._settings.sync()
        if self._settings.status() != QSettings.Status.NoError:
            return "Настройката не можа да се запази."
        self._theme = theme
        self.themeChanged.emit()
        return ""
