import { createStore } from "/js/AlpineStore.js";
import { getCsrfToken } from "/js/api.js";

const model = {
  /** Image URL: blob URL (from binary preview) or data URL (from snapshot). Used as img src. */
  computerScreenRaw: "",
  /** Mouse position in screenshot image coords [x, y] for cursor overlay. From snapshot.computer_screen_mouse. */
  computerScreenMouse: null,
  /** Whether the screenshot panel is visible (default true). User can collapse it. */
  screenshotPanelVisible: true,
  /** Interval in seconds for right-panel screenshot refresh (from settings). */
  previewIntervalSec: 5,
  /** Timer id for periodic screenshot refresh (cleared when leaving computer profile). */
  _previewRefreshTimerId: null,
  /** Last blob URL created for preview; revoked when replacing or stopping. */
  _lastPreviewBlobUrl: null,

  setComputerScreenRaw(value) {
    if (this._lastPreviewBlobUrl && this._lastPreviewBlobUrl !== value) {
      URL.revokeObjectURL(this._lastPreviewBlobUrl);
      this._lastPreviewBlobUrl = null;
    }
    this.computerScreenRaw = value && typeof value === "string" ? value : "";
  },

  setComputerScreenMouse(xy) {
    if (xy && Array.isArray(xy) && xy.length >= 2 && Number.isFinite(xy[0]) && Number.isFinite(xy[1])) {
      this.computerScreenMouse = [Number(xy[0]), Number(xy[1])];
    } else {
      this.computerScreenMouse = null;
    }
  },

  /** Start periodic screenshot refresh for right panel (every previewIntervalSec seconds). Binary JPEG + mouse in header. */
  startPreviewRefresh(intervalSec) {
    this.stopPreviewRefresh();
    const sec = Math.max(1, Math.min(60, Number(intervalSec) || 5));
    this.previewIntervalSec = sec;
    const ms = sec * 1000;
    const self = this;
    const tick = function () {
      getCsrfToken()
        .then((token) =>
          fetch("/computer_screen_preview", {
            method: "GET",
            credentials: "include",
            headers: { "X-CSRF-Token": token },
          })
        )
        .then((res) => {
          if (!res.ok) return null;
          const mouseHeader = res.headers.get("X-Computer-Screen-Mouse");
          if (mouseHeader) {
            const parts = mouseHeader.split(",").map((s) => Number(s.trim()));
            if (parts.length >= 2 && Number.isFinite(parts[0]) && Number.isFinite(parts[1])) {
              self.setComputerScreenMouse([parts[0], parts[1]]);
            }
          }
          return res.blob();
        })
        .then((blob) => {
          if (!blob || blob.size === 0) return;
          if (self._lastPreviewBlobUrl) URL.revokeObjectURL(self._lastPreviewBlobUrl);
          self._lastPreviewBlobUrl = URL.createObjectURL(blob);
          self.computerScreenRaw = self._lastPreviewBlobUrl;
        })
        .catch(() => {});
    };
    self._previewRefreshTimerId = setInterval(tick, ms);
  },

  /** Stop periodic screenshot refresh (e.g. when session ends or switching away). Do not revoke the last blob URL so the last screenshot stays visible. */
  stopPreviewRefresh() {
    if (this._previewRefreshTimerId != null) {
      clearInterval(this._previewRefreshTimerId);
      this._previewRefreshTimerId = null;
    }
    // Keep _lastPreviewBlobUrl so the last frame remains visible when session ends; it is replaced/revoked on next startPreviewRefresh or setComputerScreenRaw.
  },

  /** Sync #right-panel class so chat area expands when panel collapsed (reusable for toggle and init). */
  _syncCollapsedClass() {
    const el = document.getElementById("right-panel");
    if (!el) return;
    if (this.screenshotPanelVisible) el.classList.remove("screenshot-column-collapsed");
    else el.classList.add("screenshot-column-collapsed");
  },

  toggleScreenshotPanel() {
    this.screenshotPanelVisible = !this.screenshotPanelVisible;
    this._syncCollapsedClass();
  },
};

export const store = createStore("computerScreen", model);
