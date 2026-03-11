### vision_actions

Use these tools to operate UI by index, coordinates, keyboard, and wait.

Core rules:
- Re-identify target on current screenshot each turn.
- Prefer index-based tools; use coordinate tools only when no reliable index.
- Use one action per turn.
- Validate result from next screenshot; retry if uncertain.

Methods:
- `click_index`, `double_click_index`, `right_click_index`, `hover_index` (`index`, `goal`)
- `type_text_at_index` (`index`, `goal`, `text`, optional `clear_first`)
- `drag_index_to_index` (`index`, `to_index`, `goal`)
- `scroll_at_index` (`index`, `goal`, `amount`)
- `click_at`, `double_click_at`, `right_click_at`, `hover_at` (`x`, `y`, `goal`)
- `type_text_at` (`x`, `y`, `goal`, `text`)
- `type_text_focused` (`goal`, `text`)
- `press_keys` (`goal`, `keys`)
- `wait` (`goal`, `seconds`)

Parameter constraints:
- `goal` is required for all methods and should describe the action, target element (if any), and expected result, e.g., "Click the 'Download PDF' link to open the file", "Click submit button to submit form", "Scroll down to load more items".
- `x`, `y`: pixel coordinates in image bounds.
- `amount` for scroll: scroll wheel notches (1 notch ≈ 20-30 pixels). Valid range: 1-30. Positive=up, negative=down. Typical: 5-10 for small scroll, 15-25 for page scroll.
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
