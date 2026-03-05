### response

Use **only when the task is complete**: send your final answer to the user and **end the current agent run**. Calling this tool stops further screenshot/tool cycles.

- **tool_name**: `response`
- **tool_args**: `text` (string) — the final message to the user (summary, result, or confirmation).

~~~json
{
    "thoughts": ["Task completed. Sending final summary to user."],
    "headline": "Task complete",
    "tool_name": "response",
    "tool_args": {
        "text": "I have finished ... Here is the result: ..."
    }
}
~~~

Do not call response in the middle of a multi-step task; use it only when the goal is achieved or you have nothing left to do.
