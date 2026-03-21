### hotkey

Use for keyboard shortcuts (e.g. Copy, Paste, Save, Undo).

**Call priority:** Prefer **composite_action** or **hotkey** when one call achieves the goal. Use **hotkey** when the action is only a key combination (no click or text input).

Parameters (in `tool_args`; no separate method name):
- **`goal`** (required): Describe the action and expected result. If the shortcut applies to a visible target (e.g. a button or menu), describe that **target element**: **text** — include the exact visible text; **other** — brief description of features (e.g. Save button, folder icon).
- **`keys`** (required): list of modifier and key names, e.g. `["command", "c"]` (macOS) or `["ctrl", "c"]` (Windows/Linux); may also be a comma-separated string or JSON array string.
