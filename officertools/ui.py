# -*- coding: utf-8 -*-
"""Launcher and tool windows. Sizes follow the real monitor DPI."""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.font as tkfont
import tkinter.scrolledtext as scrolledtext
from pathlib import Path
from tkinter import ttk

from officertools.catalog import BY_EXE, BY_ID, CATEGORIES, TOOLS, Tool
from officertools.dpi import apply_tk_scaling, system_dpi
from officertools.engine.common import Job, open_folder
from officertools.engine.dispatch import UI_ONLY, run

STATE_PATH = Path(os.environ.get("APPDATA") or str(Path.home())) / "OfficerTools" / "state.json"

# Warm paper page, ink sidebar, one accent. Avoid the default gray Tk palette.
PAGE = "#f3efe7"
SIDE = "#1c1917"
SIDE_MUTED = "#a8a29e"
SIDE_ACTIVE = "#292524"
CARD = "#fffcf8"
INK = "#1c1917"
MUTED = "#78716c"
LINE = "#e7e0d4"
ACCENT = "#0f766e"
ACCENT_ACTIVE = "#115e59"


class ScrollArea(object):
    """Vertical scroller whose wheel works over the child widgets, not only the bare canvas."""

    def __init__(self, parent, bg):
        self.canvas = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(parent, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas._scroll_area = self
        self.inner._scroll_area = self

    def _on_inner(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self.win, width=event.width)

    def wheel(self, event):
        if getattr(event, "num", None) == 4:
            steps = -3
        elif getattr(event, "num", None) == 5:
            steps = 3
        else:
            steps = int(-event.delta / 120 * 3) or (-3 if event.delta > 0 else 3)
        self.canvas.yview_scroll(steps, "units")


def install_wheel(root):
    def on_wheel(event):
        x, y = root.winfo_pointerxy()
        widget = root.winfo_containing(x, y)
        while widget is not None:
            if isinstance(widget, tk.Text):
                return
            area = getattr(widget, "_scroll_area", None)
            if area is not None:
                area.wheel(event)
                return "break"
            widget = getattr(widget, "master", None)

    root.bind_all("<MouseWheel>", on_wheel)
    root.bind_all("<Button-4>", on_wheel)
    root.bind_all("<Button-5>", on_wheel)


def pill(parent, text, command, app, primary=False):
    bg = ACCENT if primary else CARD
    fg = "#fafaf9" if primary else INK
    active = ACCENT_ACTIVE if primary else "#f5f0e8"
    return tk.Button(
        parent, text=text, command=command, font=app.font,
        bg=bg, fg=fg, activebackground=active, activeforeground=fg,
        relief="flat", bd=0, cursor="hand2",
        padx=app.px(14), pady=app.px(7),
        highlightthickness=0,
    )


def state_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "OfficerTools"
    if sys.platform.startswith("linux"):
        return Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")) / "OfficerTools"
    return STATE_PATH.parent


def load_state():
    path = state_dir() / "state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"favorites": [], "recent": []}


def save_state(data) -> None:
    folder = state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "state.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class App(object):
    def __init__(self, root, initial=None):
        self.root = root
        self.dpi = apply_tk_scaling(root)
        self.scale = self.dpi / 96.0
        self.state = load_state()
        self.category = tk.StringVar(value="全部")
        self.query = tk.StringVar()
        root.title("OfficerTools")
        root.configure(bg=PAGE)
        root.geometry(self._geo(1180, 760))
        root.minsize(self.px(920), self.px(600))
        self._fonts()
        self._style_ttk()
        install_wheel(root)
        self.bucket = "全部"
        self._cols = 0
        if initial:
            root.withdraw()
            ToolWindow(self, BY_ID[initial])
            return
        self._build()

    def px(self, value):
        return max(1, int(round(value * self.scale)))

    def _geo(self, w, h):
        return "{}x{}".format(self.px(w), self.px(h))

    def _fonts(self):
        family = "Segoe UI"
        if sys.platform == "win32":
            family = "Microsoft YaHei UI"
        elif sys.platform == "darwin":
            family = "PingFang SC"
        else:
            family = "Noto Sans CJK SC"
        available = set(tkfont.families(self.root))
        if family not in available:
            family = "TkDefaultFont"
        self.family = family
        self.font = tkfont.Font(family=family, size=11)
        self.font_small = tkfont.Font(family=family, size=9)
        self.font_title = tkfont.Font(family=family, size=20)
        self.font_card = tkfont.Font(family=family, size=13)

    def _style_ttk(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=PAGE, foreground=INK, font=self.font)
        style.configure("TFrame", background=PAGE)
        style.configure("TLabel", background=PAGE, foreground=INK)
        style.configure("TEntry", fieldbackground=CARD, foreground=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=INK, arrowcolor=INK)
        style.map("TCombobox", fieldbackground=[("readonly", CARD)])
        style.configure("TCheckbutton", background=PAGE, foreground=INK)
        style.configure("Vertical.TScrollbar", background=PAGE, troughcolor=PAGE, arrowcolor=MUTED, bordercolor=PAGE)

    def _build(self):
        side = tk.Frame(self.root, bg=SIDE, width=self.px(216))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="OfficerTools", font=self.font_title, bg=SIDE, fg="#fafaf9").pack(anchor="w", padx=self.px(22), pady=(self.px(26), 0))
        tk.Label(side, text="办公工具", font=self.font_small, bg=SIDE, fg=SIDE_MUTED).pack(anchor="w", padx=self.px(22), pady=(0, self.px(22)))
        nav_host = tk.Frame(side, bg=SIDE)
        nav_host.pack(fill="both", expand=True)
        self.nav_area = ScrollArea(nav_host, SIDE)
        self.nav_buttons = {}
        for name in ["全部", "收藏", "最近"] + CATEGORIES:
            btn = tk.Label(self.nav_area.inner, text=name, font=self.font, bg=SIDE, fg="#e7e5e4", anchor="w", padx=self.px(18), pady=self.px(8), cursor="hand2")
            btn.pack(fill="x", padx=self.px(12), pady=1)
            btn.bind("<Button-1>", lambda e, n=name: self.pick_bucket(n))
            self.nav_buttons[name] = btn
        self._paint_nav()

        main = tk.Frame(self.root, bg=PAGE)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=PAGE)
        top.pack(fill="x", padx=self.px(28), pady=(self.px(22), self.px(8)))
        tk.Label(top, text="全部工具", font=self.font_title, bg=PAGE, fg=INK).pack(side="left")
        self.heading = top.winfo_children()[0]
        search_wrap = tk.Frame(top, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        search_wrap.pack(side="right")
        tk.Label(search_wrap, text="搜索", font=self.font_small, bg=CARD, fg=MUTED).pack(side="left", padx=(self.px(10), 0))
        entry = tk.Entry(search_wrap, textvariable=self.query, font=self.font, bg=CARD, fg=INK, relief="flat", width=24, insertbackground=INK, highlightthickness=0)
        entry.pack(side="left", padx=self.px(8), pady=self.px(7))
        entry.bind("<KeyRelease>", lambda e: self.refresh())

        list_host = tk.Frame(main, bg=PAGE)
        list_host.pack(fill="both", expand=True, padx=self.px(16), pady=(0, self.px(12)))
        self.area = ScrollArea(list_host, PAGE)
        self.canvas = self.area.canvas
        self.cards = self.area.inner
        self.canvas.bind("<Configure>", self._on_canvas_configure, add="+")
        self.refresh()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure("cards", width=event.width)
        cols = 3 if event.width >= self.px(760) else (2 if event.width >= self.px(520) else 1)
        if cols != self._cols:
            self._cols = cols
            self.refresh()

    def _paint_nav(self):
        for name, btn in self.nav_buttons.items():
            active = name == self.bucket
            btn.configure(bg=SIDE_ACTIVE if active else SIDE, fg="#fafaf9" if active else "#d6d3d1")

    def pick_bucket(self, name):
        self.bucket = name
        self.heading.configure(text={"全部": "全部工具", "收藏": "收藏", "最近": "最近使用"}.get(name, name))
        self._paint_nav()
        self.refresh()

    def selected_bucket(self):
        return getattr(self, "bucket", "全部")

    def refresh(self):
        if not hasattr(self, "cards"):
            return
        for child in self.cards.winfo_children():
            child.destroy()
        for col in range(6):
            self.cards.grid_columnconfigure(col, weight=0, uniform="")
        bucket = self.selected_bucket()
        query = self.query.get().strip().lower()
        tools = []
        for tool in TOOLS:
            if bucket == "收藏" and tool.id not in self.state["favorites"]:
                continue
            if bucket == "最近" and tool.id not in self.state["recent"]:
                continue
            if bucket not in ("全部", "收藏", "最近") and tool.category != bucket:
                continue
            blob = (tool.name + tool.summary + tool.category).lower()
            if query and query not in blob:
                continue
            tools.append(tool)
        if bucket == "最近":
            order = {tid: i for i, tid in enumerate(self.state["recent"])}
            tools.sort(key=lambda t: order.get(t.id, 999))
        cols = self._cols or 3
        if not tools:
            tk.Label(self.cards, text="没有匹配的工具。", font=self.font, bg=PAGE, fg=MUTED).grid(row=0, column=0, sticky="w", padx=12, pady=20)
            return
        for col in range(cols):
            self.cards.grid_columnconfigure(col, weight=1, uniform="card")
        for index, tool in enumerate(tools):
            self._card(tool, index // cols, index % cols)

    def _card(self, tool: Tool, row, col):
        shell = tk.Frame(self.cards, bg=PAGE)
        shell.grid(row=row, column=col, sticky="nsew", padx=self.px(8), pady=self.px(8))
        frame = tk.Frame(shell, bg=CARD, highlightbackground=LINE, highlightthickness=1, cursor="hand2")
        frame.pack(fill="both", expand=True)
        head = tk.Frame(frame, bg=CARD)
        head.pack(fill="x", padx=self.px(16), pady=(self.px(14), 0))
        tk.Label(head, text=tool.category, font=self.font_small, bg=CARD, fg=ACCENT).pack(side="left")
        star = "已收藏" if tool.id in self.state["favorites"] else "收藏"
        mark = tk.Label(head, text=star, font=self.font_small, bg=CARD, fg=MUTED, cursor="hand2")
        mark.pack(side="right")
        mark.bind("<Button-1>", lambda e, t=tool: self.toggle_fav(t))
        name = tk.Label(frame, text=tool.name, font=self.font_card, bg=CARD, fg=INK, anchor="w")
        name.pack(fill="x", padx=self.px(16), pady=(self.px(6), 0))
        summary = tk.Label(frame, text=tool.summary, font=self.font_small, bg=CARD, fg=MUTED, anchor="w", justify="left", wraplength=self.px(280))
        summary.pack(fill="x", padx=self.px(16), pady=(self.px(6), self.px(16)))

        def open_tool(_event=None, t=tool):
            self.open_tool(t)

        def hover(_event=None, on=True):
            frame.configure(highlightbackground=ACCENT if on else LINE)

        for widget in (frame, head, name, summary):
            widget.bind("<Button-1>", open_tool)
            widget.bind("<Enter>", lambda e: hover(on=True))
            widget.bind("<Leave>", lambda e: hover(on=False))

    def toggle_fav(self, tool: Tool):
        fav = self.state["favorites"]
        if tool.id in fav:
            fav.remove(tool.id)
        else:
            fav.append(tool.id)
        save_state(self.state)
        self.refresh()

    def open_tool(self, tool: Tool):
        recent = [tool.id] + [i for i in self.state["recent"] if i != tool.id]
        self.state["recent"] = recent[:30]
        save_state(self.state)
        ToolWindow(self, tool)


class ToolWindow(object):
    def __init__(self, app: App, tool: Tool):
        self.app = app
        self.tool = tool
        self.win = tk.Toplevel(app.root)
        self.win.title(tool.name)
        self.win.configure(bg=PAGE)
        self.win.geometry(app._geo(780, 680))
        self.win.minsize(app.px(640), app.px(500))
        self.vars = {}
        pad = app.px(22)
        host = tk.Frame(self.win, bg=PAGE)
        host.pack(fill="both", expand=True)
        self.area = ScrollArea(host, PAGE)
        frm = tk.Frame(self.area.inner, bg=PAGE)
        frm.pack(fill="both", expand=True, padx=pad, pady=pad)
        tk.Label(frm, text=tool.category, font=app.font_small, bg=PAGE, fg=ACCENT).pack(anchor="w")
        tk.Label(frm, text=tool.name, font=app.font_title, bg=PAGE, fg=INK).pack(anchor="w", pady=(2, 0))
        tk.Label(frm, text=tool.summary, font=app.font, bg=PAGE, fg=MUTED, wraplength=app.px(700), justify="left").pack(anchor="w", pady=(4, app.px(14)))
        if tool.id in UI_ONLY or tool.id == "calc":
            self._special(frm)
        else:
            self._form(frm)
        self.log = scrolledtext.ScrolledText(
            frm, height=10, font=app.font, wrap="word",
            bg=CARD, fg=INK, insertbackground=INK, relief="flat",
            highlightbackground=LINE, highlightthickness=1, bd=0, padx=10, pady=8,
        )
        self.log.pack(fill="x", pady=(pad, 0))

    def _form(self, frm):
        app = self.app
        for field in self.tool.fields:
            tk.Label(frm, text=field.label, font=app.font_small, bg=PAGE, fg=MUTED).pack(anchor="w", pady=(app.px(8), 2))
            if field.kind in ("text", "number"):
                var = tk.StringVar(value=field.default)
                tk.Entry(frm, textvariable=var, font=app.font, bg=CARD, fg=INK, relief="flat", highlightbackground=LINE, highlightthickness=1, insertbackground=INK).pack(fill="x", ipady=app.px(6))
                self.vars[field.key] = var
            elif field.kind == "choice":
                var = tk.StringVar(value=field.default or (field.options[0] if field.options else ""))
                ttk.Combobox(frm, textvariable=var, values=field.options, state="readonly", font=app.font).pack(fill="x", ipady=2)
                self.vars[field.key] = var
            elif field.kind == "check":
                var = tk.StringVar(value=field.default or "0")
                ttk.Checkbutton(frm, variable=var, onvalue="1", offvalue="0").pack(anchor="w")
                self.vars[field.key] = var
            elif field.kind == "multiline":
                text = tk.Text(frm, height=5, font=app.font, wrap="word", bg=CARD, fg=INK, relief="flat", highlightbackground=LINE, highlightthickness=1, insertbackground=INK, padx=8, pady=6)
                text.insert("1.0", field.default)
                text.pack(fill="x")
                self.vars[field.key] = text
            elif field.kind in ("file", "files", "dir"):
                row = tk.Frame(frm, bg=PAGE)
                row.pack(fill="x")
                var = tk.StringVar()
                tk.Entry(row, textvariable=var, font=app.font, bg=CARD, fg=INK, relief="flat", highlightbackground=LINE, highlightthickness=1, insertbackground=INK).pack(side="left", fill="x", expand=True, ipady=app.px(6))
                pill(row, "浏览", lambda f=field, v=var: self.browse(f, v), app).pack(side="left", padx=(8, 0))
                self.vars[field.key] = var
            if field.help:
                tk.Label(frm, text=field.help, font=app.font_small, bg=PAGE, fg=MUTED).pack(anchor="w", pady=(2, 0))
        bar = tk.Frame(frm, bg=PAGE)
        bar.pack(fill="x", pady=(app.px(16), 0))
        pill(bar, "开始", self.execute, app, primary=True).pack(side="left")
        pill(bar, "打开输出文件夹", self.open_out, app).pack(side="left", padx=8)

    def browse(self, field, var):
        if field.kind == "dir":
            path = filedialog.askdirectory(parent=self.win)
            if path:
                var.set(path)
            return
        if field.kind == "files":
            paths = filedialog.askopenfilenames(parent=self.win)
            if paths:
                var.set("|".join(paths))
            return
        path = filedialog.askopenfilename(parent=self.win)
        if path:
            var.set(path)

    def values(self):
        data = {}
        for key, widget in self.vars.items():
            if isinstance(widget, tk.Text):
                data[key] = widget.get("1.0", "end").strip("\n")
            else:
                data[key] = widget.get()
        return data

    def outdir(self):
        folder = state_dir() / "output" / self.tool.id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def write(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def execute(self):
        self.log.delete("1.0", "end")
        job = Job(self.tool.id, self.values(), self.outdir())
        try:
            result = run(job)
        except Exception as exc:
            self.write(str(exc))
            return
        self.write(result.message)
        for path in result.files:
            self.write(str(path))

    def open_out(self):
        open_folder(self.outdir())

    def _special(self, frm):
        tid = self.tool.id
        if tid == "calc":
            self._form(frm)
            return
        if tid == "pick-color":
            ColorTool(self)
        elif tid == "image-viewer":
            ViewerTool(self)
        elif tid == "annotate":
            AnnotateTool(self)
        elif tid == "magnifier":
            MagnifierTool(self)


class ColorTool(object):
    def __init__(self, host: ToolWindow):
        self.host = host
        self.image = None
        pill(host.win, "打开图片", self.load, host.app, primary=True).pack(anchor="w", padx=22)
        self.canvas = tk.Canvas(host.win, background="#111", highlightthickness=0)
        bar = ttk.Scrollbar(host.win, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True, padx=14, pady=8)
        self.canvas._scroll_area = self.canvas
        self.canvas.wheel = lambda event: self.canvas.yview_scroll(int(-event.delta / 120 * 3) or (-3 if event.delta > 0 else 3), "units")
        self.canvas.bind("<Button-1>", self.pick)
        self.sample = tk.Label(host.win, text="点击图片读取原始像素", font=host.app.font, anchor="w", bg=PAGE, fg=INK)
        self.sample.pack(fill="x", padx=14, pady=(0, 8))

    def load(self):
        from PIL import Image, ImageTk

        path = filedialog.askopenfilename(parent=self.host.win)
        if not path:
            return
        self.image = Image.open(path).convert("RGB")
        self._draw()

    def _draw(self):
        from PIL import ImageTk

        im = self.image
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(), 200)
        ch = max(self.canvas.winfo_height(), 200)
        scale = min(cw / im.width, ch / im.height, 1)
        self.view_scale = scale
        shown = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.Resampling.LANCZOS) if scale < 0.999 else im
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)

    def pick(self, event):
        if self.image is None:
            return
        x = min(self.image.width - 1, max(0, int(event.x / self.view_scale)))
        y = min(self.image.height - 1, max(0, int(event.y / self.view_scale)))
        r, g, b = self.image.getpixel((x, y))
        hexv = "#{:02X}{:02X}{:02X}".format(r, g, b)
        self.sample.configure(text="{}    RGB({}, {}, {})    像素 ({}, {}) / 原图 {}×{}".format(hexv, r, g, b, x, y, self.image.width, self.image.height), background=hexv)


