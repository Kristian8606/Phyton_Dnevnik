"""Check and download Windows installers from the project's GitHub releases."""

import ctypes
from dataclasses import dataclass
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from PySide6.QtCore import QIODevice, QObject, Property, QSaveFile, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .i18n import localized
from . import __version__


REPOSITORY = "Kristian8606/Phyton_Dnevnik"
RELEASE_METADATA_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASE_DOWNLOAD_URL = f"https://github.com/{REPOSITORY}/releases/download"


@dataclass(frozen=True)
class Update:
    tag: str
    filename: str
    checksum: str

    @property
    def url(self) -> str:
        return f"{RELEASE_DOWNLOAD_URL}/{self.tag}/{self.filename}"

    def matches(self, file: Path) -> bool:
        with file.open("rb") as source:
            return file_digest(source, "sha256").hexdigest() == self.checksum


def select_update(release: dict, installed: str) -> Update | None:
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        return None
    version = tag[1:]
    if tuple(map(int, version.split("."))) <= tuple(map(int, installed.split("."))):
        return None
    filename = f"Dnevnik-{version}-windows-x64.exe"
    for asset in release.get("assets", []):
        digest = asset.get("digest") or ""
        if asset.get("name") == filename and re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            return Update(tag, filename, digest.removeprefix("sha256:"))
    raise ValueError(localized("Новата версия няма проверим Windows инсталатор."))


def installer_arguments(application: Path, process_id: int) -> list[str]:
    return [
        "/SILENT", "/SP-", "/NORESTART", "/NOCLOSEAPPLICATIONS",
        f"/DnevnikParent={process_id}", f"/DIR={application.parent}",
    ]


def start_windows_process(arguments, **options):
    # An external installer must load system DLLs independently of PyInstaller.
    bundled_libraries = getattr(sys, "_MEIPASS", None)
    if bundled_libraries:
        set_dll_directory = ctypes.windll.kernel32.SetDllDirectoryW
        set_dll_directory(None)
    try:
        return subprocess.Popen(arguments, **options)
    finally:
        if bundled_libraries:
            set_dll_directory(ctypes.c_wchar_p(bundled_libraries))


class WindowsUpdates(QObject):
    changed = Signal()

    def __init__(self, directory: Path, parent=None):
        super().__init__(parent)
        self._directory = directory
        self._message = ""
        self._candidate = None
        self._installer = None
        self._reply = None
        self._download = None
        self._network = QNetworkAccessManager(self)
        self._network.setRedirectPolicy(QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        self._network.setTransferTimeout(45_000)

    @Property(bool, constant=True)
    def supported(self):
        return sys.platform == "win32"

    @Property(bool, notify=changed)
    def busy(self):
        return self._reply is not None

    @Property(bool, notify=changed)
    def ready(self):
        return self._installer is not None

    @Property(str, notify=changed)
    def message(self):
        return self._message

    def _complete(self, message):
        self._reply = None
        if self._download is not None:
            if self._download.isOpen():
                self._download.cancelWriting()
            self._download.deleteLater()
            self._download = None
        self._message = message
        self.changed.emit()

    def _get(self, url, accept, finished):
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", f"Dnevnik/{__version__}".encode("ascii"))
        request.setRawHeader(b"Accept", accept)
        self._reply = self._network.get(request)
        self._reply.finished.connect(finished)
        return self._reply

    @Slot()
    def check(self):
        if not self.supported or self.busy:
            return
        self._installer = None
        self._candidate = None
        self._get(RELEASE_METADATA_URL, b"application/vnd.github+json", self._release_received)
        self._message = localized("Проверявам за нова версия…")
        self.changed.emit()

    def _release_received(self):
        reply = self._reply
        reply.deleteLater()
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status == 404:
            self._complete(localized("Няма достъпна версия. Провери дали хранилището е публично и дали има публикуван Windows инсталатор."))
            return
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._complete(localized("Проверката за обновяване не завърши. Опитай отново."))
            return
        try:
            self._candidate = select_update(json.loads(bytes(reply.readAll())), __version__)
        except (ValueError, KeyError, TypeError, AttributeError):
            self._complete(localized("Новата версия няма проверим Windows инсталатор."))
            return
        if self._candidate is None:
            self._complete(localized("Използваш последната версия."))
            return
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._complete(localized("Папката за инсталатора не можа да се създаде."))
            return

        path = self._directory / self._candidate.filename
        self._download = QSaveFile(str(path), self)
        if not self._download.open(QIODevice.OpenModeFlag.WriteOnly):
            self._complete(localized("Инсталаторът не може да се запише."))
            return
        self._checksum = sha256()
        self._write_failed = False
        download = self._get(self._candidate.url, b"application/octet-stream", self._installer_received)
        download.setReadBufferSize(256 * 1024)
        download.readyRead.connect(self._write_download)
        self._message = localized("Изтеглям версия {version}…").format(version=self._candidate.tag[1:])
        self.changed.emit()

    def _write_download(self):
        chunk = bytes(self._reply.readAll())
        if self._download.write(chunk) != len(chunk):
            self._write_failed = True
            if self._reply.isRunning():
                self._reply.abort()
            return
        self._checksum.update(chunk)

    def _installer_received(self):
        reply = self._reply
        reply.deleteLater()
        if not self._write_failed and reply.error() == QNetworkReply.NetworkError.NoError:
            self._write_download()
        if self._write_failed:
            self._complete(localized("Инсталаторът не може да се запише."))
        elif reply.error() != QNetworkReply.NetworkError.NoError:
            self._complete(localized("Изтеглянето не завърши. Опитай отново."))
        elif self._checksum.hexdigest() != self._candidate.checksum:
            self._complete(localized("Изтегленият файл не премина проверката. Опитай отново."))
        elif not self._download.commit():
            self._complete(localized("Инсталаторът не може да се запише."))
        else:
            self._installer = self._directory / self._candidate.filename
            self._complete(localized("Версия {version} е готова за инсталиране.").format(version=self._candidate.tag[1:]))

    @Slot(result=bool)
    def install(self):
        if not self.supported or not self.ready:
            return False
        try:
            if not self._candidate.matches(self._installer):
                raise OSError
            application = Path(sys.executable)
            arguments = installer_arguments(application, os.getpid())
            if not getattr(sys, "frozen", False):
                arguments.pop()
            start_windows_process([str(self._installer), *arguments])
        except OSError:
            self._installer = None
            self._complete(localized("Инсталаторът не можа да се стартира. Провери за обновяване отново."))
            return False
        return True
