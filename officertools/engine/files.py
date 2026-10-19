# -*- coding: utf-8 -*-
from __future__ import annotations

import difflib
import filecmp
import hashlib
import os
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image

from officertools.engine.common import Job, Result, unique, checkpoint


AUDIO_EXT = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _walk_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for name in filenames:
            checkpoint()
            yield Path(dirpath) / name


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            checkpoint()
            h.update(chunk)
    return h.hexdigest()


def duplicates(job: Job, exts=None) -> Result:
    root = job.directory()
    groups = {}
    for path in _walk_files(root):
        if exts and path.suffix.lower() not in exts:
            continue
        try:
            if path.stat().st_size == 0:
                continue
            digest = _hash(path)
        except OSError:
            continue
        groups.setdefault(digest, []).append(path)
    lines = []
    count = 0
    for paths in groups.values():
        if len(paths) < 2:
            continue
        count += 1
        lines.append("重复组 {}".format(count))
        lines.extend("  " + str(p) for p in paths)
    if not lines:
        lines.append("没有找到重复文件。")
    dest = job.outdir / "duplicates.txt"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return Result("\n".join(lines[:200]), [dest])


def dup_files(job: Job) -> Result:
    return duplicates(job)


def dup_audio(job: Job) -> Result:
    return duplicates(job, AUDIO_EXT)


def _ahash(path: Path):
    im = Image.open(path).convert("L").resize((16, 16), Image.Resampling.LANCZOS)
    pixels = list(im.getdata())
    avg = sum(pixels) / float(len(pixels))
    return tuple(1 if p >= avg else 0 for p in pixels)


def dup_photos(job: Job) -> Result:
    root = job.directory()
    threshold = int(job.number("threshold", 6))
    items = []
    for path in _walk_files(root):
        if path.suffix.lower() not in IMAGE_EXT:
            continue
        try:
            items.append((path, _ahash(path)))
        except Exception:
            continue
    used = set()
    lines = []
    groups = 0
    for i, (path, sig) in enumerate(items):
        if i in used:
            continue
        group = [path]
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            dist = sum(a != b for a, b in zip(sig, items[j][1]))
            if dist <= threshold:
                used.add(j)
                group.append(items[j][0])
        if len(group) > 1:
            groups += 1
            lines.append("相似组 {}".format(groups))
            lines.extend("  " + str(p) for p in group)
    if not lines:
        lines.append("没有找到相似图片。")
    dest = job.outdir / "similar-photos.txt"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return Result("\n".join(lines[:200]), [dest])


def rename(job: Job) -> Result:
    pattern = job.opt("pattern") or "{n}_{name}{ext}"
    now = datetime.now().strftime("%Y%m%d")
    lines = []
    outputs = []
    plan = []
    for n, path in enumerate(job.files(), 1):
        stat = path.stat()
        name = pattern.format(n="{:03d}".format(n), name=path.stem, ext=path.suffix, date=now,
                              size=stat.st_size, folder=path.parent.name, mtime=datetime.fromtimestamp(stat.st_mtime).strftime("%Y%m%d_%H%M%S"))
        if not name or name in (".","..") or any(ch in name for ch in '<>:"/\\|?*'):
            raise RuntimeError("名称包含无效字符：" + name)
        dest = path.with_name(name)
        if dest != path and dest.exists():
            raise RuntimeError("目标文件已存在，请修改模板：" + str(dest))
        if dest in [p[1] for p in plan]:
            raise RuntimeError("模板生成了重复名称：" + name)
        plan.append((path,dest))
        lines.append(path.name + " → " + dest.name)
    preview = job.opt("preview", "1") == "1"
    if not preview:
        changed=[]
        try:
            for path,dest in plan:
                job.checkpoint()
                if path != dest:
                    path.rename(dest)
                    changed.append((path,dest))
                outputs.append(dest)
        except Exception:
            for path,dest in reversed(changed):
                dest.rename(path)
            raise
    report=job.outdir/"rename-plan.txt"
    report.write_text("\n".join(lines),encoding="utf-8")
    return Result(("预览（未修改文件）：" if preview else "已重命名：") + "\n" + "\n".join(lines), [report]+outputs)


