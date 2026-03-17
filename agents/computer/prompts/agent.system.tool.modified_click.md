### modified_click

Use for **modifier+click** to multi-select: **Cmd/Ctrl+click** (add non-contiguous items) or **Shift+click** (select a contiguous range).

**Call priority:** Prefer **modified_click** when selecting multiple items in one call instead of multiple single clicks.

**Modifier behavior:**
- **Cmd (macOS) / Ctrl (Windows/Linux) + click** — Add each clicked item to the selection (non-contiguous). Use when selecting scattered items (e.g. rows 2, 5, 7). Pass all indices in `indices` (e.g. `[2, 5, 7]`); do **not** set `range_select`.
- **Shift + click** — Select a contiguous range from first to last. Use when selecting "from item A to item B" (e.g. rows 3 through 8). Pass **only the first and last index** in order as `indices` (e.g. `[3, 8]`) and set **`range_select`: true**. The tool will click the first item, then Shift+click the last item so the UI selects the range.

Methods:
- **`modified_click_index`** (`indices`, `goal`, optional `range_select`) — By default holds Cmd/Ctrl and clicks each index (add to selection). If **`range_select`: true**, `indices` must be exactly two numbers `[first, last]` in order; the tool clicks first then Shift+clicks last to select the range. Use when the annotated screenshot shows index numbers on list items, checkboxes, or file picker items.
- **`modified_click_at`** (`goal`, `positions`, optional `range_select`) — Same modifier logic by position: list of `{x, y}` or `[x, y]`. For range, pass two positions and `range_select`: true.

Parameter constraints:
- **`goal`** is required. Describe the **target elements**: if an item is **text**, include the **exact visible text**; if **other** (icon, row, checkbox), give a **brief description of its features**. Then state which items you are selecting and the expected result.
