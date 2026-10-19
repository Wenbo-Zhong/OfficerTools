"""Offline Tesseract OCR with explicit model discovery and isolated work files."""
import re
import tempfile
import contextlib
from pathlib import Path
from PIL import Image, ImageOps, ImageSequence
from pypdf import PdfReader, PdfWriter

from .common import Job, Result, find_tool, run_cmd, safe_stem
from .pdf_extended import open_pdf, page_image
from .pdf import parse_ranges, _write


class MissingLanguage(RuntimeError):
    pass


LANGUAGES={"中文":"chi_sim","简体中文":"chi_sim","zh":"chi_sim","zh-cn":"chi_sim","繁体中文":"chi_tra","zh-tw":"chi_tra",
    "英文":"eng","英语":"eng","en":"eng","日语":"jpn","ja":"jpn","韩语":"kor","ko":"kor","法语":"fra","fr":"fra",
    "德语":"deu","de":"deu","俄语":"rus","ru":"rus","西班牙语":"spa","es":"spa","阿拉伯语":"ara","ar":"ara",
    "泰语":"tha","th":"tha","越南语":"vie","vi":"vie","印地语":"hin","hi":"hin","自动识别":"auto"}


def language(job):
    return "+".join(LANGUAGES.get(item.strip().lower(),item.strip().lower()) for item in job.opt("lang","chi_sim+eng").split("+"))


def select_engine(job):
    requested=job.opt("engine","auto")
    requested={"自动选择":"auto","Qwen3.5-2B":"qwen","Tesseract":"tesseract"}.get(requested,requested)
    if requested not in ("auto","tesseract","qwen"): raise RuntimeError("请选择有效的 OCR 引擎。")
    if requested!="qwen":
        try:
            engine(job)
            return "tesseract"
        except MissingLanguage:
            if requested=="tesseract": raise
    from .vlm import model_files
    model_files()
    job.checkpoint(0,"使用 Qwen3.5-2B 多语言识别（"+language(job)+"）")
    return "qwen"


def engine(job):
    executable=find_tool(["tesseract"])
    if not executable: raise MissingLanguage("未找到 Tesseract OCR 引擎。")
    lang=language(job)
    if lang=="auto": raise MissingLanguage("自动判断语言需要使用 Qwen 引擎。")
    if not re.fullmatch(r"[A-Za-z0-9_-]+(?:\+[A-Za-z0-9_-]+)*",lang):
        raise RuntimeError("语言格式应为 chi_sim+eng、chi_sim 或 eng。")
    data=Path(executable).parent.parent/"tessdata"
    if not data.is_dir(): data=Path(executable).parent/"tessdata"
    args=[]
    if data.is_dir():
        missing=[item for item in lang.split("+") if not (data/(item+".traineddata")).is_file()]
        if missing: raise MissingLanguage("缺少 OCR 语言模型："+", ".join(missing)+"。可选择自动引擎，使用 Qwen 备用识别。")
        args=["--tessdata-dir",str(data)]
    else:
        installed=run_cmd([executable,"--list-langs"]).splitlines()
        if any(item not in [line.strip() for line in installed] for item in lang.split("+")):
            raise MissingLanguage("本机 Tesseract 未安装所选语言模型。")
    psm=job.opt("psm","3")
    if psm not in ("3","4","6","7","11","12","13"):
        raise RuntimeError("不支持的页面分割方式。")
    return executable,args+["-l",lang,"--oem","1","--psm",psm]


def qwen_pdf(path,dest,dpi,text):
    """Search/copy layer; VLM transcription does not expose glyph coordinates."""
    import fitz
    from html import escape
    with Image.open(path) as image:
        w,h=image.size
    document=fitz.open()
    try:
        page=document.new_page(width=w*72/dpi,height=h*72/dpi)
        page.insert_image(page.rect,filename=str(path))
        if text.strip():
            rectangle=fitz.Rect(4,4,max(5,page.rect.width-4),max(5,page.rect.height-4))
            html='<div style="font-family:sans-serif;font-size:10pt">'+escape(text).replace("\n","<br>")+"</div>"
            page.insert_htmlbox(rectangle,html,opacity=0)
        document.save(str(dest),garbage=4,deflate=True)
    finally: document.close()


