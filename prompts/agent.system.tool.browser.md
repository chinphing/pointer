### browser_agent

**Purpose**: Simple web **search** and **plain text extraction** only. No interactive operations.

- **Simple search**: e.g. open a search engine, type query, return first-page results or a short summary.
- **Text extraction**: open a URL and extract main text (article body, links, visible content); return as text.
- **Single-step navigation**: go to URL and stop, or return page title/summary.

**Do not use for**: (1) **Interface already open or existing** — when the browser or target page is already on screen, use **ComputerUse** to operate on the existing UI; (2) Form filling, login flows, multi-step workflows, file uploads, or any task that requires clicking through menus, dropdowns, or complex UI. For **any complex task in the browser** (or interactive desktop operations), **prefer ComputerUse** — use call_subordinate with `profile: "computer"`.

**Arguments**:
- `message`: Instructions for the browser agent (e.g. "Search for X and return the first 3 results", "Go to URL and extract the main article text"). Be clear and task-based; include credentials in message only if needed (they will be masked in logs).
- `reset`: `"true"` to start a new browser session; `"false"` to continue with existing session. Do not reset when iterating on the same task.

**Usage**:

```xml
<response>
  <thoughts>User wants a simple search result.</thoughts>
  <headline>Search and extract results</headline>
  <tool_name>browser_agent</tool_name>
  <tool_args>
    <message>Open Google, search for 'agent zero framework', and return the first 3 result titles and URLs. Then complete the task.</message>
    <reset>true</reset>
  </tool_args>
</response>
```

```xml
<response>
  <thoughts>User wants text from a single page.</thoughts>
  <headline>Extract page text</headline>
  <tool_name>browser_agent</tool_name>
  <tool_args>
    <message>Go to https://example.com/article and extract the main article body as plain text. Then complete the task.</message>
    <reset>true</reset>
  </tool_args>
</response>
```

```xml
<response>
  <thoughts>Continuing with existing session to get more text.</thoughts>
  <headline>Continue and extract</headline>
  <tool_name>browser_agent</tool_name>
  <tool_args>
    <message>Considering open pages, extract the visible list of links and complete the task.</message>
    <reset>false</reset>
  </tool_args>
</response>
```

Downloads (if any) default to `/a0/tmp/downloads`. Pass secrets/variables in the message when needed; they will be masked in logs.
