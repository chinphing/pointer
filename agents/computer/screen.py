from __future__ import annotations

import base64
from io import BytesIO
from typing import List, Tuple

import mss
import pyautogui
from PIL import Image


def screenshot_current_monitor() -> Tuple[Image.Image, tuple]:
    x, y = pyautogui.position()
    with mss.mss() as sct:
        for mon in sct.monitors[1:]:
            if (
                mon["left"] <= x < mon["left"] + mon["width"]
                and mon["top"] <= y < mon["top"] + mon["height"]
            ):
                img = sct.grab(mon)
                return Image.frombytes("RGB", img.size, img.rgb), (
                    mon["left"],
                    mon["top"],
                    mon["width"],
                    mon["height"],
                )
        img = sct.grab(sct.monitors[0])
        mon = sct.monitors[0]
        return Image.frombytes("RGB", img.size, img.rgb), (
            mon["left"],
            mon["top"],
            mon["width"],
            mon["height"],
        )


def encode_image(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def encode_image_file(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def strip_markdown_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rsplit("```", 1)[0]
    return t.strip()


def denormalize_position(position: List[int], bbox: tuple) -> List[int]:
    # left, top, width, height = bbox
    # x = max(0, min(1000, int(position[0])))
    # y = max(0, min(1000, int(position[1])))
    # real_x = left + int(round((x / 1000.0) * width))
    # real_y = top + int(round((y / 1000.0) * height))
    # return [real_x, real_y]
    return position
