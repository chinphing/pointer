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
- `type_text_at_index` (`index`, `goal`, `text`, optional `clear_first`, `delta_x`, `delta_y`, `target_in_bbox`)
- `drag_index_to_index` (`index`, `to_index`, `goal`)
- `scroll_at_index` (`index`, `goal`, `amount`, optional `delta_x`, `delta_y`, `target_in_bbox`)
     `amount` for scroll: scroll wheel notches. Valid range: [1, 30] for scroll  up. [-30, -1] for scroll down.
- **Coordinate-based** (target has no index; follow the three principles above): `click_at`, `double_click_at`, `right_click_at`, `hover_at` (`goal`, `x`, `y`); `type_text_at` (`goal`, `x`, `y`, `text`)
- `type_text_focused` (`goal`, `text`)
- `press_keys` (`goal`, `keys`)
- `wait` (`goal`, `seconds`)

Parameter constraints:
- `goal` is required for all methods and should describe the action, target element (if any), and expected result.
- Optional `delta_x`, `delta_y` (index-based): pixel offset; for click_index, double_click_index, type_text_at_index, right_click_index, hover_index, scroll_at_index. Not used for drag_index_to_index. **Optional `target_in_bbox`**: `"inside"` or `"outside"` (default). You must specify whether the target is inside or outside the reference (numbered) bbox — this is important.
- **Coordinate-based** `x`, `y`: required for click_at, double_click_at, right_click_at, hover_at, type_text_at. **Normalized coordinates** in the prompt’s scale; converted to pixels at execution. Reference must have explicit coordinates and be within 50 pixels of the target; derive x, y from that anchor—do not guess. Generally: hover_index to a nearby marked element first, then use these tools.
- `wait.seconds`: 0-60.

**Reading task workflow:**
1. First, extract current visible content → `extract_data:extract`
2. Then scroll to next section
3. Repeat: extract → scroll → extract → scroll until reading complete
4. When subtask complete: call `task_done:merge`
5. When later work needs saved data: call `task_done:read`

Example:
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
