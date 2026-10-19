import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from PIL import Image
from officertools import ui
from officertools.catalog import BY_ID


class FeatureUiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=tk.Tk()
        self.root.withdraw()
        with patch.object(ui,"load_state",return_value={"favorites":[],"recent":[]}):
            self.app=ui.App(self.root)
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()
        self.temp.cleanup()

    def window(self,name):
        host=ui.ToolWindow(self.app,BY_ID[name])
        host.win.withdraw()
        host.output_folder=Path(self.temp.name)/name
        self.root.update()
        return host

    def test_actual_pdf_view_and_search(self):
        path=Path(self.temp.name)/"sample.pdf"
        doc=fitz.open()
        for word in ("first","needle"):
            page=doc.new_page(width=100,height=120)
            page.insert_text((10,30),word)
        doc.save(str(path));doc.close()
        host=self.window("pdf-reader")
        viewer=host.special
        viewer.document=fitz.open(str(path))
        viewer.go(0)
        self.assertEqual(viewer.image.size,(167,200))
        viewer.search.set("needle");viewer.find()
        self.assertEqual(viewer.page,1)
        viewer.set_zoom(2)
        self.assertEqual(viewer.photo.width(),334)
        host.win.destroy()
        self.assertIsNone(viewer.document)

    def test_annotation_undo_and_original_pixel_output(self):
        path=Path(self.temp.name)/"sample.png"
        Image.new("RGB",(200,150),"white").save(path)
        host=self.window("annotate")
        editor=host.special
        editor._open(path)
        editor.strokes=[("矩形",[(10,10),(100,100)],"#ff0000",3,""),
                        ("文字",[(30,30),(30,30)],"#0000ff",3,"文字")]
        editor.redraw_annotations()
        self.assertEqual(editor.rendered.getpixel((10,10)),(255,0,0))
        editor.undo();self.assertEqual(len(editor.strokes),1)
        editor.save()
        with Image.open(host.outdir()/"annotated.png") as image:
            self.assertEqual(image.size,(200,150))
            self.assertEqual(image.getpixel((10,10)),(255,0,0))
        host.win.destroy()

    def test_background_task_returns_without_blocking_tk(self):
        host=self.window("calc")
        host.vars["expr"].set("sqrt(16)+25%")
        host.execute()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            self.root.update()
            if not host.worker.is_alive() and host.events.empty(): break
            time.sleep(.01)
        self.assertIn("4.25",host.log.get("1.0","end"))
        self.assertEqual(float(host.progress["value"]),100)
        host.win.destroy()


if __name__=="__main__": unittest.main()
