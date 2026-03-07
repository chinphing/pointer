### vision_actions

Operate the current screen by index, by coordinates, or by keyboard. Each turn you receive an annotated screenshot.

**How to read the annotated image:** Each interactive element is wrapped in a **colored box**; the **index number** is shown in a small **same-color** label that may be **above, below, to the left, or to the right** of the box. Use **color and proximity** (the label is next to its box) to match the correct index to the target element. When multiple boxes could match the same target (e.g. a button inside a larger container), **prefer the index whose bbox tightly wraps the target** (smallest fit) for precise positioning; avoid the index of a larger bbox that merely contains it. Indices are ordered left-to-right, then top-to-bottom (1 to N).

**Priority:** Prefer **index-based** tools when the target has a number on the image. If the target element has **no number** (e.g. "收藏" is visible but unmarked), use **coordinate-based** tools: **click_at**, **double_click_at**, **right_click_at**, **hover_at**, **type_text_at** with **x, y** in your model's native coordinate system (see below). Use press_keys, wait, and close_popup (method=esc) without index or coordinates.

**Validation and retry:** Verify strictly: only treat an action as successful when the expected result is **clearly visible** on the next screen. Do not pass with "maybe" or "probably". If the expected change is not visible: (1) **retry** the same action first (1–2 times), (2) then try a **different method** (e.g. different index, coordinates, or shortcut), (3) only after **several attempts** still fail may you conclude the goal was not achieved.

---

### Text Input Guide (Important!)

Text input is one of the most error-prone operations. Follow these guidelines carefully:

**1. When to use which typing method:**
- **type_text_at_index** — Click the field first, then type. Use when you need to ensure the field is focused (most common case).
- **type_text_at** — Click at x,y coordinates first, then type. Use when the target has no index but you know its coordinates.
- **type_text_focused** — Type directly without clicking. **Only use when you are certain the field already has focus** (e.g., you just clicked it in the previous step, or the cursor is visibly blinking in the field).

**2. Before typing — always check for existing text:**
- Look at the current screenshot: does the input field already contain text?
- If yes, decide: **replace** or **append**?
  - To **replace**: Clear the field first. Options:
    - Select all then type: use OS-specific shortcut (see OS shortcuts reference) → then `type_text_at_index`
    - Triple-click to select all, then type
    - Use select-all shortcut then Delete/Backspace
  - To **append**: Click at the end of the text, then type
- If the field is empty: proceed directly with typing

**3. Common text input mistakes to avoid:**
- Don't assume the field is focused — click it first unless you're certain
- Don't append to existing text unless the user explicitly asked for it
- Don't forget to clear search boxes that have placeholder/default text
- When using coordinate-based typing (type_text_at), ensure your coordinates are accurate

**4. Validation after typing:**
- Check that the text appears correctly in the field
- Verify cursor position (should be at end of typed text for append, or after the new text for replace)
- If text doesn't appear, the field may not have received focus — retry with a clear click first

When reasoning about which index to use, **describe the element's position** (e.g. top-left, center, bottom-right) so the vision model can target it more reliably.

