"""Small, DPI-aware pictograms drawn locally; no icon fonts or downloads."""
import math

from PIL import Image, ImageDraw, ImageFont, ImageTk


def navigation_icon(app, name, color):
    """One 20px grid and 1.6px stroke for every navigation pictogram."""
    cache = getattr(app, "_nav_icon_cache", None)
    if cache is None:
        cache = app._nav_icon_cache = {}
    size = app.px(20)
    key = (name, color, size)
    if key in cache:
        return cache[key]
    unit = size * 3 / 20
    image = Image.new("RGBA", (size * 3, size * 3))
    draw = ImageDraw.Draw(image)
    width = max(1, round(1.6 * unit))

    def coords(values):
        return tuple(round(v * unit) for v in values)

    def line(values):
        draw.line(coords(values), fill=color, width=width, joint="curve")

    def rect(values, radius=1):
        draw.rounded_rectangle(coords(values), radius=round(radius * unit), outline=color, width=width)

    def ellipse(values):
        draw.ellipse(coords(values), outline=color, width=width)

    if name == "全部":
        for x in (3, 11):
            for y in (3, 11):
                rect((x, y, x + 6, y + 6))
    elif name == "收藏":
        points = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            radius = 8 if i % 2 == 0 else 3.7
            points.extend((10 + math.cos(angle) * radius, 10 + math.sin(angle) * radius))
        line(points + points[:2])
    elif name == "最近":
        ellipse((2, 2, 18, 18))
        line((10, 5, 10, 10, 14, 12))
    elif name == "PDF":
        line((4, 2, 12, 2, 16, 6, 16, 18, 4, 18, 4, 2))
        line((12, 2, 12, 6, 16, 6))
        line((7, 10, 13, 10))
        line((7, 14, 13, 14))
    elif name == "格式转换":
        line((2, 6, 17, 6, 13, 2))
        line((18, 14, 3, 14, 7, 18))
    elif name == "图片":
        rect((2, 3, 18, 17))
        ellipse((5, 6, 8, 9))
        line((3, 15, 9, 10, 12, 13, 15, 10, 18, 13))
    elif name == "识别":
        for values in ((2, 7, 2, 2, 7, 2), (13, 2, 18, 2, 18, 7),
                       (2, 13, 2, 18, 7, 18), (13, 18, 18, 18, 18, 13)):
            line(values)
        line((6, 6, 14, 6))
        line((10, 6, 10, 14))
    elif name == "录屏截屏":
        rect((2, 3, 18, 15))
        line((8, 6, 8, 12, 13, 9, 8, 6))
        line((10, 15, 10, 18, 6, 18, 14, 18))
    elif name == "文件":
        line((2, 7, 2, 4, 8, 4, 10, 7))
        rect((2, 7, 18, 17))
    elif name == "系统":
        rect((5, 5, 15, 15), radius=2)
        ellipse((8, 8, 12, 12))
        for offset in (7, 13):
            line((offset, 2, offset, 5))
            line((offset, 15, offset, 18))
            line((2, offset, 5, offset))
            line((15, offset, 18, offset))
    elif name == "阅读":
        line((10, 5, 6, 3, 2, 3, 2, 16, 6, 16, 10, 18,
              14, 16, 18, 16, 18, 3, 14, 3, 10, 5, 10, 18))
    photo = ImageTk.PhotoImage(image.resize((size, size), Image.Resampling.LANCZOS), master=app.root)
    cache[key] = photo
    return photo


CATEGORY_COLORS = {
    "PDF": ("#e45b68", "#fff0f2"),
    "图片": ("#8b5ad7", "#f3edff"),
    "格式转换": ("#4479df", "#edf3ff"),
    "识别": ("#179c90", "#e8f8f5"),
    "录屏截屏": ("#df8a25", "#fff5e6"),
    "文件": ("#3a91b4", "#eaf6fb"),
    "系统": ("#6474ce", "#eef0ff"),
    "阅读": ("#329e79", "#eaf8f0"),
}

DARK_CATEGORY_COLORS = {
    "PDF": ("#ff8b99", "#3b2533"), "图片": ("#bc9aff", "#302745"),
    "格式转换": ("#8bb4ff", "#21334f"), "识别": ("#64d5c6", "#193a3b"),
    "录屏截屏": ("#f4bf73", "#3c3022"), "文件": ("#81cbe8", "#203746"),
    "系统": ("#a5b2ff", "#2a304d"), "阅读": ("#7bd8af", "#203b33"),
}


def category_colors(dark=False):
    return DARK_CATEGORY_COLORS if dark else CATEGORY_COLORS

# Explicit operation badges keep tools within the same category distinguishable.
OPERATIONS = {
    "page-master": "SORT", "page-cut": "CUT", "links": "URL",
    "merge": "+", "split": "/", "extract": "OUT", "delete": "-",
    "rotate": "90", "crop": "CUT", "nup": "4", "pagenum": "123",
    "watermark": "WM", "unlock": "OPEN", "lock": "KEY", "optimize": "ZIP",
    "bw": "B/W", "deskew": "FIX", "images": "IMG", "to-image": "IMG",
    "to-text": "TXT", "to-html": "WEB", "to-word": "W", "info": "i",
    "rename": "Aa", "to-pdf": "PDF", "convert": "GO", "resize": "SIZE",
    "compress": "ZIP", "splice": "+", "stamp": "TIME", "exif": "i",
    "effect": "FX", "to-ico": "ICO", "preview": "IMG",
}


