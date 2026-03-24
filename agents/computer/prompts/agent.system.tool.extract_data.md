### extract_data

**Single operation:** **`extract_data:extract`** — capture visible content from the current screenshot, append it to the task’s temp storage (`extract_data` fragments), and return a **short saved-data summary** so you can see what was stored without re-reading the full text.

**Do not use for CAPTCHA/code verification.** When the screen shows a CAPTCHA (image grid, slider, distorted text + input, "select all that contain…", etc.), use **captcha_verify** directly — do not call extract_data first to "read the CAPTCHA requirement". captcha_verify infers type and requirement from the screenshot; extract_data is for reading page/content for later use, not for preparing CAPTCHA actions.

---

#### extract_data:extract

Extract current visible content as markdown and append to the task’s temp storage. The response includes a **saved data summary** (length is configurable via agent data `computer_extract_summary_max_chars` if set) so you see what was stored without re-reading.

**tool_args:**
- `instruction` (required) — What to extract from the screen.
- `task_index` (required) — Which task this extract belongs to.

After extract, scroll if needed and extract again. **Do not** call **`task_done:checkpoint`** just because this subtask’s reading is done — checkpoint **only** when **Mandatory (task_done reminder)** appears (N assistant turns; Settings). Merged text on disk comes from **`task_done:checkpoint`**; to pull **all** saved tasks into one reply at the end, use **`task_done:read`**. For cross-task context mid-flow, rely on recent **tool summaries**, **Persisted execution state**, and prior **`task_done:checkpoint`** results in the inject/history.

---

**Workflow:**
1. Extract current view → `extract_data:extract` (response shows saved summary).
2. Scroll → extract again as needed until the read pass for that subtask is done.
3. When **Mandatory (task_done reminder)** appears (~N assistant turns) → **`task_done:checkpoint`** with the appropriate `task_index` + **`plans`** (merge + truncate). **Ideal:** you **just finished** that subtask’s extract/read cycle; if not, checkpoint with current `plans`/`progress` anyway.
4. **Only at the end**, when you need **all** saved data for the final response → `task_done:read` (then use the result and call `response`).

Example:
```xml
<tool_name>extract_data:extract</tool_name>
<tool_args>
  <instruction>Extract visible article text as markdown</instruction>
  <task_index>2</task_index>
</tool_args>
```
