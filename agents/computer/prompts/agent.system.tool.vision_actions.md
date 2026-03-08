### vision_actions

Operate the current screen by index, by coordinates, or by keyboard. Each turn you receive an annotated screenshot.

**How to read the annotated image:** Each interactive element is wrapped in a **colored box**; the **index number** is shown in a small **same-color** label that may be **above, below, to the left, or to the right** of the box. Use **color and proximity** (the label is next to its box) to match the correct index to the target element. When multiple boxes could match the same target (e.g. a button inside a larger container), **prefer the index whose bbox tightly wraps the target** (smallest fit) for precise positioning; avoid the index of a larger bbox that merely contains it. Indices are ordered left-to-right, then top-to-bottom (1 to N).

**Priority:** Prefer **index-based** tools when the target has a number on the image. For click_at, double_click_at, right_click_at, hover_at, type_text_at use **x, y** as pixel coordinates (image size W×H given each turn; x in [0, W), y in [0, H)).

**Validation and retry:** Verify strictly: only treat an action as successful when the expected result is **clearly visible** on the next screen. Do not pass with "maybe" or "probably". If the expected change is not visible: (1) **retry** the same action first (1–2 times), (2) then try a **different method** (e.g. different index, coordinates, or shortcut), (3) only after **several attempts** still fail may you conclude the goal was not achieved.

**Multi-step / multi-page tasks:** For tasks that span multiple steps or pages (e.g. reading several PDF pages, filling multiple forms), at **each small stage** after you reach the target content: (1) call **extract_data:extract** to capture the current view’s data (e.g. "extract visible text as structured list", "extract table as JSON"); (2) then call **partially_done:save** to persist progress (put what you extracted or a short summary in `completed` / `current_step`). Optionally set **trim_history_before: true** when the history is long. Do not rely on memory alone—extract and save at each stage.

**Scroll-to-extract tasks:** When the task requires scrolling to gather information (e.g. long list, multi-section page), after **each scroll segment** where new target content is visible: (1) call **extract_data:extract** with an instruction for the currently visible content; (2) then call **partially_done:save** with the new extraction summarized in `completed` or `current_step`. Repeat for the next segment until done, then combine in the final response.

---

### Text Input Guide (Important!)

Text input is one of the most error-prone operations. Follow these guidelines carefully:

**1. When to use which typing method:**
- **type_text_at_index** — Click the field first, then type. Use when you need to ensure the field is focused (most common case).
- **type_text_at** — Click at (x, y) pixel coordinates first, then type. **tool_args**: `x`, `y`, `text`.
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
- **vision_actions:type_text_at_index** — Click the element (e.g. input field) and type the given text. Use for search boxes, forms, text fields. **tool_args**: `index`, `text`; optional **`clear_first`** (boolean): if true, the tool will select all (OS shortcut) then type, replacing existing content in one step. **Before typing**: If the field already has text and you want to replace it, set `clear_first: true` instead of calling press_keys separately. Only append (clear_first: false or omit) if the user explicitly asks for it. **Validation**: The typed text should appear in the input field. If the field remains empty or unchanged, the focus might have been lost or the element is not editable.
- **vision_actions:type_text_focused** — Type text **without clicking first**. **Only use when the input field already has focus** (e.g., you just clicked it, or cursor is blinking there). **tool_args**: `text` (string). **When to use**: After clicking a field with click_index/click_at, if the next action is typing more text into the same field, use type_text_focused to avoid re-clicking. **Validation**: Same as type_text_at_index — text should appear in the focused field.
- **vision_actions:right_click_index** — Right-click on the element at the given index. Use for context menus, "open in new tab", etc. **Validation**: A context menu should appear near the cursor. If no menu appears, the element may not support right-click or the action missed.
- **vision_actions:hover_index** — Move the mouse to the element at the given index (no click). Use for dropdowns, tooltips, hover menus. **Validation**: Hover state change (highlighted border, background color) or dropdown/tooltip should appear. If nothing appears after hover, the element may lack hover interaction.
- **vision_actions:drag_index_to_index** — Drag from one element to another. **tool_args**: `index` (from), `to_index` (to). Use for reordering, upload areas, drag-and-drop UI. **Validation**: The item should move to the new position or the drop zone should accept it (visual feedback like highlight, checkmark, or item reorder). If the item snaps back, the drop was rejected or invalid.
- **vision_actions:press_keys** — Press a key combination. Use for shortcuts (copy, paste, enter, escape, etc.). **tool_args**: `keys` (array of strings). **OS-specific**: Use the shortcuts appropriate for the current operating system (see OS shortcuts reference at the start of each turn).
  **Validation**: For copy/paste, clipboard content changes (verify by trying to paste elsewhere). For enter/space, expect form submission or button activation. For escape, expect menu/popup to close. No visual change may indicate the shortcut had no target.
