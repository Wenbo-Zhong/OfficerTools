"""Uncompressed DICOM rendering, without loading NumPy or an OCR engine."""
import struct
from PIL import Image, ImageOps
import pydicom
from .common import Result, safe_stem


def convert(job):
    ds=pydicom.dcmread(str(job.file()))
    if ds.file_meta.TransferSyntaxUID.is_compressed:
        raise RuntimeError("此 DICOM 使用压缩像素，当前支持未压缩灰度和 RGB；请先导出未压缩影像。")
    rows,cols=int(ds.Rows),int(ds.Columns)
    bits=int(ds.BitsAllocated)
    samples=int(ds.SamplesPerPixel)
    count=int(getattr(ds,"NumberOfFrames",1))
    if bits not in (8,16) or samples not in (1,3):
        raise RuntimeError("支持 8/16 位灰度及 8 位 RGB DICOM。")
    raw=ds.PixelData
    size=rows*cols*samples*bits//8
    if len(raw)<size*count:
        raise RuntimeError("DICOM 像素数据不完整。")
    outputs=[]
    for n in range(count):
        job.checkpoint(n*100/count,"第 {} / {} 帧".format(n+1,count))
        data=raw[n*size:(n+1)*size]
        if samples==3:
            if bits!=8: raise RuntimeError("彩色影像目前支持 8 位通道。")
            if int(getattr(ds,"PlanarConfiguration",0))==1:
                plane=rows*cols
                image=Image.merge("RGB",[Image.frombytes("L",(cols,rows),data[i*plane:(i+1)*plane]) for i in range(3)])
            else:
                mode="YCbCr" if str(ds.PhotometricInterpretation)=="YBR_FULL" else "RGB"
                if str(ds.PhotometricInterpretation) not in ("RGB","YBR_FULL"):
                    raise RuntimeError("暂不支持此彩色像素排列："+str(ds.PhotometricInterpretation))
                image=Image.frombytes(mode,(cols,rows),data).convert("RGB")
        else:
            signed=bool(ds.PixelRepresentation)
            stored=int(ds.BitsStored)
            mask=(1<<stored)-1
            sign=1<<(stored-1)
            fmt=("<" if ds.is_little_endian else ">")+("B" if bits==8 else "H")
            slope=float(getattr(ds,"RescaleSlope",1))
            intercept=float(getattr(ds,"RescaleIntercept",0))
            values=[]
            for value, in struct.iter_unpack(fmt,data):
                value &= mask
                if signed and value & sign: value-=1<<stored
                values.append(value*slope+intercept)
            def first(value):
                return float(value[0] if isinstance(value,(list,tuple,pydicom.multival.MultiValue)) else value)
            width=job.number("window-width",0) or first(getattr(ds,"WindowWidth",0))
            center=job.number("window-center",0) if job.number("window-width",0) else first(getattr(ds,"WindowCenter",0))
            if width>1:
                lo=center-.5-(width-1)/2
                span=width-1
            else:
                lo=min(values);span=max(1,max(values)-lo)
            pixels=bytes(max(0,min(255,round((value-lo)*255/span))) for value in values)
            image=Image.frombytes("L",(cols,rows),pixels)
            if str(ds.PhotometricInterpretation)=="MONOCHROME1": image=ImageOps.invert(image)
        dest=job.outdir/(safe_stem(job.file())+"_{:03d}.png".format(n+1))
        image.save(dest)
        outputs.append(dest)
    return Result("已导出 {} 帧，应用了窗宽窗位与灰度反转（如适用）。".format(count),outputs)
