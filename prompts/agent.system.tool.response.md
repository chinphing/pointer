### response

Final answer to the user. Ends task processing; use only when done or no task active. Put the result in the `text` arg.

Output format (XML):

```xml
<response>
  <thoughts>Brief reasoning for this final answer.</thoughts>
  <headline>Short headline for the response</headline>
  <tool_name>response</tool_name>
  <tool_args>
    <text>Full answer or result to the user.</text>
  </tool_args>
</response>
```

{{ include "agent.system.response_tool_tips.md" }}