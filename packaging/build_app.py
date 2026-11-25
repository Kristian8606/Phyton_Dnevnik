"""Bundle the application on the host operating system."""

import os
from pathlib import Path
import sys

from PyInstaller.__main__ import run


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    os.environ.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / "build" / "cache"))
    run([
        "--noconfirm", "--workpath", str(ROOT / "build"), "--distpath", str(ROOT / "dist"),
        str(ROOT / "packaging" / "Dnevnik.spec"),
    ])
    if sys.platform == "win32":
        run([
            "--noconfirm", "--onefile", "--name", "DnevnikUpdateBackup",
            "--specpath", str(ROOT / "build"), "--paths", str(ROOT),
            "--workpath", str(ROOT / "build" / "update-backup"), "--distpath", str(ROOT / "dist"),
            str(ROOT / "packaging" / "backup_before_update.py"),
        ])
