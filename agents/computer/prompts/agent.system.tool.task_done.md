### task_done

When a **subtask is complete**, call `task_done` with `task_index`. The tool will **automatically** merge any extract fragments for that task (if present) and save the result; you do not call merge separately.

The response includes a **saved data summary** in the form: “Task N: saved … data. To use it, call extract_data:load with task_index=N.” When a later task needs that data, use `extract_data:load` with that `task_index` instead of re-extracting.

**Call timing:** Call **once per completed task** (with that task’s `task_index`). After each call, the tool stashes data, summarizes experience and progress, and clears prior history for the next task.

---

#### task_done (complete a task)

**tool_args:**
- `task_index` (required) — The subtask index you just finished.

If there are extract fragments for this task (from `extract_data:extract`), they are merged automatically and saved. If the tool reports no fragments (nothing to merge), note in plans that this task had no data and continue to the next subtask or call `task_done:read` when all tasks are done.

Example:

```xml
<response>
  <thoughts>Subtask 2 extraction complete, marking done</thoughts>
  <tool_name>task_done</tool_name>
  <tool_args>
    <task_index>2</task_index>
  </tool_args>
</response>
```

---

#### task_done:read

Use **only when you finally need the full content** of all saved tasks—e.g. to produce the user-facing response, do synthesis, comparison, or analysis. Until then, rely on the **summaries** already in each `task_done` response (e.g. “Task N: saved … data”); do not call read just to “have” the data.

Loads all saved task outputs and cleans task storage.

**tool_args:** none

**IMPORTANT:** Call `task_done:read` only (1) after every subtask has been marked complete with `task_done` (task_index), and (2) when you actually need the full text (e.g. right before calling `response` or doing final processing). Do not read all data in the middle of the workflow; summaries are enough for planning and progress.

Example:

```xml
<response>
  <thoughts>All subtasks complete, loading saved results for final response</thoughts>
  <tool_name>task_done:read</tool_name>
  <tool_args>
  </tool_args>
</response>
```

**Workflow summary:**
1. For each subtask: `extract_data:extract` → when done → **task_done** with that **task_index** (response gives a saved-data summary). For a later step that needs one task’s full content, use **extract_data:load** (you may call load in the middle).
2. **Only at the end**, when you need **all** saved data for the final answer: call **task_done:read** once, then use the loaded content and call `response`.
