import io
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

import fitz
from PIL import Image, ImageDraw
from pypdf import PdfReader

from officertools.engine.common import Job, Cancelled
from officertools.engine.dispatch import run
from officertools.engine.pdf_extended import estimate_angle


class ParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pdf = self.root / "sample.pdf"
        doc = fitz.open()
        for n in range(3):
            page = doc.new_page(width=300,height=400)
            page.insert_text((30,50),"Sample page {}".format(n+1))
            page.draw_rect(fitz.Rect(30,80,120,140),color=(1,0,0),fill=(.8,.8,.8))
        doc.save(str(self.pdf))
        doc.close()

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, tool, **opts):
        opts.setdefault("file",str(self.pdf))
        return run(Job(tool,opts,self.root/tool))

    def test_deskew_angle_and_pdf_preserves_text(self):
        im=Image.new("RGB",(600,800),"white")
        d=ImageDraw.Draw(im)
        for y in range(80,700,30):
            for x in range(40,520,24):
                d.rectangle((x,y,x+15,y+5),fill="black")
        tilted=im.rotate(4,fillcolor="white")
        angle=estimate_angle(tilted,10)
        self.assertAlmostEqual(angle,-4,delta=.4)
        result=self.run_tool("pdf-deskew",dpi="72",ranges="2",mode="preserve")
        reader=PdfReader(str(result.files[0]))
        self.assertEqual(len(reader.pages),3)
        self.assertIn("Sample page 2",reader.pages[1].extract_text())
        self.assertEqual(reader.pages[0].get_contents().get_data(),PdfReader(str(self.pdf)).pages[0].get_contents().get_data())

    def test_bw_is_bilevel_and_keeps_unselected_pages(self):
        result=self.run_tool("pdf-bw",dpi="72",ranges="2",**{"bw-mode":"threshold","threshold":"180"})
        reader=PdfReader(str(result.files[0]))
        self.assertIn("Sample page 1",reader.pages[0].extract_text())
        images=list(reader.pages[1].images)
        self.assertTrue(images)
        self.assertEqual(images[0].image.mode,"1")

    def test_tiff_deskew_and_batch_pdf(self):
        path=self.root/"scan.tiff"
        frames=[Image.new("RGB",(180,240),"white") for _ in range(2)]
        frames[0].save(path,save_all=True,append_images=frames[1:])
        result=self.run_tool("pdf-deskew",file=str(path),dpi="72",ranges="1")
        with Image.open(result.files[0]) as image:
            self.assertEqual(image.n_frames,2)
        result=self.run_tool("pdf-deskew",file=str(self.pdf)+"|"+str(self.pdf),dpi="72",ranges="1")
        self.assertEqual(len(result.files),2)
        self.assertNotEqual(result.files[0],result.files[1])

    def test_page_edit_cut_and_links(self):
        result=self.run_tool("pdf-page-master",order="3,1,blank,2")
        reader=PdfReader(str(result.files[0]))
        self.assertEqual(len(reader.pages),4)
        self.assertIn("page 3",reader.pages[0].extract_text())
        self.assertEqual(reader.pages[2].extract_text(),"")
        result=self.run_tool("pdf-page-cut",rows="2",cols="2",ranges="1")
        reader=PdfReader(str(result.files[0]))
        self.assertEqual(len(reader.pages),6)
        self.assertEqual(float(reader.pages[0].mediabox.width),150)
        result=self.run_tool("pdf-links",url="https://example.org",ranges="2")
        with fitz.open(str(result.files[0])) as doc:
            self.assertEqual(doc[1].get_links()[0]["uri"],"https://example.org")
            self.assertFalse(doc[0].get_links())

    def test_watermark_transparency_and_conversion_assets(self):
        result=self.run_tool("pdf-watermark",text="测试水印",opacity="0.2",angle="30",tile="1",ranges="2")
        with fitz.open(str(result.files[0])) as doc:
            self.assertIn("Sample page 2",doc[1].get_text())
            self.assertEqual(doc[0].get_pixmap().samples,fitz.open(str(self.pdf))[0].get_pixmap().samples)
            states=PdfReader(str(result.files[0])).pages[1]["/Resources"]["/ExtGState"]
            self.assertTrue(any(float(s.get("/ca",1))==.2 for s in states.values()))
        result=self.run_tool("pdf-to-word")
        with zipfile.ZipFile(str(result.files[0])) as archive:
            self.assertIn(b"Sample page 1",archive.read("word/document.xml"))
        result=self.run_tool("pdf-to-html")
        self.assertIn("position:absolute",result.files[0].read_text("utf-8"))

    def test_pdf417_and_alpha_compression(self):
        result=self.run_tool("pdf417",text="中文 PDF417",columns="6",security="2")
        with Image.open(result.files[0]) as image:
            self.assertGreater(image.width,100)
        path=self.root/"alpha.png"
        Image.new("RGBA",(64,64),(255,0,0,80)).save(path)
        result=self.run_tool("img-compress",files=str(path),fmt="auto")
        with Image.open(result.files[0]) as image:
            self.assertEqual(image.getpixel((0,0))[3],80)

    def test_conversion_preserves_embedded_images(self):
        blob=io.BytesIO();Image.new("RGB",(24,24),"blue").save(blob,"PNG")
        path=self.root/"with-image.pdf"
        doc=fitz.open(str(self.pdf));doc[0].insert_image(fitz.Rect(150,80,220,150),stream=blob.getvalue())
        doc.save(str(path));doc.close()
        result=self.run_tool("pdf-to-word",file=str(path),ranges="1")
        with zipfile.ZipFile(str(result.files[0])) as archive:
            self.assertTrue(any(name.startswith("word/media/") for name in archive.namelist()))
        result=self.run_tool("pdf-to-html",file=str(path),ranges="1")
        self.assertIn("data:image/png;base64",result.files[0].read_text("utf-8"))

    def test_preview_rename_and_independent_time(self):
        path=self.root/"file.txt"
        path.write_text("test")
        result=self.run_tool("rename",files=str(path),pattern="{n}_{name}{ext}",preview="1")
        self.assertTrue(path.exists())
        self.run_tool("rename",files=str(path),pattern="{n}_{name}{ext}",preview="0")
        renamed=self.root/"001_file.txt"
        self.assertTrue(renamed.exists())
        before=renamed.stat()
        self.run_tool("filetime",files=str(renamed),offset="3600",access="0",modified="1")
        after=renamed.stat()
        self.assertAlmostEqual(after.st_mtime,before.st_mtime+3600,delta=.1)
        self.assertAlmostEqual(after.st_atime,before.st_atime,delta=.1)

    def test_scientific_calculator_and_cancel(self):
        result=self.run_tool("calc",expr="sqrt(9)+50%+sin(pi/2)")
        self.assertTrue(result.message.endswith("4.5"))
        with self.assertRaises(RuntimeError):
            self.run_tool("calc",expr="__import__('os')")
        event=threading.Event();event.set()
        with self.assertRaises(Cancelled):
            run(Job("pdf-deskew",{"file":str(self.pdf)},self.root/"cancel",cancel=event))

    def test_pdf_security_crop_number_and_nup(self):
        result=self.run_tool("pdf-lock",password="open",**{"owner-password":"owner","allow-copy":"0","allow-print":"0"})
        reader=PdfReader(str(result.files[0]));reader.decrypt("open")
        permissions=int(reader.trailer["/Encrypt"]["/P"])
        self.assertEqual(permissions & 4,0)
        self.assertEqual(permissions & 16,0)
        result=self.run_tool("pdf-crop",auto="1",padding="8",ranges="1")
        reader=PdfReader(str(result.files[0]))
        self.assertLess(float(reader.pages[0].mediabox.width),300)
        self.assertEqual(float(reader.pages[1].mediabox.width),300)
        result=self.run_tool("pdf-nup",paper="A4-landscape",rows="1",cols="2",margin="12",gap="6")
        reader=PdfReader(str(result.files[0]))
        self.assertEqual(len(reader.pages),2)
        self.assertGreater(float(reader.pages[0].mediabox.width),800)
        self.assertIn("Sample page 1",reader.pages[0].extract_text())
        result=self.run_tool("pdf-pagenum",start="8",ranges="2",position="top-right")
        reader=PdfReader(str(result.files[0]))
        self.assertFalse(reader.pages[0].images)
        self.assertTrue(reader.pages[1].images)

    def test_dicom_signed_multiframe_window(self):
        import struct
        from pydicom.dataset import FileDataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, generate_uid
        path=self.root/"image.dcm"
        meta=FileMetaDataset()
        meta.TransferSyntaxUID=ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID=generate_uid();meta.MediaStorageSOPInstanceUID=generate_uid()
        ds=FileDataset(str(path),{},file_meta=meta,preamble=b"\0"*128)
        ds.is_little_endian=True;ds.is_implicit_VR=False
        ds.Rows=2;ds.Columns=2;ds.BitsAllocated=16;ds.BitsStored=12;ds.HighBit=11
        ds.PixelRepresentation=1;ds.SamplesPerPixel=1;ds.PhotometricInterpretation="MONOCHROME1"
        ds.NumberOfFrames=2;ds.WindowWidth=200;ds.WindowCenter=0
        ds.PixelData=struct.pack("<8h",-100,0,50,100,-100,0,50,100)
        ds.save_as(str(path))
        result=self.run_tool("dicom-preview",file=str(path))
        self.assertEqual(len(result.files),2)
        with Image.open(result.files[0]) as im:
            self.assertEqual(im.getpixel((0,0)),255)
            self.assertEqual(im.getpixel((1,1)),0)

    def test_slideshow_controls_and_media_args(self):
        from officertools.engine.external import _record_args
        from unittest.mock import patch
        path=self.root/"slide.png";Image.new("RGB",(20,20),"red").save(path)
        result=self.run_tool("slideshow",files=str(path),interval="3",title="<test>")
        html=result.files[0].read_text("utf-8")
        self.assertIn("setInterval",html)
        self.assertIn("3000",html)
        self.assertIn("&lt;test&gt;",html)
        with patch("officertools.engine.external._ffmpeg",return_value="ffmpeg"):
            cmd,_,_= _record_args(Job("screen-record",{"bbox":"10,20,640,480","audio-device":"Microphone"},self.root),False)
        self.assertIn("640x480",cmd)
        self.assertIn("audio=Microphone",cmd)


if __name__ == "__main__":
    unittest.main()
