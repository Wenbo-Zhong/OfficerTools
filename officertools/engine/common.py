# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional
from officertools.paths import application_root


class Cancelled(RuntimeError):
    pass


_current = threading.local()


def checkpoint():
    job=getattr(_current,"job",None)
    if job: job.checkpoint()


class InputPaths(list):
    def __iter__(self):
        for item in super().__iter__():
            checkpoint()
            yield item


class Job(object):
    def __init__(self, tool, opts, outdir, progress=None, cancel=None):
        self.tool = tool
        self.opts = opts  # type: Dict[str, str]
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.progress = progress or (lambda value, message: None)
        self.cancel = cancel or threading.Event()

    def checkpoint(self, value=None, message=""):
        if self.cancel.is_set():
            raise Cancelled("任务已取消，已完成的输出会保留。")
        if value is not None:
            self.progress(value, message)

    def opt(self, key, default=""):
        return (self.opts.get(key) or default).strip()

    def files(self, key="files"):
        raw = self.opts.get(key) or ""
        paths = [Path(p) for p in raw.split("|") if p.strip()]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            raise RuntimeError("找不到文件：\n" + "\n".join(missing))
        return InputPaths(paths)

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
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    program = Path(args[0]).resolve()
    if program.parent.name == "bin" and program.parent.parent.name == "Library" and program.parent.parent.parent.name == "vendor":
        vendor = program.parent.parent.parent
        env = os.environ.copy()
        env["FONTCONFIG_PATH"] = str(vendor / "Library/etc/fonts")
        env["FONTCONFIG_FILE"] = str(vendor / "Library/etc/fonts/fonts.conf")
        env["POPPLER_DATADIR"] = str(vendor / "share/poppler")
        options["env"] = env
    job = getattr(_current, "job", None)
    if job:
        job.checkpoint()
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        **options,
    )
    while True:
        try:
            output, _ = proc.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            if job and job.cancel.is_set():
                proc.terminate()
                try:
                    proc.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                job.checkpoint()
    if proc.returncode != 0:
        raise RuntimeError((output or "命令失败")[-4000:])
    return output or ""


def find_tool(names) -> Optional[str]:
    root = application_root()
    for name in names:
        for directory in (root / "vendor/Library/bin", root / "vendor/ghostscript/bin", root / "vendor/tesseract/bin"):
            filename = name + ".exe" if sys.platform == "win32" and not name.endswith(".exe") else name
            candidate = directory / filename
            if candidate.is_file():
                return str(candidate)
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
