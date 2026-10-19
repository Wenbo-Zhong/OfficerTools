"""Shared resources for the launcher and tools/<category>/<tool>.exe."""
import sys
from pathlib import Path


def application_root():
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parents[1]
    directory = Path(sys.executable).resolve().parent
    # Walk only the exact packaged tools layout, not arbitrary ancestor folders.
    if directory.parent.name == "tools":
        return directory.parent.parent
    return directory
