# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from officertools.engine.common import Job, Result, find_tool, run_cmd, safe_stem
from officertools.engine.pdf import _write_docx
from officertools.engine.raster import render_pdf


def _ffmpeg() -> str:
    path = find_tool(["ffmpeg"])
    if not path:
        raise RuntimeError("需要安装 FFmpeg，并把 ffmpeg 加入 PATH。")
    return path


def audio_convert(job: Job) -> Result:
    ffmpeg = _ffmpeg()
    fmt = job.opt("fmt") or "mp3"
    outputs = []
    for path in job.files():
        dest = job.outdir / (safe_stem(path) + "." + fmt)
        run_cmd([ffmpeg, "-y", "-i", str(path), str(dest)])
        outputs.append(dest)
    return Result("已转换 {} 个音频。".format(len(outputs)), outputs)


def video_convert(job: Job) -> Result:
    ffmpeg = _ffmpeg()
    fmt = job.opt("fmt") or "mp4"
    outputs = []
    for path in job.files():
        dest = job.outdir / (safe_stem(path) + "." + fmt)
        run_cmd([ffmpeg, "-y", "-i", str(path), str(dest)])
        outputs.append(dest)
    return Result("已转换 {} 个视频。".format(len(outputs)), outputs)


def _record_args(job: Job, gif: bool):
    ffmpeg = _ffmpeg()
    seconds = int(job.number("seconds", 10))
    fps = int(job.number("fps", 12 if gif else 30))
    dest = job.outdir / ("capture.gif" if gif else "capture.mp4")
    cmd = [ffmpeg, "-y"]
    if sys.platform == "win32":
        cmd += ["-f", "gdigrab", "-framerate", str(fps), "-i", "desktop"]
    elif sys.platform == "darwin":
        cmd += ["-f", "avfoundation", "-framerate", str(fps), "-i", "1:none"]
    else:
        cmd += ["-f", "x11grab", "-framerate", str(fps), "-i", os.environ.get("DISPLAY", ":0.0")]
    if seconds > 0:
        cmd += ["-t", str(seconds)]
    if gif:
        cmd += ["-vf", "fps={},scale=iw:-1:flags=lanczos".format(fps), str(dest)]
    else:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest)]
    return cmd, dest, seconds


def screen_record(job: Job) -> Result:
    cmd, dest, seconds = _record_args(job, False)
    if seconds <= 0:
        subprocess.Popen(cmd)
        return Result("已启动 FFmpeg。关闭它的窗口即停止录像。输出：\n" + str(dest))
    run_cmd(cmd)
    return Result("录像完成。", [dest])


def gif_record(job: Job) -> Result:
    cmd, dest, seconds = _record_args(job, True)
    run_cmd(cmd)
    return Result("GIF 已保存。", [dest])


