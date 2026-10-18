# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import DictionaryObject, NameObject, NumberObject, RectangleObject

from officertools.engine.common import Job, Result, find_tool, run_cmd, safe_stem, unique
from officertools.engine.raster import render_pdf, save_images_as_pdf


def _reader(path: Path, password: str = "") -> PdfReader:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        if not password:
            raise RuntimeError("这个 PDF 有打开密码。")
        status = reader.decrypt(password)
        if status == 0:
            raise RuntimeError("密码不正确。")
    return reader


def _write(writer: PdfWriter, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        writer.write(fh)
    return dest


def parse_ranges(spec: str, count: int):
    spec = (spec or "").strip()
    if not spec:
        return list(range(count))
    chosen = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a)
            end = int(b)
        else:
            start = end = int(part)
        if start < 1 or end > count or end < start:
            raise RuntimeError("页码超出范围：{}（共 {} 页）".format(part, count))
        chosen.extend(range(start - 1, end))
    if not chosen:
        raise RuntimeError("没有选中任何页面。")
    return chosen


def _pages(job: Job):
    path = job.file()
    reader = _reader(path, job.opt("password"))
    indexes = parse_ranges(job.opt("ranges"), len(reader.pages))
    return path, reader, indexes


def merge(job: Job) -> Result:
    files = job.files()
    writer = PdfWriter()
    for path in files:
        reader = _reader(path, job.opt("password"))
        writer.append(reader)
    dest = job.outdir / "merged.pdf"
    _write(writer, dest)
    return Result("已合并 {} 个文件，共 {} 页。".format(len(files), len(writer.pages)), [dest])