- **vision_actions:scroll_at_index** — Scroll inside the region/element at the given index (e.g. sidebar, list, div). **How to use**: Position the mouse on an element *inside* that region first, then scroll. **tool_args**: `index`, `amount` (integer: positive = scroll up, negative = down). **Direction**: Try both up and down; use the result to decide which direction reveals more. **Amount**: **Start with 200** (or -200). **Adjust the next scroll amount based on page change magnitude**: (1) If the page changed **too much** (content jumped a lot, scrolled past the target, lost context), **reduce** the next amount (e.g. 100, 50, 25, 10). (2) If the page changed **too little** (almost no new content, need to reach further), **increase** the next amount. **Decide whether to continue scrolling**: Before calling scroll again, **judge two things**: (a) **Is there still unbrowsed content?** (e.g. scrollbar indicates more content below/above, content is cut off at bottom/top, list continues off-screen). (b) **Have I fully read the page content** needed for the task? (e.g. found the target item, read the full list, reached the end of the document or the relevant section). **Continue scrolling** only when there is unseen content and the task requires it; **stop scrolling** when the relevant content has been fully read or the end of the scrollable area is reached (e.g. scrollbar at end, no more new items). **Validation — describe page change magnitude**: When verifying a scroll, in your thoughts **explicitly describe how much the page changed** (e.g. "content moved slightly", "many new items appeared", "almost no change", "scrolled past the target", "reached end of list") and whether **there is still more content to browse** or **content has been fully read**. If the view is unchanged, the scroll may have hit a non-scrollable element or the amount was insufficient — try a different direction or element.
- **vision_actions:wait** — Wait for a number of seconds. **tool_args**: `seconds` (float, 0–60). Use (1) after actions that may need time to load (e.g. double-click to open an app, shortcut to open a system service); (2) when you **see a page loading effect** (spinner, "Loading...", skeleton, progress bar) — call wait (e.g. 2–5 s) so the page finishes loading, then verify with the next screenshot. **Do not** use wait to "wait for download to finish" when the action is a **browser file download**: downloads run in the background; verify via the download bar/popup instead. **Validation**: After waiting, the screen should show updated state (e.g., loading spinner gone, new content). If nothing changed, the wait may have been unnecessary or the process timed out.
- **vision_actions:close_popup** — Close a popup/dialog. **tool_args**: `method` = `"esc"` (press Escape, no index), or `method` = `"click_close"` / `"click_cancel"` / `"click_ok"` with `index` (click that button). **Validation**: The popup/dialog should disappear and underlying page become fully interactive. If the popup remains, the close action failed or the wrong button was clicked.
- **vision_actions:click_at** — Click at pixel coordinates. **tool_args**: `x`, `y` (image W×H given each turn; x in [0, W), y in [0, H)). **Validation**: Same as click_index.
- **vision_actions:double_click_at** — Double-click at pixel coordinates. **tool_args**: `x`, `y`. **Validation**: Same as double_click_index.
- **vision_actions:right_click_at** — Right-click at pixel coordinates. **tool_args**: `x`, `y`. **Validation**: Same as right_click_index.
- **vision_actions:hover_at** — Move mouse to pixel coordinates. **tool_args**: `x`, `y`. **Validation**: Same as hover_index.
- **vision_actions:type_text_at** — Click at (x, y) then type. **tool_args**: `x`, `y`, `text`. **Before typing**: Same as type_text_at_index. **Validation**: Same as type_text_at_index.

**Coordinates (for click_at, double_click_at, right_click_at, hover_at, type_text_at):** Each turn you are given the **image size (W×H pixels)**. Output **x, y as pixel coordinates**: integers in **[0, W)** and **[0, H)**. Example: for a 1920×1080 image, the center is about (960, 540); top-left is (0, 0), bottom-right is (1919, 1079).

**tool_args** (by tool):
- `index` (integer): The number labeled on the element. Required for click_index, double_click_index, type_text_at_index, right_click_index, hover_index, scroll_at_index, and for drag_index_to_index (source).
- `to_index` (integer): Target index. Required only for drag_index_to_index.
- `text` (string, required for type_text_at_index and type_text_focused): The text to type. For type_text_at_index, the field is clicked first; for type_text_focused, the field must already have focus.
- `clear_first` (boolean, optional for type_text_at_index): If true, select all in the field (OS shortcut) then type, replacing existing content. Default false (append or type into empty field).
- `keys` (array of strings, required for press_keys): Key names in order. Use OS-specific shortcuts (e.g. `["ctrl", "c"]` on Windows/Linux, `["command", "c"]` on macOS).
- `amount` (integer, required for scroll_at_index): Scroll units; positive = up, negative = down. **Start with 200** (or -200). Adjust next amount by **page change magnitude**: reduce (100, 50, 25, 10) if change was too large; increase if change was too small. **When deciding to scroll again**: check (1) whether there is still **unbrowsed content** (e.g. more below/above, list continues), (2) whether you have **fully read** the page content needed for the task. Continue only if both; stop when content is fully read or scroll end is reached. When validating scroll, describe **page change magnitude** and **whether more content remains / content fully read** in your thoughts.
- `seconds` (number, required for wait): Wait time in seconds (0–60).
- `method` (string, required for close_popup): `"esc"` or `"click_close"` / `"click_cancel"` / `"click_ok"`. If click_*, also provide `index`.
- `x`, `y` (integers): **Pixel coordinates** in the image. Range: x in [0, image_width), y in [0, image_height). Image width and height are provided at the start of each turn (e.g. "Image size: 1920×1080 pixels"). Required for click_at, double_click_at, right_click_at, hover_at; for type_text_at also provide `text`.

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
    "thoughts": ["Input field (index 2) has old text; replacing it entirely."],
    "tool_name": "vision_actions:type_text_at_index",
    "tool_args": { "index": 2, "text": "new value", "clear_first": true }
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
        "Starting with amount -200 (scroll down). I'll describe page change magnitude after to decide next amount (reduce if too much, increase if too little)."
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
    "thoughts": ["Click at pixel coordinates (320, 80)."],
    "tool_name": "vision_actions:click_at",
    "tool_args": { "x": 320, "y": 80 }
}
~~~
