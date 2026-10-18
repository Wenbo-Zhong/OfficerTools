# -*- coding: utf-8 -*-
"""Per-monitor DPI awareness. Call enable() before importing tkinter."""
from __future__ import annotations

import sys

_enabled = False


def enable() -> None:
    global _enabled
    if _enabled or sys.platform != "win32":
        _enabled = True
        return
    import ctypes

    user32 = ctypes.windll.user32
    # -4 = DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 (Windows 10 1703+)
    try:
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            _enabled = True
            return
    except Exception:
        pass
    try:
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE (Windows 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        _enabled = True
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    _enabled = True


def system_dpi(widget=None) -> float:
    """Physical pixels per inch. 96 means 100% scaling."""
    if sys.platform == "win32":
        import ctypes

        if widget is not None:
            try:
                hwnd = widget.winfo_id()
                dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
                if dpi:
                    return float(dpi)
            except Exception:
                pass
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)
            if dpi:
                return float(dpi)
        except Exception:
            pass
        return 96.0
    if widget is not None:
        try:
            return float(widget.winfo_fpixels("1i"))
        except Exception:
            pass
    return 96.0


def apply_tk_scaling(root) -> float:
    """Point-based Tk fonts and paddings follow the real DPI, so Windows does not stretch a bitmap."""
    dpi = system_dpi(root)
    # Tk scaling is pixels per typographic point (72 pt = 1 inch).
    root.tk.call("tk", "scaling", dpi / 72.0)
    return dpi
