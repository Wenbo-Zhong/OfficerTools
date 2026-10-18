# -*- coding: utf-8 -*-
"""Render PDF pages at a chosen DPI. Prefers Ghostscript, then Poppler."""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageOps

from officertools.engine.common import find_tool, run_cmd, safe_stem


def render_pdf(path: Path, outdir: Path, dpi: int, gray: bool = False):
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob(safe_stem(path) + "-*.png"):
        old.unlink()
    gs = find_tool(["gswin64c", "gswin32c", "gs"])
    if gs:
        pattern = str(outdir / (safe_stem(path) + "-%03d.png"))
        device = "pnggray" if gray else "png16m"
        run_cmd([
            gs, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
            "-sDEVICE=" + device, "-r{}".format(dpi), "-o", pattern, str(path),
        ])
    else:
        pdftoppm = find_tool(["pdftoppm"])
        if not pdftoppm:
            raise RuntimeError(
                "要把 PDF 画成图片，需要安装 Ghostscript（gswin64c）或 Poppler（pdftoppm），并加入 PATH。"
            )
        prefix = str(outdir / safe_stem(path))
        args = [pdftoppm, "-png", "-r", str(dpi)]
        if gray:
            args.append("-gray")
        args.extend([str(path), prefix])
        run_cmd(args)
    images = sorted(outdir.glob("*.png"))
    if not images:
        raise RuntimeError("没有导出任何页面。")
    return images


def save_images_as_pdf(images, dest: Path, dpi: int) -> None:
    opened = [Image.open(p).convert("RGB") for p in images]
    if not opened:
        raise RuntimeError("没有图片。")
    first, rest = opened[0], opened[1:]
    dest.parent.mkdir(parents=True, exist_ok=True)
    first.save(str(dest), save_all=True, append_images=rest, resolution=dpi)
    for im in opened:
        im.close()


def deskew_image(path: Path) -> Path:
    im = Image.open(path).convert("L")
    small = im
    if max(im.size) > 1600:
        scale = 1600 / float(max(im.size))
        small = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.Resampling.BILINEAR)
    bw = small.point(lambda p: 0 if p < 180 else 255)
    # Projection variance over a small angle range. Pure Python, good enough for office scans.
    best_angle = 0.0
    best_score = -1.0
    pixels = bw.load()
    w, h = bw.size
    for deg10 in range(-60, 61, 2):
        angle = deg10 / 10.0
        rotated = bw.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False, fillcolor=255)
        rp = rotated.load()
        score = 0.0
        step = 4
        for y in range(0, h, step):
            ink = 0
            for x in range(0, w, step):
                if rp[x, y] < 128:
                    ink += 1
            score += ink * ink
        if score > best_score:
            best_score = score
            best_angle = angle
    fixed = Image.open(path).convert("RGB").rotate(best_angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    dest = path.with_name(path.stem + "_fixed.png")
    fixed.save(dest, format="PNG")
    return dest


def cleanup_dir(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(str(path), ignore_errors=True)
