### mouse

Use for clicks, hover, and scroll at current cursor. Prefer **index-based** when the target has an index on the annotated image; use **coordinate-based** only when the target has no index (see coordinate-based principles in computer_usage). When choosing **`index`**, if several numbers could apply (e.g. similar label backgrounds), pick the one whose badge lies **inside** the target control’s rectangle — inner **corners** or inner **top / bottom / left / right** edge centers are valid; avoid outer-only labels when an inner label exists for the same target.

**Call priority:** Use this tool when a single mouse action is needed. Prefer **composite_action** or **hotkey** or **modified_click** when one call achieves the goal with fewer tool invocations.

Methods:
- **Index-based** (require `index`, `goal`): `click_index`, `double_click_index`, `right_click_index`, `hover_index`.
- **Coordinate-based** (require `goal`, `x`, `y`): `click_at`, `double_click_at`, `right_click_at`, `hover_at`.
- **Scroll at current cursor** (no index): `scroll_at_current` (`goal`, `amount`) — use when the mouse is already inside the scrollable area. Amount: positive = up, negative = down; valid range 1–10 or -10–-1; generally use 10 or -10.

Parameter constraints:
- **`goal`** is required for all methods. Describe the **target element**: if the target is **text**, include the **exact visible text**; if it is another element (icon, image, button), give a **brief description of its features** (e.g. folder icon, blue arrow). Then state the action and expected result.
- For coordinate-based methods: `x`, `y` are normalized coordinates (same scale as in the prompt). Derive from a reference with explicit coordinates; do not guess.

Scroll workflow: When the mouse is already in the scrollable area, use `scroll_at_current` directly. When you need to target a specific region first, use **composite_action:scroll_at_index**, then **mouse:scroll_at_current** for further scrolls.
