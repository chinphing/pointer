import { createStore } from "/js/AlpineStore.js";
import { getCsrfToken } from "/js/api.js";

const model = {
  /** Main panel: blob URL from periodic preview, or data URL when auto-refresh is off. */
  computerScreenRaw: "",
  /** Mouse position in main screenshot image coords [x, y] (preview API or snapshot when static). */
  computerScreenMouse: null,
  /** Optional: inject / model-visible frame (data URL), only when setting show_model_input is on. */
  computerScreenModelInput: "",
  /** Mouse for model-input image coords (from snapshot). */
  computerScreenModelMouse: null,
  /** Whether the screenshot panel is visible (default true). User can collapse it. */
  screenshotPanelVisible: true,
  /** Interval in seconds for right-panel screenshot refresh (from settings). */
  previewIntervalSec: 5,
  /** Timer id for periodic screenshot refresh (cleared when leaving computer profile). */
  _previewRefreshTimerId: null,
  /** Last blob URL created for preview; revoked when replacing or stopping. */
  _lastPreviewBlobUrl: null,

  previewRefreshActive() {
    return this._previewRefreshTimerId != null;
  },

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

  setComputerScreenModelInput(value) {
    this.computerScreenModelInput = value && typeof value === "string" ? value : "";
  },

  setComputerScreenModelMouse(xy) {
    if (xy && Array.isArray(xy) && xy.length >= 2 && Number.isFinite(xy[0]) && Number.isFinite(xy[1])) {
      this.computerScreenModelMouse = [Number(xy[0]), Number(xy[1])];
    } else {
      this.computerScreenModelMouse = null;
    }
  },

  /** Start periodic JPEG preview for main panel; first frame loads immediately. */
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
    tick();
    self._previewRefreshTimerId = setInterval(tick, ms);
  },

  /** Stop periodic preview; keep last blob URL visible until replaced. */
  stopPreviewRefresh() {
    if (this._previewRefreshTimerId != null) {
      clearInterval(this._previewRefreshTimerId);
      this._previewRefreshTimerId = null;
    }
  },

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
