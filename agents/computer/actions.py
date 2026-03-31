from __future__ import annotations

import platform
import time
from typing import List, Optional

import pyautogui
import pyperclip
from pynput.mouse import Button, Controller as MouseController
from langchain_core.tools import tool
from PIL import Image

import logging

from scroll_heatmap import _image_hash

try:
    import screen as _screen_mod
except ImportError:
    _screen_mod = None

# Side length (pixels) of the square region around the mouse used to judge scroll effect; avoids dynamic content elsewhere.
SCROLL_COMPARE_CROP_SIZE = 500


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


class RawAction:
    """
    Raw mouse and keyboard action interface.
    Provides low-level operations WITHOUT any mouse movement.
    Caller MUST ensure mouse is already at the correct position before calling these methods.
    """

    def __init__(
        self,
        dry_run: bool = False,
        paste_key: Optional[List[str]] = None,
        stop_event=None,
    ):
        self.dry_run = dry_run
        self.paste_key = paste_key
        self.last_action = None
        self.stop_event = stop_event
        
        if self.paste_key is None:
            system = platform.system()
            if system == "Darwin":
                self.paste_key = ["command", "v"]
            else:
                self.paste_key = ["ctrl", "v"]

        self.mouse = MouseController()

    def set_stop_event(self, stop_event) -> None:
        self.stop_event = stop_event

    def _check_stop(self) -> None:
        if self.stop_event and self.stop_event.is_set():
            raise RuntimeError("Stopped")

    def _click(self) -> str:
        """
        Click at the current mouse position.
        Caller MUST ensure mouse is already at the target position.
        """
        self._check_stop()
        if not self.dry_run:
            self.mouse.click(Button.left)
            time.sleep(0.1)
        position = [int(self.mouse.position[0]), int(self.mouse.position[1])]
        self.last_action = {"tool": "click", "tool_input": {"position": position}}
        result = f"Clicked at current position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

    def _double_click(self) -> str:
        """
        Double-click at the current mouse position.
        Caller MUST ensure mouse is already at the target position.
        """
        self._check_stop()
        if not self.dry_run:
            self.mouse.click(Button.left, 2)
            time.sleep(0.1)
        position = [int(self.mouse.position[0]), int(self.mouse.position[1])]
        self.last_action = {"tool": "double_click", "tool_input": {"position": position}}
        result = f"Double-clicked at current position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

    def _right_click(self) -> str:
        """
        Right-click at the current mouse position.
        Caller MUST ensure mouse is already at the target position.
        """
        self._check_stop()
        if not self.dry_run:
            self.mouse.click(Button.right)
            time.sleep(0.1)
        position = [int(self.mouse.position[0]), int(self.mouse.position[1])]
        self.last_action = {"tool": "right_click", "tool_input": {"position": position}}
        result = f"Right-clicked at current position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

    def _hover(self, duration: float = 0.5) -> str:
        """
        Hover at the current mouse position for the specified duration.
        Caller MUST ensure mouse is already at the target position.
        
        Args:
            duration: How long to hover in seconds.
        """
        self._check_stop()
        if not self.dry_run:
            time.sleep(duration)
        position = [int(self.mouse.position[0]), int(self.mouse.position[1])]
        self.last_action = {"tool": "hover", "tool_input": {"position": position, "duration": duration}}
        result = f"Hovered at current position [{position[0]}, {position[1]}] for {duration}s."
        logger.info(result)
        return result

    def _type_text(self, text: str, clear_field_first: bool = False) -> str:
        """
        Type text at the current cursor position.
        Caller MUST ensure the target input field is already focused.
        
        Args:
            text: The text to type.
            clear_field_first: Whether to clear the field first (Ctrl+A).
        """
        self._check_stop()
        if not self.dry_run:
            if clear_field_first:
                pyautogui.keyDown("ctrl")
                pyautogui.keyDown("a")
                pyautogui.keyUp("a")
                pyautogui.keyUp("ctrl")
                time.sleep(0.05)
            pyperclip.copy(text)
            time.sleep(0.05)
            for key in self.paste_key:
                pyautogui.keyDown(key)
            for key in reversed(self.paste_key):
                pyautogui.keyUp(key)
            time.sleep(0.1)
        self.last_action = {"tool": "type_text", "tool_input": {"text": text, "clear_field_first": clear_field_first}}
        result = f"Typed text: {text}"
        logger.info(result)
        return result

    def _scroll(self, clicks: int) -> str:
        """
        Scroll at the current mouse position.
        Caller MUST ensure mouse is already at the target position.
        
        Args:
            clicks: Number of clicks (positive=up, negative=down).
        """
        self._check_stop()
        if not self.dry_run:
            before_hash = _scroll_region_hash(int(self.mouse.position[0]), int(self.mouse.position[1]))
            self.mouse.scroll(0, clicks)
            time.sleep(0.2)
            after_hash = _scroll_region_hash(int(self.mouse.position[0]), int(self.mouse.position[1]))
            changed = before_hash != after_hash
        else:
            changed = True
        position = [int(self.mouse.position[0]), int(self.mouse.position[1])]
        self.last_action = {"tool": "scroll", "tool_input": {"clicks": clicks, "position": position}}
        direction = "down" if clicks < 0 else "up"
        result = f"Scrolled {direction} {abs(clicks)} units at current position {position}. Content changed: {changed}"
        logger.info(result)
        return result

    def _key_down(self, key: str) -> None:
        """Press and hold a key."""
        if not self.dry_run:
            pyautogui.keyDown(key)

    def _key_up(self, key: str) -> None:
        """Release a key."""
        if not self.dry_run:
            pyautogui.keyUp(key)

    def _press_keys(self, keys: List[str]) -> str:
        """
        Press a key combination.
        
        Args:
            keys: List of keys to press simultaneously (e.g., ["ctrl", "c"]).
        """
        self._check_stop()
        if not keys:
            raise ValueError("keys is required")
        if not self.dry_run:
            pyautogui.hotkey(*keys, interval=0.05)
            time.sleep(0.3)
        self.last_action = {"tool": "press_keys", "tool_input": {"keys": keys}}
        key_combo = "+".join(keys)
        result = f"Pressed key combination: {key_combo}."
        logger.info(result)
        return result

    def _wait(self, seconds: float) -> str:
        """
        Wait for the specified number of seconds.
        
        Args:
            seconds: Number of seconds to wait.
        """
        self._check_stop()
        if not self.dry_run:
            time.sleep(seconds)
        self.last_action = {"tool": "wait", "tool_input": {"seconds": seconds}}
        result = f"Waited for {seconds} seconds."
        logger.info(result)
        return result


# Backward compatibility alias
ActionTools = RawAction