def split(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    ranges = job.opt("ranges")
    outputs = []
    if ranges:
        groups = []
        for part in ranges.split(","):
            groups.append(parse_ranges(part, len(reader.pages)))
    else:
        span = max(1, int(job.number("span", 1)))
        groups = [list(range(i, min(i + span, len(reader.pages)))) for i in range(0, len(reader.pages), span)]
    for n, indexes in enumerate(groups, 1):
        writer = PdfWriter()
        for i in indexes:
            writer.add_page(reader.pages[i])
        dest = job.outdir / "{}_{:03d}.pdf".format(safe_stem(path), n)
        outputs.append(_write(writer, dest))
    return Result("已分成 {} 个 PDF。".format(len(outputs)), outputs)


def extract(job: Job) -> Result:
    path, reader, indexes = _pages(job)
    writer = PdfWriter()
    for i in indexes:
        writer.add_page(reader.pages[i])
    dest = job.outdir / (safe_stem(path) + "_pages.pdf")
    _write(writer, dest)
    return Result("已提取 {} 页。".format(len(indexes)), [dest])


def delete(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    drop = set(parse_ranges(job.opt("ranges"), len(reader.pages)))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i not in drop:
            writer.add_page(page)
    if len(writer.pages) == 0:
        raise RuntimeError("不能删掉全部页面。")
    dest = job.outdir / (safe_stem(path) + "_kept.pdf")
    _write(writer, dest)
    return Result("已删除 {} 页，保留 {} 页。".format(len(drop), len(writer.pages)), [dest])


def rotate(job: Job) -> Result:
    path, reader, indexes = _pages(job)
    angle = int(job.opt("angle") or "90")
    chosen = set(indexes)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in chosen:
            page.rotate(angle)
        writer.add_page(page)
    dest = job.outdir / (safe_stem(path) + "_rotated.pdf")
    _write(writer, dest)
    return Result("已旋转 {} 页。".format(len(chosen)), [dest])


def crop(job: Job) -> Result:
    path, reader, indexes = _pages(job)
    chosen = set(indexes) if job.opt("ranges") else set(range(len(reader.pages)))
    top = job.number("top", 0)
    right = job.number("right", 0)
    bottom = job.number("bottom", 0)
    left = job.number("left", 0)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in chosen:
            box = page.mediabox
            page.mediabox = RectangleObject((
                float(box.left) + left,
                float(box.bottom) + bottom,
                float(box.right) - right,
                float(box.top) - top,
            ))
        writer.add_page(page)
    dest = job.outdir / (safe_stem(path) + "_cropped.pdf")
    _write(writer, dest)
    return Result("已裁剪页面。", [dest])


def nup(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    cols = max(1, int(job.number("cols", 2)))
    rows = max(1, int(job.number("rows", 2)))
    per = cols * rows
    writer = PdfWriter()
    pages = list(reader.pages)
    for start in range(0, len(pages), per):
        chunk = pages[start:start + per]
        base = chunk[0]
        width = float(base.mediabox.width)
        height = float(base.mediabox.height)
        canvas = writer.add_blank_page(width=width, height=height)
        cell_w = width / cols
        cell_h = height / rows
        for n, page in enumerate(chunk):
            col = n % cols
            row = n // cols
            pw = float(page.mediabox.width) or 1
            ph = float(page.mediabox.height) or 1
            scale = min(cell_w / pw, cell_h / ph)
            x = col * cell_w + (cell_w - pw * scale) / 2
            y = height - (row + 1) * cell_h + (cell_h - ph * scale) / 2
            canvas.merge_transformed_page(page, Transformation().scale(scale, scale).translate(x, y))
    dest = job.outdir / (safe_stem(path) + "_nup.pdf")
    _write(writer, dest)
    return Result("已按 {}×{} 排版。".format(cols, rows), [dest])


def _overlay_text(page, text, size, opacity, y=None, center=True):
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    if y is None:
        y = height / 2
    x = width / 2 if center else 36
    # WinAnsi cannot encode CJK. Use a content stream with a Type0-less fallback:
    # draw with a standard font only when the text is Latin; otherwise build a
    # simple appearance via a generated single-page PDF is not possible without a font.
    # Embed a tiny identity by writing UTF-16 hex into a FreeText-like stamp using
    # a content stream of individual unencoded glyphs is unreliable. Use report-free
    # approach: create an XObject image is heavy. Stamp via annotation contents.
    packet = io.BytesIO()
    # Minimal PDF page is created by pypdf blank + text in Latin1.
    try:
        encoded = text.encode("latin-1")
        literal = "(" + encoded.decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"
        stream = "q\nBT /F1 {} Tf {} {} Td {} Tj ET\nQ\n".format(int(size), 0 if center else x, y, literal).encode("latin-1")
        use_font = True
    except UnicodeEncodeError:
        use_font = False
        stream = b""
    if use_font:
        from pypdf.generic import DecodedStreamObject
        form = DecodedStreamObject()
        form.set_data(stream)
        form.update({
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): RectangleObject((0, 0, width, height)),
            NameObject("/Resources"): DictionaryObject({
                NameObject("/Font"): DictionaryObject({
                    NameObject("/F1"): DictionaryObject({
                        NameObject("/Type"): NameObject("/Font"),
                        NameObject("/Subtype"): NameObject("/Type1"),
                        NameObject("/BaseFont"): NameObject("/Helvetica"),
                    })
                })
            }),
            NameObject("/FormType"): NumberObject(1),
        })
        # Opacity through an ExtGState is optional; skip if it complicates viewers.
        page.merge_transformed_page  # keep attribute referenced for older checkers
        writer_page_resources = page.get("/Resources")
        if writer_page_resources is None:
            page[NameObject("/Resources")] = DictionaryObject()
        # Simpler path: wrap text in a one-page PDF using pypdf's _writer after creating via PdfWriter blank is circular.
        # Attach as an optional content by merging a PDF built below.
        return _merge_latin_watermark(page, text, size, opacity)
    return _merge_cjk_watermark(page, text, size, opacity)


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _merge_latin_watermark(page, text, size, opacity):
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    pdf = _text_pdf(text, width, height, size, opacity, latin=True)
    stamp = PdfReader(io.BytesIO(pdf)).pages[0]
    page.merge_page(stamp)
    return page


def _merge_cjk_watermark(page, text, size, opacity):
    from PIL import Image, ImageDraw, ImageFont

    width = max(1, int(float(page.mediabox.width) * 200 / 72))
    height = max(1, int(float(page.mediabox.height) * 200 / 72))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _cjk_font(int(size * 200 / 72))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    alpha = max(0, min(255, int(float(opacity) * 255)))
    draw.text(((width - tw) / 2, (height - th) / 2), text, fill=(80, 80, 80, alpha), font=font)
    blob = io.BytesIO()
    image.convert("RGB")  # keep RGBA for PDF mask
    image.save(blob, format="PNG")
    blob.seek(0)
    stamp_buf = io.BytesIO()
    image.save(stamp_buf, format="PDF", resolution=200)
    stamp_buf.seek(0)
    stamp = PdfReader(stamp_buf).pages[0]
    page.merge_page(stamp)
    return page


def _cjk_font(size: int):
    from PIL import ImageFont

    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _text_pdf(text, width, height, size, opacity, latin=True) -> bytes:
    y = height / 2
    content = "BT /F1 {} Tf 1 0 0 1 {} {} Tm ({}) Tj ET".format(
        int(size), 72, y, _escape_pdf_text(text)
    )
    stream = content.encode("latin-1", "replace")
    objects = []
    objects.append("1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append("2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n")
    objects.append(
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {} {}] /Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n".format(
            width, height
        )
    )
    objects.append("4 0 obj<< /Length {} >>stream\n".format(len(stream)).encode("ascii") + stream + b"\nendstream\nendobj\n")
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj if isinstance(obj, bytes) else obj.encode("ascii"))
    xref = len(out)
    out.extend("xref\n0 {}\n".format(len(offsets)).encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend("{:010d} 00000 n \n".format(off).encode("ascii"))
    out.extend("trailer<< /Size {} /Root 1 0 R >>\nstartxref\n{}\n%%EOF".format(len(offsets), xref).encode("ascii"))
    return bytes(out)


def watermark(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    text = job.opt("text") or "草稿"
    size = job.number("size", 48)
    opacity = job.opt("opacity") or "0.18"
    writer = PdfWriter()
    for page in reader.pages:
        _merge_cjk_watermark(page, text, size, opacity)
        writer.add_page(page)
    dest = job.outdir / (safe_stem(path) + "_watermark.pdf")
    _write(writer, dest)
    return Result("已添加水印。", [dest])


def pagenum(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    start = int(job.number("start", 1))
    fmt = job.opt("fmt") or "{n} / {total}"
    total = len(reader.pages)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        label = fmt.replace("{n}", str(start + i)).replace("{total}", str(total))
        _stamp_bottom(page, label)
        writer.add_page(page)
    dest = job.outdir / (safe_stem(path) + "_pagenum.pdf")
    _write(writer, dest)
    return Result("已加上页码。", [dest])


def _stamp_bottom(page, text):
    from PIL import Image, ImageDraw

    width = max(1, int(float(page.mediabox.width) * 150 / 72))
    height = max(1, int(float(page.mediabox.height) * 150 / 72))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _cjk_font(max(14, int(11 * 150 / 72)))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) / 2, height - (bbox[3] - bbox[1]) - int(28 * 150 / 72)), text, fill=(0, 0, 0, 255), font=font)
    blob = io.BytesIO()
    image.save(blob, format="PDF", resolution=150)
    blob.seek(0)
    page.merge_page(PdfReader(blob).pages[0])


