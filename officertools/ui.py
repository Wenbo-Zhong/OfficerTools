# -*- coding: utf-8 -*-
"""Launcher and tool windows. Sizes follow the real monitor DPI."""
from __future__ import annotations

import json
import math
import os
import sys
import time
import queue
import threading
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
from officertools.icons import category_colors, navigation_icon, tool_icon
from officertools.theme import palette, system_theme
from officertools.paths import application_root

STATE_PATH = Path(os.environ.get("APPDATA") or str(Path.home())) / "OfficerTools" / "state.json"

# Shared semantic colors also cover individual tool windows.
globals().update(palette("light"))
CURRENT_THEME = "light"


class ScrollArea(object):
    """Vertical scroller whose wheel works over the child widgets, not only the bare canvas."""

    def __init__(self, parent, bg):
        self._animation = None
        self._target = None
        self._last_frame = 0.0
        self.canvas = tk.Canvas(parent, bg=bg, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(
            parent, orient="vertical", command=self._scrollbar,
            style="{}.{}.Vertical.TScrollbar".format("Side" if bg == SIDE else "Page", CURRENT_THEME),
        )
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Destroy>", lambda e: self._stop())
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas._scroll_area = self
        self.inner._scroll_area = self

    def _on_inner(self, _event):
        self._update_region()

    def _update_region(self):
        bounds = self.canvas.bbox("all")
        if bounds:
            height = max(bounds[3], self.canvas.winfo_height())
            self.canvas.configure(scrollregion=(0, 0, bounds[2], height))
            if self._target is not None:
                self._target = min(self._target, max(0, height - self.canvas.winfo_height()))

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self.win, width=event.width)
        self._update_region()

    def _stop(self):
        if self._animation is not None:
            self.canvas.after_cancel(self._animation)
            self._animation = None
        self._target = None

    def reset(self):
        self._stop()
        self.canvas.yview_moveto(0)

    def _scrollbar(self, *args):
        self._stop()
        self.canvas.yview(*args)

    def _frame(self):
        self._animation = None
        bounds = self.canvas.bbox("all")
        if not bounds or self._target is None:
            return
        height = max(bounds[3], self.canvas.winfo_height())
        self._target = max(0, min(self._target, height - self.canvas.winfo_height()))
        position = self.canvas.yview()[0] * height
        now = time.perf_counter()
        elapsed = min(0.05, now - self._last_frame)
        self._last_frame = now
        remaining = self._target - position
        if abs(remaining) <= 1:
            self.canvas.yview_moveto(self._target / height)
            self._target = None
            return
        step = remaining * (1 - math.exp(-elapsed / 0.055))
        # Canvas positions are integral pixels; avoid rounding away the last steps.
        if abs(step) < 1:
            step = math.copysign(1, remaining)
        self.canvas.yview_moveto((position + step) / height)
        self._animation = self.canvas.after(16, self._frame)

    def wheel(self, event):
        if getattr(event, "num", None) == 4:
            distance = -80
        elif getattr(event, "num", None) == 5:
            distance = 80
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return
            distance = -delta * 3 if sys.platform == "darwin" else -delta / 120 * 80
        height = max(self.inner.winfo_height(), self.canvas.winfo_height())
        scale = float(self.canvas.tk.call("tk", "scaling")) * 72 / 96
        position = self.canvas.yview()[0] * height
        origin = self._target if self._target is not None else position
        self._target = max(0, min(origin + distance * scale, height - self.canvas.winfo_height()))
        if self._animation is None:
            self._last_frame = time.perf_counter()
            self._animation = self.canvas.after(16, self._frame)

    def touchpad(self, _event, delta_x, delta_y):
        self._stop()
        self.canvas.tk.call("tk::ScrollByPixels", str(self.canvas), delta_x, delta_y)


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

    def on_touchpad(event):
        widget = getattr(event, "widget", None)
        if widget is None:
            x, y = root.winfo_pointerxy()
            widget = root.winfo_containing(x, y)
        while widget is not None:
            if isinstance(widget, tk.Text):
                return
            area = getattr(widget, "_scroll_area", None)
            if area is not None:
                try:
                    dx, dy = root.tk.call("tk::PreciseScrollDeltas", event.delta)
                    dx, dy = float(dx), float(dy)
                except (tk.TclError, TypeError, ValueError):
                    return "break"
                handler = getattr(area, "touchpad", None)
                if handler:
                    handler(event, dx, dy)
                else:
                    canvas = getattr(area, "canvas", area)
                    canvas.tk.call("tk::ScrollByPixels", str(canvas), dx, dy)
                return "break"
            widget = getattr(widget, "master", None)

    # Tk 9 emits high-resolution trackpad input as a separate event. Older
    # Tk releases do not recognize this binding, so keep mouse-wheel support.
    try:
        root.bind_all("<TouchpadScroll>", on_touchpad)
    except tk.TclError:
        pass


