"""Check and download Windows installers from the project's GitHub releases."""

from dataclasses import dataclass
from hashlib import file_digest
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import QObject, Property, QProcess, QProcessEnvironment, QTimer, Signal, Slot

from . import __version__


REPOSITORY = "Kristian8606/Phyton_Dnevnik"


@dataclass(frozen=True)
class Update:
    tag: str
    filename: str
    checksum: str

    def matches(self, file: Path) -> bool:
        with file.open("rb") as source:
            return file_digest(source, "sha256").hexdigest() == self.checksum


def select_update(release: dict, installed: str) -> Update | None:
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return None
    version = tag[1:]
    if tuple(map(int, version.split("."))) <= tuple(map(int, installed.split("."))):
        return None
    filename = f"Dnevnik-{version}-windows-x64.exe"
    for asset in release.get("assets", []):
        digest = asset.get("digest") or ""
        if asset.get("name") == filename and re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            return Update(tag, filename, digest.removeprefix("sha256:"))
    raise ValueError("Новата версия няма проверим Windows инсталатор.")


def github_cli() -> str:
    locations = [
        Path(os.environ.get(key, "")) / "GitHub CLI"
        for key in ("ProgramFiles", "ProgramFiles(x86)")
    ]
    locations.extend(Path(entry.strip('"')) for entry in os.get_exec_path())
    for location in locations:
        executable = location / "gh.exe"
        if location.is_absolute() and executable.is_file():
            return str(executable)
    return ""


class WindowsUpdates(QObject):
    changed = Signal()

    def __init__(self, directory: Path, parent=None):
        super().__init__(parent)
        self._directory = directory
        self._phase = ""
        self._message = ""
        self._candidate = None
        self._installer = None
        self._temporary = None
        self._process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("GH_PROMPT_DISABLED", "1")
        environment.insert("GH_NO_UPDATE_NOTIFIER", "1")
        self._process.setProcessEnvironment(environment)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._process_error)
        self._timeout = QTimer(self, singleShot=True, interval=180_000)
        self._timeout.timeout.connect(self._timed_out)

    @Property(bool, constant=True)
    def supported(self):
        return sys.platform == "win32"

    @Property(bool, notify=changed)
    def busy(self):
        return bool(self._phase)

    @Property(bool, notify=changed)
    def ready(self):
        return self._installer is not None

    @Property(str, notify=changed)
    def message(self):
        return self._message

    def _complete(self, message):
        self._timeout.stop()
        self._phase = ""
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
        self._message = message
        self.changed.emit()

    def _run(self, phase, message, arguments):
        self._phase = phase
        self._message = message
        self._timeout.start()
        self.changed.emit()
        self._process.start(self._cli, arguments)

    @Slot()
    def check(self):
        if not self.supported or self.busy or self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self._installer = None
        self._candidate = None
        self._cli = github_cli()
        if not self._cli:
            self._complete("Инсталирай GitHub CLI и влез в GitHub, за да провериш за обновяване.")
            return
        self._run("check", "Проверявам за нова версия…", [
            "api", "--hostname", "github.com", f"repos/{REPOSITORY}/releases/latest",
        ])

    def _finished(self, exit_code, exit_status):
        output = bytes(self._process.readAllStandardOutput())
        self._process.readAllStandardError()
        if not self._phase:
            return
        if exit_code or exit_status != QProcess.ExitStatus.NormalExit:
            message = ("Провери дали си влязъл през GitHub CLI и имаш достъп до хранилището."
                       if self._phase == "check" else "Изтеглянето не завърши. Опитай отново.")
            self._complete(message)
            return
        try:
            if self._phase == "check":
                self._candidate = select_update(json.loads(output), __version__)
                if self._candidate is None:
                    self._complete("Използваш последната версия.")
                    return
                self._directory.mkdir(parents=True, exist_ok=True)
                self._temporary = TemporaryDirectory(dir=self._directory)
                self._run("download", f"Изтеглям версия {self._candidate.tag[1:]}…", [
                    "release", "download", self._candidate.tag,
                    "--repo", f"github.com/{REPOSITORY}", "--pattern", self._candidate.filename,
                    "--dir", self._temporary.name,
                ])
                return
            downloaded = Path(self._temporary.name) / self._candidate.filename
            if not self._candidate.matches(downloaded):
                self._complete("Изтегленият файл не премина проверката. Опитай отново.")
                return
            self._installer = downloaded.replace(self._directory / self._candidate.filename)
        except (OSError, ValueError, KeyError, TypeError):
            message = ("Не успях да проверя инсталатора за новата версия."
                       if self._phase == "check" else "Инсталаторът не можа да се запази или провери.")
            self._complete(message)
            return
        self._complete(f"Версия {self._candidate.tag[1:]} е готова за инсталиране.")

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._complete("GitHub CLI не можа да се стартира.")

    def _timed_out(self):
        self._process.kill()

    @Slot(result=bool)
    def install(self):
        if not self.supported or not self.ready:
            return False
        try:
            if not self._candidate.matches(self._installer):
                raise OSError
            os.startfile(str(self._installer))
        except OSError:
            self._installer = None
            self._complete("Инсталаторът не можа да се стартира. Провери за обновяване отново.")
            return False
        return True
