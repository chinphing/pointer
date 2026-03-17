### composite_action

Use for **one-call combos** that achieve the goal in a single tool call: click+type, or move+scroll. Prefer this over calling **mouse** then **hotkey** or **mouse** multiple times when one composite call is enough.

**Call priority:** Prefer **fewest tool calls**. Use **composite_action** first when the task is “click and type” or “scroll at a specific element”; then hotkey and modified_click; then mouse. Use **wait** when a delay is needed (e.g. loading).

**Reminder:** Click and type can be done **in one call** with composite_action (`type_text_at_index` or `type_text_at`). Do not call mouse:click_index then type separately — use one composite_action call.

Methods:
- **`type_text_at_index`** (`index`, `goal`, `text`, optional `clear_first`) — Clicks the element at index to focus, then types. Use when the target has an index; do not call mouse:click_index first. `clear_first`: if true, selects all then types (replacing existing content).
- **`type_text_at`** (`goal`, `x`, `y`, `text`) — Clicks at normalized coordinates then types. Use when the target has no index; derive x, y from a reference.
- **`scroll_at_index`** (`index`, `goal`, `amount`) — Moves to the element at index and scrolls there. Amount: positive = up, negative = down; valid range 1–10 or -10–-1; generally use 10 or -10. Use 5 or -5 to keep previously edited content in view while scrolling to find e.g. Save button.

Parameter constraints:
- **`goal`** is required. Describe the **target element**: if the target is **text**, include the **exact visible text**; if it is another element (icon, image, button), give a **brief description of its features** (e.g. folder icon, blue arrow). Then state the action and expected result.
- For scroll_at_index, prefer an element **inside** the scrollable region (e.g. a list item); avoid large headings outside the viewport.
