# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

from officertools.catalog import BY_EXE, BY_ID


def tool_from_exe():
    if not getattr(sys, "frozen", False):
        return None
    stem = Path(sys.executable).stem
    if stem in ("办公工具箱", "OfficerTools", "officertools"):
        return ""
    tool = BY_EXE.get(stem)
    return tool.id if tool else ""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    baked = tool_from_exe()
    tool_id = ""
    if argv and not argv[0].startswith("-") and argv[0] in BY_ID:
        tool_id = argv.pop(0)
    elif baked:
        tool_id = baked
    if argv and argv[0] == "--run":
        _cli(tool_id, argv[1:])
        return
    from officertools.dpi import enable

    enable()
    import tkinter as tk

    from officertools.ui import App

    root = tk.Tk()
    App(root, initial=tool_id or None)
    root.mainloop()


def _cli(tool_id, argv):
    if not tool_id:
        print("用法: python -m officertools <工具id> --run key=value ...")
        print("工具: " + ", ".join(sorted(BY_ID)))
        return
    opts = {}
    files = []
    out = None
    for item in argv:
        if item.startswith("--out="):
            out = item.split("=", 1)[1]
        elif "=" in item:
            key, value = item.split("=", 1)
            opts[key] = value
        else:
            files.append(item)
    if files and "files" not in opts and "file" not in opts:
        opts["files"] = "|".join(files)
        if len(files) == 1:
            opts["file"] = files[0]
    from officertools.engine.common import Job
    from officertools.engine.dispatch import run

    folder = Path(out) if out else Path.cwd() / "officertools-out" / tool_id
    result = run(Job(tool_id, opts, folder))
    print(result.message)
    for path in result.files:
        print(path)


if __name__ == "__main__":
    main()