def pill(parent, text, command, app, primary=False):
    if sys.platform == "darwin":
        return ttk.Button(
            parent, text=text, command=command, style="TButton",
            default="active" if primary else "normal", cursor="hand2",
        )
    return ttk.Button(
        parent, text=text, command=command,
        style="Primary.Pill.TButton" if primary else "Pill.TButton",
        cursor="hand2",
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
        self.theme = system_theme()
        globals()["CURRENT_THEME"] = self.theme
        self.colors = palette(self.theme)
        globals().update(self.colors)
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
        self._theme_job = self.root.after(3000, self._watch_theme)
        self.root.bind("<Destroy>", self._on_destroy, add="+")
        if initial:
            root.withdraw()
            window = ToolWindow(self, BY_ID[initial])
            window.win.protocol("WM_DELETE_WINDOW", root.destroy)
            return
        self._build()

    def _watch_theme(self):
        if self._theme_job is not None:
            self.root.after_cancel(self._theme_job)
        self.apply_theme(system_theme())
        self._theme_job = self.root.after(3000, self._watch_theme)

    def _on_destroy(self, event):
        if event.widget is self.root and self._theme_job is not None:
            self.root.after_cancel(self._theme_job)
            self._theme_job = None

    def apply_theme(self, name):
        """Recolor in place so open forms, logs, focus and scroll positions survive."""
        name = "dark" if name == "dark" else "light"
        if name == self.theme:
            return
        previous = self.colors
        old_categories = category_colors(self.theme == "dark")
        self.theme = name
        globals()["CURRENT_THEME"] = name
        self.colors = palette(name)
        replacements = {previous[key]: value for key, value in self.colors.items()}
        new_categories = category_colors(name == "dark")
        for category, pair in old_categories.items():
            replacements.update(zip(pair, new_categories[category]))
        globals().update(self.colors)
        images = {}
        for (tool_id, pixels, dark), photo in list(getattr(self, "_icon_cache", {}).items()):
            if dark != (name == "dark"):
                size = round(pixels / self.scale)
                images[str(photo)] = tool_icon(self, BY_ID[tool_id], size)
        self._style_ttk()

        def recolor(widget):
            options = widget.keys()
            changes = {}
            for option in ("background", "foreground", "activebackground", "activeforeground",
                           "highlightbackground", "highlightcolor", "insertbackground",
                           "selectbackground", "selectforeground", "disabledforeground"):
                if option in options:
                    current = str(widget.cget(option))
                    if current in replacements:
                        changes[option] = replacements[current]
            if "image" in options:
                photo = images.get(str(widget.cget("image")))
                if photo is not None:
                    changes["image"] = photo
            if changes:
                widget.configure(**changes)
            if isinstance(widget, ttk.Scrollbar):
                prefix = "Side" if str(widget.cget("style")).startswith("Side") else "Page"
                widget.configure(style="{}.{}.Vertical.TScrollbar".format(prefix, self.theme))
            elif isinstance(widget, tk.Scrollbar):
                widget.configure(bg=SCROLL, activebackground=SCROLL_HOVER, troughcolor=CARD)
            for child in widget.winfo_children():
                recolor(child)

        recolor(self.root)
        if hasattr(self, "nav_buttons"):
            self._paint_nav()

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
        self.font_small = tkfont.Font(family=family, size=10)
        self.font_title = tkfont.Font(family=family, size=20, weight="bold")
        self.font_card = tkfont.Font(family=family, size=12, weight="bold")

    def _style_ttk(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("aqua" if sys.platform == "darwin" else "clam")
        except tk.TclError:
            pass
        style.configure(".", background=PAGE, foreground=INK, font=self.font)
        style.configure("TFrame", background=PAGE)
        style.configure("TLabel", background=PAGE, foreground=INK)
        style.configure("TEntry", fieldbackground=CARD, foreground=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure("TCombobox", fieldbackground=CARD, background=CARD, foreground=INK, arrowcolor=INK)
        style.map("TCombobox", fieldbackground=[("readonly", CARD)])
        style.map("TCombobox", foreground=[("readonly", INK)], selectbackground=[("readonly", CARD)], selectforeground=[("readonly", INK)])
        style.configure("TCombobox", selectbackground=ACCENT, selectforeground=ON_ACCENT)
        style.configure("TCheckbutton", background=PAGE, foreground=INK)
        style.map("TCheckbutton", background=[("active", PAGE)], foreground=[("active", INK)],
                  indicatorbackground=[("selected", ACCENT), ("!selected", CARD)])
        if sys.platform == "darwin":
            style.configure("TButton", font=self.font, padding=(10, 4))
        else:
            style.configure("Pill.TButton", background=CARD, foreground=INK,
                            bordercolor=LINE, focuscolor=ACCENT, borderwidth=1,
                            relief="flat", padding=(12, 6), font=self.font)
            style.map("Pill.TButton", background=[("pressed", BUTTON_HOVER), ("active", BUTTON_HOVER)],
                      foreground=[("disabled", MUTED)])
            style.configure("Primary.Pill.TButton", background=ACCENT, foreground=ON_ACCENT,
                            bordercolor=ACCENT, focuscolor=ACCENT_ACTIVE, borderwidth=1,
                            relief="flat", padding=(12, 6), font=self.font)
            style.map("Primary.Pill.TButton", background=[("pressed", ACCENT_ACTIVE), ("active", ACCENT_ACTIVE)],
                      foreground=[("disabled", ON_ACCENT)])
        style.configure("App.Horizontal.TProgressbar", thickness=self.px(6),
                        background=ACCENT, troughcolor=CARD, bordercolor=LINE,
                        lightcolor=ACCENT, darkcolor=ACCENT, borderwidth=0, relief="flat")
        self.root.option_add("*selectBackground", ACCENT)
        self.root.option_add("*selectForeground", ON_ACCENT)
        self.root.option_add("*TCombobox*Listbox.background", CARD)
        self.root.option_add("*TCombobox*Listbox.foreground", INK)
        self._style_scrollbars(style)

    def _style_scrollbars(self, style):
        """Rounded image elements avoid platform arrows and raised native borders."""
        from PIL import Image, ImageDraw, ImageTk

        if not hasattr(self, "_scroll_images"):
            self._scroll_images = []
        for name, track, normal, hover in (
            ("Page", PAGE, SCROLL, SCROLL_HOVER),
            ("Side", SIDE, SIDE_SCROLL, SIDE_SCROLL_HOVER),
        ):
            element = name + "." + self.theme + ".Scrollbar.thumb"
            scrollbar = "{}.{}.Vertical.TScrollbar".format(name, self.theme)
            if element in style.element_names():
                continue
            images = []
            for color in (normal, hover, ACCENT, track):
                width, height = self.px(10), self.px(32)
                image = Image.new("RGB", (width * 3, height * 3), track)
                ImageDraw.Draw(image).rounded_rectangle(
                    (self.px(2) * 3, 0, (width - self.px(2)) * 3 - 1, height * 3 - 1),
                    radius=self.px(3) * 3, fill=color,
                )
                photo = ImageTk.PhotoImage(
                    image.resize((width, height), Image.Resampling.LANCZOS), master=self.root,
                )
                images.append(photo)
            self._scroll_images.extend(images)
            # Reuse element names if another App is constructed on the same Tcl interpreter.
            if element not in style.element_names():
                style.element_create(
                    element, "image", images[0], ("disabled", images[3]),
                    ("pressed", images[2]), ("active", images[1]),
                    border=self.px(5), sticky="nsew",
                )
            style.layout(scrollbar, [
                ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                    (element, {"expand": "1", "sticky": "nsew"}),
                ]}),
            ])
            style.configure(
                scrollbar, troughcolor=track, background=track, bordercolor=track,
                lightcolor=track, darkcolor=track, borderwidth=0, relief="flat",
                gripcount=0, arrowsize=0,
            )

    def _build(self):
        side = tk.Frame(self.root, bg=SIDE, width=self.px(216))
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="OfficerTools", font=self.font_card, bg=SIDE, fg=SIDE_TITLE).pack(anchor="w", padx=self.px(22), pady=(self.px(30), 0))
        tk.Label(side, text="让办公更轻松", font=self.font_small, bg=SIDE, fg=SIDE_MUTED).pack(anchor="w", padx=self.px(22), pady=(self.px(6), self.px(26)))
        tk.Label(side, text="工作空间", font=self.font_small, bg=SIDE, fg=SIDE_MUTED).pack(anchor="w", padx=self.px(24), pady=(0, self.px(8)))
        about = tk.Label(side, text="关于与开源许可", font=self.font_small, bg=SIDE, fg=SIDE_MUTED,
                         cursor="hand2", padx=8, pady=5)
        about.bind("<Button-1>", lambda _event: self.show_about())
        about.bind("<Enter>", lambda _event: about.configure(fg=SIDE_SELECTED))
        about.bind("<Leave>", lambda _event: about.configure(fg=SIDE_MUTED))
        about.pack(side="bottom", pady=self.px(20))
        nav_host = tk.Frame(side, bg=SIDE)
        nav_host.pack(fill="both", expand=True)
        self.nav_area = ScrollArea(nav_host, SIDE)
        self.nav_buttons = {}
        for name in ["全部", "收藏", "最近"] + CATEGORIES:
            btn = tk.Frame(self.nav_area.inner, bg=SIDE, cursor="hand2")
            btn.pack(fill="x", padx=self.px(12), pady=1)
            icon = tk.Label(btn, image=navigation_icon(self, name, SIDE_INK), bg=SIDE)
            icon.pack(side="left", padx=(self.px(14), self.px(12)), pady=self.px(11))
            label = tk.Label(btn, text=name, font=self.font, bg=SIDE, fg=SIDE_INK, anchor="w")
            label.pack(side="left", fill="x", expand=True, padx=(0, self.px(14)))
            for widget in (btn, icon, label):
                widget.bind("<Button-1>", lambda e, n=name: self.pick_bucket(n))
            self.nav_buttons[name] = btn
        self._paint_nav()

        main = tk.Frame(self.root, bg=PAGE)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=PAGE)
        top.pack(fill="x", padx=self.px(28), pady=(self.px(26), self.px(10)))
        tk.Label(top, text="全部工具", font=self.font_title, bg=PAGE, fg=INK).pack(side="left")
        self.heading = top.winfo_children()[0]
        search_wrap = tk.Frame(top, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        search_wrap.pack(side="right")
        icon_slot = tk.Frame(search_wrap, bg=CARD, width=self.px(36), height=self.px(38))
        icon_slot.pack(side="left", fill="y")
        icon_slot.pack_propagate(False)
        search_icon = tk.Label(icon_slot, text="⌕", font=(self.family, 18), bg=CARD, fg=MUTED)
        search_icon.place(relx=0.5, rely=0.5, anchor="center")
        placeholder = "搜索工具"
        search_text = tk.StringVar(value=placeholder)
        entry = tk.Entry(search_wrap, textvariable=search_text, font=self.font, bg=CARD, fg=MUTED,
                         relief="flat", width=22, insertbackground=INK, highlightthickness=0,
                         borderwidth=0)
        entry.pack(side="left", padx=(0, self.px(5)), pady=self.px(8))

        def sync_search(*_):
            value = search_text.get()
            is_placeholder = value == placeholder
            entry.configure(fg=MUTED if is_placeholder else INK)
            self.query.set("" if is_placeholder else value)

        def focus_search(_event=None):
            if search_text.get() == placeholder:
                search_text.set("")
                entry.configure(fg=INK)

        def blur_search(_event=None):
            if not search_text.get():
                search_text.set(placeholder)

        search_text.trace_add("write", sync_search)
        self.query.trace_add("write", lambda *_: self.refresh())
        entry.bind("<FocusIn>", focus_search)
        entry.bind("<FocusOut>", blur_search)
        self.root.bind("<Control-f>", lambda e: (entry.focus_set(), "break"))
        if sys.platform == "darwin":
            self.root.bind("<Command-f>", lambda e: (entry.focus_set(), "break"))
        entry.bind("<Escape>", lambda e: (search_text.set(""), "break"))
        clear_slot = tk.Frame(search_wrap, bg=CARD, width=self.px(34), height=self.px(38))
        clear_slot.pack(side="left", fill="y", padx=(0, self.px(3)))
        clear_slot.pack_propagate(False)
        clear = tk.Label(clear_slot, text="×", font=(self.family, 18), bg=CARD, fg=MUTED,
                         cursor="hand2")
        clear.place(relx=0.5, rely=0.5, anchor="center")
        clear.bind("<Button-1>", lambda _event: (search_text.set(""), entry.focus_set()))
        clear.bind("<Enter>", lambda _event: clear.configure(fg=INK))
        clear.bind("<Leave>", lambda _event: clear.configure(fg=MUTED))

        info = tk.Frame(main, bg=PAGE)
        info.pack(fill="x", padx=self.px(28), pady=(0, self.px(16)))
        self.result_label = tk.Label(info, font=self.font_small, bg=PAGE, fg=MUTED)
        self.result_label.pack(side="left")
        shortcut = "⌘ F 搜索" if sys.platform == "darwin" else "Ctrl + F 搜索"
        tk.Label(info, text=shortcut + "  ·  ☆ 收藏常用工具", font=self.font_small, bg=PAGE, fg=MUTED).pack(side="right")

        list_host = tk.Frame(main, bg=PAGE)
        list_host.pack(fill="both", expand=True, padx=self.px(16), pady=(0, self.px(12)))
        self.area = ScrollArea(list_host, PAGE)
        self.canvas = self.area.canvas
        self.cards = self.area.inner
        self.canvas.bind("<Configure>", self._on_canvas_configure, add="+")
        self.refresh()

    def show_about(self):
        win = tk.Toplevel(self.root)
        win.title("关于 OfficerTools")
        win.configure(bg=PAGE)
        win.geometry(self._geo(600, 400))
        tk.Label(win, text="OfficerTools", font=self.font_title, bg=PAGE, fg=INK).pack(anchor="w", padx=self.px(24), pady=(self.px(24), self.px(12)))
        tk.Label(win, text="Copyright © 2026 Wenbo Zhong\n本项目采用 AGPL-3.0-or-later 许可证。\n\nWindows 完整包包含 Ghostscript、Poppler 和 FFmpeg。\n各组件的版权与许可证归其作者所有。\n许可证、对应源码和构建材料随完整发布包提供。",
                 font=self.font, bg=PAGE, fg=MUTED, justify="left", wraplength=self.px(550)).pack(anchor="w", padx=self.px(24))
        root = application_root()
        bar = tk.Frame(win, bg=PAGE)
        bar.pack(anchor="w", padx=self.px(24), pady=self.px(20))
        pill(bar, "查看许可证", lambda: open_folder(root / "licenses" if (root / "licenses").is_dir() else root), self).pack(side="left")
        pill(bar, "查看源码", lambda: open_folder(root / "sources" if (root / "sources").is_dir() else root), self).pack(side="left", padx=self.px(10))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure("cards", width=event.width)
        cols = 3 if event.width >= self.px(760) else (2 if event.width >= self.px(520) else 1)
        if cols != self._cols:
            self._cols = cols
            self.refresh()

    def _paint_nav(self):
        for name, btn in self.nav_buttons.items():
            active = name == self.bucket
            bg = SIDE_ACTIVE if active else SIDE
            fg = SIDE_SELECTED if active else SIDE_INK
            btn.configure(bg=bg)
            icon, label = btn.winfo_children()
            icon.configure(bg=bg, image=navigation_icon(self, name, fg))
            label.configure(bg=bg, fg=fg)

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
        result_key = (self.selected_bucket(), self.query.get().strip().lower())
        if result_key != getattr(self, "_result_key", None):
            self._result_key = result_key
            self.area.reset()
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
        self.result_label.configure(text="{} 个工具{}".format(len(tools), "  ·  搜索结果" if query else "  ·  选择工具即可开始"))
        cols = self._cols or 3
        if not tools:
            message = "没有找到匹配的工具\n试试工具名称、类别或功能关键词。" if query else ("还没有收藏工具\n点击工具卡片右上角的 ☆，把常用工具放在这里。" if bucket == "收藏" else "还没有使用记录\n打开一个工具后，就能在这里快速找到它。")
            tk.Label(self.cards, text=message, font=self.font, bg=PAGE, fg=MUTED, justify="center", pady=self.px(64)).grid(row=0, column=0, columnspan=cols, sticky="ew")
            return
        for col in range(cols):
            self.cards.grid_columnconfigure(col, weight=1, uniform="card")
        for index, tool in enumerate(tools):
            self._card(tool, index // cols, index % cols)

    def _card(self, tool: Tool, row, col):
        shell = tk.Frame(self.cards, bg=PAGE)
        shell.grid(row=row, column=col, sticky="nsew", padx=self.px(8), pady=self.px(8))
        frame = tk.Frame(shell, bg=CARD, highlightbackground=LINE, highlightthickness=1, cursor="hand2", takefocus=True)
        frame.pack(fill="both", expand=True)
        head = tk.Frame(frame, bg=CARD)
        head.pack(fill="x", padx=self.px(16), pady=(self.px(14), 0))
        icon = tk.Label(head, image=tool_icon(self, tool), bg=CARD)
        icon.pack(side="left")
        star = "★" if tool.id in self.state["favorites"] else "☆"
        mark = tk.Label(head, text=star, font=self.font_card, bg=CARD, fg=ACCENT if star == "★" else MUTED,
                        cursor="hand2", padx=5, pady=2)
        mark.bind("<Button-1>", lambda _event, t=tool: self.toggle_fav(t))
        mark.pack(side="right", anchor="n")
        name = tk.Label(frame, text=tool.name, font=self.font_card, bg=CARD, fg=INK, anchor="w")
        name.pack(fill="x", padx=self.px(16), pady=(self.px(12), 0))
        summary = tk.Label(frame, text=tool.summary, font=self.font_small, bg=CARD, fg=MUTED, anchor="w", justify="left", wraplength=self.px(280))
        summary.pack(fill="x", padx=self.px(16), pady=(self.px(6), self.px(16)))
        footer = tk.Frame(frame, bg=CARD)
        footer.pack(side="bottom", fill="x", padx=self.px(16), pady=(0, self.px(14)))
        color, tint = category_colors(self.theme == "dark")[tool.category]
        category = tk.Label(footer, text=tool.category, font=self.font_small, bg=tint, fg=color, padx=self.px(7), pady=self.px(2))
        category.pack(side="left")
        arrow = tk.Label(footer, text="打开 →", font=self.font_small, bg=CARD, fg=MUTED)
        arrow.pack(side="right")
        summary.bind("<Configure>", lambda e: summary.configure(wraplength=max(self.px(80), e.width)))

        def open_tool(_event=None, t=tool):
            self.open_tool(t)

        def hover(_event=None, on=True):
            frame.configure(highlightbackground=ACCENT if on else LINE)

        frame.bind("<Return>", open_tool)
        frame.bind("<space>", open_tool)
        frame.bind("<FocusIn>", lambda e: hover(on=True))
        frame.bind("<FocusOut>", lambda e: hover(on=False))
        for widget in (frame, head, icon, name, summary, footer, category, arrow):
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
        if self.bucket == "最近":
            self.refresh()
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
        self.events = queue.Queue()
        self.worker = None
        self.cancel_event = threading.Event()
        self.output_folder = None
        self._wrapping_labels = []
        pad = app.px(22)
        host = tk.Frame(self.win, bg=PAGE)
        host.pack(fill="both", expand=True)
        self.area = ScrollArea(host, PAGE)
        frm = tk.Frame(self.area.inner, bg=PAGE)
        frm.pack(fill="both", expand=True, padx=pad, pady=pad)
        header = tk.Frame(frm, bg=PAGE)
        header.pack(fill="x", pady=(0, app.px(12)))
        tk.Label(header, image=tool_icon(app, tool, 64), bg=PAGE).pack(side="left", padx=(0, app.px(14)))
        titles = tk.Frame(header, bg=PAGE)
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text=tool.category, font=app.font_small, bg=PAGE, fg=category_colors(app.theme == "dark")[tool.category][0]).pack(anchor="w")
        tk.Label(titles, text=tool.name, font=app.font_title, bg=PAGE, fg=INK).pack(anchor="w", pady=(2, 0))
        summary = tk.Label(frm, text=tool.summary, font=app.font, bg=PAGE, fg=MUTED,
                           wraplength=app.px(700), justify="left", anchor="w")
        summary.pack(anchor="w", fill="x", pady=(4, app.px(14)))
        self._wrapping_labels.append(summary)
        if tool.id in UI_ONLY or tool.id == "calc":
            self._special(frm)
        else:
            self._form(frm)
        frm.bind("<Configure>", self._fit_wrapping_labels, add="+")
        self.log = scrolledtext.ScrolledText(
            frm, height=10, font=app.font, wrap="word",
            bg=CARD, fg=INK, insertbackground=INK, relief="flat",
            highlightbackground=LINE, highlightthickness=1, bd=0, padx=10, pady=8,
        )
        self.log.pack(fill="x", pady=(pad, 0))
        self.log.vbar.configure(bg=SCROLL, activebackground=SCROLL_HOVER, troughcolor=CARD, relief="flat", bd=0)

    def _fit_wrapping_labels(self, event):
        width = max(self.app.px(140), min(self.app.px(700), event.width - self.app.px(8)))
        for label in self._wrapping_labels:
            label.configure(wraplength=width)

    def _form(self, frm):
        app = self.app
        for field in self.tool.fields:
            tk.Label(frm, text=field.label, font=app.font_small, bg=PAGE, fg=MUTED).pack(anchor="w", pady=(app.px(8), 2))
            if field.kind in ("text", "number"):
                var = tk.StringVar(value=field.default)
                tk.Entry(frm, textvariable=var, show="•" if "password" in field.key else "", font=app.font, bg=CARD, fg=INK, relief="flat", highlightbackground=LINE, highlightthickness=1, insertbackground=INK).pack(fill="x", ipady=app.px(3))
                self.vars[field.key] = var
                if field.key == "bbox":
                    pill(frm,"在屏幕上选择区域",lambda v=var:self.select_region(v),app).pack(anchor="w",pady=4)
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
                tk.Entry(row, textvariable=var, font=app.font, bg=CARD, fg=INK, relief="flat", highlightbackground=LINE, highlightthickness=1, insertbackground=INK).pack(side="left", fill="x", expand=True, ipady=app.px(3))
                pill(row, "浏览", lambda f=field, v=var: self.browse(f, v), app).pack(side="left", padx=(8, 0))
                if field.kind == "files":
                    pill(row, "+文件夹", lambda v=var: self.add_folder(v), app).pack(side="left", padx=4)
                    pill(row, "排序/移除", lambda v=var:self.manage_queue(v), app).pack(side="left")
                self.vars[field.key] = var
            if field.help:
                help_label = tk.Label(frm, text=field.help, font=app.font_small, bg=PAGE, fg=MUTED,
                                      wraplength=app.px(700), justify="left", anchor="w")
                help_label.pack(anchor="w", fill="x", pady=(2, 0))
                self._wrapping_labels.append(help_label)
        bar = tk.Frame(frm, bg=PAGE)
        bar.pack(fill="x", pady=(app.px(16), 0))
        pill(bar, "开始", self.execute, app, primary=True).pack(side="left")
        pill(bar, "打开输出文件夹", self.open_out, app).pack(side="left", padx=8)
        pill(bar, "输出位置", self.choose_output, app).pack(side="left")
        pill(bar, "取消", self.cancel_event.set, app).pack(side="left", padx=8)
        self.progress = ttk.Progressbar(frm, maximum=100, style="App.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(8, 0))
        self.win.bind("<Destroy>",lambda event:self.cancel_event.set() if event.widget==self.win else None,add="+")

    def manage_queue(self,var):
        dialog=tk.Toplevel(self.win)
        dialog.title("文件队列：按列表顺序处理")
        dialog.geometry(self.app._geo(700,400))
        listing=tk.Listbox(dialog,selectmode="extended",font=self.app.font)
        listing.pack(fill="both",expand=True,padx=12,pady=12)
        for path in var.get().split("|"):
            if path: listing.insert("end",path)
        def move(delta):
            selected=list(listing.curselection())
            if not selected or min(selected)+delta<0 or max(selected)+delta>=listing.size(): return
            items=list(listing.get(0,"end"))
            for index in (selected if delta<0 else reversed(selected)):
                items[index],items[index+delta]=items[index+delta],items[index]
            listing.delete(0,"end")
            for item in items: listing.insert("end",item)
            for index in selected: listing.selection_set(index+delta)
        def remove():
            for index in reversed(listing.curselection()): listing.delete(index)
        def save():
            var.set("|".join(listing.get(0,"end")))
            dialog.destroy()
        bar=tk.Frame(dialog)
        bar.pack(fill="x",padx=12,pady=8)
        for label,command in (("上移",lambda:move(-1)),("下移",lambda:move(1)),("移除",remove),("清空",lambda:listing.delete(0,"end")),("完成",save)):
            pill(bar,label,command,self.app).pack(side="left",padx=4)

    def choose_output(self):
        path = filedialog.askdirectory(parent=self.win)
        if path:
            self.output_folder = Path(path)
            self.write("输出到：" + path)

    def select_region(self,var):
        from PIL import ImageGrab, ImageTk
        root_visible = self.app.root.state() != "withdrawn"
        self.win.withdraw()
        self.app.root.withdraw()
        def show():
            try:
                capture=ImageGrab.grab(all_screens=True)
                left=top=0
                if sys.platform=="win32":
                    import ctypes
                    left=ctypes.windll.user32.GetSystemMetrics(76)
                    top=ctypes.windll.user32.GetSystemMetrics(77)
                overlay=tk.Toplevel(self.win)
                overlay.overrideredirect(True)
                overlay.attributes("-topmost",True)
                overlay.geometry("{}x{}{:+d}{:+d}".format(capture.width,capture.height,left,top))
                canvas=tk.Canvas(overlay,highlightthickness=0,cursor="crosshair")
                canvas.pack(fill="both",expand=True)
                photo=ImageTk.PhotoImage(capture)
                canvas.photo=photo
                canvas.create_image(0,0,anchor="nw",image=photo)
                canvas.create_text(24,24,anchor="nw",text="拖动选择区域，Esc 取消",fill="#ff3355",font=self.app.font)
                state={}
                def finish(event=None):
                    overlay.destroy()
                    self.win.deiconify()
                    if root_visible:
                        self.app.root.deiconify()
                def down(event):
                    state["start"]=(event.x,event.y)
                def drag(event):
                    if "start" in state:
                        canvas.delete("selection")
                        canvas.create_rectangle(*state["start"],event.x,event.y,outline="#ff3355",width=3,tags="selection")
                def up(event):
                    if "start" in state:
                        x,y=state["start"]
                        w,h=abs(event.x-x),abs(event.y-y)
                        if w>1 and h>1:
                            # Even dimensions are required by the MP4 encoder.
                            var.set("{},{},{},{}".format(left+min(x,event.x),top+min(y,event.y),w-w%2,h-h%2))
                    finish()
                canvas.bind("<ButtonPress-1>",down)
                canvas.bind("<B1-Motion>",drag)
                canvas.bind("<ButtonRelease-1>",up)
                overlay.bind("<Escape>",finish)
                overlay.focus_force()
            except Exception as exc:
                self.win.deiconify()
                if root_visible: self.app.root.deiconify()
                self.write(str(exc))
        self.win.after(200,show)

    def add_folder(self, var):
        path = filedialog.askdirectory(parent=self.win)
        if path:
            current = [p for p in var.get().split("|") if p]
            current.extend(str(p) for p in sorted(Path(path).rglob("*")) if p.is_file())
            var.set("|".join(dict.fromkeys(current)))

    def browse(self, field, var):
        if field.kind == "dir":
            path = filedialog.askdirectory(parent=self.win)
            if path:
                var.set(path)
            return
        if field.kind == "files":
            paths = filedialog.askopenfilenames(parent=self.win)
            if paths:
                current = [p for p in var.get().split("|") if p]
                var.set("|".join(dict.fromkeys(current + list(paths))))
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
        folder = self.output_folder or state_dir() / "output" / self.tool.id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def write(self, text):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def execute(self):
        if self.worker and self.worker.is_alive():
            self.write("正在处理，请等待完成或取消。")
            return
        self.log.delete("1.0", "end")
        self.cancel_event.clear()
        job = Job(self.tool.id, self.values(), self.outdir(),
                  progress=lambda value, text: self.events.put(("progress", (value, text))),
                  cancel=self.cancel_event)
        def work():
            try:
                self.events.put(("result", run(job)))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        self.worker = threading.Thread(target=work, daemon=True)
        def start_worker():
            self.worker.start()
            self.poll_task()
        if self.tool.id in ("ocr-screen","screenshot"):
            self.capture_visibility=self.app.root.state()!="withdrawn"
            self.win.withdraw()
            self.app.root.withdraw()
            self.win.after(200,start_worker)
        else:
            start_worker()

    def restore_capture_windows(self):
        if hasattr(self,"capture_visibility"):
            if self.capture_visibility: self.app.root.deiconify()
            self.win.deiconify()
            del self.capture_visibility

    def poll_task(self):
        if not self.win.winfo_exists():
            self.cancel_event.set()
            return
        while not self.events.empty():
            kind, data = self.events.get_nowait()
            if kind == "progress":
                self.progress.configure(value=data[0])
                if data[1]=="屏幕截图已完成": self.restore_capture_windows()
                if data[1]:
                    self.write(data[1])
            elif kind == "error":
                self.restore_capture_windows()
                self.write(data)
            else:
                self.restore_capture_windows()
                self.progress.configure(value=100)
                self.write(data.message)
                for path in data.files:
                    self.write(str(path))
        if self.worker.is_alive() or not self.events.empty():
            self.win.after(80, self.poll_task)

    def open_out(self):
        open_folder(self.outdir())

    def _special(self, frm):
        tid = self.tool.id
        if tid == "calc":
            self._form(frm)
            return
        if tid == "pick-color":
            self.special = ColorTool(self)
        elif tid == "image-viewer":
            self.special = ViewerTool(self)
        elif tid == "pdf-reader":
            self.special = PdfViewerTool(self)
        elif tid == "annotate":
            self.special = AnnotateTool(self)
        elif tid == "magnifier":
            self.special = MagnifierTool(self)


class ColorTool(object):
    def __init__(self, host: ToolWindow):
        self.host = host
        self.image = None
        pill(host.win, "打开图片", self.load, host.app, primary=True).pack(anchor="w", padx=22)
        pill(host.win,"从屏幕取色",self.capture,host.app).pack(anchor="w",padx=22,pady=4)
        pill(host.win,"复制颜色",self.copy,host.app).pack(anchor="w",padx=22)
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
        from PIL import Image, ImageTk

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

    def capture(self):
        from PIL import ImageGrab
        root_visible=self.host.app.root.state()!="withdrawn"
        self.host.win.withdraw()
        self.host.app.root.withdraw()
        def grab():
            try:
                self.image=ImageGrab.grab(all_screens=True).convert("RGB")
            except Exception as exc:
                self.host.write(str(exc))
            finally:
                if root_visible: self.host.app.root.deiconify()
                self.host.win.deiconify()
            if self.image: self._draw()
        self.host.win.after(200,grab)

    def copy(self):
        if hasattr(self,"hex_value"):
            self.host.win.clipboard_clear()
            self.host.win.clipboard_append(self.hex_value)

    def pick(self, event):
        if self.image is None:
            return
        x = min(self.image.width - 1, max(0, int(event.x / self.view_scale)))
        y = min(self.image.height - 1, max(0, int(event.y / self.view_scale)))
        r, g, b = self.image.getpixel((x, y))
        hexv = "#{:02X}{:02X}{:02X}".format(r, g, b)
        self.hex_value=hexv
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

        self.canvas.wheel = self._wheel
        self.canvas.touchpad = self._touchpad

    def _touchpad(self, _event, delta_x, delta_y):
        self.canvas.tk.call("tk::ScrollByPixels", str(self.canvas), delta_x, delta_y)

    def _wheel(self, event):
        delta = getattr(event, "delta", 0)
        if getattr(event, "num", None) == 4:
            step = -3
        elif getattr(event, "num", None) == 5:
            step = 3
        elif delta:
            step = int(-delta / 120 * 3) or (-3 if delta > 0 else 3)
        else:
            return
        if getattr(event, "state", 0) & 0x1:
            self.canvas.xview_scroll(step, "units")
        else:
            self.canvas.yview_scroll(step, "units")

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


class PdfViewerTool(ViewerTool):
    def __init__(self, host):
        super().__init__(host)
        self.document = None
        self.page = 0
        self.page_number = tk.StringVar(value="1")
        self.search = tk.StringVar()
        if sys.platform == "darwin":
            navigation = tk.Frame(host.win, bg=PAGE)
            navigation.pack(fill="x", padx=22, pady=(4, 1))
            search_bar = tk.Frame(host.win, bg=PAGE)
            search_bar.pack(fill="x", padx=22, pady=(1, 4))
        else:
            navigation = tk.Frame(host.win, bg=PAGE)
            navigation.pack(fill="x", padx=22, pady=4)
            search_bar = navigation
        pill(navigation,"上一页",lambda:self.go(self.page-1),host.app).pack(side="left")
        pill(navigation,"下一页",lambda:self.go(self.page+1),host.app).pack(side="left",padx=4)
        tk.Entry(navigation,textvariable=self.page_number,width=5).pack(side="left")
        pill(navigation,"跳页",self.jump,host.app).pack(side="left",padx=4)
        tk.Entry(search_bar,textvariable=self.search,width=14).pack(side="left")
        pill(search_bar,"查找下一页",self.find,host.app).pack(side="left",padx=4)
        self.canvas.wheel = self._wheel_page
        self.canvas.touchpad = self._touchpad_page
        host.win.bind("<Destroy>",self.close,add="+")

    def _wheel_page(self, event):
        """Scroll within a page, then let macOS wheel/trackpad gestures change pages."""
        if sys.platform != "darwin" or not self.document:
            return self._wheel(event)
        number = getattr(event, "num", None)
        delta = getattr(event, "delta", 0)
        direction = -1 if number == 4 or delta > 0 else 1 if number == 5 or delta < 0 else 0
        if not direction:
            return
        first, last = self.canvas.yview()
        at_edge = (direction > 0 and last >= 0.999) or (direction < 0 and first <= 0.001)
        if at_edge:
            next_page = self.page + direction
            if 0 <= next_page < len(self.document):
                self.go(next_page)
                self.canvas.yview_moveto(0 if direction > 0 else 1)
            return
        step = -3 if direction < 0 else 3
        self.canvas.yview_scroll(step, "units")

    def _touchpad_page(self, event, delta_x, delta_y):
        if not self.document or not delta_y:
            return self._touchpad(event, delta_x, delta_y)
        first, last = self.canvas.yview()
        direction = 1 if delta_y < 0 else -1
        at_edge = (direction > 0 and last >= 0.999) or (direction < 0 and first <= 0.001)
        if at_edge:
            next_page = self.page + direction
            if 0 <= next_page < len(self.document):
                self.go(next_page)
                self.canvas.yview_moveto(0 if direction > 0 else 1)
            return
        self._touchpad(event, delta_x, delta_y)

    def close(self,event):
        if event.widget == self.host.win and self.document:
            self.document.close()
            self.document=None

    def load(self):
        import fitz
        from tkinter import simpledialog, messagebox
        path=filedialog.askopenfilename(parent=self.host.win,filetypes=[("PDF","*.pdf")])
        if not path:
            return
        try:
            document=fitz.open(path)
            if document.needs_pass:
                password=simpledialog.askstring("打开 PDF","请输入打开密码",show="•",parent=self.host.win)
                if not password or not document.authenticate(password):
                    document.close()
                    raise RuntimeError("密码不正确或已取消。")
            if self.document:
                self.document.close()
            self.document=document
            self.go(0)
        except Exception as exc:
            messagebox.showerror("无法打开 PDF",str(exc),parent=self.host.win)

    def jump(self):
        try:
            self.go(int(self.page_number.get())-1)
        except ValueError:
            self.host.write("请输入有效页码。")

    def go(self,index):
        if not self.document:
            return
        self.page=max(0,min(len(self.document)-1,index))
        from officertools.engine.pdf_extended import page_image
        self.image=page_image(self.document[self.page],120)
        self.page_number.set(str(self.page+1))
        self.redraw()
        self.canvas.yview_moveto(0)
        self.host.write("第 {} / {} 页".format(self.page+1,len(self.document)))

    def find(self):
        if not self.document or not self.search.get():
            return
        text=self.search.get().casefold()
        for offset in range(1,len(self.document)+1):
            index=(self.page+offset)%len(self.document)
            if text in self.document[index].get_text().casefold():
                self.go(index)
                return
        self.host.write("未找到文字。扫描页需要先识别文字。")


class AnnotateTool(object):
    def __init__(self, host: ToolWindow):
        from officertools.engine.external import screenshot

        self.host = host
        self.color = "#e11d48"
        self.start = None
        self.strokes = []
        self.mode = tk.StringVar(value="画笔")
        self.width = tk.StringVar(value="3")
        bar = tk.Frame(host.win, bg=PAGE)
        bar.pack(fill="x", padx=22, pady=6)
        pill(bar, "截取全屏", self.capture, host.app, primary=True).pack(side="left")
        pill(bar, "打开图片", self.load, host.app).pack(side="left", padx=6)
        pill(bar, "保存 PNG", self.save, host.app).pack(side="left")
        pill(bar, "撤销", self.undo, host.app).pack(side="left", padx=4)
        options=tk.Frame(host.win,bg=PAGE)
        options.pack(fill="x",padx=22)
        ttk.Combobox(options,textvariable=self.mode,values=("画笔","直线","箭头","矩形","椭圆","文字"),state="readonly",width=8).pack(side="left")
        ttk.Combobox(options,textvariable=self.width,values=("1","2","3","5","8","12"),state="readonly",width=4).pack(side="left",padx=6)
        pill(options,"颜色",self.choose_color,host.app).pack(side="left")
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
        self.canvas.bind("<ButtonRelease-1>", self.up)

    def choose_color(self):
        from tkinter.colorchooser import askcolor
        value=askcolor(self.color,parent=self.host.win)[1]
        if value:
            self.color=value

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.redraw_annotations()

    def redraw_annotations(self):
        from PIL import ImageDraw, ImageTk
        from officertools.engine.pdf import _cjk_font
        im=self.image.copy()
        draw=ImageDraw.Draw(im)
        for mode,points,color,width,text in self.strokes:
            if mode in ("画笔","直线","箭头"):
                draw.line(points,fill=color,width=width)
                if mode=="箭头":
                    (x0,y0),(x,y)=points[0],points[-1]
                    angle=math.atan2(y-y0,x-x0)
                    length=max(12,width*4)
                    draw.polygon([(x,y),(x-length*math.cos(angle-.45),y-length*math.sin(angle-.45)),(x-length*math.cos(angle+.45),y-length*math.sin(angle+.45))],fill=color)
            elif mode=="文字":
                draw.text(points[0],text,font=_cjk_font(max(16,width*6)),fill=color)
            else:
                (x0,y0),(x1,y1)=points[0],points[-1]
                box=(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))
                (draw.rectangle if mode=="矩形" else draw.ellipse)(box,outline=color,width=width)
        self.rendered=im
        self.photo=ImageTk.PhotoImage(im)
        self.canvas.delete("all")
        self.canvas.create_image(0,0,anchor="nw",image=self.photo)

    def point(self,event):
        return (self.canvas.canvasx(event.x),self.canvas.canvasy(event.y))

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
        self.strokes=[]
        self.rendered=self.image.copy()
        self.photo = ImageTk.PhotoImage(self.image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo, tags="base")
        self.canvas.configure(scrollregion=(0, 0, self.image.width, self.image.height))
        self.host.write("原图 {}×{}，保存时不会缩小。".format(self.image.width, self.image.height))

    def down(self, event):
        if not hasattr(self,"image"):
            return
        self.start = self.point(event)
        self.points=[self.start]

    def drag(self, event):
        if not self.start:
            return
        point=self.point(event)
        if self.mode.get()=="画笔":
            self.points.append(point)
        self.canvas.delete("preview")
        coords=(*self.start,*point)
        mode=self.mode.get()
        if mode in ("矩形","椭圆"):
            (self.canvas.create_rectangle if mode=="矩形" else self.canvas.create_oval)(*coords,outline=self.color,width=int(self.width.get()),tags="preview")
        else:
            self.canvas.create_line(*(sum(self.points,()) if mode=="画笔" else coords),fill=self.color,width=int(self.width.get()),tags="preview",arrow="last" if mode=="箭头" else "none")

    def up(self, event):
        if not self.start:
            return
        from tkinter import simpledialog
        mode=self.mode.get()
        text=""
        if mode=="文字":
            text=simpledialog.askstring("文字标注","请输入文字",parent=self.host.win) or ""
        points=self.points+[self.point(event)] if mode=="画笔" else [self.start,self.point(event)]
        if mode!="文字" or text:
            self.strokes.append((mode,points,self.color,int(self.width.get()),text))
        self.redraw_annotations()
        self.start = None

    def save(self):
        from PIL import ImageDraw

        if not hasattr(self, "image"):
            return
        im = self.rendered
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
        pill(bar,"停止",self.stop,host.app).pack(side="left",padx=6)
        self.canvas = tk.Canvas(host.win, background="#111", highlightthickness=0, width=480, height=320)
        self.canvas.pack(padx=8, pady=8)
        self.running = False

    def loop(self):
        if self.running:
            return
        self.running = True
        self.tick()

    def stop(self):
        self.running=False

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