def render_icon(tool_id, category, size=52, dark=False):
    """Render at 3x resolution for crisp edges at fractional monitor scales."""
    scale = 3
    im = Image.new("RGBA", (size * scale, size * scale))
    d = ImageDraw.Draw(im)
    fg, bg = category_colors(dark).get(category, ("#5865df", "#eef0ff"))
    def box(coords):
        return tuple(round(v * size * scale / 56) for v in coords)
    def line(coords, fill=fg, width=2):
        d.line(box(coords), fill=fill, width=max(1, round(width * size * scale / 56)))
    def rect(coords, fill=None, outline=fg, radius=2):
        d.rounded_rectangle(box(coords), radius=radius * size * scale / 56,
                            fill=fill, outline=outline, width=max(1, round(2 * size * scale / 56)))
    def text(x, y, value, pixels, color):
        # Pillow's bundled bitmap font is portable across supported Windows versions.
        font = ImageFont.load_default()
        mask = Image.new("RGBA", (100, 20))
        ImageDraw.Draw(mask).text((1, 0), value, font=font, fill=color)
        bounds = mask.getbbox()
        if bounds:
            mask = mask.crop(bounds)
            height = round(pixels * size * scale / 56)
            mask = mask.resize((max(1, round(mask.width * height / mask.height)), height), Image.Resampling.LANCZOS)
            im.alpha_composite(mask, (round(x * size * scale / 56), round(y * size * scale / 56)))
    rect((0, 0, 55, 55), bg, bg, 13)
    if tool_id in ("qrcode", "barcode", "pdf417"):
        if tool_id == "qrcode":
            for x, y in ((12, 12), (30, 12), (12, 30)):
                rect((x, y, x + 13, y + 13), outline=fg, radius=1)
                rect((x + 4, y + 4, x + 9, y + 9), fg, fg, 0)
            for x, y in ((31, 31), (39, 37), (31, 42), (42, 29)):
                rect((x, y, x + 4, y + 4), fg, fg, 0)
        else:
            for i, x in enumerate(range(12, 44, 4)):
                line((x, 14, x, 41 if i % 3 else 36), width=1 if i % 2 else 2)
            if tool_id == "pdf417":
                line((11, 25, 44, 25), bg, 3)
                line((11, 33, 44, 33), bg, 3)
        return im.resize((size, size), Image.Resampling.LANCZOS)
    if category == "图片" or tool_id in ("image-viewer", "dup-photos"):
        rect((10, 11, 40, 37))
        d.ellipse(box((16, 16, 22, 22)), fill=fg)
        line((12, 34, 22, 25, 28, 31, 34, 24, 39, 29))
    elif category == "录屏截屏" or tool_id == "ocr-screen":
        if tool_id == "voice-record":
            rect((22, 10, 32, 31), radius=5)
            line((17, 24, 17, 30, 22, 36, 32, 36, 37, 30, 37, 24))
            line((27, 36, 27, 43, 19, 43, 35, 43))
        elif tool_id == "magnifier":
            d.ellipse(box((11, 10, 34, 33)), outline=fg, width=round(2 * size * scale / 56))
            line((31, 31, 43, 43), width=4)
        else:
            rect((10, 12, 43, 35))
            line((26, 35, 26, 42, 18, 42, 35, 42))
    elif category == "文件":
        line((10, 19, 10, 13, 23, 13, 28, 19))
        rect((10, 19, 43, 39), radius=3)
    elif tool_id == "calc":
        rect((14, 8, 40, 45), radius=4)
        rect((19, 13, 35, 21), fg, fg)
        for x in (20, 28, 36):
            for y in (28, 36):
                rect((x - 2, y - 2, x + 1, y + 1), fg, fg, 0)
    elif tool_id == "shutdown":
        d.arc(box((12, 12, 42, 42)), 300, 600, fill=fg, width=round(3 * size * scale / 56))
        line((27, 9, 27, 27), width=3)
    else:
        line((14, 9, 32, 9, 41, 18, 41, 43, 14, 43, 14, 9))
        line((32, 9, 32, 19, 41, 19))
        for y in (25, 31, 37):
            line((20, y, 33, y), width=1.5)
    special = {
        "slideshow": "PLAY", "pick-color": "RGB", "screenshot": "SNAP",
        "screen-record": "REC", "gif-record": "GIF", "voice-record": "MIC",
        "annotate": "PEN", "magnifier": "+", "speech": "TTS",
        "dup-files": "=", "dup-photos": "=", "dup-audio": "=",
        "filetime": "TIME", "zip-batch": "ZIP", "unzip-batch": "OUT",
        "mkdir-batch": "+", "autocopy": "COPY", "checksum": "HASH",
        "textdiff": "DIFF", "disk-bench": "MB/s", "pdf-reader": "READ",
        "image-viewer": "VIEW", "calc": "", "shutdown": "",
    }
    operation = special.get(tool_id)
    if operation is None:
        operation = "OCR" if tool_id.startswith("ocr-") else OPERATIONS.get(tool_id.split("-", 1)[-1], "GO")
    if operation:
        badge_width = min(33, max(18, len(operation) * 6 + 6))
        rect((54 - badge_width, 34, 54, 52), fg, fg, 5)
        text(57 - badge_width, 39, operation, 8, "#111722" if dark else "white")
    return im.resize((size, size), Image.Resampling.LANCZOS)


def tool_icon(app, tool, size=52):
    cache = getattr(app, "_icon_cache", None)
    if cache is None:
        cache = app._icon_cache = {}
    dark = getattr(app, "theme", "light") == "dark"
    key = (tool.id, app.px(size), dark)
    if key not in cache:
        cache[key] = ImageTk.PhotoImage(render_icon(tool.id, tool.category, key[1], dark), master=app.root)
    return cache[key]
