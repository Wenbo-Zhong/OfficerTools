import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from officertools.engine.common import Job
from officertools.engine.dispatch import run

STAGE=Path(__file__).resolve().parents[1]/".toolchain/release-ocr"


@unittest.skipUnless((STAGE/"vendor/tesseract/bin/tesseract.exe").exists(),"OCR native runtime is not staged")
class OfflineOcrTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.image=self.root/"中文样本.png"
        self.sample=Image.new("RGB",(1500,400),"white")
        draw=ImageDraw.Draw(self.sample)
        font=ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc",58)
        draw.text((60,60),"中文识别测试",font=font,fill="black")
        draw.text((60,180),"OFFLINE OCR 123456",font=font,fill="black")
        self.sample.save(self.image,dpi=(300,300))
        self.discovery=patch("officertools.engine.common.application_root",return_value=STAGE)
        self.discovery.start()
        self.environment=patch.dict(os.environ,{"PATH":"","TESSDATA_PREFIX":"C:/missing-models"})
        self.environment.start()

    def tearDown(self):
        self.environment.stop();self.discovery.stop();self.temp.cleanup()

    def test_real_bilingual_ocr_and_searchable_pdf(self):
        result=run(Job("ocr-image",{"files":str(self.image),"psm":"6","output":"both"},self.root/"image"))
        text=re.sub(r"\s+","",result.files[0].read_text("utf-8"))
        self.assertIn("中文识别测试",text)
        self.assertIn("OFFLINEOCR123456",text)
        reader=PdfReader(str(result.files[1]))
        self.assertEqual(len(reader.pages),1)
        self.assertIn("OFFLINE",reader.pages[0].extract_text())
        self.assertFalse(any((self.root/"image").glob("ocr-*")))

    def test_pdf_page_selection_password_and_no_option_mutation(self):
        plain=self.root/"scan.pdf"
        self.sample.save(plain,save_all=True,append_images=[self.sample],resolution=300)
        from pypdf import PdfWriter
        writer=PdfWriter();writer.append(PdfReader(str(plain)));writer.encrypt("secret")
        source=self.root/"locked.pdf"
        with source.open("wb") as stream: writer.write(stream)
        opts={"file":str(source),"password":"secret","ranges":"2","dpi":"200","psm":"6"}
        before=dict(opts)
        result=run(Job("ocr-pdf",opts,self.root/"pdf"))
        self.assertEqual(opts,before)
        reader=PdfReader(str(result.files[1]))
        self.assertEqual(len(reader.pages),1)
        self.assertIn("OFFLINE",reader.pages[0].extract_text())
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width),360,delta=1)

    def test_screen_region_and_positional_outputs(self):
        with patch("PIL.ImageGrab.grab",return_value=self.sample.copy()) as grab:
            result=run(Job("ocr-screen",{"bbox":"10,20,1500,400","psm":"6","output":"tsv"},self.root/"screen"))
        self.assertEqual(grab.call_args.kwargs["bbox"],(10,20,1510,420))
        self.assertIn("OFFLINE",result.files[0].read_text("utf-8"))
        self.assertTrue(any(p.suffix==".tsv" for p in result.files))
        result=run(Job("ocr-image",{"files":str(self.image),"psm":"6","output":"hocr"},self.root/"hocr"))
        self.assertIn("ocr_page",result.files[1].read_text("utf-8"))

    def test_missing_language_has_clear_error(self):
        with self.assertRaisesRegex(RuntimeError,"缺少 OCR 语言模型"):
            run(Job("ocr-image",{"files":str(self.image),"lang":"jpn","engine":"tesseract"},self.root/"missing"))


if __name__=="__main__": unittest.main()