class ViewerTool(object):
    def __init__(self, host: ToolWindow):
        self.host = host
        self.zoom = 1.0
        bar = tk.Frame(host.win, bg=PAGE)
        bar.pack(fill="x", padx=22)
        pill(bar, "打开", self.load, host.app, primary=True).pack(side="left")
        pill(bar, "100%", lambda: self.set_zoom(1), host.app).pack(side="left", padx=6)
        pill(bar, "放大", lambda: self.set_zoom(self.zoom * 1.25), host.app).pack(side="left")
        pill(bar, "缩小", lambda: self.set_zoom(self.zoom / 1.25), host.app).pack(side="left", padx=6)
        wrap = tk.Frame(host.win, bg=PAGE)
        wrap.pack(fill="both", expand=True, padx=14, pady=8)
        self.canvas = tk.Canvas(wrap, background="#20242a", highlightthickness=0)
        ybar = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        xbar = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        ybar.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas._scroll_area = self.canvas

        def wheel(event, canvas=self.canvas):
            step = int(-event.delta / 120 * 3) or (-3 if event.delta > 0 else 3)
            if getattr(event, "state", 0) & 0x1:
                canvas.xview_scroll(step, "units")
            else:
                canvas.yview_scroll(step, "units")

        self.canvas.wheel = wheel

    def load(self):
        from PIL import Image

        path = filedialog.askopenfilename(parent=self.host.win)
        if path:
            self.image = Image.open(path).convert("RGB")
            self.zoom = 1.0
            self.redraw()

    def set_zoom(self, zoom):
        self.zoom = max(0.1, min(8, zoom))
        self.redraw()

    def redraw(self):
        from PIL import Image, ImageTk

        if not hasattr(self, "image"):
            return
        w = max(1, int(self.image.width * self.zoom))
        h = max(1, int(self.image.height * self.zoom))
        shown = self.image.resize((w, h), Image.Resampling.NEAREST if self.zoom >= 1 else Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.configure(scrollregion=(0, 0, w, h))


class AnnotateTool(object):
    def __init__(self, host: ToolWindow):
        from officertools.engine.external import screenshot

        self.host = host
        self.color = "#e11d48"
        self.start = None
        self.strokes = []
        bar = tk.Frame(host.win, bg=PAGE)
        bar.pack(fill="x", padx=22, pady=6)
        pill(bar, "截取全屏", self.capture, host.app, primary=True).pack(side="left")
        pill(bar, "打开图片", self.load, host.app).pack(side="left", padx=6)
        pill(bar, "保存 PNG", self.save, host.app).pack(side="left")
        wrap = tk.Frame(host.win, bg=PAGE)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, background="#111", cursor="crosshair", highlightthickness=0)
        ybar = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        xbar = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        ybar.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas._scroll_area = self.canvas
        self.canvas.wheel = lambda event, canvas=self.canvas: canvas.yview_scroll(int(-event.delta / 120 * 3) or (-3 if event.delta > 0 else 3), "units")
        self.canvas.bind("<ButtonPress-1>", self.down)
        self.canvas.bind("<B1-Motion>", self.drag)

    def capture(self):
        from officertools.engine.common import Job
        from officertools.engine.external import screenshot

        result = screenshot(Job("screenshot", {}, self.host.outdir()))
        self._open(result.files[0])

    def load(self):
        path = filedialog.askopenfilename(parent=self.host.win)
        if path:
            self._open(Path(path))

    def _open(self, path):
        from PIL import Image, ImageTk

        self.path = Path(path)
        self.image = Image.open(path).convert("RGB")
        self.photo = ImageTk.PhotoImage(self.image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo, tags="base")
        self.canvas.configure(scrollregion=(0, 0, self.image.width, self.image.height))
        self.host.write("原图 {}×{}，保存时不会缩小。".format(self.image.width, self.image.height))

    def down(self, event):
        self.start = (event.x, event.y)

    def drag(self, event):
        if not self.start:
            return
        self.canvas.delete("preview")
        self.canvas.create_line(self.start[0], self.start[1], event.x, event.y, fill=self.color, width=max(2, int(self.host.app.scale * 2)), tags="preview", capstyle="round")
        self.canvas.bind("<ButtonRelease-1>", self.up)

    def up(self, event):
        if not self.start:
            return
        item = (self.start[0], self.start[1], event.x, event.y)
        self.strokes.append(item)
        self.canvas.delete("preview")
        self.canvas.create_line(*item, fill=self.color, width=max(2, int(self.host.app.scale * 2)), capstyle="round")
        self.start = None

    def save(self):
        from PIL import ImageDraw

        if not hasattr(self, "image"):
            return
        im = self.image.copy()
        draw = ImageDraw.Draw(im)
        # Canvas is 1:1 with the image origin. If the window clipped it, coordinates still match pixels.
        width = max(2, int(3 * self.host.app.dpi / 96.0))
        for x1, y1, x2, y2 in self.strokes:
            draw.line((x1, y1, x2, y2), fill=self.color, width=width)
        dest = self.host.outdir() / "annotated.png"
        im.save(dest, format="PNG")
        self.host.write("已保存 " + str(dest))


