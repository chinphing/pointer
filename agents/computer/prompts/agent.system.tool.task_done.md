### task_done

Task done has two methods: **save** and **read**.

---

#### task_done:save

Use when one subtask is complete.
It merges all extracts for the `task_index` and saves formal output.

**tool_args:**
- `task_index` (required)

Example:

~~~json
{
    "thoughts": ["Subtask 2 extraction complete, saving merged result"],
    "tool_name": "task_done:save",
    "tool_args": { "task_index": 2 }
}
~~~

---

#### task_done:read

Use when subsequent work needs saved data (response, analysis, comparison, synthesis).
It loads all saved task outputs and cleans task storage.

**tool_args:** none

Example:

~~~json
{
    "thoughts": ["Need saved task data for next step, loading all results"],
    "tool_name": "task_done:read",
    "tool_args": {}
}
~~~

**Workflow summary:**
1. For each subtask: `extract_data:extract` (multiple times) → `task_done:save` (once per subtask)
2. When later work needs data: `task_done:read` → continue with response or processing
