# -*- coding: utf-8 -*-
from __future__ import annotations

from officertools.engine import external, files, images, pdf
from officertools.engine.common import Job, Result

HANDLERS = {
    "pdf-merge": pdf.merge,
    "pdf-split": pdf.split,
    "pdf-extract": pdf.extract,
    "pdf-delete": pdf.delete,
    "pdf-rotate": pdf.rotate,
    "pdf-crop": pdf.crop,
    "pdf-nup": pdf.nup,
    "pdf-pagenum": pdf.pagenum,
    "pdf-watermark": pdf.watermark,
    "pdf-unlock": pdf.unlock,
    "pdf-lock": pdf.lock,
    "pdf-optimize": pdf.optimize,
    "pdf-bw": pdf.to_bw,
    "pdf-deskew": pdf.deskew,
    "pdf-images": pdf.images_out,
    "pdf-to-image": pdf.to_images,
    "pdf-to-text": pdf.to_text,
    "pdf-to-html": pdf.to_html,
    "pdf-to-word": pdf.to_docx,
    "pdf-info": pdf.info,
    "pdf-rename": pdf.rename,
    "img-to-pdf": images.images_to_pdf,
    "tiff-merge": images.tiff_tool,
    "chm-to-pdf": external.chm_to_pdf,
    "img-convert": images.convert,
    "img-resize": images.resize,
    "img-compress": images.compress,
    "img-crop": images.crop,
    "img-watermark": images.watermark,
    "img-splice": images.splice,
    "img-stamp": images.stamp,
    "img-exif": images.exif,
    "img-effect": images.effect,
    "png-to-ico": images.png_to_ico,
    "slideshow": images.slideshow,
    "qrcode": images.qrcode_tool,
    "barcode": images.barcode_tool,
    "pdf417": images.pdf417_tool,
    "dicom-preview": images.dicom_preview,
    "ocr-image": external.ocr_image,
    "ocr-pdf": external.ocr_pdf,
    "ocr-screen": external.ocr_screen,
    "screenshot": external.screenshot,
    "screen-record": external.screen_record,
    "gif-record": external.gif_record,
    "voice-record": external.voice_record,
    "audio-convert": external.audio_convert,
    "video-convert": external.video_convert,
    "office-convert": external.office_convert,
    "office-to-image": external.office_to_image,
    "office-to-text": external.office_to_text,
    "speech": external.speech,
    "dup-files": files.dup_files,
    "dup-photos": files.dup_photos,
    "dup-audio": files.dup_audio,
    "rename": files.rename,
    "filetime": files.filetime,
    "zip-batch": files.zip_batch,
    "unzip-batch": files.unzip_batch,
    "mkdir-batch": files.mkdir_batch,
    "autocopy": files.autocopy,
    "checksum": files.checksum,
    "textdiff": files.textdiff,
    "calc": external.calc,
    "shutdown": external.shutdown,
    "disk-bench": files.disk_bench,
    "pdf-reader": pdf.pdf_reader,
}

UI_ONLY = {"pick-color", "annotate", "magnifier", "image-viewer"}


def run(job: Job) -> Result:
    if job.tool in UI_ONLY:
        raise RuntimeError("这个工具在窗口里操作。")
    handler = HANDLERS.get(job.tool)
    if handler is None:
        raise RuntimeError("没有这个工具：" + job.tool)
    return handler(job)
