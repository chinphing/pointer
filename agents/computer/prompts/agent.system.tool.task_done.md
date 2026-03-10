### task_done

Task done has two methods: **merge** and **read**.

---

#### task_done:merge

Use when one subtask is complete.
It merges all extracts for the `task_index` and saves formal output.

**tool_args:**
- `task_index` (required)

Example:

~~~json
{
    "thoughts": ["Subtask 2 extraction complete, merging and saving result"],
    "tool_name": "task_done:merge",
    "tool_args": { "task_index": 2 }
}
~~~

---

#### task_done:read

Use when subsequent work needs saved data (response, analysis, comparison, synthesis).
It loads all saved task outputs and cleans task storage.
**IMPORTANT: Only call `task_done:read` AFTER all `task_done:merge` calls are complete.**
Do not call `task_done:read` before saving all required data - it will be empty.

**tool_args:** none

Example:

~~~json
{
    "thoughts": ["All subtasks complete, loading saved results for final response"],
    "tool_name": "task_done:read",
    "tool_args": {}
}
~~~

**Workflow summary:**
1. For each subtask: `extract_data:extract` (multiple times) → `task_done:merge` (once per subtask)
2. After ALL subtasks are merged: `task_done:read` → continue with response or processing
