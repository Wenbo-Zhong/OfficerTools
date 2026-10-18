# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps, ImageFont

from officertools.engine.common import Job, Result, safe_stem
from officertools.engine.pdf import _cjk_font

RESAMPLE = Image.Resampling.LANCZOS


def _save(im: Image.Image, dest: Path, fmt: str, quality: int) -> Path:
    fmt = fmt.lower()
    dest = dest.with_suffix("." + ("jpg" if fmt == "jpeg" else fmt))
    out = im
    if fmt in ("jpeg", "jpg", "bmp"):
        if out.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", out.size, (255, 255, 255))
            bg.paste(out, mask=out.split()[-1])
            out = bg
        else:
            out = out.convert("RGB")
        dest = dest.with_suffix(".jpg" if fmt in ("jpeg", "jpg") else ".bmp")
        out.save(dest, quality=quality, dpi=out.info.get("dpi", (300, 300)))
    elif fmt == "png":
        out.save(dest, format="PNG", optimize=True)
    elif fmt == "webp":
        out.save(dest, format="WEBP", quality=quality, method=6)
    elif fmt == "gif":
        out.convert("P", palette=Image.Palette.ADAPTIVE).save(dest, format="GIF")
    elif fmt == "tiff":
        out.save(dest, format="TIFF", compression="tiff_lzw")
    else:
        raise RuntimeError("不支持的格式：" + fmt)
    return dest


def convert(job: Job) -> Result:
    fmt = job.opt("fmt") or "png"
    quality = int(job.number("quality", 92))
    outputs = []
    for path in job.files():
        im = Image.open(path)
        dest = _save(im, job.outdir / safe_stem(path), fmt, quality)
        im.close()
        outputs.append(dest)
    return Result("已转换 {} 张。".format(len(outputs)), outputs)


def resize(job: Job) -> Result:
    mode = job.opt("mode") or "pixel"
    outputs = []
    for path in job.files():
        im = Image.open(path)
        w, h = im.size
        if mode == "percent":
            scale = job.number("percent", 50) / 100.0
            size = (max(1, int(w * scale)), max(1, int(h * scale)))
        elif mode == "width":
            nw = max(1, int(job.number("width", w)))
            size = (nw, max(1, int(h * nw / float(w))))
        elif mode == "height":
            nh = max(1, int(job.number("height", h)))
            size = (max(1, int(w * nh / float(h))), nh)
        else:
            size = (max(1, int(job.number("width", w))), max(1, int(job.number("height", h))))
        out = im.resize(size, RESAMPLE)
        dest = job.outdir / (safe_stem(path) + "_{}x{}{}".format(size[0], size[1], path.suffix or ".png"))
        out.save(dest)
        im.close()
        outputs.append(dest)
    return Result("已调整 {} 张，使用 Lanczos 重采样。".format(len(outputs)), outputs)


def compress(job: Job) -> Result:
    quality = int(job.number("quality", 80))
    max_edge = int(job.number("max-edge", 0))
    outputs = []
    for path in job.files():
        im = Image.open(path)
        if max_edge > 0 and max(im.size) > max_edge:
            im.thumbnail((max_edge, max_edge), RESAMPLE)
        dest = _save(im.convert("RGB") if im.mode not in ("RGB", "L") else im, job.outdir / (safe_stem(path) + "_c"), "jpeg", quality)
        im.close()
        outputs.append(dest)
    return Result("已压缩 {} 张。".format(len(outputs)), outputs)


