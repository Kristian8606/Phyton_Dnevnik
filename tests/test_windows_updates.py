from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cash_ledger.updates import github_cli, installer_arguments, select_update


class WindowsUpdateTests(unittest.TestCase):
    def test_installer_uses_current_folder_and_waits_for_the_running_program(self):
        path = Path("Apps with spaces") / "Dnevnik.exe"
        arguments = installer_arguments(path, 1234)
        self.assertIn("/SILENT", arguments)
        self.assertIn("/NORESTART", arguments)
        self.assertIn("/NOCLOSEAPPLICATIONS", arguments)
        self.assertIn("/DnevnikParent=1234", arguments)
        self.assertIn(f"/DIR={path.parent}", arguments)

    def test_uses_the_cli_bundled_next_to_the_installed_program(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            bundled_cli = folder / "gh.exe"
            bundled_cli.touch()
            with patch("sys.frozen", True, create=True), patch("sys.executable", str(folder / "Dnevnik.exe")):
                self.assertEqual(github_cli(), str(bundled_cli))

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
        with TemporaryDirectory() as temporary:
            file = Path(temporary) / filename
            file.write_bytes(contents)
            self.assertTrue(update.matches(file))
            file.write_bytes(b"incorrect installer")
            self.assertFalse(update.matches(file))
        with self.assertRaises(ValueError):
            select_update({"tag_name": "v0.1.10", "assets": [{"name": filename}]}, "0.1.9")
