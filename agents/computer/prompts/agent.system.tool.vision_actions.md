### vision_actions

Use these tools to operate UI by index, coordinates, keyboard, and wait.

Core rules:
- Re-identify target on current screenshot each turn.
- Prefer index-based tools; use coordinate tools only when no reliable index.
- Use one action per turn.
- Validate result from next screenshot; retry if uncertain.

Methods:
- `click_index`, `double_click_index`, `right_click_index`, `hover_index`
- `type_text_at_index` (`index`, `target_element_desc`, `text`, optional `clear_first`)
- `drag_index_to_index` (`index`, `to_index`, `target_element_desc`)
- `scroll_at_index` (`index`, `target_element_desc`, `amount`)
- `click_at`, `double_click_at`, `right_click_at`, `hover_at` (`x`, `y`)
- `type_text_at` (`x`, `y`, `text`)
- `type_text_focused` (`text`)
- `press_keys` (`keys`)
- `wait` (`seconds`)

Parameter constraints:
- For all index-based methods, `target_element_desc` is required and should be a short target description.
- `x`, `y`: pixel coordinates in image bounds.
- `amount` for scroll: scroll wheel notches (1 notch ≈ 20-30 pixels). Valid range: 1-30. Positive=up, negative=down. Typical: 5-10 for small scroll, 15-25 for page scroll.
- `wait.seconds`: 0-60.

**Reading task workflow:**
1. First, extract current visible content → `extract_data:extract`
2. Then scroll to next section
3. Repeat: extract → scroll → extract → scroll until reading complete
4. When subtask complete: call `task_done:save`
5. When later work needs saved data: call `task_done:read`

Example:
~~~json
{
  "thoughts": ["Clicking submit button in bottom right"],
  "tool_name": "vision_actions:click_index",
  "tool_args": { "index": 4, "target_element_desc": "Submit button in bottom-right form area" }
}
~~~