- **vision_actions:click_index** — Single click on the element at the given index. Use for buttons, links, icons. **Validation**: For links, expect navigation (URL change or new page load). For buttons, expect a state change (e.g., popup, loading spinner, new content). If nothing changes, the click may have missed or the element might be inactive.
- **vision_actions:double_click_index** — Double-click on the element at the given index. Use for opening files or selecting words. **Validation**: File should open in associated app or inline preview. Text selection should highlight the word under cursor. If no change occurs, the double-click likely missed or the target is not double-clickable.
- **vision_actions:type_text_at_index** — Click the element (e.g. input field) and type the given text. Use for search boxes, forms, text fields. **Before typing**: Check if the field already contains text. If it does, decide whether to clear it first (e.g., select all with Ctrl+A then type, or use Ctrl+A followed by Delete/Backspace, or triple-click to select all). Only append to existing text if the user explicitly asks for it. **Validation**: The typed text should appear in the input field, replacing any selected text. Cursor should move to end of text. If the field remains empty or unchanged, the focus might have been lost or the element is not editable.
- **vision_actions:type_text_focused** — Type text **without clicking first**. **Only use when the input field already has focus** (e.g., you just clicked it, or cursor is blinking there). **tool_args**: `text` (string). **When to use**: After clicking a field with click_index/click_at, if the next action is typing more text into the same field, use type_text_focused to avoid re-clicking. **Validation**: Same as type_text_at_index — text should appear in the focused field.
- **vision_actions:right_click_index** — Right-click on the element at the given index. Use for context menus, "open in new tab", etc. **Validation**: A context menu should appear near the cursor. If no menu appears, the element may not support right-click or the action missed.
- **vision_actions:hover_index** — Move the mouse to the element at the given index (no click). Use for dropdowns, tooltips, hover menus. **Validation**: Hover state change (highlighted border, background color) or dropdown/tooltip should appear. If nothing appears after hover, the element may lack hover interaction.
- **vision_actions:drag_index_to_index** — Drag from one element to another. **tool_args**: `index` (from), `to_index` (to). Use for reordering, upload areas, drag-and-drop UI. **Validation**: The item should move to the new position or the drop zone should accept it (visual feedback like highlight, checkmark, or item reorder). If the item snaps back, the drop was rejected or invalid.
- **vision_actions:press_keys** — Press a key combination. Use for shortcuts (copy, paste, enter, escape, etc.). **tool_args**: `keys` (array of strings). **OS-specific**: Use the shortcuts appropriate for the current operating system (see OS shortcuts reference at the start of each turn).
  **Validation**: For copy/paste, clipboard content changes (verify by trying to paste elsewhere). For enter/space, expect form submission or button activation. For escape, expect menu/popup to close. No visual change may indicate the shortcut had no target.
- **vision_actions:scroll_at_index** — Scroll inside the region/element at the given index (e.g. sidebar, list, div). **How to use**: To see more content in a region, you must position the mouse on an element *inside* that region first, then scroll (this tool moves to the element at `index` and scrolls there). **tool_args**: `index`, `amount` (integer: positive = scroll up, negative = down). **Direction**: Try both up and down; use the result to decide which direction reveals more. **Amount**: Start with a bold value (e.g. 200 or -200). If the interface change shows the scroll was too large, scroll back by half, then try smaller amounts: 100, 50, 25, 10. **If key information is still missing after scrolling**, consider reducing the scroll amount (e.g. try 50, 25, or 10) and scroll again so content is not skipped. **Validation**: New items should come into view (list items, page content). If the view remains unchanged, the scroll may have been applied to a non-scrollable element or the amount was insufficient.
- **vision_actions:wait** — Wait for a number of seconds. **tool_args**: `seconds` (float, 0–60). Use for page load, animations. **Validation**: After waiting, the screen should show updated state (e.g., loading spinner gone, new content appeared, page fully loaded). If nothing changed, the wait may have been unnecessary or the process timed out.
- **vision_actions:close_popup** — Close a popup/dialog. **tool_args**: `method` = `"esc"` (press Escape, no index), or `method` = `"click_close"` / `"click_cancel"` / `"click_ok"` with `index` (click that button). **Validation**: The popup/dialog should disappear and underlying page become fully interactive. If the popup remains, the close action failed or the wrong button was clicked.
- **vision_actions:click_at** — Click at coordinates (use when the target has no index). **tool_args**: `x`, `y` in your model's native system (see below). **Validation**: Same as click_index: expect navigation, state change, or UI feedback. If nothing happens, the coordinates likely missed the intended target.
- **vision_actions:double_click_at** — Double-click at x, y. **tool_args**: `x`, `y`. **Validation**: Same as double_click_index: expect file open or text selection. If no change, the coordinates missed or target doesn't support double-click.
- **vision_actions:right_click_at** — Right-click at x, y. **tool_args**: `x`, `y`. **Validation**: Same as right_click_index: expect context menu to appear. If no menu, coordinates missed or target doesn't support right-click.
- **vision_actions:hover_at** — Move mouse to x, y. **tool_args**: `x`, `y`. **Validation**: Same as hover_index: expect hover state change or tooltip/dropdown. If nothing changes, coordinates missed or no hover interaction available.
- **vision_actions:type_text_at** — Click at x, y then type text. **tool_args**: `x`, `y`, `text`. **Before typing**: Same as type_text_at_index — check if the clicked location already has text, and clear it if needed (e.g., select all then type, or use keyboard shortcuts to clear). Only append if explicitly requested. **Validation**: Same as type_text_at_index: text should appear in the input field at the clicked location, replacing any selected text. If unchanged, the click missed or the target is not an editable field.

