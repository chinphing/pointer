### vision_actions

Use these tools to operate UI by index, by absolute coordinates (screenshot pixels), keyboard, and wait.

Core rules:
- Re-identify target on current screenshot each turn.
- Use index-based tools when the target has an index on the annotated image.
- When the target has **no** index, use **coordinate-based** tools (`click_at`, `double_click_at`, `right_click_at`, `hover_at`, `type_text_at`) with `x`, `y` in **screenshot pixels**. **Use the screenshot width and height as the coordinate range**: x in [0, image width], y in [0, image height]. **Do not use normalized coordinates** (e.g. 0-1 or 0-1000). The prompt includes reference bboxes (5 nearest to the mouse). When inferring coordinates: first decide whether the target is INSIDE or OUTSIDE the reference bbox. **If inside:** derive x, y as a point within the reference bbox (e.g. bbox center, or the target's position within the box—left/center/right horizontally, top/center/bottom vertically). **If outside:** consider which of the four directions (above, below, left, right) the target lies relative to the reference element, and derive x, y accordingly.
- Use one action per turn.
- The prompt includes the current mouse position (screenshot coords) so you can judge after an action whether the click landed on target or deviated, and adjust strategy.
- For coordinate-based positioning: each step that brings the pointer **closer** to the target counts as success; you may try up to **3 times**—no need to hit the target in one shot. Validate from the next screenshot; retry if not yet on target.

Methods:
- `click_index`, `double_click_index`, `right_click_index`, `hover_index` (`index`, `goal`, optional `delta_x`, `delta_y`)
- `type_text_at_index` (`index`, `goal`, `text`, optional `clear_first`, `delta_x`, `delta_y`)
- `drag_index_to_index` (`index`, `to_index`, `goal`)
- `scroll_at_index` (`index`, `goal`, `amount`, optional `delta_x`, `delta_y`)
- **Coordinate-based** (target has no index; use prompt reference bboxes to infer x, y): `click_at`, `double_click_at`, `right_click_at`, `hover_at` (`goal`, `x`, `y`); `type_text_at` (`goal`, `x`, `y`, `text`)
- `type_text_focused` (`goal`, `text`)
- `press_keys` (`goal`, `keys`)
- `wait` (`goal`, `seconds`)

Parameter constraints:
- `goal` is required for all methods and should describe the action, target element (if any), and expected result.
- Optional `delta_x`, `delta_y` (index-based): target outside the anchor bbox. delta_x &gt; 0 = from right edge, &lt; 0 from left; delta_y &gt; 0 = from bottom edge, &lt; 0 from top. For click_index, double_click_index, type_text_at_index, right_click_index, hover_index, scroll_at_index. Not used for drag_index_to_index.
- **Coordinate-based** `x`, `y`: required for click_at, double_click_at, right_click_at, hover_at, type_text_at. **Screenshot pixel coordinates** with origin (0,0) at top-left. **Coordinate range: x in [0, image width], y in [0, image height]—use screenshot dimensions; do not use normalized coordinates (e.g. 0-1 or 0-1000).** Use the reference bboxes (5 nearest to the mouse) in the prompt: first decide if the target is INSIDE or OUTSIDE the reference bbox. If inside: infer x, y as a point within the bbox (e.g. bbox center or target position within the box). If outside: consider the four directions (above, below, left, right) relative to the reference element to infer the target position.
- `amount` for scroll: scroll wheel notches. Valid range: 1-30. Positive=up, negative=down.
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