def recognize(job, inputs, workspace, pdf_mode=False, selected=None):
    selected=selected or select_engine(job)
    executable,options=engine(job) if selected=="tesseract" else (None,None)
    output=job.opt("output","both" if pdf_mode else "text")
    if output not in ("text","searchable","both","hocr","tsv"):
        raise RuntimeError("不支持的 OCR 输出格式。")
    if selected=="qwen" and output in ("hocr","tsv"):
        raise RuntimeError("Qwen 不提供可靠的逐字坐标，暂不导出 hOCR/TSV；请选择 text 或 both。")
    configs=["txt"]
    if output in ("searchable","both"): configs.append("pdf")
    if output in ("hocr","tsv"): configs.append(output)
    parts=[];outputs=[];writer=PdfWriter()
    with contextlib.ExitStack() as stack:
        if selected=="qwen":
            from .vlm import Recognizer
            recognizer=stack.enter_context(Recognizer(job))
        for n,(path,label) in enumerate(inputs):
            job.checkpoint(n*100/len(inputs),"识别 {} / {}：{}".format(n+1,len(inputs),label))
            base=workspace/("result-{:04d}".format(n+1))
            if selected=="tesseract":
                args=[executable,str(path),str(base)]+options+["--dpi",str(int(job.number("dpi",300)))]+configs
                run_cmd(args)
                text=base.with_suffix(".txt").read_text("utf-8")
            else:
                text=recognizer.transcribe(path,language(job))
                if output in ("searchable","both"):
                    qwen_pdf(path,base.with_suffix(".pdf"),int(job.number("dpi",300)),text)
            parts.append("===== {} =====\n{}".format(label,text))
            if output in ("searchable","both"):
                reader=PdfReader(str(base.with_suffix(".pdf")))
                writer.append(reader)
            if output in ("hocr","tsv"):
                dest=job.outdir/("{:03d}_{}".format(n+1,safe_stem(Path(label)))+"."+output)
                dest.write_bytes(base.with_suffix("."+output).read_bytes())
                outputs.append(dest)
    text="\n\n".join(parts)
    dest=job.outdir/"ocr.txt";dest.write_text(text,encoding="utf-8");outputs.insert(0,dest)
    if output in ("searchable","both"):
        dest=job.outdir/((safe_stem(job.file()) if pdf_mode else "ocr")+"_searchable.pdf")
        _write(writer,dest);outputs.append(dest)
    job.checkpoint(100,"识别完成")
    message="已使用 {} 离线识别 {} 页/张。".format("Qwen3.5-2B" if selected=="qwen" else "Tesseract",len(inputs))
    if output in ("searchable","both"):
        message+="已生成带文字层的 PDF（识别结果可能有误，请校对）。"
        if selected=="qwen": message+="Qwen 文字层位置为估计，仅用于检索与复制，不提供精确字框。"
    return Result(message+"\n\n"+text[:8000],outputs)


def image(job):
    selected=select_engine(job)
    with tempfile.TemporaryDirectory(prefix="ocr-",dir=str(job.outdir)) as temp:
        workspace=Path(temp);inputs=[]
        for source in job.files():
            with Image.open(source) as original:
                for n,frame in enumerate(ImageSequence.Iterator(original)):
                    job.checkpoint()
                    prepared=ImageOps.exif_transpose(frame).convert("RGBA")
                    white=Image.new("RGBA",prepared.size,"white")
                    white.alpha_composite(prepared)
                    path=workspace/("input-{:04d}.png".format(len(inputs)+1))
                    white.convert("RGB").save(path,dpi=(300,300))
                    inputs.append((path,source.name+(" / 第 {} 页".format(n+1) if getattr(original,"n_frames",1)>1 else "")))
        if not inputs: raise RuntimeError("请选择要识别的图片。")
        return recognize(job,inputs,workspace,selected=selected)


def pdf(job):
    selected=select_engine(job)
    dpi=int(job.number("dpi",300))
    if not 72<=dpi<=600: raise RuntimeError("OCR 分辨率应为 72–600 DPI。")
    with tempfile.TemporaryDirectory(prefix="ocr-",dir=str(job.outdir)) as temp:
        workspace=Path(temp);inputs=[]
        with open_pdf(job) as doc:
            indexes=parse_ranges(job.opt("ranges"),len(doc))
            for k,n in enumerate(indexes):
                job.checkpoint(k*30/len(indexes),"准备第 {} 页".format(n+1))
                path=workspace/("page-{:04d}.png".format(n+1))
                page_image(doc[n],dpi).save(path,dpi=(dpi,dpi))
                inputs.append((path,"第 {} 页".format(n+1)))
        if not inputs: raise RuntimeError("PDF 没有可识别页面。")
        return recognize(job,inputs,workspace,pdf_mode=True,selected=selected)


def screen(job):
    from .external import screenshot
    select_engine(job)
    shot=screenshot(job)
    job.checkpoint(0,"屏幕截图已完成")
    child=Job(job.tool,dict(job.opts,files=str(shot.files[0])),job.outdir,progress=job.progress,cancel=job.cancel)
    return image(child)