class MagnifierTool(object):
    def __init__(self, host: ToolWindow):
        self.host = host
        self.factor = tk.StringVar(value="2")
        bar = tk.Frame(host.win, bg=PAGE)
        bar.pack(fill="x", padx=22, pady=6)
        tk.Label(bar, text="倍数", font=host.app.font, bg=PAGE, fg=MUTED).pack(side="left")
        ttk.Combobox(bar, textvariable=self.factor, values=("2", "3", "4"), width=4, state="readonly").pack(side="left", padx=6)
        pill(bar, "开始", self.loop, host.app, primary=True).pack(side="left")
        self.canvas = tk.Canvas(host.win, background="#111", highlightthickness=0, width=480, height=320)
        self.canvas.pack(padx=8, pady=8)
        self.running = False

    def loop(self):
        self.running = True
        self.tick()

    def tick(self):
        if not self.running or not self.host.win.winfo_exists():
            return
        from PIL import Image, ImageGrab, ImageTk

        factor = int(self.factor.get() or "2")
        x = self.host.win.winfo_pointerx()
        y = self.host.win.winfo_pointery()
        half = 80
        box = (x - half, y - half, x + half, y + half)
        try:
            im = ImageGrab.grab(bbox=box)
        except Exception as exc:
            self.host.write(str(exc))
            return
        shown = im.resize((im.width * factor, im.height * factor), Image.Resampling.NEAREST)
        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.host.win.after(80, self.tick)
