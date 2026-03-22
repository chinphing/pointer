### extract_data

Two methods: **extract** (capture and save; response includes a short summary of what was saved) and **load** (load previously saved task data for use in a later task—no re-extraction).

**Do not use for CAPTCHA/code verification.** When the screen shows a CAPTCHA (image grid, slider, distorted text + input, "select all that contain…", etc.), use **captcha_verify** directly — do not call extract_data first to "read the CAPTCHA requirement". captcha_verify infers type and requirement from the screenshot; extract_data is for reading page/content for later use, not for preparing CAPTCHA actions.

---

#### extract_data:extract

Extract current visible content as markdown and append to the task’s temp storage. The response includes a **saved data summary** (length is configurable via agent data `computer_extract_summary_max_chars` if set) so you see what was stored without re-reading.

**tool_args:**
- `instruction` (required) — What to extract from the screen.
- `task_index` (required) — Which task this extract belongs to.

After extract, scroll if needed and extract again. **Do not** call **`task_done:checkpoint`** just because this subtask’s reading is done — checkpoint **only** when **Mandatory (task_done reminder)** appears (N assistant turns; Settings). To use this data in a **later** task, call `extract_data:load` (merges fragments on demand if not yet checkpointed) or wait until a checkpoint/read has produced a merged file.

---

#### extract_data:load

When a **later** task needs the full content of one or more previously saved tasks (merged files and/or fragment files from **`extract_data:extract`**), call `extract_data:load` with that task_index (or list). You **may** call load in the middle of the workflow whenever a step actually needs another task’s data (e.g. task 3 needs task 1’s content → load task 1). Do not re-extract; load directly.

**tool_args:**
- `task_index` (required) — One task index, or multiple: pass a list `[1, 2, 3]` or comma-separated `"1,2,3"` to load several tasks at once. The response will include sections `=== Task N ===` for each.

Prefer tasks already checkpointed with **`task_done:checkpoint`** (merged). **Fallback:** if a task has not been merged yet, load will merge its fragments first and then return the merged content (same merge as checkpoint).

---

**Workflow:**
1. Extract current view → `extract_data:extract` (response shows saved summary).
2. Scroll → extract again as needed until the read pass for that subtask is done.
3. When **Mandatory (task_done reminder)** appears (~N assistant turns) → **`task_done:checkpoint`** with the appropriate `task_index` + **`plans`** (merge + truncate). **Ideal:** you **just finished** that subtask’s extract/read cycle; if not, checkpoint with current `plans`/`progress` anyway.
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