def crop(job: Job) -> Result:
    mode = job.opt("mode") or "margin"
    outputs = []
    for path in job.files():
        im = Image.open(path)
        w, h = im.size
        if mode == "center":
            cw = int(job.number("right", w)) or w
            ch = int(job.number("top", h)) or h
            left = max(0, (w - cw) // 2)
            top = max(0, (h - ch) // 2)
            box = (left, top, min(w, left + cw), min(h, top + ch))
        else:
            left = int(job.number("left", 0))
            top = int(job.number("top", 0))
            right = int(job.number("right", 0))
            bottom = int(job.number("bottom", 0))
            box = (left, top, w - right, h - bottom)
        if box[2] <= box[0] or box[3] <= box[1]:
            raise RuntimeError("裁剪区域无效：" + path.name)
        dest = job.outdir / (safe_stem(path) + "_crop" + (path.suffix or ".png"))
        im.crop(box).save(dest)
        im.close()
        outputs.append(dest)
    return Result("已裁剪 {} 张。".format(len(outputs)), outputs)


def watermark(job: Job) -> Result:
    text = job.opt("text") or "草稿"
    alpha = max(0, min(255, int(job.number("opacity", 80))))
    outputs = []
    for path in job.files():
        im = Image.open(path).convert("RGBA")
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        font = _cjk_font(max(18, im.width // 28))
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        step_x = max(tw + 40, 80)
        step_y = max(th + 80, 80)
        for y in range(20, im.height, step_y):
            for x in range(20, im.width, step_x):
                draw.text((x, y), text, font=font, fill=(60, 60, 60, alpha))
        out = Image.alpha_composite(im, layer)
        dest = job.outdir / (safe_stem(path) + "_wm.png")
        out.save(dest)
        outputs.append(dest)
    return Result("已添加水印。", outputs)


def splice(job: Job) -> Result:
    images = [Image.open(p).convert("RGBA") for p in job.files()]
    gap = int(job.number("gap", 0))
    vertical = job.opt("direction") != "horizontal"
    if vertical:
        width = max(im.width for im in images)
        height = sum(im.height for im in images) + gap * (len(images) - 1)
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        y = 0
        for im in images:
            canvas.paste(im, ((width - im.width) // 2, y), im)
            y += im.height + gap
    else:
        height = max(im.height for im in images)
        width = sum(im.width for im in images) + gap * (len(images) - 1)
        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        x = 0
        for im in images:
            canvas.paste(im, (x, (height - im.height) // 2), im)
            x += im.width + gap
    dest = job.outdir / "spliced.png"
    canvas.save(dest)
    for im in images:
        im.close()
    return Result("已拼接，输出 {}×{} 像素。".format(canvas.width, canvas.height), [dest])


def stamp(job: Job) -> Result:
    text = job.opt("text") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    corner = job.opt("corner") or "bottom-right"
    outputs = []
    for path in job.files():
        im = Image.open(path).convert("RGBA")
        draw = ImageDraw.Draw(im)
        font = _cjk_font(max(16, im.width // 40))
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad = max(8, im.width // 80)
        if "left" in corner:
            x = pad
        else:
            x = im.width - tw - pad
        if "top" in corner:
            y = pad
        else:
            y = im.height - th - pad
        draw.rectangle((x - 6, y - 4, x + tw + 6, y + th + 4), fill=(0, 0, 0, 140))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
        dest = job.outdir / (safe_stem(path) + "_stamp.png")
        im.save(dest)
        outputs.append(dest)
    return Result("已写入时间戳。", outputs)


def exif(job: Job) -> Result:
    action = job.opt("action") or "view"
    lines = []
    outputs = []
    for path in job.files():
        im = Image.open(path)
        info = dict(im.getexif().items()) if hasattr(im, "getexif") else {}
        try:
            from PIL.ExifTags import TAGS
            named = {TAGS.get(k, k): v for k, v in info.items()}
        except Exception:
            named = info
        if action == "strip":
            dest = job.outdir / (safe_stem(path) + path.suffix)
            data = list(im.getdata())
            clean = Image.new(im.mode, im.size)
            clean.putdata(data)
            clean.save(dest)
            outputs.append(dest)
            lines.append(path.name + "：已清除 EXIF")
        else:
            if not named:
                lines.append(path.name + "：没有 EXIF")
            else:
                lines.append(path.name)
                for k, v in list(named.items())[:40]:
                    lines.append("  {} = {}".format(k, v))
        im.close()
    dest = job.outdir / "exif.txt"
    dest.write_text("\n".join(lines), encoding="utf-8")
    outputs.append(dest)
    return Result("\n".join(lines[:80]), outputs)


def effect(job: Job) -> Result:
    b = job.number("brightness", 1)
    c = job.number("contrast", 1)
    s = job.number("sharpness", 1)
    outputs = []
    for path in job.files():
        im = Image.open(path).convert("RGB")
        im = ImageEnhance.Brightness(im).enhance(b)
        im = ImageEnhance.Contrast(im).enhance(c)
        im = ImageEnhance.Sharpness(im).enhance(s)
        if job.flag("gray"):
            im = ImageOps.grayscale(im)
        dest = job.outdir / (safe_stem(path) + "_fx.png")
        im.save(dest)
        outputs.append(dest)
    return Result("已处理 {} 张。".format(len(outputs)), outputs)


def png_to_ico(job: Job) -> Result:
    path = job.file()
    im = Image.open(path).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    dest = job.outdir / (safe_stem(path) + ".ico")
    im.save(dest, format="ICO", sizes=sizes)
    return Result("已生成多尺寸 ICO（最大 256）。", [dest])


def slideshow(job: Job) -> Result:
    title = job.opt("title") or "幻灯片"
    files = job.files()
    folder = job.outdir / "slides"
    folder.mkdir(parents=True, exist_ok=True)
    names = []
    for i, path in enumerate(files, 1):
        im = Image.open(path)
        dest = folder / ("{:03d}.png".format(i))
        im.save(dest)
        names.append(dest.name)
        im.close()
    html = folder / "index.html"
    items = ",".join('"{}"'.format(n) for n in names)
    html.write_text(
        """<!DOCTYPE html><meta charset="utf-8"><title>{title}</title>
<style>html,body{{margin:0;background:#111;color:#eee;height:100%}}
img{{max-width:100vw;max-height:100vh;object-fit:contain;display:block;margin:auto}}
body{{display:flex;align-items:center;justify-content:center;font-family:sans-serif}}</style>
<body><img id="p"><script>
const files=[{items}]; let i=0; const img=document.getElementById('p');
function show(){{img.src=files[i];}}
document.onkeydown=e=>{{if(e.key==='ArrowRight')i=(i+1)%files.length; if(e.key==='ArrowLeft')i=(i-1+files.length)%files.length; show();}};
show();
</script></body>""".format(title=title, items=items),
        encoding="utf-8",
    )
    return Result("幻灯片已生成，用方向键切换。图片按原始像素显示。", [html])


def qrcode_tool(job: Job) -> Result:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    text = job.opt("text")
    if not text:
        raise RuntimeError("请输入内容。")
    box = max(2, int(job.number("box", 12)))
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    im = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    dest = job.outdir / "qrcode.png"
    im.save(dest)
    return Result("已生成 {}×{} 的二维码。".format(im.width, im.height), [dest])


def barcode_tool(job: Job) -> Result:
    import barcode
    from barcode.writer import ImageWriter

    text = job.opt("text") or "1234567890"
    module = max(1, int(job.number("module", 2)))
    code = barcode.get("code128", text, writer=ImageWriter())
    dest = job.outdir / "barcode"
    path = Path(code.save(str(dest), {"module_width": module * 0.4, "module_height": 18, "font_size": 12, "quiet_zone": 4, "dpi": 300}))
    return Result("已生成 Code128。", [path])


def pdf417_tool(job: Job) -> Result:
    text = job.opt("text") or "HELLO"
    # Compact PDF417 encoder is large; draw a Code128 fallback only when library lacks pdf417.
    try:
        import barcode
        from barcode.writer import ImageWriter
        if "pdf417" in barcode.provided_barcodes():
            code = barcode.get("pdf417", text, writer=ImageWriter())
            path = Path(code.save(str(job.outdir / "pdf417"), {"dpi": 300}))
            return Result("已生成 PDF417。", [path])
    except Exception:
        pass
    raise RuntimeError("当前 python-barcode 不包含 PDF417。请改用二维码工具，或安装带 PDF417 的条码库。")


def images_to_pdf(job: Job) -> Result:
    from officertools.engine.raster import save_images_as_pdf

    files = job.files()
    dpi = int(job.number("dpi", 300))
    prepared = []
    for path in files:
        im = Image.open(path).convert("RGB")
        dest = job.outdir / (safe_stem(path) + "_pdfsrc.png")
        im.save(dest)
        prepared.append(dest)
        im.close()
    dest = job.outdir / "images.pdf"
    save_images_as_pdf(prepared, dest, dpi)
    return Result("已按 {} DPI 生成 PDF，没有预先缩小图片。".format(dpi), [dest])


def tiff_tool(job: Job) -> Result:
    mode = job.opt("mode") or "merge"
    files = job.files()
    if mode == "split":
        outputs = []
        for path in files:
            im = Image.open(path)
            n = getattr(im, "n_frames", 1)
            for i in range(n):
                im.seek(i)
                dest = job.outdir / "{}_{:03d}.tiff".format(safe_stem(path), i + 1)
                im.copy().save(dest, format="TIFF")
                outputs.append(dest)
        return Result("已拆成 {} 页。".format(len(outputs)), outputs)
    frames = []
    for path in files:
        im = Image.open(path)
        n = getattr(im, "n_frames", 1)
        for i in range(n):
            im.seek(i)
            frames.append(im.copy().convert("RGB"))
    dest = job.outdir / "merged.tiff"
    frames[0].save(dest, save_all=True, append_images=frames[1:], compression="tiff_lzw")
    return Result("已合并 {} 页 TIFF。".format(len(frames)), [dest])


def dicom_preview(job: Job) -> Result:
    path = job.file()
    data = path.read_bytes()
    # Very small parser for explicit/implicit little-endian grayscale, uncompressed.
    if not data.startswith(b"DICM") and data[128:132] != b"DICM":
        if data[128:132] != b"DICM":
            raise RuntimeError("不是 DICOM 文件。")
    offset = 132 if data[128:132] == b"DICM" else 0
    rows = cols = bits = 0
    samples = 1
    pixel = None
    # Walk until Pixel Data (7FE0,0010). Explicit VR little endian is the common office case.
    i = offset
    while i + 8 <= len(data):
        group = int.from_bytes(data[i:i + 2], "little")
        elem = int.from_bytes(data[i + 2:i + 4], "little")
        vr = data[i + 4:i + 6]
        if vr in (b"OB", b"OW", b"OF", b"SQ", b"UT", b"UN"):
            length = int.from_bytes(data[i + 8:i + 12], "little")
            start = i + 12
        else:
            length = int.from_bytes(data[i + 6:i + 8], "little")
            start = i + 8
        if length == 0xFFFFFFFF:
            raise RuntimeError("这个 DICOM 使用压缩或未定义长度，当前只能转换未压缩图像。")
        chunk = data[start:start + length]
        tag = (group, elem)
        if tag == (0x0028, 0x0010):
            rows = int.from_bytes(chunk[:2], "little")
        elif tag == (0x0028, 0x0011):
            cols = int.from_bytes(chunk[:2], "little")
        elif tag == (0x0028, 0x0100):
            bits = int.from_bytes(chunk[:2], "little")
        elif tag == (0x0028, 0x0002):
            samples = int.from_bytes(chunk[:2], "little")
        elif tag == (0x7FE0, 0x0010):
            pixel = chunk
            break
        i = start + length
    if not pixel or not rows or not cols:
        raise RuntimeError("没有读到未压缩的像素数据。")
    if samples != 1 or bits not in (8, 16):
        raise RuntimeError("目前只转换 8/16 位灰度 DICOM。")
    if bits == 8:
        im = Image.frombytes("L", (cols, rows), pixel[:rows * cols])
    else:
        import array
        vals = array.array("H")
        raw = pixel[: rows * cols * 2]
        vals.frombytes(raw if len(raw) == rows * cols * 2 else raw.ljust(rows * cols * 2, b"\x00"))
        lo = min(vals) if vals else 0
        hi = max(vals) if vals else 1
        span = max(1, hi - lo)
        lut = bytes(max(0, min(255, (v - lo) * 255 // span)) for v in vals)
        im = Image.frombytes("L", (cols, rows), lut)
    dest = job.outdir / (safe_stem(path) + ".png")
    im.save(dest)
    return Result("已导出 {}×{} PNG。".format(cols, rows), [dest])
