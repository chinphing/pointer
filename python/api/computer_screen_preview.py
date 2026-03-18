"""API handler: fresh screenshot as binary JPEG + mouse in header. For right-panel preview (computer profile)."""
from python.helpers.api import ApiHandler, Request, Response
from python.helpers.state_snapshot import get_fresh_computer_screen_preview_binary


# Header name for mouse position in image coords "x,y"
MOUSE_HEADER = "X-Computer-Screen-Mouse"


class Computer_screen_preview(ApiHandler):
    """GET/POST: return current monitor screenshot as image/jpeg body; mouse position in X-Computer-Screen-Mouse header."""

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        jpeg_bytes, mouse_xy = get_fresh_computer_screen_preview_binary()
        if not jpeg_bytes:
            return Response(response=b"", status=204, mimetype="image/jpeg")
        headers = {}
        if mouse_xy and len(mouse_xy) >= 2:
            headers[MOUSE_HEADER] = f"{mouse_xy[0]},{mouse_xy[1]}"
        return Response(
            response=jpeg_bytes,
            status=200,
            mimetype="image/jpeg",
            headers=headers,
        )
