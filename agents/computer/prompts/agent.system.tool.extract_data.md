### extract_data

Extract structured data from the **current screen** using the vision model. Use this when the user asks to "get", "extract", "list", or "read" information from the screen (e.g. links, table content, form values, visible text).

- **extract_data:extract** — Take a screenshot, send it to the vision LLM with your extraction instruction, and return the extracted content. **tool_args**: `instruction` (string, required): what to extract (e.g. "extract all visible links as a list of {text, url}", "return the table as JSON", "list the menu items").

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
