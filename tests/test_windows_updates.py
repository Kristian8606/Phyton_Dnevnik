import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PySide6.QtCore import Property
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from cash_ledger.updates import WindowsUpdates, installer_arguments, select_update


class SimulatedWindowsUpdates(WindowsUpdates):
    @Property(bool, constant=True)
    def supported(self):
        return True


class WindowsUpdateTests(unittest.TestCase):
    def test_installer_uses_current_folder_and_waits_for_the_running_program(self):
        path = Path("Apps with spaces") / "Dnevnik.exe"
        arguments = installer_arguments(path, 1234)
        self.assertIn("/SILENT", arguments)
        self.assertIn("/NORESTART", arguments)
        self.assertIn("/NOCLOSEAPPLICATIONS", arguments)
        self.assertIn("/DnevnikParent=1234", arguments)
        self.assertIn(f"/DIR={path.parent}", arguments)

    def test_download_completes_only_when_the_public_file_matches_the_release(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        contents = b"test installer"
        filename = "Dnevnik-8.0.0-windows-x64.exe"
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            listing = directory / "release.json"
            asset_root = directory / "download"
            asset = asset_root / "v8.0.0" / filename
            asset.parent.mkdir(parents=True)
            listing.write_text(json.dumps({
                "tag_name": "v8.0.0",
                "assets": [{"name": filename, "digest": "sha256:" + sha256(contents).hexdigest()}],
            }))
            for payload in (b"incorrect installer", contents):
                with self.subTest(payload=payload):
                    asset.write_bytes(payload)
                    updater = SimulatedWindowsUpdates(directory / "updates")
                    with patch("cash_ledger.updates.RELEASE_METADATA_URL", listing.as_uri()), \
                         patch("cash_ledger.updates.RELEASE_DOWNLOAD_URL", asset_root.as_uri()):
                        updater.check()
                        for _ in range(200):
                            if not updater.busy:
                                break
                            QTest.qWait(10)
                    self.assertFalse(updater.busy, updater.message)
                    usable = payload == contents
                    self.assertEqual(updater.ready, usable, updater.message)
                    result = directory / "updates" / filename
                    self.assertEqual(result.is_file(), usable)
                    if usable:
                        self.assertEqual(result.read_bytes(), contents)

    def test_only_newer_stable_versions_are_offered(self):
        self.assertIsNone(select_update({"tag_name": "v0.1.4"}, "0.1.4"))
        self.assertIsNone(select_update({"tag_name": "v0.1.4"}, "0.1.10"))
        self.assertIsNone(select_update({"tag_name": "v1.0.0-rc1", "prerelease": True}, "0.1.4"))

    def test_requires_the_exact_windows_installer_and_sha256(self):
        filename = "Dnevnik-0.1.10-windows-x64.exe"
        contents = b"test installer"
        checksum = sha256(contents).hexdigest()
        release = {"tag_name": "v0.1.10", "assets": [{"name": filename, "digest": "sha256:" + checksum}]}
        update = select_update(release, "0.1.9")
        self.assertEqual(update.filename, filename)
        self.assertEqual(update.tag, "v0.1.10")
        self.assertEqual(
            update.url,
            f"https://github.com/Kristian8606/Phyton_Dnevnik/releases/download/v0.1.10/{filename}",
        )
        with TemporaryDirectory() as temporary:
            file = Path(temporary) / filename
            file.write_bytes(contents)
            self.assertTrue(update.matches(file))
            file.write_bytes(b"incorrect installer")
            self.assertFalse(update.matches(file))
        with self.assertRaises(ValueError):
            select_update({"tag_name": "v0.1.10", "assets": [{"name": filename}]}, "0.1.9")
