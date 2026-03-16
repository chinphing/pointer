### vision_actions

Use these tools to operate UI by index, by absolute coordinates (screenshot pixels), keyboard, and wait.

Core rules:
- Re-identify target on current screenshot each turn.
- Use index-based tools when the target has an index on the annotated image. When using delta_x/delta_y, always set **target_in_bbox** to `"inside"` or `"outside"` according to whether the target is inside or outside the reference (numbered) bbox — this information is important.
- When the target has **no** index, use **coordinate-based** tools only under the **coordinate-based principles** below.
- Use one action per turn.

**Coordinate-based principles** (click_at, type_text_at, etc.):
1. **Reference selection**: The reference element must have **explicit coordinates** in the prompt and must be **very close to the target** (distance within 50 pixels). Only use a reference that satisfies both.
2. **Coordinate generation**: You **must** derive x, y using the reference element’s coordinates as the **anchor** (e.g. from the reference bbox). Do **not** guess coordinates without a clear basis—guessed coordinates are useless.
3. **Positioning flow**: In general, **first** use **hover_index** on a marked element that is close to the target to position the cursor; **then** use coordinate-based tools with x, y inferred from that reference (same normalized scale as the prompt, e.g. [0, 1000] or [0, 1]).
- The prompt includes the current mouse position (screenshot coords) so you can judge after an action whether the click landed on target or deviated, and adjust strategy.
- For coordinate-based positioning: each step that brings the pointer **closer** to the target counts as success; you may try up to **3 times**—no need to hit the target in one shot. Validate from the next screenshot; retry if not yet on target.

Methods:
- `click_index`, `double_click_index`, `right_click_index`, `hover_index` (`index`, `goal`, optional `delta_x`, `delta_y`, `target_in_bbox`)
- **Multi-select by index** — `multi_select_by_index` (`indices`, `goal`): Select **several items at once** (list rows, files, checkboxes). **Implementation**: the tool **holds Cmd (macOS) or Ctrl (Windows/Linux)**, then **clicks each target element in order** by index, then **releases Cmd/Ctrl** — same as user doing “Ctrl+click” / “Cmd+click” to add to selection. **When to use**: "select multiple", "select items 1, 3, 5", "select several rows/files". **indices**: which item numbers to select — list of integers (e.g. `[1, 3, 5]`) or comma-separated string (e.g. `"1,3,5"`). Each must be a 1-based index on the annotated image.
- `type_text_at_index` (`index`, `goal`, `text`, optional `clear_first`, `delta_x`, `delta_y`, `target_in_bbox`)
- `drag_index_to_index` (`index`, `to_index`, `goal`)
- `scroll_at_index` (`index`, `goal`, `amount`, optional `delta_x`, `delta_y`, `target_in_bbox`)
     `amount` for scroll: scroll wheel notches. Valid range: [1, 10] for scroll up, [-10, -1] for scroll down. **Generally use 10** (or -10). Use **5 or -5** when you want to keep the previously edited content in view and scroll to find the Save button.
- `scroll_at_current` (`goal`, `amount`) — Scroll at **current cursor position** (no index). You may call it **directly when the mouse is already inside the scrollable area**; otherwise use `scroll_at_index` first to position, then use `scroll_at_current` for further scrolls. Same `amount` convention: positive = up, negative = down. Generally use 10/-10; use 5/-5 to keep the previously edited content in view and scroll to find the Save button.
- **Coordinate-based** (target has no index; follow the three principles above): `click_at`, `double_click_at`, `right_click_at`, `hover_at` (`goal`, `x`, `y`); `type_text_at` (`goal`, `x`, `y`, `text`)
- `press_keys` (`goal`, `keys`)
- `wait` (`goal`, `seconds`)

**multi_select_by_index — when to use:** Use when the **annotated screenshot shows index numbers** (e.g. [1], [2], [3]) on the items: web lists, in-app lists, checkbox groups, web file pickers, CAPTCHA image grids. Prefer it over multiple single clicks.

