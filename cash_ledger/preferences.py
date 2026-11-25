"""Preferences for the desktop interface."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Property, QSettings, QTranslator, Signal, Slot

from . import __version__
from .i18n import language as current_language, localized, set_language


THEMES = ("system", "light", "dark")
LANGUAGES = ("bg", "en")


class JournalTranslator(QTranslator):
    def isEmpty(self):
        return False

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        translated = localized(sourceText, context=disambiguation or context)
        return translated if translated != sourceText else None


def _apply_language(language: str) -> None:
    if current_language() == language:
        return
    set_language(language)
    app = QCoreApplication.instance()
    if app is None:
        return
    translator = getattr(app, "_journal_translator", None)
    if translator is None:
        translator = app._journal_translator = JournalTranslator(app)
    if language == "en":
        app.installTranslator(translator)
    else:
        app.removeTranslator(translator)


class Preferences(QObject):
    themeChanged = Signal()
    languageChanged = Signal()

    def __init__(self, location: Path, parent=None):
        super().__init__(parent)
        self._settings = QSettings(str(location), QSettings.Format.IniFormat)
        theme = self._settings.value("appearance/theme", "system", type=str)
        self._theme = theme if theme in THEMES else "system"
        language = self._settings.value("appearance/language", "bg", type=str)
        self._language = language if language in LANGUAGES else "bg"
        _apply_language(self._language)

    @Property(str, constant=True)
    def version(self):
        return __version__

    @Property(str, notify=themeChanged)
    def theme(self):
        return self._theme

    @Property(str, notify=languageChanged)
    def language(self):
        return self._language

    @Slot(str, result=str)
    def setLanguage(self, language):
        if language not in LANGUAGES or language == self._language:
            return ""
        self._settings.setValue("appearance/language", language)
        self._settings.sync()
        if self._settings.status() != QSettings.Status.NoError:
            return localized("Настройката не можа да се запази.")
        self._language = language
        _apply_language(language)
        self.languageChanged.emit()
        return ""

    @Slot(str, result=str)
    def setTheme(self, theme):
        if theme not in THEMES or theme == self._theme:
            return ""
        self._settings.setValue("appearance/theme", theme)
        self._settings.sync()
        if self._settings.status() != QSettings.Status.NoError:
            return localized("Настройката не можа да се запази.")
        self._theme = theme
        self.themeChanged.emit()
        return ""
