# User is not responding to your message.
If you have a task in progress, continue on your own.
If you have no task, use the **`response`** tool to say you are waiting for the user (do not invent unsupported tool args).

# Example
```xml
<response>
  <thoughts>No further work until the user replies.</thoughts>
  <headline>Waiting for user</headline>
  <tool_name>response</tool_name>
  <tool_args>
    <text>I have no more work for now; reply when you need anything.</text>
  </tool_args>
</response>
```
