"""Bundle the application on the host operating system."""

import os
from pathlib import Path

from PyInstaller.__main__ import run


ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    os.environ.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / "build" / "cache"))
    run([
        "--noconfirm", "--workpath", str(ROOT / "build"), "--distpath", str(ROOT / "dist"),
        str(ROOT / "packaging" / "KasovDnevnik.spec"),
    ])
