import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from officertools.theme import system_theme


class SystemThemeTests(unittest.TestCase):
    def windows_registry(self, value=None, error=None):
        registry = MagicMock()
        registry.QueryValueEx.return_value = (value, 4)
        registry.QueryValueEx.side_effect = error
        return registry

    def test_windows_uses_application_appearance(self):
        for value, expected in ((0, "dark"), (1, "light"), (42, "light")):
            with self.subTest(value=value), patch("officertools.theme.sys.platform", "win32"), patch.dict(
                "sys.modules", {"winreg": self.windows_registry(value)}
            ):
                self.assertEqual(system_theme(), expected)

    def test_missing_windows_setting_defaults_to_light(self):
        with patch("officertools.theme.sys.platform", "win32"), patch.dict(
            "sys.modules", {"winreg": self.windows_registry(error=OSError("Unavailable"))}
        ):
            self.assertEqual(system_theme(), "light")

    def test_macos_and_linux_appearance(self):
        for platform, output, expected in (
            ("darwin", "Dark\n", "dark"), ("darwin", "Light\n", "light"),
            ("linux", "'prefer-dark'\n", "dark"),
            ("linux", "'default'\n", "light"), ("linux", "'prefer-light'\n", "light"),
        ):
            with self.subTest(platform=platform, output=output), patch(
                "officertools.theme.sys.platform", platform
            ), patch("officertools.theme.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=output)):
                self.assertEqual(system_theme(), expected)

    def test_command_errors_default_to_light(self):
        for error in (OSError("Missing"), subprocess.TimeoutExpired("gsettings", 1)):
            with self.subTest(error=error), patch("officertools.theme.sys.platform", "linux"), patch(
                "officertools.theme.subprocess.run", side_effect=error
            ):
                self.assertEqual(system_theme(), "light")
        with patch("officertools.theme.sys.platform", "darwin"), patch(
            "officertools.theme.subprocess.run", return_value=SimpleNamespace(returncode=1, stdout="Dark")
        ):
            self.assertEqual(system_theme(), "light")

    def test_unsupported_platform_defaults_to_light(self):
        with patch("officertools.theme.sys.platform", "unknown"):
            self.assertEqual(system_theme(), "light")


if __name__ == "__main__":
    unittest.main()
