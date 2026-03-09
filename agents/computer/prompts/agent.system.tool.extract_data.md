### extract_data

Extract visible content from the **current screen** as **markdown** and append it to a **task-specific temp file**. Use when you need to **read or extract page data for temporary storage** (e.g. before scrolling, because after scrolling the current content is no longer visible).

**Trigger:** When you need to read or extract page data for temporary storage—especially **before each scroll**: scroll away and the current view is lost, so you must extract and save the current visible content first. After you have read all content via multiple extracts, call **task_done** to summarize the full article or result.

**Output format:** Markdown. The tool appends each extraction to the task's temp file with a "Target" (your instruction) and "Content" (extracted markdown).

**tool_args:**
- `instruction` (string, required): What to extract from the screen (e.g. "All visible text in the article body", "Table rows as markdown", "List of links").
- `task_index` (integer, required): Subtask index for file naming. Same index used later in **task_done** to read and summarize this task's extractions.

**Rule:** Before each scroll, extract the currently visible content with **extract_data** and save; only then scroll. When you have collected all segments for a subtask, call **task_done** with that subtask's index to produce the final summarized content.

**Example**

~~~json
{
    "thoughts": ["Visible article segment; extracting before scrolling. Task index 2."],
    "tool_name": "extract_data:extract",
    "tool_args": {
        "instruction": "Extract all visible article text as markdown (paragraphs, headings).",
        "task_index": 2
    }
}
~~~
