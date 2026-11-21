from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cash_ledger.updates import select_update


class WindowsUpdateTests(unittest.TestCase):
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
