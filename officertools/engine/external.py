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
    paths=job.files()
    for n,path in enumerate(paths):
        job.checkpoint(n*100/len(paths),path.name)
        dest = job.outdir / (safe_stem(path) + "." + fmt)
        args=[ffmpeg,"-y","-i",str(path)]
        if job.number("start",0)>0: args += ["-ss",job.opt("start")]
        if job.number("duration",0)>0: args += ["-t",job.opt("duration")]
        if job.number("bitrate",0)>0 and fmt not in ("wav","flac"): args += ["-b:a",job.opt("bitrate")+"k"]
        if job.number("sample-rate",0)>0: args += ["-ar",job.opt("sample-rate")]
        if job.number("channels",0)>0: args += ["-ac",job.opt("channels")]
        run_cmd(args+[str(dest)])
        outputs.append(dest)
    return Result("已转换 {} 个音频。".format(len(outputs)), outputs)


def video_convert(job: Job) -> Result:
    ffmpeg = _ffmpeg()
    fmt = job.opt("fmt") or "mp4"
    outputs = []
    paths=job.files()
    for n,path in enumerate(paths):
        job.checkpoint(n*100/len(paths),path.name)
        dest = job.outdir / (safe_stem(path) + "." + fmt)
        args=[ffmpeg,"-y","-i",str(path)]
        if job.number("start",0)>0: args += ["-ss",job.opt("start")]
        if job.number("duration",0)>0: args += ["-t",job.opt("duration")]
        width=int(job.number("width",0))
        if width>0:
            if width%2: raise RuntimeError("输出宽度需为偶数。")
            args += ["-vf","scale={}:-2".format(width)]
        if job.number("fps",0)>0: args += ["-r",job.opt("fps")]
        if fmt in ("mp4","mkv","mov"):
            args += ["-c:v","libx264","-crf",str(max(0,min(51,int(job.number("crf",23))))),"-pix_fmt","yuv420p"]
        run_cmd(args+[str(dest)])
        outputs.append(dest)
    return Result("已转换 {} 个视频。".format(len(outputs)), outputs)


def _record_args(job: Job, gif: bool):
    ffmpeg = _ffmpeg()
    seconds = int(job.number("seconds", 10))
    fps = int(job.number("fps", 12 if gif else 30))
    dest = job.outdir / ("capture.gif" if gif else "capture.mp4")
    cmd = [ffmpeg, "-y"]
    if sys.platform == "win32":
        cmd += ["-f", "gdigrab", "-framerate", str(fps)]
        if job.opt("bbox"):
            x,y,w,h=parse_bbox(job.opt("bbox"))
            cmd += ["-offset_x",str(x),"-offset_y",str(y),"-video_size","{}x{}".format(w,h)]
        cmd += ["-i", "desktop"]
        if job.opt("audio-device") and not gif:
            cmd += ["-f","dshow","-i","audio="+job.opt("audio-device")]
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
    # FFmpeg needs a normal 'q' to finalize MP4 when a user stops recording.
    import tempfile
    with tempfile.TemporaryFile() as log:
        options={"creationflags":subprocess.CREATE_NO_WINDOW} if sys.platform=="win32" else {}
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log,**options)
        while True:
            try:
                code=proc.wait(timeout=.2)
                break
            except subprocess.TimeoutExpired:
                if job.cancel.is_set():
                    proc.communicate(input=b"q\n",timeout=15)
                    code=proc.returncode
                    break
        if code:
            log.seek(0)
            raise RuntimeError(log.read().decode("utf-8",errors="replace")[-3000:])
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


def parse_bbox(raw):
    values=[int(v.strip()) for v in raw.split(",")]
    if len(values)!=4 or values[2]<=0 or values[3]<=0:
        raise RuntimeError("区域格式：左,上,宽,高；宽高需大于零。")
    return values


def screenshot(job: Job) -> Result:
    from PIL import ImageGrab

    try:
        if job.opt("bbox"):
            x,y,w,h=parse_bbox(job.opt("bbox"))
            im=ImageGrab.grab(bbox=(x,y,x+w,y+h),all_screens=True)
        else:
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


