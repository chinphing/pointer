"""
Cross-platform focus/caret position in screen coordinates.
Used to draw a focus indicator on screenshots so the model sees where the text cursor is.
Returns (x, y) in screen pixels or None if unavailable.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from typing import Optional, Tuple

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", RECT),
        ]

    GUI_CARETBLINKING = 0x4


def get_focus_position() -> Optional[Tuple[int, int]]:
    """
    Return (screen_x, screen_y) of the current text input focus/caret, or None if unavailable.
    Cross-platform: Windows (GetGUIThreadInfo caret), macOS (AX focused element bounds), Linux (xdotool/window).
    """
    system = platform.system()
    if system == "Darwin":
        return _get_focus_position_macos()
    if system == "Windows":
        return _get_focus_position_windows()
    if system == "Linux":
        return _get_focus_position_linux()
    return None


def _get_focus_position_windows() -> Optional[Tuple[int, int]]:
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if not user32.GetGUIThreadInfo(0, ctypes.byref(info)):
            return None
        if not (info.flags & GUI_CARETBLINKING) or not info.hwndCaret:
            return None
        rect = info.rcCaret
        if rect.left == 0 and rect.top == 0 and rect.right == 0 and rect.bottom == 0:
            return None
        # Convert client coords to screen coords
        user32.MapWindowPoints(info.hwndCaret, None, ctypes.byref(rect), 2)
        x = (rect.left + rect.right) // 2
        y = rect.bottom  # caret tip
        return (x, y)
    except Exception:
        return None


def _get_focus_position_macos() -> Optional[Tuple[int, int]]:
    try:
        script = """
        tell application "System Events"
            -- 获取当前最前面的进程
            set frontApp to first application process whose frontmost is true
            try
                -- 尝试获取该进程中拥有焦点的元素
                set fe to (first UI element of frontApp whose focused is true)
                
                -- 如果找不到 focus，尝试获取整个窗口（备选方案）
                -- set fe to window 1 of frontApp
                
                set {x1, y1, x2, y2} to (get value of attribute "AXFrame" of fe) -- 另一种更通用的获取坐标方式
                
                set x to x1 + 12
                set y to y1 + (y2 - y1) / 2
                
                return (round x) as text & "," & (round y) as text
            on error err
                return "Error: " & err -- 打印具体错误方便调试
            end try
        end tell
        """
        out = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        parts = out.stdout.strip().split(",")
        if len(parts) != 2:
            return None
        x, y = int(parts[0]), int(parts[1])
        return (x, y)
    except Exception:
        return None


def _get_focus_position_linux() -> Optional[Tuple[int, int]]:
    # Try xdotool: get active window position + approximate caret (e.g. center of window or use mouse)
    try:
        out = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowgeometry", "--shell"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if out.returncode != 0:
            return None
        x, y = None, None
        for line in out.stdout.strip().splitlines():
            if line.startswith("X="):
                x = int(line.split("=", 1)[1])
            elif line.startswith("Y="):
                y = int(line.split("=", 1)[1])
        if x is not None and y is not None:
            # Return top-left of window + offset (approximate caret)
            return (x + 20, y + 20)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None
