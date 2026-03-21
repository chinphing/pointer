"""
Set-of-marks (SOM) annotation via HTTP: POST /api/v1/annotate/all.

Local RF-DETR / Paddle inference was removed; `BoxAnnotator` is a thin client.
Swap implementations by typing against `SomAnnotator` and providing another class.
"""
from __future__ import annotations

import base64
import os
from io import BytesIO
from typing import List, Protocol, Sequence, Tuple

import requests
from PIL import Image

DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SEC = 120.0
ANNOTATE_PATH = "/api/v1/annotate/all"


class AnnotateApiError(RuntimeError):
    """Annotate service returned an error or an unexpected payload."""


class SomAnnotator(Protocol):
    def predict_and_annotate_all(
        self,
        image: Image.Image,
        threshold: float = 0.1,
        overlap_threshold: float = 0.1,
        padding: int = 3,
    ) -> Tuple[Image.Image, List[Sequence[float]]]:
        ...


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class BoxAnnotator:
    """
    Calls the annotate API: multipart image + threshold / overlap_threshold / padding.
    Returns (annotated PNG as PIL RGB/RGBA, boxes in input image pixel space).
    """

    def __init__(
        self,
        api_base: str | None = None,
        timeout_sec: float | None = None,
    ) -> None:
        self._api_base = (api_base or os.environ.get("COMPUTER_ANNOTATE_API_BASE") or DEFAULT_API_BASE).rstrip("/")
        self._timeout = timeout_sec if timeout_sec is not None else _env_float(
            "COMPUTER_ANNOTATE_TIMEOUT", DEFAULT_TIMEOUT_SEC
        )

    def _url(self) -> str:
        return f"{self._api_base}{ANNOTATE_PATH}"

    def predict_and_annotate_all(
        self,
        image: Image.Image,
        threshold: float = 0.1,
        overlap_threshold: float = 0.1,
        padding: int = 3,
    ) -> Tuple[Image.Image, List[Sequence[float]]]:
        buf = BytesIO()
        image.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        files = {"file": ("screen.png", png_bytes, "image/png")}
        data = {
            "threshold": str(threshold),
            "overlap_threshold": str(overlap_threshold),
            "padding": str(padding),
        }

        try:
            r = requests.post(self._url(), files=files, data=data, timeout=self._timeout)
        except requests.RequestException as e:
            raise AnnotateApiError(f"annotate request failed: {e}") from e

        try:
            payload = r.json()
        except ValueError as e:
            raise AnnotateApiError(f"annotate response not JSON (HTTP {r.status_code}): {r.text[:500]}") from e

        if r.status_code != 200:
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            raise AnnotateApiError(f"annotate HTTP {r.status_code}: {detail!r}")

        if not isinstance(payload, dict):
            raise AnnotateApiError("annotate response JSON must be an object")

        boxes_raw = payload.get("boxes")
        b64 = payload.get("image_base64")
        rw = payload.get("width")
        rh = payload.get("height")

        if not isinstance(boxes_raw, list) or b64 is None or rw is None or rh is None:
            raise AnnotateApiError("annotate response missing boxes, image_base64, width, or height")

        try:
            rw_i, rh_i = int(rw), int(rh)
        except (TypeError, ValueError) as e:
            raise AnnotateApiError(f"invalid width/height in response: {rw!r}, {rh!r}") from e

        try:
            annotated = Image.open(BytesIO(base64.b64decode(b64)))
        except Exception as e:
            raise AnnotateApiError(f"failed to decode image_base64: {e}") from e

        iw, ih = image.size
        if (rw_i, rh_i) != (iw, ih):
            raise AnnotateApiError(
                f"annotate response size {(rw_i, rh_i)} != input image size {(iw, ih)}"
            )
        if annotated.size != (iw, ih):
            raise AnnotateApiError(
                f"decoded annotated image size {annotated.size} != input image size {(iw, ih)}"
            )

        boxes: List[List[float]] = []
        for item in boxes_raw:
            if not isinstance(item, (list, tuple)) or len(item) < 4:
                continue
            boxes.append([float(item[0]), float(item[1]), float(item[2]), float(item[3])])

        boxes_sorted: List[Sequence[float]] = [tuple(b) for b in boxes]
        return annotated, boxes_sorted


if __name__ == "__main__":
    p = '/Users/yunyun/Desktop/agent-zero/small_3x.png'
    im = Image.open(p)
    ann, boxes = BoxAnnotator().predict_and_annotate_all(im)
    out = os.path.splitext(p)[0] + "_annotated.png"
    ann.save(out)
    print(f"Saved {out}, {len(boxes)} boxes")