def _soffice(job=None):
    if job and job.opt("component"):
        return str(job.file("component"))
    found=find_tool(["soffice", "libreoffice"])
    if found: return found
    if sys.platform=="win32":
        candidates=[]
        for key in ("PROGRAMFILES","PROGRAMFILES(X86)","LOCALAPPDATA"):
            base=os.environ.get(key)
            if base:
                for folder in ("LibreOffice","OpenOffice 4"):
                    candidates.append(Path(base)/folder/"program/soffice.exe")
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive,r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\soffice.exe",0,winreg.KEY_READ|view) as key:
                        candidates.append(Path(winreg.QueryValue(key,None).strip('"')))
                except OSError:
                    pass
        return next((str(p) for p in candidates if p.is_file()),None)
    return None


def office_convert(job: Job) -> Result:
    fmt = job.opt("fmt") or "pdf"
    soffice = _soffice(job)
    outputs = []
    if soffice and fmt in ("pdf", "docx", "html", "txt"):
        for path in job.files():
            run_cmd([soffice, "--headless", "--convert-to", fmt, "--outdir", str(job.outdir), str(path)])
            dest = job.outdir / (safe_stem(path) + "." + fmt)
            if dest.exists():
                outputs.append(dest)
        if outputs:
            return Result("文档转换完成。", outputs)
    if fmt == "txt":
        return office_to_text(job)
    if fmt == "docx":
        for path in job.files():
            text = office_text_from(path)
            dest = job.outdir / (safe_stem(path) + ".docx")
            _write_docx(dest, text.splitlines())
            outputs.append(dest)
        return Result("已按段落生成 DOCX。当前使用文字提取模式，不保留原始版式。", outputs)
    if fmt == "html":
        for path in job.files():
            text = office_text_from(path)
            dest = job.outdir / (safe_stem(path) + ".html")
            dest.write_text("<meta charset='utf-8'><pre>{}</pre>".format(text.replace("&", "&amp;").replace("<", "&lt;")), encoding="utf-8")
            outputs.append(dest)
        return Result("已生成 HTML 文本。", outputs)
    raise RuntimeError("未检测到可用的文档转换组件，无法转换为 PDF。请安装并配置文档转换组件后重试。")


def office_to_image(job: Job) -> Result:
    soffice = _soffice(job)
    if not soffice:
        raise RuntimeError("未检测到可用的文档转换组件，无法将文档转为图片。请安装并配置文档转换组件后重试。")
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
    from .ocr import image
    return image(job)


def ocr_pdf(job: Job) -> Result:
    from .ocr import pdf
    return pdf(job)


def ocr_screen(job: Job) -> Result:
    from .ocr import screen
    return screen(job)


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
    import ast
    import math
    import operator
    import re
    expr = job.opt("expr")
    if not expr:
        raise RuntimeError("请输入表达式。")
    source = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", expr).replace("^", "**")
    operators={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow,ast.Mod:operator.mod}
    functions={name:getattr(math,name) for name in ("sin","cos","tan","asin","acos","atan","sqrt","log","log10","exp","floor","ceil","fabs")}
    functions.update(abs=abs,round=round)
    def evaluate(node):
        if isinstance(node,ast.Expression):
            return evaluate(node.body)
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            return node.value
        if isinstance(node,ast.Name) and node.id in ("pi","e","tau"):
            return getattr(math,node.id)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            return evaluate(node.operand)*(1 if isinstance(node.op,ast.UAdd) else -1)
        if isinstance(node,ast.BinOp) and type(node.op) in operators:
            a,b=evaluate(node.left),evaluate(node.right)
            if isinstance(node.op,ast.Pow) and (abs(b)>1000 or abs(a)>1e100):
                raise RuntimeError("乘方数值过大。")
            return operators[type(node.op)](a,b)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in functions and not node.keywords:
            return functions[node.func.id](*[evaluate(arg) for arg in node.args])
        raise RuntimeError("不支持的表达式，请使用数字、运算符或科学函数。")
    if len(source)>1000:
        raise RuntimeError("表达式过长。")
    value = evaluate(ast.parse(source,mode="eval"))
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
