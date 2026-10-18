# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class Job(object):
    def __init__(self, tool, opts, outdir):
        self.tool = tool
        self.opts = opts  # type: Dict[str, str]
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)

    def opt(self, key, default=""):
        return (self.opts.get(key) or default).strip()

    def files(self, key="files"):
        raw = self.opts.get(key) or ""
        paths = [Path(p) for p in raw.split("|") if p.strip()]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            raise RuntimeError("找不到文件：\n" + "\n".join(missing))
        return paths

    def file(self, key="file"):
        paths = self.files(key)
        if not paths:
            raise RuntimeError("请选择文件。")
        return paths[0]

    def directory(self, key="dir"):
        raw = self.opt(key)
        if not raw:
            raise RuntimeError("请选择文件夹。")
        path = Path(raw)
        if not path.is_dir():
            raise RuntimeError("找不到文件夹：" + str(path))
        return path

    def flag(self, key):
        return self.opt(key) in ("1", "true", "yes", "on")

    def number(self, key, default=0.0):
        raw = self.opt(key)
        if not raw:
            return float(default)
        return float(raw)


class Result(object):
    def __init__(self, message, files=None):
        self.message = message
        self.files = files or []  # type: List[Path]


def which(name: str) -> Optional[str]:
    return shutil.which(name)


def run_cmd(args: List[str], cwd: Optional[str] = None) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stdout or "命令失败")[-4000:])
    return proc.stdout or ""


def find_tool(names) -> Optional[str]:
    for name in names:
        found = which(name)
        if found:
            return found
    return None


def safe_stem(path: Path) -> str:
    stem = path.stem
    cleaned = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in stem)
    return cleaned or "output"


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(1, 10000):
        cand = path.with_name(path.stem + "_" + str(i) + path.suffix)
        if not cand.exists():
            return cand
    return path


def open_folder(path: Path) -> None:
    path = path.resolve()
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def sys_platform() -> str:
    import sys
    return sys.platform
