### wait
pause execution for a set time or until a timestamp
use args "seconds" "minutes" "hours" "days" for duration
use "until" with ISO timestamp for a specific time
usage:

1 wait duration
```xml
<response>
  <thoughts>I need to wait...</thoughts>
  <headline>Waiting for duration</headline>
  <tool_name>wait</tool_name>
  <tool_args>
    <minutes>1</minutes>
    <seconds>30</seconds>
  </tool_args>
</response>
```

2 wait timestamp
```xml
<response>
  <thoughts>I will wait until...</thoughts>
  <headline>Waiting until timestamp</headline>
  <tool_name>wait</tool_name>
  <tool_args>
    <until>2025-10-20T10:00:00Z</until>
  </tool_args>
</response>
```
