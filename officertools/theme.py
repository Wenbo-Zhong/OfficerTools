"""System appearance detection with a light fallback and no extra dependencies."""
import subprocess
import sys


LIGHT = {
    "PAGE": "#f5f7fc", "SIDE": "#edf1f9", "SIDE_MUTED": "#65748f",
    "SIDE_ACTIVE": "#dce3fa", "SIDE_INK": "#465572", "SIDE_TITLE": "#243553",
    "SIDE_SELECTED": "#4352bb", "CARD": "#ffffff", "INK": "#202c46",
    "MUTED": "#748099", "LINE": "#e4e9f2", "ACCENT": "#5865df",
    "ACCENT_ACTIVE": "#4652c6", "BUTTON_HOVER": "#edf0ff", "ON_ACCENT": "#fafaf9",
    "SCROLL": "#c8d0e2", "SCROLL_HOVER": "#9ba8ca",
    "SIDE_SCROLL": "#bec9df", "SIDE_SCROLL_HOVER": "#8d9fbe",
}
DARK = {
    "PAGE": "#111722", "SIDE": "#0c121d", "SIDE_MUTED": "#8999b3",
    "SIDE_ACTIVE": "#293655", "SIDE_INK": "#b6c3d8", "SIDE_TITLE": "#f0f4fc",
    "SIDE_SELECTED": "#c2caff", "CARD": "#1b2433", "INK": "#e8edf7",
    "MUTED": "#9aa9c1", "LINE": "#303d52", "ACCENT": "#929cff",
    "ACCENT_ACTIVE": "#7784ef", "BUTTON_HOVER": "#2b3650", "ON_ACCENT": "#10162b",
    "SCROLL": "#40506b", "SCROLL_HOVER": "#63779c",
    "SIDE_SCROLL": "#33415b", "SIDE_SCROLL_HOVER": "#566b90",
}


def system_theme():
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "dark" if value == 0 else "light"
        if sys.platform == "darwin":
            command = ["defaults", "read", "-g", "AppleInterfaceStyle"]
        elif sys.platform.startswith("linux"):
            command = ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"]
        else:
            return "light"
        result = subprocess.run(command, capture_output=True, text=True, timeout=1)
        if result.returncode == 0 and "dark" in result.stdout.lower():
            return "dark"
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return "light"


def palette(name):
    return dict(DARK if name == "dark" else LIGHT)
