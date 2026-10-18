# -*- coding: utf-8 -*-
"""Tool catalog aligned with the OfficeBox suites."""
from __future__ import annotations

from typing import Dict, List, NamedTuple


class Field(NamedTuple):
    key: str
    label: str
    kind: str  # files, file, dir, text, number, choice, check, multiline
    default: str = ""
    options: tuple = ()
    help: str = ""


class Tool(NamedTuple):
    id: str
    name: str
    category: str
    summary: str
    fields: tuple
    exe: str


def F(key, label, kind, default="", options=(), help=""):
    return Field(key, label, kind, default, tuple(options), help)


TOOLS: List[Tool] = [
    Tool("pdf-merge", "PDF 合并", "PDF", "按顺序把多个 PDF 合成一个。", (F("files", "PDF 文件", "files"),), "PDF合并"),
    Tool("pdf-split", "PDF 分割", "PDF", "按固定页数切开，或按区间导出。", (
        F("file", "PDF 文件", "file"),
        F("span", "每份页数（和区间二选一）", "number", "1"),
        F("ranges", "页码区间", "text", "", (), "例如 1-3,5,8-10"),
    ), "PDF分割"),
    Tool("pdf-extract", "PDF 提取页面", "PDF", "把选中的页另存为一个 PDF。", (
        F("file", "PDF 文件", "file"),
        F("ranges", "页码", "text", "1", (), "例如 1-3,5"),
    ), "PDF提取页面"),
    Tool("pdf-delete", "PDF 删除页面", "PDF", "删掉指定页后保存。", (
        F("file", "PDF 文件", "file"),
        F("ranges", "要删除的页", "text", "", (), "例如 2,4-6"),
    ), "PDF删除页面"),
    Tool("pdf-rotate", "PDF 旋转", "PDF", "顺时针旋转选中页面。", (
        F("file", "PDF 文件", "file"),
        F("angle", "角度", "choice", "90", ("90", "180", "270")),
        F("ranges", "页码，空表示全部", "text"),
    ), "PDF旋转"),
    Tool("pdf-crop", "PDF 页面裁剪", "PDF", "按边距缩小页面可见区域，单位是点（1 点 = 1/72 英寸）。", (
        F("file", "PDF 文件", "file"),
        F("top", "上", "number", "36"),
        F("right", "右", "number", "36"),
        F("bottom", "下", "number", "36"),
        F("left", "左", "number", "36"),
        F("ranges", "页码，空表示全部", "text"),
    ), "PDF页面裁剪"),
    Tool("pdf-nup", "PDF 多页合一", "PDF", "把多页缩排到一张纸上。", (
        F("file", "PDF 文件", "file"),
        F("cols", "列", "number", "2"),
        F("rows", "行", "number", "2"),
    ), "PDF多页合一"),
    Tool("pdf-pagenum", "PDF 加页码", "PDF", "在页面底部写上页码。", (
        F("file", "PDF 文件", "file"),
        F("start", "起始编号", "number", "1"),
        F("fmt", "格式", "text", "{n} / {total}"),
    ), "PDF加页码"),
    Tool("pdf-watermark", "PDF 加水印", "PDF", "给页面加上文字水印。", (
        F("file", "PDF 文件", "file"),
        F("text", "水印文字", "text", "内部资料"),
        F("size", "字号（点）", "number", "48"),
        F("opacity", "不透明度 0-1", "text", "0.18"),
    ), "PDF加水印"),
    Tool("pdf-unlock", "PDF 解密", "PDF", "用打开密码生成一份未加密的 PDF。", (
        F("file", "PDF 文件", "file"),
        F("password", "打开密码", "text"),
    ), "PDF解密"),
    Tool("pdf-lock", "PDF 加密", "PDF", "设置打开密码。", (
        F("file", "PDF 文件", "file"),
        F("password", "打开密码", "text"),
    ), "PDF加密"),
    Tool("pdf-optimize", "PDF 压缩", "PDF", "压缩内容流。扫描件体积要明显变小，需要本机装有 Ghostscript。", (
        F("file", "PDF 文件", "file"),
        F("gs", "尝试 Ghostscript", "check", "1"),
    ), "PDF压缩"),
    Tool("pdf-bw", "PDF 转黑白", "PDF", "把页面渲染成灰度后再组成 PDF。需要 Ghostscript 或 pdftoppm。", (
        F("file", "PDF 文件", "file"),
        F("dpi", "渲染分辨率", "choice", "200", ("150", "200", "300", "400")),
    ), "PDF转黑白"),
    Tool("pdf-deskew", "PDF 纠偏", "PDF", "检测页面倾斜并转正。需要 Ghostscript 或 pdftoppm。", (
        F("file", "PDF 文件", "file"),
        F("dpi", "渲染分辨率", "choice", "200", ("150", "200", "300")),
    ), "PDF纠偏"),
    Tool("pdf-images", "PDF 提取图片", "PDF", "导出内嵌图片，保留原始像素。", (F("file", "PDF 文件", "file"),), "PDF提取图片"),
    Tool("pdf-to-image", "PDF 转图片", "PDF", "按真实 DPI 把每一页导出为 PNG。需要 Ghostscript 或 pdftoppm。", (
        F("file", "PDF 文件", "file"),
        F("dpi", "分辨率", "choice", "200", ("72", "150", "200", "300", "400", "600")),
    ), "PDF转图片"),
    Tool("pdf-to-text", "PDF 转文本", "PDF", "提取可选中文字。扫描件请用 OCR。", (F("file", "PDF 文件", "file"),), "PDF转文本"),
    Tool("pdf-to-html", "PDF 转 HTML", "PDF", "把文本按页写成 HTML。", (F("file", "PDF 文件", "file"),), "PDF转HTML"),
    Tool("pdf-to-word", "PDF 转 Word", "PDF", "生成可编辑的 DOCX（按文本段落）。复杂版式请另外安装 LibreOffice 后再用办公转换。", (
        F("file", "PDF 文件", "file"),
    ), "PDF转Word"),
    Tool("pdf-info", "PDF 信息", "PDF", "查看页数、页面尺寸和元数据。", (F("file", "PDF 文件", "file"),), "PDF信息"),
    Tool("pdf-rename", "PDF 批量重命名", "PDF", "用标题或页数给 PDF 重新命名。", (
        F("files", "PDF 文件", "files"),
        F("pattern", "名称模板", "text", "{title}", (), "{title} {pages} {name} {n}"),
    ), "PDF重命名"),
    Tool("img-to-pdf", "图片转 PDF", "PDF", "按图片原始像素嵌入，默认 300 DPI，避免发糊。", (
        F("files", "图片", "files"),
        F("dpi", "PDF 分辨率标记", "choice", "300", ("150", "200", "300", "600")),
    ), "图片转PDF"),
    Tool("tiff-merge", "TIFF 合并分割", "PDF", "多页 TIFF 合并，或按页拆开。", (
        F("files", "TIFF 文件", "files"),
        F("mode", "操作", "choice", "merge", ("merge", "split")),
    ), "TIFF合并分割"),
    Tool("chm-to-pdf", "CHM 转 PDF", "格式转换", "调用本机 hh.exe 或 7-Zip 解出 HTML，再汇成一个 PDF 文本。", (
        F("file", "CHM 文件", "file"),
    ), "CHM转PDF"),
    Tool("img-convert", "图片格式转换", "图片", "批量转换为 PNG、JPEG、WEBP、BMP、TIFF 或 GIF。", (
        F("files", "图片", "files"),
        F("fmt", "目标格式", "choice", "png", ("png", "jpeg", "webp", "bmp", "tiff", "gif")),
        F("quality", "JPEG/WEBP 质量", "number", "92"),
    ), "图片格式转换"),
    Tool("img-resize", "图片改尺寸", "图片", "按像素或百分比缩放，使用高质量重采样。", (
        F("files", "图片", "files"),
        F("mode", "方式", "choice", "pixel", ("pixel", "percent", "width", "height")),
        F("width", "宽", "number", "1920"),
        F("height", "高", "number", "1080"),
        F("percent", "百分比", "number", "50"),
    ), "图片改尺寸"),
    Tool("img-compress", "图片压缩", "图片", "缩小 JPEG/WEBP 体积，可选限制长边。", (
        F("files", "图片", "files"),
        F("quality", "质量", "number", "80"),
        F("max-edge", "长边上限，0 表示不限制", "number", "0"),
    ), "图片压缩"),
    Tool("img-crop", "图片裁剪", "图片", "按像素边距或中心尺寸裁剪。", (
        F("files", "图片", "files"),
        F("mode", "方式", "choice", "margin", ("margin", "center")),
        F("top", "上 / 中心高", "number", "0"),
        F("right", "右 / 中心宽", "number", "0"),
        F("bottom", "下", "number", "0"),
        F("left", "左", "number", "0"),
    ), "图片裁剪"),
    Tool("img-watermark", "图片水印", "图片", "平铺或居中文字水印。", (
        F("files", "图片", "files"),
        F("text", "文字", "text", "草稿"),
        F("opacity", "不透明度 0-255", "number", "80"),
    ), "图片水印"),
    Tool("img-splice", "图片拼接", "图片", "横向或纵向拼成一张图，不缩放原图像素。", (
        F("files", "图片（按顺序）", "files"),
        F("direction", "方向", "choice", "vertical", ("vertical", "horizontal")),
        F("gap", "间距像素", "number", "0"),
    ), "图片拼接"),
    Tool("img-stamp", "图片时间戳", "图片", "把日期时间画到图片上。", (
        F("files", "图片", "files"),
        F("text", "文字，空则用当前时间", "text"),
        F("corner", "位置", "choice", "bottom-right", ("bottom-right", "bottom-left", "top-right", "top-left")),
    ), "图片时间戳"),
    Tool("img-exif", "图片 EXIF", "图片", "查看或清除拍摄信息。", (
        F("files", "图片", "files"),
        F("action", "操作", "choice", "view", ("view", "strip")),
    ), "图片EXIF"),
    Tool("img-effect", "图片效果", "图片", "亮度、对比度、锐化和灰度。", (
        F("files", "图片", "files"),
        F("brightness", "亮度 1 为原图", "text", "1"),
        F("contrast", "对比度 1 为原图", "text", "1"),
        F("sharpness", "锐度 1 为原图", "text", "1"),
        F("gray", "转为灰度", "check", "0"),
    ), "图片效果"),
    Tool("png-to-ico", "PNG 转图标", "图片", "生成含 16 到 256 像素的 ICO，大屏上图标保持清晰。", (
        F("file", "PNG 文件", "file"),
    ), "PNG转图标"),
    Tool("slideshow", "图片幻灯片", "图片", "生成可离线打开的 HTML 幻灯片，图片以原始分辨率嵌入显示。", (
        F("files", "图片", "files"),
        F("title", "标题", "text", "幻灯片"),
    ), "图片幻灯片"),
    Tool("qrcode", "二维码", "图片", "生成高分辨率 PNG 二维码。", (
        F("text", "内容", "multiline", "https://"),
        F("box", "单块像素", "number", "12"),
    ), "二维码"),
    Tool("barcode", "一维码", "图片", "生成 Code128 条码。", (
        F("text", "内容", "text", "1234567890"),
        F("module", "模块宽度", "number", "2"),
    ), "一维码"),
    Tool("pdf417", "PDF417 码", "图片", "生成 PDF417 二维条码。", (
        F("text", "内容", "multiline", "HELLO"),
    ), "PDF417"),
    Tool("pick-color", "屏幕拾色", "图片", "在图片上点选，读取原始像素颜色。", (F("file", "图片", "file"),), "拾色器"),
    Tool("dicom-preview", "DICOM 转图片", "格式转换", "读取未压缩的灰度 DICOM，导出 16 位窗位调整后的 PNG。", (
        F("file", "DICOM 文件", "file"),
    ), "DICOM转图片"),
    Tool("ocr-image", "图片 OCR", "识别", "调用本机 Tesseract 识别图片文字。", (
        F("files", "图片", "files"),
        F("lang", "语言", "text", "chi_sim+eng"),
    ), "图片OCR"),
    Tool("ocr-pdf", "PDF OCR", "识别", "先把页面渲染成图再识别。需要 Tesseract，以及 Ghostscript 或 pdftoppm。", (
        F("file", "PDF 文件", "file"),
        F("lang", "语言", "text", "chi_sim+eng"),
        F("dpi", "分辨率", "choice", "300", ("200", "300", "400")),
    ), "PDFOCR"),
    Tool("ocr-screen", "屏幕 OCR", "识别", "截取全屏后识别文字。需要 Tesseract。", (
        F("lang", "语言", "text", "chi_sim+eng"),
    ), "屏幕OCR"),
    Tool("screenshot", "截屏", "录屏截屏", "按显示器真实像素截取全屏。", (), "截屏"),
    Tool("screen-record", "屏幕录像", "录屏截屏", "用 FFmpeg 录制屏幕和系统声音（若设备可用）。", (
        F("seconds", "秒数，0 表示直到你关闭 FFmpeg 窗口", "number", "15"),
        F("fps", "帧率", "number", "30"),
    ), "屏幕录像"),
    Tool("gif-record", "GIF 录制", "录屏截屏", "用 FFmpeg 把屏幕录成 GIF。", (
        F("seconds", "秒数", "number", "5"),
        F("fps", "帧率", "number", "12"),
    ), "GIF录制"),
    Tool("voice-record", "录音", "录屏截屏", "用 FFmpeg 录制麦克风。", (
        F("seconds", "秒数", "number", "10"),
    ), "录音"),
    Tool("annotate", "截图标注", "录屏截屏", "在截图上画线、矩形和文字，按原始像素保存。", (), "截图标注"),
    Tool("magnifier", "放大镜", "录屏截屏", "放大屏幕上的一块区域，按真实像素取样。", (
        F("factor", "倍数", "choice", "2", ("2", "3", "4")),
    ), "放大镜"),
    Tool("audio-convert", "音频转换", "格式转换", "用 FFmpeg 批量转换音频。", (
        F("files", "音频文件", "files"),
        F("fmt", "格式", "choice", "mp3", ("mp3", "wav", "flac", "aac", "ogg", "m4a")),
    ), "音频转换"),
    Tool("video-convert", "视频转换", "格式转换", "用 FFmpeg 批量转换视频。", (
        F("files", "视频文件", "files"),
        F("fmt", "格式", "choice", "mp4", ("mp4", "mkv", "webm", "mov", "avi")),
    ), "视频转换"),
    Tool("office-convert", "办公文档转换", "格式转换", "有 LibreOffice 时做版式转换；否则把 DOCX/XLSX/PPTX 抽成文本。", (
        F("files", "文档", "files"),
        F("fmt", "目标", "choice", "pdf", ("pdf", "txt", "html", "docx")),
    ), "办公文档转换"),
    Tool("office-to-image", "文档转图片", "格式转换", "用 LibreOffice 转成 PDF 后再导出 PNG。", (
        F("files", "文档", "files"),
        F("dpi", "分辨率", "choice", "150", ("72", "150", "200", "300")),
    ), "文档转图片"),
    Tool("office-to-text", "文档转文本", "格式转换", "从 DOCX、XLSX、PPTX、HTML、TXT 提取文字。", (
        F("files", "文档", "files"),
    ), "文档转文本"),
    Tool("speech", "文字转语音", "格式转换", "Windows 使用系统语音，macOS 使用 say，Linux 使用 espeak。", (
        F("text", "文字", "multiline", "你好"),
        F("rate", "语速", "number", "0"),
    ), "文字转语音"),
    Tool("dup-files", "重复文件", "文件", "按内容哈希查找完全相同的文件。", (
        F("dir", "文件夹", "dir"),
    ), "重复文件"),
    Tool("dup-photos", "重复图片", "文件", "用感知哈希找出看起来相同的图片。", (
        F("dir", "文件夹", "dir"),
        F("threshold", "距离阈值，越小越严格", "number", "6"),
    ), "重复图片"),
    Tool("dup-audio", "重复音频", "文件", "按文件内容查找重复音频。", (
        F("dir", "文件夹", "dir"),
    ), "重复音频"),
    Tool("rename", "批量重命名", "文件", "支持 {n} {name} {ext} {date}。", (
        F("files", "文件", "files"),
        F("pattern", "新名称", "text", "{n}_{name}{ext}"),
    ), "批量重命名"),
    Tool("filetime", "修改文件时间", "文件", "设置访问时间和修改时间。", (
        F("files", "文件", "files"),
        F("when", "时间", "text", "", (), "YYYY-MM-DD HH:MM:SS，空表示现在"),
    ), "修改文件时间"),
    Tool("zip-batch", "批量压缩", "文件", "每个文件单独打包，或打成一个压缩包。", (
        F("files", "文件", "files"),
        F("mode", "方式", "choice", "one", ("one", "each")),
    ), "批量压缩"),
    Tool("unzip-batch", "批量解压", "文件", "把 ZIP 解到同名文件夹。", (F("files", "ZIP 文件", "files"),), "批量解压"),
    Tool("mkdir-batch", "批量建文件夹", "文件", "一行一个文件夹名。", (
        F("dir", "放在这个目录下", "dir"),
        F("names", "名称列表", "multiline", "文件夹1\n文件夹2"),
    ), "批量建文件夹"),
    Tool("autocopy", "文件复制", "文件", "把文件复制到目标文件夹，同名时可选覆盖。", (
        F("files", "文件", "files"),
        F("dir", "目标文件夹", "dir"),
        F("overwrite", "覆盖同名", "check", "0"),
    ), "文件复制"),
    Tool("checksum", "文件校验", "文件", "计算 MD5 和 SHA256。", (F("files", "文件", "files"),), "文件校验"),
    Tool("textdiff", "文本比较", "文件", "按行比较两段文字或两个文本文件。", (
        F("file-a", "文件 A，可空", "file"),
        F("file-b", "文件 B，可空", "file"),
        F("text-a", "文本 A", "multiline"),
        F("text-b", "文本 B", "multiline"),
    ), "文本比较"),
    Tool("calc", "计算器", "系统", "四则运算、乘方和百分数。表达式在本地计算。", (
        F("expr", "表达式", "text", "1+2*3"),
    ), "计算器"),
    Tool("shutdown", "定时关机", "系统", "到时间后关机、重启或休眠。", (
        F("minutes", "延迟分钟", "number", "30"),
        F("action", "动作", "choice", "shutdown", ("shutdown", "restart", "sleep", "cancel")),
        F("confirm", "我确认执行", "check", "0"),
    ), "定时关机"),
    Tool("disk-bench", "磁盘测速", "系统", "对所选文件夹做顺序写入和读取。", (
        F("dir", "测试目录", "dir"),
        F("mb", "测试大小 MB", "number", "256"),
    ), "磁盘测速"),
    Tool("pdf-reader", "PDF 阅读", "阅读", "分页显示提取出的文字，并可以用系统程序打开原文件。", (
        F("file", "PDF 文件", "file"),
    ), "PDF阅读"),
    Tool("image-viewer", "图片查看", "阅读", "按原始像素查看图片，可放大到 100% 以上。", (
        F("file", "图片", "file"),
    ), "图片查看"),
]

BY_ID: Dict[str, Tool] = {t.id: t for t in TOOLS}
BY_EXE: Dict[str, Tool] = {t.exe: t for t in TOOLS}
CATEGORIES: List[str] = []
for _t in TOOLS:
    if _t.category not in CATEGORIES:
        CATEGORIES.append(_t.category)