def lock(job: Job) -> Result:
    path = job.file()
    password = job.opt("password")
    if not password:
        raise RuntimeError("请填写打开密码。")
    reader = _reader(path)
    writer = PdfWriter()
    writer.append(reader)
    writer.encrypt(password)
    dest = job.outdir / (safe_stem(path) + "_locked.pdf")
    _write(writer, dest)
    return Result("已加密。", [dest])


def unlock(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    writer = PdfWriter()
    writer.append(reader)
    dest = job.outdir / (safe_stem(path) + "_unlocked.pdf")
    _write(writer, dest)
    return Result("已去掉打开密码。", [dest])


def optimize(job: Job) -> Result:
    path = job.file()
    if job.flag("gs"):
        gs = find_tool(["gswin64c", "gswin32c", "gs"])
        if gs:
            dest = job.outdir / (safe_stem(path) + "_optimized.pdf")
            run_cmd([
                gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/ebook", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                "-sOutputFile=" + str(dest), str(path),
            ])
            return Result("已用 Ghostscript 压缩。", [dest])
    reader = _reader(path, job.opt("password"))
    writer = PdfWriter()
    for page in reader.pages:
        page.compress_content_streams()
        writer.add_page(page)
    dest = job.outdir / (safe_stem(path) + "_optimized.pdf")
    _write(writer, dest)
    return Result("已压缩内容流。扫描件若体积变化不大，请安装 Ghostscript 后再试。", [dest])


def to_text(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    parts = []
    for i, page in enumerate(reader.pages, 1):
        parts.append("----- 第 {} 页 -----\n{}".format(i, page.extract_text() or ""))
    dest = job.outdir / (safe_stem(path) + ".txt")
    dest.write_text("\n\n".join(parts), encoding="utf-8")
    return Result("已提取文本。扫描件如果几乎没有文字，请用 PDF OCR。", [dest])


def to_html(job: Job) -> Result:
    text_result = to_text(job)
    text = text_result.files[0].read_text(encoding="utf-8")
    body = "".join("<p>{}</p>".format(escape(line)) for line in text.splitlines())
    dest = job.outdir / (safe_stem(job.file()) + ".html")
    dest.write_text(
        "<!DOCTYPE html><meta charset='utf-8'><title>{}</title><body style='font:16px/1.6 sans-serif'>{}</body>".format(
            escape(job.file().name), body
        ),
        encoding="utf-8",
    )
    return Result("已生成 HTML。", [dest])


def to_docx(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    paragraphs = []
    for i, page in enumerate(reader.pages, 1):
        paragraphs.append("第 {} 页".format(i))
        paragraphs.extend((page.extract_text() or "").splitlines() or [""])
    dest = job.outdir / (safe_stem(path) + ".docx")
    _write_docx(dest, paragraphs)
    return Result("已生成 DOCX。这是按段落提取的文字，不是版式还原。", [dest])


def _write_docx(dest: Path, paragraphs) -> None:
    def p(text):
        return (
            "<w:p><w:r><w:rPr><w:rFonts w:ascii='Calibri' w:hAnsi='Calibri' w:eastAsia='Microsoft YaHei'/>"
            "<w:sz w:val='21'/></w:rPr><w:t xml:space='preserve'>{}</w:t></w:r></w:p>".format(escape(text))
        )
    document = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        "<w:body>{}<w:sectPr><w:pgSz w:w='11906' w:h='16838'/></w:sectPr></w:body></w:document>"
    ).format("".join(p(line) for line in paragraphs))
    content_types = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
        "<Default Extension='xml' ContentType='application/xml'/>"
        "<Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
        "</Types>"
    )
    rels = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>"
        "</Relationships>"
    )
    with zipfile.ZipFile(str(dest), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)


