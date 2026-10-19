import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from officertools.engine.common import find_tool


class VendorDiscoveryTests(unittest.TestCase):
    def test_bundled_components_take_priority_over_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ffmpeg = root / "vendor/Library/bin/ffmpeg.exe"
            gs = root / "vendor/ghostscript/bin/gswin64c.exe"
            for path in (ffmpeg, gs):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"test")
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "platform", "win32"), patch.object(
                sys, "executable", str(root / "OfficerTools.exe")
            ), patch("officertools.engine.common.which", return_value="C:/other.exe"):
                self.assertEqual(find_tool(["ffmpeg"]), str(ffmpeg))
                self.assertEqual(find_tool(["gswin64c", "gs"]), str(gs))

    def test_missing_bundle_falls_back_to_path(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "executable", str(Path(folder) / "OfficerTools.exe")
        ), patch("officertools.engine.common.which", side_effect=[None, "C:/installed/gs.exe"]):
            self.assertEqual(find_tool(["gswin64c", "gs"]), "C:/installed/gs.exe")

    def test_nested_tool_finds_shared_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ffmpeg = root / "vendor/Library/bin/ffmpeg.exe"
            ffmpeg.parent.mkdir(parents=True)
            ffmpeg.write_bytes(b"test")
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "platform", "win32"), patch.object(
                sys, "executable", str(root / "tools/media/convert.exe")
            ), patch("officertools.engine.common.which", return_value=None):
                self.assertEqual(find_tool(["ffmpeg"]), str(ffmpeg))


if __name__ == "__main__":
    unittest.main()
