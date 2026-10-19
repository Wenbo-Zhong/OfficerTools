"""Shared resources for the launcher and tools/<category>/<tool>.exe."""
import os
import sys
from pathlib import Path


def application_root():
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parents[1]
    # PyInstaller one-file builds extract bundled vendor assets alongside the
    # temporary Python runtime. Keep data files discoverable after relocation.
    extraction = getattr(sys, "_MEIPASS", None)
    if extraction and sys.platform.startswith("linux"):
        return Path(extraction)
    directory = Path(sys.executable).resolve().parent
    # PyInstaller stores --add-data files in Contents/Resources on macOS.
    if sys.platform == "darwin":
        return directory.parent / "Resources"
    # Walk only the exact packaged tools layout, not arbitrary ancestor folders.
    if directory.parent.name == "tools":
        return directory.parent.parent
    return directory


def configure_bundled_fonts():
    """Make bundled Linux fonts available before Tk enumerates font families."""
    if not sys.platform.startswith("linux") or not getattr(sys, "frozen", False):
        return
    fonts = application_root() / "vendor/etc/fonts"
    config = fonts / "fonts.conf"
    if config.is_file():
        os.environ["FONTCONFIG_PATH"] = str(fonts)
        os.environ["FONTCONFIG_FILE"] = str(config)
    tk_root = application_root() / "vendor/system-tk"
    tcl_library = tk_root / "tcl8.6"
    tk_library = tk_root / "tk8.6"
    if tcl_library.is_dir() and tk_library.is_dir():
        os.environ["TCL_LIBRARY"] = str(tcl_library)
        os.environ["TK_LIBRARY"] = str(tk_library)
