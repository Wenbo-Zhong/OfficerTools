import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from PIL import Image

from officertools.engine import ocr,vlm
from officertools.engine.common import Job,Cancelled


class VlmTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def job(self,**opts): return Job("ocr-image",opts,self.root/"out")

    def test_installed_language_stays_on_tesseract(self):
        with patch.object(ocr,"engine",return_value=("tesseract",[])),patch.object(vlm,"model_files") as models:
            self.assertEqual(ocr.select_engine(self.job()),"tesseract")
            models.assert_not_called()

    def test_missing_language_falls_back_but_forced_tesseract_does_not(self):
        with patch.object(ocr,"engine",side_effect=ocr.MissingLanguage("missing")),patch.object(vlm,"model_files"):
            self.assertEqual(ocr.select_engine(self.job(lang="日语")),"qwen")
            with self.assertRaises(ocr.MissingLanguage): ocr.select_engine(self.job(engine="tesseract"))
        with patch.object(ocr,"engine",side_effect=RuntimeError("bad setting")),patch.object(vlm,"model_files") as models:
            with self.assertRaisesRegex(RuntimeError,"bad setting"):ocr.select_engine(self.job())
            models.assert_not_called()

    def test_language_aliases_and_content_parts(self):
        self.assertEqual(ocr.language(self.job(lang="日语+en")),"jpn+eng")
        self.assertEqual(ocr.language(self.job(lang="自动识别")),"auto")
        self.assertEqual(vlm.response_text([{"type":"reasoning","text":"skip"},{"type":"text","text":"日本語"}]),"日本語")
        self.assertEqual(vlm.response_text("hello"),"hello")
        self.assertEqual(vlm.response_text(None),"")

    def test_gpu_failure_retries_cpu_and_reuses_it_for_next_page(self):
        sessions=[]
        class FakeSession:
            def __init__(self,job,backend):self.backend=backend;self.closed=False;sessions.append(self)
            def start(self):
                if self.backend=="vulkan":raise RuntimeError("no GPU")
            def transcribe(self,path,language):return "日本語"
            def close(self):self.closed=True
        with patch.object(vlm,"model_files"),patch.object(vlm,"Session",FakeSession):
            with vlm.Recognizer(self.job()) as recognizer:
                self.assertEqual(recognizer.transcribe(self.root/"page.png","jpn"),"日本語")
                self.assertEqual(recognizer.transcribe(self.root/"page2.png","jpn"),"日本語")
            self.assertEqual([s.backend for s in sessions],["vulkan","cpu"])
            self.assertTrue(all(s.closed for s in sessions))

    def test_cancellation_does_not_retry_another_backend(self):
        sessions=[]
        class FakeSession:
            def __init__(self,job,backend):self.backend=backend;self.closed=False;sessions.append(self)
            def start(self):raise Cancelled("cancel")
            def close(self):self.closed=True
        with patch.object(vlm,"model_files"),patch.object(vlm,"Session",FakeSession):
            with self.assertRaises(Cancelled):
                with vlm.Recognizer(self.job()) as recognizer:recognizer.transcribe(self.root/"page.png","auto")
            self.assertEqual(len(sessions),1)
            self.assertTrue(sessions[0].closed)

    def test_searchable_pdf_keeps_image_and_unicode(self):
        image=self.root/"page.png"
        Image.new("RGB",(600,300),"#eeccaa").save(image)
        dest=self.root/"result.pdf"
        ocr.qwen_pdf(image,dest,150,"日本語のテスト\nПривет мир\n12345")
        with fitz.open(str(dest)) as doc:
            self.assertEqual(len(doc),1)
            text=doc[0].get_text()
            self.assertIn("日本語",text)
            self.assertIn("Привет",text)
            self.assertIn("12345",text)
            pix=doc[0].get_pixmap()
            self.assertEqual(pix.pixel(100,100),(238,204,170))

    def test_qwen_rejects_unreliable_word_position_exports(self):
        with self.assertRaisesRegex(RuntimeError,"逐字坐标"):
            ocr.recognize(self.job(output="tsv"),[],self.root,selected="qwen")


if __name__=="__main__":unittest.main()
