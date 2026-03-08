### extract_data

Extract structured data from the **current screen** using the vision model.

**When to use vs. when to do it in thoughts:** For **simple, small data** (e.g. a few items, one short paragraph, a single number or label), you can **read the screen and write the result directly in your thoughts** or in the next response—no need to call extract_data. Use **extract_data:extract** only when the data is **complex or large**: e.g. **tables** (multiple rows/columns), **many fields** (long lists, forms with many values), or content that benefits from structured extraction (JSON, repeated rows). This keeps tool use for cases where the extra pass is worthwhile.

- **extract_data:extract** — Take a screenshot, send it to the vision LLM with your extraction instruction, and return the extracted content. **tool_args**: `instruction` (string, required): what to extract (e.g. "extract all visible links as a list of {text, url}", "return the table as JSON", "list the menu items").

**Visibility and scroll (reliability):** Data from a **single view of the full target** (e.g. full table) is more reliable than splitting into two or more extractions. When possible, **scroll first** so the full target is visible, then extract once. When the full target cannot fit in one view, **scroll in small, continuous steps** so each new visible region overlaps or is adjacent to the previous one—avoid large scrolls that skip a middle portion and cause that content to be never captured.

**Priority**: Use this when the user's goal is to **obtain data** from the screen rather than to perform a click or navigation. For actions (click, type, scroll), use vision_actions index or coordinate tools.

**tool_args**:
- `instruction` (string, required): Clear description of what to extract and in what form (text, JSON, list, table). Example: "Extract all links on the page as a list with 'text' and 'url'."

**Example**

~~~json
{
    "thoughts": ["User asked for all links on the page. I'll use extract_data with an instruction to get links as a list."],
    "tool_name": "extract_data:extract",
    "tool_args": { "instruction": "Extract all visible links as a list of objects with 'text' and 'url'. Return as JSON array." }
}
~~~
