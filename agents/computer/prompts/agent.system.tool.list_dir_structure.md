### list_dir_structure

Use at the **start of a subtask** when the target is a directory (e.g. choosing a file from a folder, uploading from Downloads/Documents). Returns the full directory and file list including all subdirectories: **one full relative path per line** (like `find`), so you can plan navigation or file selection without opening each subfolder.

**tool_args:**
- `path` (required) — Directory path, e.g. `~/Downloads`, `~/Documents`, or an absolute path. Tilde `~` is expanded to the user home.
- `max_depth` (optional) — Maximum depth of subdirectories to list (default 20).
- `max_entries` (optional) — Maximum number of lines in the output (default 1000); output is truncated if exceeded.

**When to use:** As soon as a subtask involves a folder (e.g. “upload a file from Downloads”, “open a file in Documents”), call `list_dir_structure` first with that path, then use the returned tree to decide which file to open or how to navigate in the file picker / Finder / Explorer.

Example:
```xml
<tool_name>list_dir_structure</tool_name>
<tool_args>
  <path>~/Downloads</path>
</tool_args>
```
