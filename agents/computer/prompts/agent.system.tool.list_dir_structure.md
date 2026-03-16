### list_dir_structure

Use at the **start of a subtask** when the target is a directory (e.g. choosing a file from a folder, uploading from Downloads/Documents). Returns the directory and file list **breadth-first** (top-level dirs and files first, then next level): **one full relative path per line** (like `find`), so you can plan navigation or file selection without opening each subfolder.

**tool_args:**
- `path` (required) — Directory path, e.g. `~/Downloads`, `~/Documents`, or an absolute path. Tilde `~` is expanded to the user home.
- `max_entries` (optional) — Maximum number of lines in the output (default **100**). If exceeded, output is truncated; call again with a deeper subdir path when you need details.

**When to use:** Call with the **root path** first to get the top-level structure. **Call again for a subdirectory only when you are about to execute a concrete task there** (e.g. open a file in that subdir, upload from that folder)—get subdir structure on demand, not in advance. If the result is truncated (too many entries), use a deeper subdir path when you need details for that subtree.

Example:
```xml
<tool_name>list_dir_structure</tool_name>
<tool_args>
  <path>~/Downloads</path>
</tool_args>
```
