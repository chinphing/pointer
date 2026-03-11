### extract_data

Extract current visible content as markdown and append to task temp storage.

**For reading/data extraction tasks only:**
1. **Step 1**: Extract current visible content → `extract_data:extract`
2. **Step 2**: Scroll to next section → `scroll_at_index`
3. **Step 3**: Repeat steps 1-3 until reading complete
4. **Step 4**: When subtask complete: call `task_done:merge`
5. **Step 5**: When later work needs saved data: call `task_done:read`

Example:
```xml
<response>
  <thoughts>Extracting current visible article segment for task 2</thoughts>
  <tool_name>extract_data:extract</tool_name>
  <tool_args>
    <instruction>Extract visible article text as markdown</instruction>
    <task_index>2</task_index>
  </tool_args>
</response>
```