Parameter constraints:
- `goal` is required for all methods. Describe the **anchor/target** concretely so the action is unambiguous:
  - **Text as anchor**: include the **exact visible text** (e.g. “paragraph starting with ‘Upload your files’”, “button labeled ‘Copy’”).
  - **Icon or image as anchor**: add a **brief description of the image** (e.g. “folder icon”, “blue arrow pointing right”, “avatar thumbnail”).
  - **File selection**: when the target is a **file** in a list or file picker, **prefer the index whose bbox wraps the file name** (the visible filename text), not the file icon or the whole row.
  - **Other**: give **position and features** (e.g. “checkbox in top-right of the card”, “first row in the list, left cell”). Then add what you do and the expected result.
- Optional `delta_x`, `delta_y` (index-based): pixel offset; for click_index, double_click_index, type_text_at_index, right_click_index, hover_index, scroll_at_index. Not used for drag_index_to_index. **Optional `target_in_bbox`**: `"inside"` or `"outside"` (default). You must specify whether the target is inside or outside the reference (numbered) bbox — this is important.
- **Coordinate-based** `x`, `y`: required for click_at, double_click_at, right_click_at, hover_at, type_text_at. **Normalized coordinates** in the prompt’s scale; converted to pixels at execution. Reference must have explicit coordinates and be within 50 pixels of the target; derive x, y from that anchor—do not guess. Generally: hover_index to a nearby marked element first, then use these tools.
- `wait.seconds`: 0-60.

**Scroll workflow:**
- **When the mouse is already inside the scrollable area:** you may use `scroll_at_current` directly (no need to call `scroll_at_index` first).
- **When you need to target a specific region:** use `scroll_at_index` first to position and scroll; then use `scroll_at_current` for further scrolls in the same area (no re-targeting).
- **Scroll amount:** generally use **10** or **-10**. Use **5** or **-5** when you want to keep the previously edited content in view and scroll to find the Save button.

**Scroll anchor (for `scroll_at_index`):** If the scrollable area is a **list**, prefer using the **text of a list item** (e.g. a visible row title or label) as the scroll target. Be specific. If the anchor is **text**, include the **actual text content** in the goal (e.g. “line ‘Material info’”). If it is an **icon or image**, briefly describe it (e.g. “folder icon”, “thumbnail”). Otherwise give **position and features** (e.g. “first list item, left side”). Prefer an element **inside** the scrollable region; do **not** use a large heading (often outside the viewport).
**Before calling a scroll tool:** In `thoughts`, clearly describe the content at the **top** and **bottom** of the scroll region (e.g. last visible line, first visible line). This lets you verify on the next screenshot that the scroll actually happened.

**Reading task workflow:**
1. Extract current visible content → `extract_data:extract`
2. First scroll: `scroll_at_index` to position and scroll to next section
3. Further scrolls: `scroll_at_current` (same amount convention)
4. Repeat: extract → scroll → extract → scroll until reading complete
5. When subtask complete: call `task_done` with `task_index` (fragments are auto-merged)
6. When a later step needs another task’s data: `extract_data:load` (may call in the middle). **Only at the end**, when you need all data for the final response: `task_done:read`

Examples:

Single click:
```xml
<response>
  <thoughts>Clicking submit button in bottom right to submit form</thoughts>
  <tool_name>vision_actions:click_index</tool_name>
  <tool_args>
    <index>4</index>
    <goal>Click submit button to submit form</goal>
  </tool_args>
</response>
```

Multi-select by index (select several items at once):
```xml
<response>
  <thoughts>Selecting list rows 2, 4, 6 for batch delete</thoughts>
  <tool_name>vision_actions:multi_select_by_index</tool_name>
  <tool_args>
    <indices>[2, 4, 6]</indices>
    <goal>Select list rows 2, 4, 6 to batch delete</goal>
  </tool_args>
</response>
```
