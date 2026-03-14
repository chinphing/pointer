### extract_data

Two methods: **extract** (capture and save; response includes a short summary of what was saved) and **load** (load previously saved task data for use in a later task—no re-extraction).

---

#### extract_data:extract

Extract current visible content as markdown and append to the task’s temp storage. The response includes a **saved data summary** (length is configurable via agent data `computer_extract_summary_max_chars` if set) so you see what was stored without re-reading.

**tool_args:**
- `instruction` (required) — What to extract from the screen.
- `task_index` (required) — Which task this extract belongs to.

After extract, scroll if needed and extract again, or call `task_done` with this `task_index` when the task is complete. To use this data in a **later** task, call `extract_data:load` with that task’s `task_index` after it has been saved by `task_done`.

---

#### extract_data:load

When a **later** task needs the full content of one or more previously saved tasks (via `task_done`), call `extract_data:load` with that task_index (or list). You **may** call load in the middle of the workflow whenever a step actually needs another task’s data (e.g. task 3 needs task 1’s content → load task 1). Do not re-extract; load directly.

**tool_args:**
- `task_index` (required) — One task index, or multiple: pass a list `[1, 2, 3]` or comma-separated `"1,2,3"` to load several tasks at once. The response will include sections `=== Task N ===` for each.

Prefer tasks already completed with `task_done` (merged). **Fallback:** if a task has not been merged yet, load will merge its fragments first and then return the merged content (same as task_done merge).

---

**Workflow:**
1. Extract current view → `extract_data:extract` (response shows saved summary).
2. Scroll → extract again as needed until the task is done.
3. When the task is done → `task_done` with that `task_index` (response shows saved-data summary).
4. When a **later** task needs another task’s full content → `extract_data:load` with that task_index (you may call load in the middle whenever a step needs it).
5. **Only at the end**, when you need **all** saved data for the final response → `task_done:read` (then use the result and call `response`).

Example (extract):
```xml
<tool_name>extract_data:extract</tool_name>
<tool_args>
  <instruction>Extract visible article text as markdown</instruction>
  <task_index>2</task_index>
</tool_args>
```

Example (load):
```xml
<tool_name>extract_data:load</tool_name>
<tool_args>
  <task_index>1</task_index>
</tool_args>
```
