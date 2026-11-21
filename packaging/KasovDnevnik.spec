# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import platform
import runpy
import sys

root = Path(SPECPATH).parent
name = "KasovDnevnik"
version = runpy.run_path(root / "cash_ledger" / "__init__.py")["__version__"]
resources = [(str(path), "cash_ledger") for path in sorted((root / "cash_ledger").glob("*.qml"))]

analysis = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root)],
    datas=resources,
    hiddenimports=["PySide6.QtQuick"],
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive, analysis.scripts, [], exclude_binaries=True,
    name=name, console=False, upx=False,
    target_arch=platform.machine() if sys.platform == "darwin" else None,
)
bundle = COLLECT(executable, analysis.binaries, analysis.datas, name=name, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        bundle,
        name=name + ".app",
        bundle_identifier="app.kasovdnevnik.desktop",
        version=version,
        info_plist={"CFBundleDisplayName": "Касов дневник", "CFBundleVersion": version},
    )
