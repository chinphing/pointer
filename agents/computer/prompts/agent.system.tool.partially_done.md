### partially_done

Use **partially_done:save** when you have found important information or have **partially completed** the task. The tool **only saves** what you pass in tool_args and inserts it into the conversation; **it does not call an LLM to merge**. You must **perform the merge in your thoughts** before calling the tool.

- **partially_done:save** — Save the content you pass in **tool_args** to a file (one per session) and **insert it into the conversation history** as factual context. **tool_args** must already contain the **merged** snapshot (goal, completed, pending, etc.). At least one of goal/plan/completed/pending/experience/current_step/last_error required unless clearing. Optional: `trim_history_before` (boolean), `step`, `version`, `clear` (boolean).

**Merge in your thoughts (required)**
- Before calling partially_done:save, **do the merge in your thoughts**: read **all** "[Partially done]" blocks in the conversation (there may be **multiple** segments). **Merge all of them** with your current update into **one** coherent snapshot—goal, completed, pending, current step, experience (combine and deduplicate; keep completed as ground truth, append new completed items; merge pending; keep latest or most complete goal/plan). Then pass that **single merged** result in tool_args. The tool saves exactly what you pass; it does not merge. So you must produce one merged document from all previous segments + current in your thoughts, then call the tool once with that result.

**When to use**
- You found important information or partially completed the task; you want to persist a concise “completed + pending” snapshot so later turns do not forget.
- Typical scenario: **multi-stage task**. Once a stage is completed, in your thoughts **merge all existing [Partially done] segments** plus your current update into one snapshot, then call partially_done:save **once** with that merged goal/completed/pending. The saved result is always **one** merged document, not multiple segments.

**Goal and completed (important)**
- When using this tool, you can **leave `current_step` empty** and put the summary in **`goal`**: state what has already been done and what you will do next. Example phrasing for **goal**: “We have already [obtained X / completed Y]. Next we will [Z].”
- The **completed** part must be **ground truth** and **cannot be changed** in later merges—only appended to or refined. Write completed as a concise, factual summary of what is truly done (e.g. “Obtained xxx information.” “Finished booking hotel (time).”).
- **Data-extraction or reading tasks**: For tasks that involve **extracting data** (e.g. list, table, links) or **reading content** (e.g. PDF pages, articles), **Completed must include the detailed extracted/read data**, not only a one-line summary. Put the actual extracted list, table rows, key points, or read text (or a structured summary of it) in `completed` so it is persisted and available for the final answer. Example: instead of only “Read page 1”, write “Page 1 key points: (1) … (2) …” or include the extracted table/link list. This way the data is not lost when history is trimmed.
- **Examples for goal**: (1) “We have already [obtained X / completed Y]; next we will [Z] based on this.” (2) “We have already [finished step A]; next we will [step B].”

**Staged-progress markers** — When either applies, **state in your thoughts that you did data extraction** (via extract_data or by reading and writing in thoughts), then call **partially_done:save** and put the data in `completed`. **Rule: if your thoughts contain a staged-progress description** (e.g. "Staged progress: completed [step/item]; next [goal]"), your **tool_name in that same reply must be partially_done:save**—do not only write the progress in thoughts and then use another tool.
- **Marker 1 — Completed an important step**: You finished a planned item (e.g. step 1, first form, page 1). Obtain any data (extract_data for complex, or write in thoughts for simple); state in thoughts that you did data extraction; then partially_done:save with `completed` / `goal` updated (completed = ground truth; goal = “already X, next Y”).
- **Marker 2 — Partial data visible**: In a data-extraction task, the target data (or part of it) is now on screen. Obtain it (extract_data for tables/many fields, or read and write in thoughts for simple); state in thoughts that you did data extraction; then partially_done:save and put the **detailed data** in `completed`—not just “extracted section 1”. For reading tasks, put the **detailed read content** (key points, paragraphs, or structured summary) in `completed`. Repeat for each segment; use the saved results when building the final answer.

**Goal and plan**: **goal** = task’s objective and/or “already done + next” summary (you merge these in thoughts). **plan** = overall plan (steps or sub-goals).

**Experience**: Each item should state **environment and goal** first (e.g. "In the browser PDF reader"), then what worked or failed. Prefer **position and visual description** for UI elements, not index numbers.

**tool_args**:
- `goal` (string, optional): Final objective or “We have already [X]; next we will [Y].” (can carry the stage summary when step is left empty).
- `plan` (string, optional): Overall plan (steps or sub-goals).
- `completed` (string, optional): Summary of what is done so far—**ground truth**, do not alter in later merges. For **data-extraction or reading tasks**, include the **detailed extracted/read data** (e.g. list of items, table rows, key points from the page), not only a one-line note like "Read page 1" (e.g. "Page 1: point A; point B. Page 2: point C." or the actual extracted list/table).
- `pending` (string, optional): What’s left to do.
- `current_step` (string, optional): Current page/step; can be left empty if you put “already + next” in goal.
- `last_error` (string, optional): Brief note if this step failed or errored.
- `experience` (string, optional): Lessons learned (environment + operation + result; prefer position/features over indices).
- `trim_history_before` (boolean, optional): If true, after inserting, trim **current topic** history to the **first user message** and this inserted result (saves tokens).
- `step` / `version` (optional): For multiple files per session (e.g. `partially_done_1.md`).
- `clear` (boolean, optional): If true, clear the session’s partially-done file (e.g. when starting a new task).

**Example** (goal/completed/pending apply to any multi-step or data-extraction task)

~~~json
{
    "thoughts": ["Merged all [Partially done] segments with current: completed first segment; next second segment then final step. Saving single merged snapshot.", "Staged progress: completed segment 1; saving with goal format."],
    "tool_name": "partially_done:save",
    "tool_args": {
        "goal": "We have already [completed first part]. Next we will [do second part], then [final step].",
        "plan": "1. [Step one]\n2. [Step two]\n3. [Step three]",
        "completed": "[Detailed data or key points from the completed segment—lists, table rows, or summary. For extraction/reading tasks include the actual content, not only a one-line note.]",
        "pending": "[Remaining segments or steps.]",
        "experience": "[Environment] [What worked or failed; prefer position/description over indices.]"
    }
}
~~~
