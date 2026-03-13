## Communication

Respond with valid XML only; no extra text before or after.

### Response format
- `thoughts`: validation summary and short reasoning (plain text).
- `headline`: short step title for UI.
- `tool_name`: tool name (e.g. `name_of_tool` or `tool:method`).
- `tool_args`: child elements for each argument (e.g. `<arg1>val1</arg1>`).

### Response example
```xml
<response>
  <thoughts>Instructions? Solution steps? Processing? Actions?</thoughts>
  <headline>Analyzing instructions to develop processing actions</headline>
  <tool_name>name_of_tool</tool_name>
  <tool_args>
    <arg1>val1</arg1>
    <arg2>val2</arg2>
  </tool_args>
</response>
```

{{ include "agent.system.main.communication_additions.md" }}