def info(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    lines = ["文件：{}".format(path), "页数：{}".format(len(reader.pages)), "加密：{}".format(reader.is_encrypted)]
    meta = reader.metadata or {}
    for key, value in meta.items():
        lines.append("{}：{}".format(key, value))
    for i, page in enumerate(reader.pages, 1):
        box = page.mediabox
        lines.append("第 {} 页：{:.1f} × {:.1f} 点".format(i, float(box.width), float(box.height)))
    dest = job.outdir / (safe_stem(path) + "_info.txt")
    dest.write_text("\n".join(lines), encoding="utf-8")
    return Result("\n".join(lines[:40]), [dest])


def rename(job: Job) -> Result:
    files = job.files()
    pattern = job.opt("pattern") or "{title}"
    outputs = []
    lines = []
    for n, path in enumerate(files, 1):
        reader = _reader(path)
        title = ""
        if reader.metadata:
            title = str(reader.metadata.get("/Title") or "")
        title = re.sub(r'[<>:"/\\|?*]', "_", title).strip() or path.stem
        name = pattern.format(title=title, pages=len(reader.pages), name=path.stem, n=n)
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        dest = unique(path.with_name(name))
        path.rename(dest)
        outputs.append(dest)
        lines.append(path.name + " → " + dest.name)
    return Result("已重命名：\n" + "\n".join(lines), outputs)


def images_out(job: Job) -> Result:
    path = job.file()
    reader = _reader(path, job.opt("password"))
    outputs = []
    index = 1
    for page_no, page in enumerate(reader.pages, 1):
        images = getattr(page, "images", None) or []
        for image in images:
            data = image.data
            ext = (image.name.split(".")[-1] or "bin").lower()
            if ext not in ("png", "jpg", "jpeg", "jp2", "tif", "tiff", "gif", "bmp"):
                ext = "png"
            dest = job.outdir / "p{:03d}_{:03d}.{}".format(page_no, index, ext)
            dest.write_bytes(data)
            outputs.append(dest)
            index += 1
    if not outputs:
        raise RuntimeError("没有找到内嵌图片。")
    return Result("已导出 {} 张原始图片。".format(len(outputs)), outputs)


def to_images(job: Job) -> Result:
    dpi = int(job.number("dpi", 200))
    outputs = render_pdf(job.file(), job.outdir, dpi)
    return Result("已按 {} DPI 导出 {} 页。".format(dpi, len(outputs)), outputs)


def to_bw(job: Job) -> Result:
    dpi = int(job.number("dpi", 200))
    images = render_pdf(job.file(), job.outdir / "_gray", dpi, gray=True)
    dest = job.outdir / (safe_stem(job.file()) + "_bw.pdf")
    save_images_as_pdf(images, dest, dpi)
    return Result("已生成黑白 PDF。", [dest])


def deskew(job: Job) -> Result:
    from officertools.engine.raster import deskew_image

    dpi = int(job.number("dpi", 200))
    images = render_pdf(job.file(), job.outdir / "_deskew", dpi)
    fixed = []
    for image in images:
        fixed.append(deskew_image(image))
    dest = job.outdir / (safe_stem(job.file()) + "_deskew.pdf")
    save_images_as_pdf(fixed, dest, dpi)
    return Result("已纠偏并重新组成 PDF。", [dest])


def pdf_reader(job: Job) -> Result:
    return to_text(job)
