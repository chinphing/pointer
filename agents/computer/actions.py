from __future__ import annotations

import time
from typing import List, Optional

import pyautogui
import pyperclip
from langchain_core.tools import tool


import logging

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

    def set_stop_event(self, stop_event) -> None:
        self.stop_event = stop_event

    def _check_stop(self) -> None:
        if self.stop_event and self.stop_event.is_set():
            raise RuntimeError("Stopped")

    def _click(self, position: List[int]) -> str:
        self._check_stop()
        if not self.dry_run:
            pyautogui.click(*position)
            time.sleep(0.3)
        self.last_action = {"tool": "click", "tool_input": {"position": position}}
        result = f"Clicked at position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

    def _double_click(self, position: List[int]) -> str:
        self._check_stop()
        if not self.dry_run:
            pyautogui.click(*position, clicks=2, interval=0.1)
            time.sleep(0.3)
        self.last_action = {"tool": "double_click", "tool_input": {"position": position}}
        result = f"已在位置 [{position[0]}, {position[1]}] 双击。"
        logger.info(result)
        return result

    def _right_click(self, position: List[int]) -> str:
        self._check_stop()
        if not self.dry_run:
            pyautogui.rightClick(*position)
            time.sleep(0.3)
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

    def _scroll(self, amount: int) -> str:
        self._check_stop()
        if not self.dry_run:
            pyautogui.scroll(int(amount))
            time.sleep(0.2)
        self.last_action = {"tool": "scroll", "tool_input": {"amount": amount}}
        direction = "up" if amount > 0 else "down"
        result = f"Scrolled {direction} {abs(amount)} units."
        logger.info(result)
        return result

    def _scroll_at(self, position: List[int], amount: int) -> str:
        """Move to position then scroll there (so the scroll applies to that region/element)."""
        self._check_stop()
        if not self.dry_run:
            pyautogui.moveTo(position[0], position[1])
            time.sleep(0.15)
            pyautogui.scroll(int(amount))
            time.sleep(0.2)
        self.last_action = {"tool": "scroll_at", "tool_input": {"position": position, "amount": amount}}
        direction = "up" if amount > 0 else "down"
        result = f"Scrolled {direction} {abs(amount)} units at position [{position[0]}, {position[1]}]."
        logger.info(result)
        return result

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
            pyautogui.moveTo(position[0], position[1])
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

    def tools(self):
        @tool
        def click(position: List[int]) -> str:
            """Click at a normalized position [x,y] relative to the screenshot (0-1000 scale)."""
            logger.info("tool=click input=%s", {"position": position})
            try:
                result = self._click(position)
                logger.info("tool=click output=%s", result)
                return result
            except Exception as exc:
                logger.exception("tool=click error=%s", exc)
                raise

        @tool
        def double_click(position: List[int]) -> str:
            """Double click at a normalized position [x,y] relative to the screenshot (0-1000 scale)."""
            logger.info("tool=double_click input=%s", {"position": position})
            try:
                result = self._double_click(position)
                logger.info("tool=double_click output=%s", result)
                return result
            except Exception as exc:
                logger.exception("tool=double_click error=%s", exc)
                raise

        @tool
        def right_click(position: List[int]) -> str:
            """Right click at a normalized position [x,y] relative to the screenshot (0-1000 scale)."""
            logger.info("tool=right_click input=%s", {"position": position})
            try:
                result = self._right_click(position)
                logger.info("tool=right_click output=%s", result)
                return result
            except Exception as exc:
                logger.exception("tool=right_click error=%s", exc)
                raise

        @tool
        def type_text(text: str) -> str:
            """Type the given text at the current cursor location."""
            logger.info("tool=type_text input=%s", {"text": text})
            try:
                result = self._type_text(text)
                logger.info("tool=type_text output=%s", result)
                return result
            except Exception as exc:
                logger.exception("tool=type_text error=%s", exc)
                raise

        @tool
        def press_keys(keys: List[str]) -> str:
            """Press a key combo like ['ctrl','l'] or a sequence like ['enter']."""
            logger.info("tool=press_keys input=%s", {"keys": keys})
            try:
                result = self._press_keys(keys)
                logger.info("tool=press_keys output=%s", result)
                return result
            except Exception as exc:
                logger.exception("tool=press_keys error=%s", exc)
                raise

        @tool
        def scroll(amount: int) -> str:
            """Scroll by amount (positive up, negative down)."""
            logger.info("tool=scroll input=%s", {"amount": amount})
            try:
                result = self._scroll(amount)
                logger.info("tool=scroll output=%s", result)
                return result
            except Exception as exc:
                logger.exception("tool=scroll error=%s", exc)
                raise

        @tool
        def wait(seconds: float) -> str:
            """Wait for a number of seconds."""
            logger.info("tool=wait input=%s", {"seconds": seconds})
            try:
                result = self._wait(seconds)
                logger.info("tool=wait output=%s", result)
                return result
            except Exception as exc:
                logger.exception("tool=wait error=%s", exc)
                raise

        @tool
        def done() -> str:
            """Signal that the task is complete. Call this when the goal has been achieved."""
            logger.info("tool=done input=%s", {})
            try:
                result = self._done()
                logger.info("tool=done output=%s", result)
                return result
            except Exception as exc:
                logger.exception("tool=done error=%s", exc)
                raise

        return [
            click,
            double_click,
            right_click,
            type_text,
            press_keys,
            scroll,
            wait,
            done,
        ]