**Coordinate systems (for click_at, double_click_at, right_click_at, hover_at, type_text_at):** The backend converts your (x, y) to screen pixels. Use your model's native range: e.g. **Qwen** normalizes to **1000×1000** (x, y in [0, 1000]); **Kimi** normalizes to **1×1** (x, y in [0, 1]). Output (x, y) in the format your model uses for the current image.

**tool_args** (by tool):
- `index` (integer): The number labeled on the element. Required for click_index, double_click_index, type_text_at_index, right_click_index, hover_index, scroll_at_index, and for drag_index_to_index (source).
- `to_index` (integer): Target index. Required only for drag_index_to_index.
- `text` (string, required for type_text_at_index and type_text_focused): The text to type. For type_text_at_index, the field is clicked first; for type_text_focused, the field must already have focus.
- `keys` (array of strings, required for press_keys): Key names in order. Use OS-specific shortcuts (e.g. `["ctrl", "c"]` on Windows/Linux, `["command", "c"]` on macOS).
- `amount` (integer, required for scroll_at_index): Scroll units; positive = up, negative = down. Start with 200 (or -200); if too large or key info still missing, reduce and try 100, 50, 25, 10.
- `seconds` (number, required for wait): Wait time in seconds (0–60).
- `method` (string, required for close_popup): `"esc"` or `"click_close"` / `"click_cancel"` / `"click_ok"`. If click_*, also provide `index`.
- `x`, `y` (numbers, required for click_at, double_click_at, right_click_at, hover_at, type_text_at): Coordinates in the model's native system (e.g. Qwen 0–1000, Kimi 0–1). For type_text_at also provide `text`.

**Example**

~~~json
{
    "thoughts": ["Submit button in the bottom-right is index 4.", "I will click it."],
    "tool_name": "vision_actions:click_index",
    "tool_args": { "index": 4 }
}
~~~

~~~json
{
    "thoughts": ["Search box in the top-left (index 1). Typing the query."],
    "tool_name": "vision_actions:type_text_at_index",
    "tool_args": { "index": 1, "text": "agent zero" }
}
~~~

~~~json
{
    "thoughts": [
        "I already clicked the search box in the previous step and it's now focused.",
        "I need to add more text to the same field without clicking again."
    ],
    "tool_name": "vision_actions:type_text_focused",
    "tool_args": { "text": " tutorial" }
}
~~~

~~~json
{
    "thoughts": ["Copy selection with OS-specific shortcut."],
    "tool_name": "vision_actions:press_keys",
    "tool_args": { "keys": ["ctrl", "c"] }
}
~~~

*Note: Use `["command", "c"]` on macOS, `["ctrl", "c"]` on Windows/Linux.*

~~~json
{
    "thoughts": [
        "Need to see more of the sidebar (index 2). I'll position on that region and scroll.",
        "Starting with amount -200 (scroll down); if the change is too large I'll scroll back by half and try 100, 50, etc."
    ],
    "tool_name": "vision_actions:scroll_at_index",
    "tool_args": { "index": 2, "amount": -200 }
}
~~~

~~~json
{
    "thoughts": ["Right-click on link (index 2) to open in new tab."],
    "tool_name": "vision_actions:right_click_index",
    "tool_args": { "index": 2 }
}
~~~

~~~json
{
    "thoughts": ["Hover over menu (index 3) to open dropdown."],
    "tool_name": "vision_actions:hover_index",
    "tool_args": { "index": 3 }
}
~~~

~~~json
{
    "thoughts": ["Drag item index 1 to drop zone index 5."],
    "tool_name": "vision_actions:drag_index_to_index",
    "tool_args": { "index": 1, "to_index": 5 }
}
~~~

~~~json
{
    "thoughts": ["Wait 2 seconds for page to load."],
    "tool_name": "vision_actions:wait",
    "tool_args": { "seconds": 2 }
}
~~~

~~~json
{
    "thoughts": ["Close dialog by clicking Cancel (index 4)."],
    "tool_name": "vision_actions:close_popup",
    "tool_args": { "method": "click_cancel", "index": 4 }
}
~~~

~~~json
{
    "thoughts": ["The 收藏 menu has no index. I'll click at coordinates (Qwen 1000×1000): center of the menu at about (320, 80)."],
    "tool_name": "vision_actions:click_at",
    "tool_args": { "x": 320, "y": 80 }
}
~~~