def filetime(job: Job) -> Result:
    raw = job.opt("when")
    if raw:
        when = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        stamp = time.mktime(when.timetuple())
    else:
        stamp = time.time()
    offset=job.number("offset",0)
    for path in job.files():
        job.checkpoint()
        stat=path.stat()
        access=stat.st_atime+offset if offset else stamp
        modified=stat.st_mtime+offset if offset else stamp
        os.utime(str(path), (access if job.opt("access","1")=="1" else stat.st_atime,
                            modified if job.opt("modified","1")=="1" else stat.st_mtime))
        if job.flag("created"):
            if os.name != "nt":
                raise RuntimeError("设置创建时间仅支持 Windows。")
            import ctypes
            from ctypes import wintypes
            kernel=ctypes.WinDLL("kernel32",use_last_error=True)
            kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
            kernel.CreateFileW.restype=wintypes.HANDLE
            kernel.SetFileTime.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
            kernel.CloseHandle.argtypes=[wintypes.HANDLE]
            handle=kernel.CreateFileW(str(path.resolve()),0x100,7,None,3,0,None)
            if handle == wintypes.HANDLE(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                created=stat.st_ctime+offset if offset else stamp
                value=ctypes.c_ulonglong(int((created+11644473600)*10000000))
                if not kernel.SetFileTime(handle,ctypes.byref(value),None,None):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                kernel.CloseHandle(handle)
    return Result("已修改 {} 个文件的时间。".format(len(job.files())))


def zip_batch(job: Job) -> Result:
    files = job.files()
    if job.opt("mode") == "each":
        outputs = []
        for path in files:
            dest = job.outdir / (path.name + ".zip")
            with zipfile.ZipFile(str(dest), "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(str(path), path.name)
            outputs.append(dest)
        return Result("已分别压缩 {} 个文件。".format(len(outputs)), outputs)
    dest = job.outdir / "archive.zip"
    with zipfile.ZipFile(str(dest), "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(str(path), path.name)
    return Result("已打包 {} 个文件。".format(len(files)), [dest])


def unzip_batch(job: Job) -> Result:
    outputs = []
    for path in job.files():
        dest = job.outdir / path.stem
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(path)) as zf:
            password=job.opt("password").encode("utf-8") or None
            for member in zf.infolist():
                job.checkpoint()
                target=(dest/member.filename).resolve()
                if dest.resolve() not in target.parents and target != dest.resolve():
                    raise RuntimeError("压缩包包含超出目标文件夹的路径："+member.filename)
                zf.extract(member,str(dest),pwd=password)
        outputs.append(dest)
    return Result("已解压 {} 个压缩包。".format(len(outputs)), outputs)


def mkdir_batch(job: Job) -> Result:
    root = job.directory()
    names = [line.strip() for line in (job.opts.get("names") or "").splitlines() if line.strip()]
    if not names:
        raise RuntimeError("请填写文件夹名称。")
    made = []
    for name in names:
        dest = root / name
        dest.mkdir(parents=True, exist_ok=True)
        made.append(dest)
    return Result("已创建 {} 个文件夹。".format(len(made)), made)


def autocopy(job: Job) -> Result:
    dest_dir = job.directory()
    outputs = []
    for path in job.files():
        dest = dest_dir / path.name
        if dest.exists() and not job.flag("overwrite"):
            dest = unique(dest)
        shutil.copy2(str(path), str(dest))
        outputs.append(dest)
    return Result("已复制 {} 个文件。".format(len(outputs)), outputs)


def checksum(job: Job) -> Result:
    lines = []
    for path in job.files():
        md5 = hashlib.md5()
        sha = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                job.checkpoint()
                md5.update(chunk)
                sha.update(chunk)
        lines.append(path.name)
        lines.append("  MD5    " + md5.hexdigest())
        lines.append("  SHA256 " + sha.hexdigest())
    dest = job.outdir / "checksum.txt"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return Result("\n".join(lines), [dest])


def textdiff(job: Job) -> Result:
    def load(file_key, text_key):
        raw = job.opt(file_key)
        if raw:
            return Path(raw).read_text(encoding="utf-8", errors="replace").splitlines()
        return (job.opts.get(text_key) or "").splitlines()

    a = load("file-a", "text-a")
    b = load("file-b", "text-b")
    diff = list(difflib.unified_diff(a, b, fromfile="A", tofile="B", lineterm=""))
    text = "\n".join(diff) or "两段内容相同。"
    dest = job.outdir / "diff.txt"
    dest.write_text(text, encoding="utf-8")
    return Result(text[:8000], [dest])


def disk_bench(job: Job) -> Result:
    root = job.directory()
    mb = max(16, int(job.number("mb", 256)))
    path = root / ".officertools-bench.bin"
    block = b"\0" * (1024 * 1024)
    started = time.perf_counter()
    with path.open("wb") as fh:
        for _ in range(mb):
            fh.write(block)
        fh.flush()
        os.fsync(fh.fileno())
    write_s = max(0.001, time.perf_counter() - started)
    started = time.perf_counter()
    with path.open("rb") as fh:
        while fh.read(1024 * 1024):
            pass
    read_s = max(0.001, time.perf_counter() - started)
    path.unlink()
    message = "写入 {:.1f} MB/s\n读取 {:.1f} MB/s\n大小 {} MB".format(mb / write_s, mb / read_s, mb)
    dest = job.outdir / "disk-bench.txt"
    dest.write_text(message, encoding="utf-8")
    return Result(message, [dest])
