# -*- coding: utf-8 -*-
from __future__ import annotations

from officertools.engine import external, files, images, pdf, pdf_extended, dicom, ocr
from officertools.engine.common import Job, Result, Cancelled, _current

HANDLERS = {
    "pdf-merge": pdf.merge,
    "pdf-split": pdf.split,
    "pdf-extract": pdf.extract,
    "pdf-delete": pdf.delete,
    "pdf-rotate": pdf.rotate,
    "pdf-crop": pdf.crop,
    "pdf-nup": pdf.nup,
    "pdf-pagenum": pdf.pagenum,
    "pdf-watermark": pdf_extended.watermark,
    "pdf-unlock": pdf.unlock,
    "pdf-lock": pdf.lock,
    "pdf-optimize": pdf.optimize,
    "pdf-bw": pdf_extended.scan_process,
    "pdf-deskew": pdf_extended.scan_process,
    "pdf-page-master": pdf_extended.page_master,
    "pdf-page-cut": pdf_extended.page_cut,
    "pdf-links": pdf_extended.add_links,
    "pdf-images": pdf.images_out,
    "pdf-to-image": pdf.to_images,
    "pdf-to-text": pdf.to_text,
    "pdf-to-html": pdf_extended.to_html,
    "pdf-to-word": pdf_extended.to_docx,
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
    "dicom-preview": dicom.convert,
    "ocr-image": ocr.image,
    "ocr-pdf": ocr.pdf,
    "ocr-screen": ocr.screen,
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

UI_ONLY = {"pick-color", "annotate", "magnifier", "image-viewer", "pdf-reader"}


def run(job: Job) -> Result:
    if job.tool in UI_ONLY:
        raise RuntimeError("这个工具在窗口里操作。")
    handler = HANDLERS.get(job.tool)
    if handler is None:
        raise RuntimeError("没有这个工具：" + job.tool)
    previous = getattr(_current, "job", None)
    _current.job = job
    try:
        job.checkpoint(0, "准备处理")
        # Single-document operations can now accept a queue without changing CLI keys.
        inputs = job.files("file") if job.opt("file") else []
        if len(inputs) > 1 and (job.tool.startswith("pdf-") or job.tool in ("dicom-preview","png-to-ico","ocr-pdf")):
            outputs, messages = [], []
            for n, path in enumerate(inputs):
                job.checkpoint(n * 100 / len(inputs), path.name)
                opts = dict(job.opts, file=str(path))
                child = Job(job.tool, opts, job.outdir / ("{:03d}_".format(n + 1) + path.stem), cancel=job.cancel)
                _current.job = child
                try:
                    result = handler(child)
                    outputs.extend(result.files)
                    messages.append(path.name + "：" + result.message)
                except Cancelled:
                    raise
                except Exception as exc:
                    messages.append(path.name + "：失败，" + str(exc))
            return Result("\n".join(messages), outputs)
        return handler(job)
    finally:
        _current.job = previous
