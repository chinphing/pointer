### task_done

Task done tool has two methods: **save** (complete a subtask) and **read** (load all results for further usage).

---

#### task_done:save

Call **task_done:save** when a **subtask is complete**: the tool reads that subtask's **extract_data** temp file, merges the segments via LLM into one coherent document, and saves as a formal file.

**When to call:** After you have finished all **extract_data** calls for a given subtask (e.g. full article extracted for task index 2). Call with **task_index** so segments are merged and saved.

**tool_args:**
- `task_index` (integer, required): The subtask index whose extractions to merge.

**Example — saving a completed subtask:**

~~~json
{
    "thoughts": ["Finished extracting full article for subtask 2. Calling task_done:save to merge segments."],
    "tool_name": "task_done:save",
    "tool_args": { "task_index": 2 }
}
~~~

---

#### task_done:read

Call **task_done:read** when you need to **use the saved subtask results** for subsequent work — whether for providing the final response, performing analysis, summarization, comparison, or any follow-up processing that requires the previously extracted data.

**What it does:**
1. Reads all saved task files from `task_done/<context_id>/`
2. Returns all content aggregated in the response
3. **Cleans up** the directory (removes all task_done and extract_data files)

**When to call:** Whenever subsequent tasks need the previously extracted data — whether that's for final response, cross-article comparison, data synthesis, or any processing that requires the saved results.

**tool_args:** None required.

**Example — loading all results for final response:**

~~~json
{
    "thoughts": ["All 3 articles have been extracted and saved. Now loading all results to provide the final summary to the user."],
    "tool_name": "task_done:read",
    "tool_args": {}
}
~~~

Then use the loaded data in your final **response**.

---

**Workflow summary:**
1. For each subtask: `extract_data:extract` (multiple times) → `task_done:save` (once per subtask)
2. When you need the data for subsequent work: `task_done:read` → use loaded data → continue with response, analysis, comparison, or other tasks
