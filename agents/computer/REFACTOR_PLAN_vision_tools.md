# Plan: Split vision_actions into 5 tools and remove delta_x/delta_y

## Overview

Split the single `vision_actions` tool into five tools (mouse, hotkey, modified_click, composite_action, wait), add a clear call-priority rule in prompts, and remove delta_x/delta_y (and target_in_bbox) from all tools. **keyboard** is omitted for now (no current use). **wait** is a separate tool (not part of hotkey).

---

## 1. Tool split and method assignment


| Tool                 | Purpose                                | Methods                                                                                                                                                                              |
| -------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **composite_action** | One-call combos (preferred)            | `type_text_at_index`, `type_text_at`, `scroll_at_index`                                                                                                                              |
| **hotkey**           | Keyboard shortcuts                    | `press_keys`                                                                                                                                                                         |
| **modified_click**   | Modifier+click (e.g. Cmd/Ctrl+click to multi-select) | `modified_click_index` (`indices`, `goal`), `modified_click_at` (`goal`, `positions` — list of `{x, y}` or `[[x,y], ...]`)                                                          |
| **mouse**            | Clicks, hover, drag, scroll at current | `click_index`, `double_click_index`, `right_click_index`, `hover_index`, `drag_index_to_index`, `click_at`, `double_click_at`, `right_click_at`, `hover_at`, **`scroll_at_current`**  |
| **wait**             | Pause / delay                         | `wait` (`goal`, `seconds`)                                                                                                                                                           |


**Note:** `scroll_at_current` is a **basic mouse operation** (scroll at current cursor position; no move+scroll combo), so it belongs in **mouse**, not composite_action. `scroll_at_index` (move to index then scroll) stays in **composite_action**.

**Call priority:** Prefer fewest tool calls → composite_action first, then hotkey and modified_click, then mouse. Use **wait** when a delay is needed (e.g. loading).

---

## 2. Remove delta_x, delta_y, target_in_bbox

- In `agents/computer/tools/vision_actions.py` (or in shared helper used by new tools):
  - In `_get_single_index_pos`: always use index center only; remove use of `_resolve_position` and all delta/target_in_bbox.
  - Remove or simplify `_resolve_position` (no longer used).
- In all tool prompts: remove every mention of `delta_x`, `delta_y`, and `target_in_bbox`.

---

## 3. Shared helper (vision_common)

- Create `agents/computer/tools/vision_common.py`: index_map/screen_info access, `_resolve_index(index_map, index)` → `[x, y]`, `_get_coord_pos(agent, args)` for coordinate-based, scroll amount clamping, `_scroll_effect_message_from_changed`, `LAST_VISION_ACTION_KEY`, etc. All five tools import from here.

---

## 4. Five new tools and prompts

- **mouse** — `agents/computer/tools/mouse.py`, `agent.system.tool.mouse.md`: methods listed above including **scroll_at_current**.
- **hotkey** — `agents/computer/tools/hotkey.py`, `agent.system.tool.hotkey.md`: `press_keys` only.
- **modified_click** — `agents/computer/tools/modified_click.py`, `agent.system.tool.modified_click.md`: methods **`modified_click_index`** (`indices`, `goal` — multi-select by index), **`modified_click_at`** (`goal`, `positions` — list of normalized coords `[{x,y}, ...]` or `[[x,y], ...]`; modifier+click at each position).
- **composite_action** — `agents/computer/tools/composite_action.py`, `agent.system.tool.composite_action.md`: `type_text_at_index`, `type_text_at`, `scroll_at_index` (no scroll_at_current).
- **wait** — `agents/computer/tools/wait.py`, `agent.system.tool.wait.md`: `wait` (`goal`, `seconds`).

---

## 5. Deprecate vision_actions

- Remove `agents/computer/tools/vision_actions.py` and `agents/computer/prompts/agent.system.tool.vision_actions.md` after the five tools and prompts are in place and all references updated.

---

## 6. Update references

- Replace `vision_actions:`* with new tool names in:
  - `agents/computer/prompts/agent.system.main.communication.md`
  - `agents/computer/prompts/agent.system.main.computer_usage.md`
  - `agents/computer/README.md`
- Add priority rule: “Prefer fewest tool calls: composite_action first, then hotkey and modified_click, then mouse.”

---

## 7. after_execution and LAST_VISION_ACTION_KEY

- Each of the five tools should call a shared helper in `after_execution` that sets `LAST_VISION_ACTION_KEY` (tool name + method + args + result) and does the short sleep, so screen inject and logging stay consistent.

