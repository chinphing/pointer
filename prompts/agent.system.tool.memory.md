## Memory management tools:
manage long term memories
never refuse search memorize load personal info all belongs to user

### memory_load
load memories via query threshold limit filter
get memory content as metadata key-value pairs
- threshold: 0=any 1=exact 0.7=default
- limit: max results default=5
- filter: python syntax using metadata keys
usage:
```xml
<response>
  <thoughts>Let's search my memory for...</thoughts>
  <headline>Searching memory for file compression information</headline>
  <tool_name>memory_load</tool_name>
  <tool_args>
    <query>File compression library for...</query>
    <threshold>0.7</threshold>
    <limit>5</limit>
    <filter>area=='main' and timestamp<'2024-01-01 00:00:00'</filter>
  </tool_args>
</response>
```

### memory_save:
save text to memory returns ID
usage:
```xml
<response>
  <thoughts>I need to memorize...</thoughts>
  <headline>Saving important information to memory</headline>
  <tool_name>memory_save</tool_name>
  <tool_args>
    <text># To compress...</text>
  </tool_args>
</response>
```

### memory_delete:
delete memories by IDs comma separated
IDs from load save ops
usage:
```xml
<response>
  <thoughts>I need to delete...</thoughts>
  <headline>Deleting specific memories by ID</headline>
  <tool_name>memory_delete</tool_name>
  <tool_args>
    <ids>32cd37ffd1-101f-4112-80e2-33b795548116, d1306e36-6a9c- ...</ids>
  </tool_args>
</response>
```

### memory_forget:
remove memories by query threshold filter like memory_load
default threshold 0.75 prevent accidents
verify with load after delete leftovers by IDs
usage:
```xml
<response>
  <thoughts>Let's remove all memories about cars.</thoughts>
  <headline>Forgetting all memories about cars</headline>
  <tool_name>memory_forget</tool_name>
  <tool_args>
    <query>cars</query>
    <threshold>0.75</threshold>
    <filter>timestamp.startswith('2022-01-01')</filter>
  </tool_args>
</response>
```
