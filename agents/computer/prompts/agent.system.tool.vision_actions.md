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
- **Multi-select by index** — `multi_select_by_index` (`indices`, `goal`): Select **several items at once** (list rows, files, checkboxes). Tool holds Ctrl/Cmd and clicks each given index in order. **When to use**: "select multiple", "select items 1, 3, 5", "select several rows/files". **indices**: which item numbers to select — list of integers (e.g. `[1, 3, 5]`) or comma-separated string (e.g. `"1,3,5"`). Each must be a 1-based index on the annotated image.
- `type_text_at_index` (`index`, `goal`, `text`, optional `clear_first`, `delta_x`, `delta_y`, `target_in_bbox`)
- `drag_index_to_index` (`index`, `to_index`, `goal`)
- `scroll_at_index` (`index`, `goal`, `amount`, optional `delta_x`, `delta_y`, `target_in_bbox`)
     `amount` for scroll: scroll wheel notches. Valid range: [1, 30] for scroll  up. [-30, -1] for scroll down.
- `scroll_at_current` (`goal`, `amount`) — Scroll at **current cursor position** (no index). Use **after** you have already positioned with `scroll_at_index`; then keep using `scroll_at_current` for subsequent scrolls without re-targeting. Same `amount` convention: positive = up, negative = down.
- **Coordinate-based** (target has no index; follow the three principles above): `click_at`, `double_click_at`, `right_click_at`, `hover_at` (`goal`, `x`, `y`); `type_text_at` (`goal`, `x`, `y`, `text`)
- `type_text_focused` (`goal`, `text`)
- `press_keys` (`goal`, `keys`)
- `wait` (`goal`, `seconds`)

Parameter constraints:
- `goal` is required for all methods. Describe the **anchor/target** concretely so the action is unambiguous:
  - **Text as anchor**: include the **exact visible text** (e.g. “paragraph starting with ‘Upload your files’”, “button labeled ‘Copy’”).
  - **Icon or image as anchor**: add a **brief description of the image** (e.g. “folder icon”, “blue arrow pointing right”, “avatar thumbnail”).
  - **Other**: give **position and features** (e.g. “checkbox in top-right of the card”, “first row in the list, left cell”). Then add what you do and the expected result.
- Optional `delta_x`, `delta_y` (index-based): pixel offset; for click_index, double_click_index, type_text_at_index, right_click_index, hover_index, scroll_at_index. Not used for drag_index_to_index. **Optional `target_in_bbox`**: `"inside"` or `"outside"` (default). You must specify whether the target is inside or outside the reference (numbered) bbox — this is important.
- **Coordinate-based** `x`, `y`: required for click_at, double_click_at, right_click_at, hover_at, type_text_at. **Normalized coordinates** in the prompt’s scale; converted to pixels at execution. Reference must have explicit coordinates and be within 50 pixels of the target; derive x, y from that anchor—do not guess. Generally: hover_index to a nearby marked element first, then use these tools.
- `wait.seconds`: 0-60.

**Scroll workflow:**
- **First scroll** in a scrollable area: use `scroll_at_index` (e.g. on the scrollable container or a visible element in it) to position and scroll. **You may use `scroll_at_current` only after a successful `scroll_at_index`** (i.e. when the tool reports "scroll effect: screen content **changed**"). If `scroll_at_index` had no effect (screen unchanged), fix target or position and call `scroll_at_index` again; do not call `scroll_at_current` until the first scroll has taken effect.
- **Next scrolls** in the same area: use `scroll_at_current` only — no need to re-target by index; the cursor is already in the right place.

**Scroll anchor (for `scroll_at_index`):** Be specific. If the anchor is **text**, include the **actual text content** in the goal (e.g. “line ‘Material info’”). If it is an **icon or image**, briefly describe it (e.g. “folder icon”, “thumbnail”). Otherwise give **position and features** (e.g. “first list item, left side”). Prefer an element **inside** the scrollable region; do **not** use a large heading (often outside the viewport).
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