def voice_record(job: Job) -> Result:
    ffmpeg = _ffmpeg()
    seconds = max(1, int(job.number("seconds", 10)))
    dest = job.outdir / "voice.wav"
    if sys.platform == "win32":
        src = ["-f", "dshow", "-i", "audio=virtual-audio-capturer"]
        # Default to the first dshow audio device name is machine-specific.
        # Use WASAPI loop of microphone via dshow alternative "audio=@device_cm_{...}" is unknown.
        listed = subprocess.run([ffmpeg, "-list_devices", "true", "-f", "dshow", "-i", "dummy"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        name = None
        for line in (listed.stdout or "").splitlines():
            if "(audio)" in line and '"' in line:
                name = line.split('"')[1]
                break
        if not name:
            raise RuntimeError("没有找到麦克风。FFmpeg 设备列表：\n" + (listed.stdout or "")[-1500:])
        src = ["-f", "dshow", "-i", "audio=" + name]
    elif sys.platform == "darwin":
        src = ["-f", "avfoundation", "-i", ":0"]
    else:
        src = ["-f", "pulse", "-i", "default"]
    run_cmd([ffmpeg, "-y"] + src + ["-t", str(seconds), str(dest)])
    return Result("已录音 {} 秒。".format(seconds), [dest])


def screenshot(job: Job) -> Result:
    from PIL import ImageGrab

    try:
        im = ImageGrab.grab(all_screens=True)
    except TypeError:
        im = ImageGrab.grab()
    dest = job.outdir / "screenshot.png"
    im.save(dest, format="PNG")
    return Result("已截取 {}×{} 像素。".format(im.width, im.height), [dest])


def _strip_ns(blob: bytes) -> str:
    try:
        root = ET.fromstring(blob)
    except ET.ParseError:
        return ""
    texts = []
    for node in root.iter():
        if node.text and node.text.strip():
            texts.append(node.text.strip())
        if node.tail and node.tail.strip():
            texts.append(node.tail.strip())
    return "\n".join(texts)


def office_text_from(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".csv", ".log"):
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix in (".html", ".htm", ".xml"):
        return _strip_ns(path.read_bytes())
    if suffix == ".docx":
        with zipfile.ZipFile(str(path)) as zf:
            return _strip_ns(zf.read("word/document.xml"))
    if suffix == ".xlsx":
        with zipfile.ZipFile(str(path)) as zf:
            shared = []
            if "xl/sharedStrings.xml" in zf.namelist():
                root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for si in root:
                    shared.append("".join(si.itertext()))
            parts = []
            for name in zf.namelist():
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    parts.append(_strip_ns(zf.read(name)))
            return "\n".join(shared + parts)
    if suffix == ".pptx":
        with zipfile.ZipFile(str(path)) as zf:
            parts = []
            for name in sorted(zf.namelist()):
                if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                    parts.append(_strip_ns(zf.read(name)))
            return "\n\n".join(parts)
    raise RuntimeError("不能直接读取这种文档：" + suffix)


def office_to_text(job: Job) -> Result:
    outputs = []
    for path in job.files():
        text = office_text_from(path)
        dest = job.outdir / (safe_stem(path) + ".txt")
        dest.write_text(text, encoding="utf-8")
        outputs.append(dest)
    return Result("已提取文本。", outputs)


def _soffice():
    return find_tool(["soffice", "libreoffice"])


def office_convert(job: Job) -> Result:
    fmt = job.opt("fmt") or "pdf"
    soffice = _soffice()
    outputs = []
    if soffice and fmt in ("pdf", "docx", "html", "txt"):
        for path in job.files():
            run_cmd([soffice, "--headless", "--convert-to", fmt, "--outdir", str(job.outdir), str(path)])
            dest = job.outdir / (safe_stem(path) + "." + fmt)
            if dest.exists():
                outputs.append(dest)
        if outputs:
            return Result("已用 LibreOffice 转换。", outputs)
    if fmt == "txt":
        return office_to_text(job)
    if fmt == "docx":
        for path in job.files():
            text = office_text_from(path)
            dest = job.outdir / (safe_stem(path) + ".docx")
            _write_docx(dest, text.splitlines())
            outputs.append(dest)
        return Result("已按段落生成 DOCX。安装 LibreOffice 后可以做版式转换。", outputs)
    if fmt == "html":
        for path in job.files():
            text = office_text_from(path)
            dest = job.outdir / (safe_stem(path) + ".html")
            dest.write_text("<meta charset='utf-8'><pre>{}</pre>".format(text.replace("&", "&amp;").replace("<", "&lt;")), encoding="utf-8")
            outputs.append(dest)
        return Result("已生成 HTML 文本。", outputs)
    raise RuntimeError("转成 PDF 需要安装 LibreOffice，并保证 soffice 在 PATH 中。")


def office_to_image(job: Job) -> Result:
    soffice = _soffice()
    if not soffice:
        raise RuntimeError("文档转图片需要 LibreOffice。")
    dpi = int(job.number("dpi", 150))
    outputs = []
    for path in job.files():
        run_cmd([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(job.outdir), str(path)])
        pdf = job.outdir / (safe_stem(path) + ".pdf")
        outputs.extend(render_pdf(pdf, job.outdir, dpi))
    return Result("已导出图片。", outputs)


def speech(job: Job) -> Result:
    text = job.opt("text")
    if not text:
        raise RuntimeError("请输入文字。")
    dest = job.outdir / "speech.wav"
    if sys.platform == "win32":
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.SetOutputToWaveFile('{}'); $s.Speak(@'\n{}\n'@)".format(str(dest).replace("'", "''"), text.replace("'", "''"))
        )
        run_cmd(["powershell", "-NoProfile", "-Command", ps])
        return Result("已生成语音。", [dest])
    if sys.platform == "darwin":
        aiff = job.outdir / "speech.aiff"
        run_cmd(["say", "-o", str(aiff), text])
        return Result("已生成语音。", [aiff])
    espeak = find_tool(["espeak-ng", "espeak"])
    if not espeak:
        raise RuntimeError("Linux 需要安装 espeak-ng。")
    run_cmd([espeak, "-w", str(dest), text])
    return Result("已生成语音。", [dest])


def ocr_image(job: Job) -> Result:
    tesseract = find_tool(["tesseract"])
    if not tesseract:
        raise RuntimeError("需要安装 Tesseract，并把 tesseract 加入 PATH。中文请同时安装 chi_sim 语言包。")
    lang = job.opt("lang") or "chi_sim+eng"
    parts = []
    for path in job.files():
        outbase = job.outdir / safe_stem(path)
        run_cmd([tesseract, str(path), str(outbase), "-l", lang])
        text = Path(str(outbase) + ".txt").read_text(encoding="utf-8", errors="replace")
        parts.append("===== {}\n{}".format(path.name, text))
    dest = job.outdir / "ocr.txt"
    dest.write_text("\n\n".join(parts), encoding="utf-8")
    return Result("\n\n".join(parts)[:8000], [dest])


def ocr_pdf(job: Job) -> Result:
    images = render_pdf(job.file(), job.outdir / "pages", int(job.number("dpi", 300)))
    job.opts["files"] = "|".join(str(p) for p in images)
    return ocr_image(job)


def ocr_screen(job: Job) -> Result:
    shot = screenshot(job)
    job.opts["files"] = str(shot.files[0])
    return ocr_image(job)


def chm_to_pdf(job: Job) -> Result:
    path = job.file()
    work = job.outdir / "chm"
    if work.exists():
        shutil.rmtree(str(work))
    work.mkdir(parents=True)
    seven = find_tool(["7z", "7za"])
    if seven:
        run_cmd([seven, "x", "-y", "-o" + str(work), str(path)])
    elif sys.platform == "win32":
        hh = find_tool(["hh"])
        if not hh:
            raise RuntimeError("解压 CHM 需要 7-Zip。")
        run_cmd([hh, "-decompile", str(work), str(path)])
    else:
        raise RuntimeError("解压 CHM 需要 7-Zip。")
    texts = []
    for file in work.rglob("*"):
        if file.suffix.lower() in (".html", ".htm", ".txt"):
            if file.suffix.lower() == ".txt":
                texts.append(file.read_text(encoding="utf-8", errors="replace"))
            else:
                texts.append(_strip_ns(file.read_bytes()))
    if not texts:
        raise RuntimeError("CHM 里没有 HTML。")
    from officertools.engine.pdf import _text_pdf
    # Write a text PDF via DOCX-like pages of extracted text using Pillow images is heavy.
    # Produce a readable text file and a simple one-page-per-chunk PDF through report-free text pdf for latin,
    # and a DOCX which Word can print. Also a PDF of wrapped images so Chinese survives.
    from PIL import Image, ImageDraw
    from officertools.engine.pdf import _cjk_font
    from officertools.engine.raster import save_images_as_pdf

    pages = []
    blob = "\n".join(texts)
    lines = blob.splitlines() or [""]
    chunk = []
    images = []
    font = _cjk_font(28)

    def flush(n):
        im = Image.new("RGB", (1240, 1754), "white")
        draw = ImageDraw.Draw(im)
        y = 40
        for line in chunk:
            draw.text((40, y), line[:80], fill="black", font=font)
            y += 40
        dest = job.outdir / "chm-{:03d}.png".format(n)
        im.save(dest)
        images.append(dest)

    n = 1
    for line in lines:
        chunk.append(line)
        if len(chunk) >= 40:
            flush(n)
            n += 1
            chunk = []
    if chunk:
        flush(n)
    pdf = job.outdir / (safe_stem(path) + ".pdf")
    save_images_as_pdf(images, pdf, 150)
    txt = job.outdir / (safe_stem(path) + ".txt")
    txt.write_text(blob, encoding="utf-8")
    return Result("已把 CHM 正文排成 PDF。", [pdf, txt])


def calc(job: Job) -> Result:
    expr = job.opt("expr")
    if not expr:
        raise RuntimeError("请输入表达式。")
    allowed = set("0123456789+-*/().% ")
    if any(ch not in allowed for ch in expr):
        raise RuntimeError("只允许数字和 + - * / % ( )。")
    value = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 — charset checked above
    return Result("{} = {}".format(expr, value))


def shutdown(job: Job) -> Result:
    action = job.opt("action") or "shutdown"
    minutes = max(0, int(job.number("minutes", 30)))
    if action != "cancel" and not job.flag("confirm"):
        raise RuntimeError("请勾选「我确认执行」。")
    seconds = minutes * 60
    if sys.platform == "win32":
        if action == "cancel":
            run_cmd(["shutdown", "/a"])
            return Result("已取消关机计划。")
        flag = {"shutdown": "/s", "restart": "/r", "sleep": "/h"}[action]
        if action == "sleep":
            run_cmd(["shutdown", "/h"])
        else:
            run_cmd(["shutdown", flag, "/t", str(seconds)])
        return Result("已计划 {}，{} 分钟后执行。可用「取消」撤销。".format(action, minutes))
    if sys.platform == "darwin":
        if action == "cancel":
            run_cmd(["killall", "shutdown"])
            return Result("已尝试取消。")
        if action == "sleep":
            run_cmd(["pmset", "sleepnow"])
            return Result("正在休眠。")
        flag = "-h" if action == "shutdown" else "-r"
        run_cmd(["sudo", "shutdown", flag, "+{}".format(minutes)])
        return Result("已提交给 shutdown。macOS 可能要求输入管理员密码。")
    if action == "cancel":
        run_cmd(["shutdown", "-c"])
        return Result("已取消。")
    if action == "sleep":
        run_cmd(["systemctl", "suspend"])
        return Result("正在休眠。")
    flag = "-h" if action == "shutdown" else "-r"
    run_cmd(["shutdown", flag, "+{}".format(minutes)])
    return Result("已计划。")
