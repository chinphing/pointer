### task_done

Two methods only: **`task_done:checkpoint`** (merge + persist state + truncate history) and **`task_done:read`** (load all saved task data for the final answer). Do **not** call plain `task_done` without a method.

**Merges:** `extract_data:extract` only **appends** fragments. **LLM merge** runs **only** on **`task_done:checkpoint`**. **`task_done:read`** returns stored data **without** merging fragments on the fly: unmerged tasks appear as **raw** fragment text with a short notice. You **do not** need to checkpoint as soon as a subtask ends — fragments can sit on disk until the next checkpoint or until **`task_done:read`**.

**History:** After a successful **`task_done:checkpoint`**, the runtime **truncates the current topic’s message list** (tool/vision noise removed). **Plans, progress, and session experience** are persisted to disk and re-injected each vision turn as **Persisted execution state** — do not assume old tool transcripts are still in context.

**When to checkpoint (single rule):** Call **`task_done:checkpoint`** **only** when the screen inject shows **Mandatory (task_done reminder)** — i.e. after **N** assistant turns since the last checkpoint or read (N is **configurable in Settings**, default 20). **Ideal timing:** right **after** you finish the current subtask’s extraction/read work when you are at that threshold (same turn or one quick wrap-up turn first). If the reminder appears **mid-subtask**, checkpoint **now** with the active `task_index` and honest `plans` / `progress`.

---

#### task_done:checkpoint

**When:** **Only** when **Mandatory (task_done reminder)** is present (N assistant turns; Settings). Not after every subtask by default.

**tool_args:**
- `task_index` (required) — fragments for this task are merged (if any); merged file is saved for **`task_done:read`**
- `plans` (required) — full current `<plans>` markdown (same content as in your reply when you update the plan)
- `progress` (optional) — short progress note
- `learnings` or `experience_delta` (optional) — short reusable tips / problem→fix (no secrets); appended to **Experience and fixes**

If there are no extract fragments, merge is skipped; still persist `plans` / optional fields and truncate.

```xml
<response>
  <thoughts>N-turn reminder fired; subtask 2 reading done — checkpoint merge and state</thoughts>
  <headline>Checkpoint task 2</headline>
  <tool_name>task_done:checkpoint</tool_name>
  <tool_args>
    <task_index>2</task_index>
    <plans>
- 1. Foo — Done
- 2. Bar — Done
- 3. Baz — Pending
    </plans>
    <learnings>Site X: close cookie banner before clicking login.</learnings>
  </tool_args>
</response>
```

---

#### task_done:read

Use **only** when you need **all** saved task bodies for the final user answer. This call does **not** run an LLM merge: unmerged tasks appear as **raw** `extract_data` fragments in the response. Disk cleanup runs afterward (merged files and fragment files for this context).

**tool_args:** none

The response includes aggregated task content and a **Session experience summary** (from persisted learnings). Use that to **briefly** give the user reusable tips and fixes in your final **`response`** (no secrets).

**IMPORTANT:** Do not call `read` in the middle of the workflow only to peek at data — it is meant for the **final** aggregation step before **`response`**.

```xml
<response>
  <thoughts>All subtasks done; loading everything for final answer</thoughts>
  <tool_name>task_done:read</tool_name>
  <tool_args></tool_args>
</response>
```

**Workflow summary:**
1. During work: `extract_data:extract` / UI tools as needed — **no** checkpoint when a subtask ends unless the **Mandatory (task_done reminder)** is already showing.
2. When **Mandatory (task_done reminder)** appears: **`task_done:checkpoint`** with `task_index` + **`plans`** (+ optional `progress` / `learnings`); **prefer** doing it right after finishing that subtask’s read/extract when possible.
3. End: **`task_done:read`** once, then **`response`**.
