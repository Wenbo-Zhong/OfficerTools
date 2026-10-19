# -*- coding: utf-8 -*-
"""Tool catalog aligned with the OfficeBox suites."""
from __future__ import annotations

import sys
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
    Tool("pdf-to-word", "PDF 转 Word", "PDF", "提取 PDF 文字并按段落生成 DOCX，不保留原始版式。扫描件请先进行 OCR 识别。", (
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
    Tool("office-convert", "办公文档转换", "格式转换", "使用本机文档转换组件转换格式；未检测到组件时，可提取文字生成文档。", (
        F("files", "文档", "files"),
        F("fmt", "目标", "choice", "pdf", ("pdf", "txt", "html", "docx")),
    ), "办公文档转换"),
    Tool("office-to-image", "文档转图片", "格式转换", "先将文档转成 PDF，再导出 PNG 图片。需要本机文档转换组件。", (
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

# Shared options keep the form and command-line parameter names in one place.
_extra = {
    "ocr-pdf": (F("password","PDF 打开密码，可空","text"),F("ranges","识别页码范围，留空全部","text")),
    "ocr-screen": (F("bbox","识别区域：左,上,宽,高；留空全屏","text"),),
    "office-convert": (F("component","文档转换程序，可空以自动检测","file"),),
    "office-to-image": (F("component","文档转换程序，可空以自动检测","file"),),
    "dicom-preview": (F("window-width","窗宽，0 使用文件设置或自动范围","number","0"),F("window-center","窗位（指定窗宽时生效）","number","0")),
    "pdf-optimize": (F("preset","压缩级别","choice","ebook",("screen","ebook","printer","prepress","default")),F("dpi","图片目标分辨率","number","150")),
    "pdf-crop": (F("auto","自动检测并裁白边（忽略手动边距）","check","0"),F("padding","自动裁剪保留边距（点）","number","8")),
    "pdf-nup": (F("margin","纸张外边距（点）","number","12"),F("gap","格子间距（点）","number","6"),F("paper","输出纸张","choice","original",("original","A4","A4-landscape","A3","A3-landscape"))),
    "pdf-lock": (F("owner-password","权限管理密码，可空","text"),F("allow-print","允许打印","check","1"),F("allow-copy","允许复制文字与图片","check","1"),F("allow-modify","允许修改","check","1")),
    "pdf-pagenum": (F("size","字号（点）","number","11"),F("color","颜色","text","#000000"),F("position","页码位置","choice","bottom-center",("bottom-center","bottom-left","bottom-right","top-center","top-left","top-right")),F("ranges","页码范围，可空","text")),
    "pdf-images": (F("min-width","最小图片宽度（像素）","number","0"),F("min-height","最小图片高度（像素）","number","0"),F("fmt","输出格式","choice","original",("original","png","jpeg","tiff","bmp","webp"))),
    "pdf-to-image": (F("ranges","页码范围，可空","text"),F("fmt","输出格式","choice","png",("png","jpeg","tiff","bmp","webp"))),
    "screenshot": (F("bbox","截取区域：左,上,宽,高；留空为全屏","text"),),
    "screen-record": (F("bbox","录制区域：左,上,宽,高；留空为全屏","text"),F("audio-device","声音设备名称，可空","text","",(),"使用 FFmpeg DirectShow 音频设备名；录系统声需系统提供混音/回环设备。")),
    "gif-record": (F("bbox","录制区域：左,上,宽,高；留空为全屏","text"),),
    "audio-convert": (F("bitrate","音频码率 kbps，0 自动","number","0"),F("sample-rate","采样率 Hz，0 自动","number","0"),F("channels","声道数，0 保持","choice","0",("0","1","2")),F("start","起始秒","number","0"),F("duration","截取秒数，0 至结尾","number","0")),
    "video-convert": (F("width","输出宽度（偶数），0 保持","number","0"),F("fps","帧率，0 保持","number","0"),F("crf","画质 CRF，越小越清晰（0–51）","number","23"),F("start","起始秒","number","0"),F("duration","截取秒数，0 至结尾","number","0")),
    "pdf-deskew": (F("max-angle", "最大倾斜角度（0.2–45°）", "number", "10"),
        F("mode", "输出方式", "choice", "preserve", ("preserve", "raster"), "preserve：保留文字与矢量，页面尺寸不变；raster：重建扫描页，可配合裁白边。"),
        F("trim", "裁去扫描页白边（重建扫描页）", "check", "0"), F("margin", "裁白边后保留像素", "number", "12"),
        F("min-edge", "忽略短边小于此像素的页面", "number", "0"), F("quality", "重建扫描页 JPEG 质量", "number", "92")),
    "pdf-bw": (F("bw-mode", "转换方式", "choice", "auto", ("auto", "threshold", "dither", "gray"), "auto：自动二值化；threshold：指定阈值；dither：抖动黑白；gray：灰度。"),
        F("threshold", "黑白阈值（0–255）", "number", "160")),
    "pdf-watermark": (F("image", "图片水印，留空用文字", "file"), F("width", "图片水印宽度（点）", "number", "180"),
        F("angle", "旋转角度", "number", "0"), F("color", "文字颜色", "text", "#505050"),
        F("position", "位置", "choice", "center", ("center","top-left","top-right","bottom-left","bottom-right")),
        F("tile", "平铺水印", "check", "0"), F("parity", "页面奇偶", "choice", "all", ("all","odd","even"))),
    "img-compress": (F("fmt", "输出格式", "choice", "auto", ("auto","jpeg","png","webp")),),
    "pdf417": (F("columns", "数据列数（1–30）", "number", "6"), F("security", "纠错级别（0–8）", "number", "2")),
    "barcode": (F("barcode-format", "条码类型", "choice", "code128", ("code128","code39","ean13","ean8","upca","isbn13","itf")),),
    "slideshow": (F("interval", "自动切换间隔（秒）", "number", "4"), F("music", "背景音乐，可空", "file")),
    "rename": (F("preview", "只预览，不修改文件", "check", "1"),),
    "filetime": (F("offset", "在原时间上偏移秒数，0 表示设置时间", "number", "0"),
        F("access", "修改访问时间", "check", "1"), F("modified", "修改最后修改时间", "check", "1"), F("created", "修改创建时间（Windows）", "check", "0")),
    "unzip-batch": (F("password", "解压密码，可空", "text"),),
}
_summaries = {
    "ocr-image": "离线识别图片或多页 TIFF。优先使用已安装的语言包，缺少时自动改用 Qwen 多语言识别。",
    "ocr-pdf": "离线识别扫描 PDF，支持密码和页码范围。缺少语言包时可用 Qwen 备用识别。",
    "ocr-screen": "框选屏幕区域后离线识别。支持 Tesseract 和 Qwen 多语言备用引擎。",
    "dicom-preview": "批量转换未压缩 DICOM，支持多帧、灰度窗宽窗位、反色及 8 位 RGB。",
    "screen-record": "录制全屏或指定区域，可选择音频设备。点击取消会停止并保留已录制内容。",
    "screenshot": "截取全屏或自选区域，按真实像素保存。",
    "pdf-deskew": "批量校正 PDF / TIFF 扫描页。支持密码、页码范围和裁白边，另存输出，保留原件。",
    "pdf-bw": "批量将 PDF / TIFF 转为真正的黑白二值图、抖动黑白或灰度，保留未选中的页面。",
    "pdf-watermark": "添加文字或图片水印，支持角度、位置、透明度、平铺与奇偶页。",
    "pdf-to-word": "导出可编辑文字、字号与图片到 Word。复杂表格、分栏可能需要手动调整，扫描页不做 OCR。",
    "pdf-to-html": "导出带有文字位置、字体与内嵌图片的 HTML 页面。",
    "pdf-reader": "查看 PDF 实际页面，支持翻页、缩放、跳页和文字查找。",
    "pdf-optimize": "选择图片分辨率和压缩级别，或仅压缩 PDF 内容流。",
    "img-compress": "批量压缩 JPEG / PNG / WEBP，可保留透明通道并限制长边。",
    "rename": "预览批量重命名，支持 {n} {name} {ext} {date} {size} {folder} {mtime}。",
    "filetime": "分别设置创建、访问、修改时间，或按秒偏移原时间。",
    "calc": "四则运算、乘方、百分数及 sin、cos、sqrt、log 等科学函数（角度采用弧度）。",
}
_updated = []
for _tool in TOOLS:
    _fields = list(_tool.fields) + list(_extra.get(_tool.id, ()))
    if _tool.id.startswith("ocr-"):
        _fields=[f._replace(label="识别语言",help="默认 chi_sim+eng；也可填日语、jpn、俄语、rus 等。填 auto 自动判断语言，将直接使用 Qwen。") if f.key=="lang" else f for f in _fields]
        backends=("auto","metal","opencl","cpu") if sys.platform=="darwin" else ("auto","vulkan","cpu")
        backend_help=("auto：优先 Metal，再尝试 OpenCL，最后回退 CPU。" if sys.platform=="darwin" else "auto：优先 Vulkan，失败后改用 CPU。")+"Qwen 较慢且占用更多内存。"
        _fields += [F("engine","识别引擎","choice","auto",("auto","tesseract","qwen"),"auto：已安装的语言用 Tesseract，缺少语言包时用 Qwen；也可手动指定。"),
                    F("backend","Qwen 运行方式","choice","auto",backends,backend_help),
                    F("psm","Tesseract 页面分割方式","choice","3",("3","4","6","7","11"),"3：自动版面；4：单栏；6：整块文字；7：单行；11：零散文字。"),
                    F("output","输出格式","choice","both" if _tool.id=="ocr-pdf" else "text",("text","both","searchable","hocr","tsv"),"text：文字；both/searchable：另生成可搜索 PDF；hocr/tsv：文字位置与识别信息。")]
        if _tool.id=="ocr-pdf": _fields=[f._replace(kind="files") if f.key=="file" else f for f in _fields]
    if _tool.id in ("dicom-preview","png-to-ico"):
        _fields=[f._replace(kind="files") if f.key=="file" else f for f in _fields]
    if _tool.id == "screen-record":
        _fields=[f._replace(label="录制秒数，0 表示手动停止") if f.key=="seconds" else f for f in _fields]
    if _tool.id.startswith("pdf-") and _tool.id != "pdf-reader":
        _fields = [f._replace(kind="files", label="输入文件（可多选，按列表顺序）") if f.key == "file" else f for f in _fields]
        if not any(f.key == "password" for f in _fields):
            _fields.append(F("password", "PDF 打开密码，可空", "text"))
        if _tool.id in ("pdf-deskew","pdf-bw","pdf-watermark","pdf-to-word","pdf-to-html"):
            _fields.append(F("ranges", "页码范围，留空处理全部", "text", "", (), "例如 1-3,5；PDF/TIFF 均从第 1 页计数。"))
    _updated.append(_tool._replace(fields=tuple(_fields), summary=_summaries.get(_tool.id,_tool.summary)))
TOOLS = _updated + [
    Tool("pdf-page-master", "PDF 页面编排", "PDF", "按指定顺序重排、复制页面，并插入空白页。", (
        F("file","PDF 文件","files"), F("order","页面顺序","text","",(),"例如 3,1-2,blank,4；blank 或 0 表示空白页，留空保持原顺序。"), F("password","打开密码，可空","text")), "PDF页面编排"),
    Tool("pdf-page-cut", "PDF 单页切分", "PDF", "按行列把一张大页面切成多张小页面，保留文字和矢量。", (
        F("file","PDF 文件","files"), F("rows","行数","number","2"), F("cols","列数","number","1"), F("ranges","页码范围，可空","text"), F("password","打开密码，可空","text")), "PDF单页切分"),
    Tool("pdf-links", "PDF 添加链接", "PDF", "在指定页面区域添加可点击的网页链接。", (
        F("file","PDF 文件","files"), F("url","链接地址","text","https://"), F("rect","区域：左,上,右,下（点）","text","36,36,250,90"), F("ranges","页码范围，可空","text"), F("password","打开密码，可空","text")), "PDF添加链接"),
]

BY_ID: Dict[str, Tool] = {t.id: t for t in TOOLS}
BY_EXE: Dict[str, Tool] = {t.exe: t for t in TOOLS}
CATEGORIES: List[str] = []
for _t in TOOLS:
    if _t.category not in CATEGORIES:
        CATEGORIES.append(_t.category)
