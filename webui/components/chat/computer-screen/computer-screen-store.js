import { createStore } from "/js/AlpineStore.js";

const model = {
  /** Data URL (data:image/png;base64,...) or empty string. Updated from snapshot.computer_screen_raw. */
  computerScreenRaw: "",
  /** Mouse position in screenshot image coords [x, y] for cursor overlay. From snapshot.computer_screen_mouse. */
  computerScreenMouse: null,
  /** Whether the screenshot panel is visible (default true). User can collapse it. */
  screenshotPanelVisible: true,

  setComputerScreenRaw(value) {
    this.computerScreenRaw = value && typeof value === "string" ? value : "";
  },

  setComputerScreenMouse(xy) {
    if (xy && Array.isArray(xy) && xy.length >= 2 && Number.isFinite(xy[0]) && Number.isFinite(xy[1])) {
      this.computerScreenMouse = [Number(xy[0]), Number(xy[1])];
    } else {
      this.computerScreenMouse = null;
    }
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
