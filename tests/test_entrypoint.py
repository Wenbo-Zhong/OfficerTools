import unittest
from unittest.mock import patch

from officertools.main import main


class NativeEntryTests(unittest.TestCase):
    def test_native_entry_keeps_arguments(self):
        with patch("officertools.main._cli") as execute:
            main(["--tool-exe", "PDF合并", "--run", "files=C:/a b.pdf|C:/文档.pdf"])
            execute.assert_called_once_with("pdf-merge", ["files=C:/a b.pdf|C:/文档.pdf"])

    def test_native_entry_rejects_unknown_tool(self):
        with self.assertRaises(RuntimeError):
            main(["--tool-exe", "unknown"])


if __name__ == "__main__":
    unittest.main()
