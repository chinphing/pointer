from __future__ import annotations

import hashlib
import time
from typing import List, Optional, Tuple

import pyautogui
import pyperclip
from pynput.mouse import Button, Controller as MouseController
from langchain_core.tools import tool
from PIL import Image

import logging

try:
    import screen as _screen_mod
except ImportError:
    _screen_mod = None

# Side length (pixels) of the square region around the mouse used to judge scroll effect; avoids dynamic content elsewhere.
SCROLL_COMPARE_CROP_SIZE = 500


def _image_hash(pil_img: Image.Image, size: int = 64) -> str:
    """Stable hash for before/after scroll comparison (avoids hover/tooltip noise)."""
    gray = pil_img.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    return hashlib.md5(gray.tobytes()).hexdigest()


def _crop_around_mouse(
    img: Image.Image,
    mon_bbox: Tuple[int, int, int, int],
    mouse_screen_x: int,
    mouse_screen_y: int,
) -> Optional[Image.Image]:
    """Crop a SCROLL_COMPARE_CROP_SIZE square around the mouse. Always 500×500 when the image is large enough; only smaller when the screenshot itself is under 500px. Near edges the window is shifted to stay in bounds."""
    mon_left, mon_top, _mon_w, _mon_h = mon_bbox
    ix = mouse_screen_x - mon_left
    iy = mouse_screen_y - mon_top
    crop_w = min(SCROLL_COMPARE_CROP_SIZE, img.width)
    crop_h = min(SCROLL_COMPARE_CROP_SIZE, img.height)
    if crop_w <= 0 or crop_h <= 0:
        return None
    left = max(0, min(ix - crop_w // 2, img.width - crop_w))
    top = max(0, min(iy - crop_h // 2, img.height - crop_h))
    right = left + crop_w
    bottom = top + crop_h
    return img.crop((left, top, right, bottom))


def _scroll_region_hash(mouse_screen_x: int, mouse_screen_y: int) -> Optional[str]:
    """Screenshot current monitor, crop SCROLL_COMPARE_CROP_SIZE around mouse, return hash. Returns None on failure."""
    if _screen_mod is None:
        return None
    try:
        img, mon_bbox = _screen_mod.screenshot_current_monitor()
        region = _crop_around_mouse(img, mon_bbox, mouse_screen_x, mouse_screen_y)
        return _image_hash(region if region is not None else img)
    except Exception:
        return None


logger = logging.getLogger(__name__)

class ActionTools:
    def __init__(
        self,
        dry_run: bool = False,
        paste_key: Optional[List[str]] = None,
        stop_event=None,
    ):
        self.dry_run = dry_run
        self.paste_key = paste_key or ["command", "v"]
        self.last_action = None
        self.stop_event = stop_event

        self.mouse = MouseController()

    def set_stop_event(self, stop_event) -> None:
        self.stop_event = stop_event

    def _check_stop(self) -> None:
        if self.stop_event and self.stop_event.is_set():
            raise RuntimeError("Stopped")

    def _click(self, position: List[int]) -> str:
        self._check_stop()
        if not self.dry_run:
            self.mouse.position = (position[0], position[1])
            time.sleep(0.05)
            self.mouse.click(Button.left)
            time.sleep(0.1)
        self.last_action = {"tool": "click", "tool_input": {"position": position}}
        result = f"Clicked at position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

    def _click_add_to_selection_batch(self, positions: List[List[int]]) -> None:
        """Hold Ctrl (or Cmd on macOS) once, click each position in order, then release. One modifier press for all clicks."""
        if not positions:
            return
        import platform as _pf
        keys = ["command"] if _pf.system() == "Darwin" else ["ctrl"]
        self._check_stop()
        if not self.dry_run:
            for k in keys:
                pyautogui.keyDown(k)
            time.sleep(0.05)
            for i, pos in enumerate(positions):
                self._check_stop()
                self.mouse.position = (pos[0], pos[1])
                time.sleep(0.05)
                self.mouse.click(Button.left)
                time.sleep(0.08)
            for k in reversed(keys):
                pyautogui.keyUp(k)
            time.sleep(0.1)
        self.last_action = {"tool": "click_add_to_selection_batch", "tool_input": {"positions_count": len(positions)}}

    def _double_click(self, position: List[int]) -> str:
        self._check_stop()
        if not self.dry_run:
            self.mouse.position = (position[0], position[1])
            time.sleep(0.05)
            self.mouse.click(Button.left, 2)
            time.sleep(0.1)
        self.last_action = {"tool": "double_click", "tool_input": {"position": position}}
        result = f"Double-clicked at position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

    def _right_click(self, position: List[int]) -> str:
        self._check_stop()
        if not self.dry_run:
            self.mouse.position = (position[0], position[1])
            time.sleep(0.05)
            self.mouse.click(Button.right)
            time.sleep(0.1)
        self.last_action = {"tool": "right_click", "tool_input": {"position": position}}
        result = f"Right-clicked at position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

    def _type_text(self, text: str) -> str:
        """Type text at the current cursor location (assumes field is already focused)."""
        self._check_stop()
        old = pyperclip.paste()
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey(*self.paste_key)
        time.sleep(0.05)
        pyperclip.copy(old)
        time.sleep(0.2)
        self.last_action = {"tool": "type_text", "tool_input": {"text": text}}
        result = f"Typed text: '{text}'."
        logger.info(result)
        return result

    def _press_keys(self, keys: List[str]) -> str:
        self._check_stop()
        if not keys:
            raise ValueError("keys is required")
        if not self.dry_run:
            pyautogui.hotkey(*keys)
            time.sleep(0.3)
        self.last_action = {"tool": "press_keys", "tool_input": {"keys": keys}}
        key_combo = "+".join(keys)
        result = f"Pressed key combination: {key_combo}."
        logger.info(result)
        return result

    def _scroll(self, amount: int) -> Tuple[str, Optional[bool]]:
        """Scroll at current cursor. Returns (result_message, screen_changed or None). Compares hash of SCROLL_COMPARE_CROP_SIZE region around mouse only."""
        self._check_stop()
        screen_changed: Optional[bool] = None
        if not self.dry_run and _screen_mod is not None:
            scroll_done = False
            try:
                mx, my = pyautogui.position()
                pre_hash = _scroll_region_hash(mx, my)
                pyautogui.scroll(int(amount))
                scroll_done = True
                time.sleep(0.25)
                post_hash = _scroll_region_hash(mx, my)
                screen_changed = pre_hash != post_hash if (pre_hash is not None and post_hash is not None) else None
            except Exception:
                if not scroll_done:
                    pyautogui.scroll(int(amount))
                    time.sleep(0.2)
        elif not self.dry_run:
            pyautogui.scroll(int(amount))
            time.sleep(0.2)
        self.last_action = {"tool": "scroll", "tool_input": {"amount": amount}}
        direction = "up" if amount > 0 else "down"
        result = f"Trying to scroll {direction} {abs(amount)} units."
        logger.info(result)
        return (result, screen_changed)

    def _scroll_at(self, position: List[int], amount: int) -> Tuple[str, Optional[bool]]:
        """Move to position (hover settles), then reuse _scroll for before/scroll/after and screen_changed. Returns (result_message, screen_changed or None)."""
        self._check_stop()
        if not self.dry_run:
            self.mouse.position = (position[0], position[1])
            time.sleep(0.05)
        _, screen_changed = self._scroll(amount)
        self.last_action = {"tool": "scroll_at", "tool_input": {"position": position, "amount": amount}}
        direction = "up" if amount > 0 else "down"
        result = f"Trying to scroll {direction} {abs(amount)} units at position [{position[0]}, {position[1]}]."
        logger.info(result)
        return (result, screen_changed)

    def _wait(self, seconds: float) -> str:
        self._check_stop()
        time.sleep(float(seconds))
        self.last_action = {"tool": "wait", "tool_input": {"seconds": seconds}}
        result = f"Waited {seconds} seconds."
        logger.info(result)
        return result

    def _hover(self, position: List[int]) -> str:
        self._check_stop()
        if not self.dry_run:
            self.mouse.position = (position[0], position[1])
            time.sleep(0.2)
        self.last_action = {"tool": "hover", "tool_input": {"position": position}}
        result = f"Moved mouse to position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

    def _drag(self, from_position: List[int], to_position: List[int]) -> str:
        self._check_stop()
        if not self.dry_run:
            pyautogui.moveTo(from_position[0], from_position[1])
            time.sleep(0.1)
            pyautogui.mouseDown()
            time.sleep(0.05)
            pyautogui.moveTo(to_position[0], to_position[1], duration=0.2)
            time.sleep(0.05)
            pyautogui.mouseUp()
            time.sleep(0.2)
        self.last_action = {
            "tool": "drag",
            "tool_input": {"from_position": from_position, "to_position": to_position},
        }
        result = f"Dragged from [{from_position[0]}, {from_position[1]}] to [{to_position[0]}, {to_position[1]}]."
        logger.info(result)
        return result

    def _done(self) -> str:
        self._check_stop()
        self.last_action = {"tool": "done", "tool_input": {}}
        result = "Task completed successfully. Goal achieved."
        logger.info(result)
        return result
