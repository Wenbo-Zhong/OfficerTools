import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from officertools import ui


class ScrollTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        with patch.object(ui, "load_state", return_value={"favorites": [], "recent": []}):
            self.app = ui.App(self.root)
        self.root.geometry(self.app._geo(920, 600))
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        self.assertEqual(self.errors, [])

    def advance(self, milliseconds):
        self.root.after(milliseconds, self.root.quit)
        self.root.mainloop()

    def test_wheel_animates_and_accumulates(self):
        area = self.app.area
        event = SimpleNamespace(delta=-120, num=None)
        area.wheel(event)
        self.assertEqual(area.canvas.yview()[0], 0)
        self.advance(40)
        first = area.canvas.yview()[0]
        self.assertGreater(first, 0)
        target = area._target
        area.wheel(event)
        self.assertGreater(area._target, target)
        self.advance(650)
        self.assertGreater(area.canvas.yview()[0], first)
        self.assertIsNone(area._animation)

    def test_switch_from_bottom_resets_short_and_empty_categories(self):
        for category in ("系统", "收藏", "最近"):
            self.app.pick_bucket("全部")
            self.root.update()
            self.app.canvas.yview_moveto(1)
            self.app.area.wheel(SimpleNamespace(delta=-120, num=None))
            self.app.pick_bucket(category)
            self.root.update()
            self.advance(100)
            self.assertEqual(self.app.canvas.yview()[0], 0, category)
            self.assertIsNone(self.app.area._animation)

    def test_search_from_bottom_resets_and_short_content_cannot_scroll(self):
        self.app.canvas.yview_moveto(1)
        self.app.query.set("PDF 合并")
        self.root.update()
        self.assertEqual(self.app.canvas.yview()[0], 0)
        self.app.area.wheel(SimpleNamespace(delta=-12000, num=None))
        self.advance(100)
        self.assertEqual(self.app.canvas.yview()[0], 0)

    def test_scrollbar_interrupts_animation_and_destroy_is_safe(self):
        area = self.app.area
        area.wheel(SimpleNamespace(delta=-120, num=None))
        area._scrollbar("moveto", "0.5")
        self.assertIsNone(area._animation)
        position = area.canvas.yview()
        self.advance(100)
        self.assertEqual(area.canvas.yview(), position)
        area.wheel(SimpleNamespace(delta=-120, num=None))
        self.root.update_idletasks()


if __name__ == "__main__":
    unittest.main()
