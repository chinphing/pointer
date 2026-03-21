### Linux Shortcuts Reference

Primary modifier: `ctrl`

| Action | Shortcut | Tool Usage |
|---|---|---|
| Select All | `ctrl+a` | `keys ["ctrl","a"]` |
| Copy | `ctrl+c` | `keys ["ctrl","c"]` |
| Paste | `ctrl+v` | `keys ["ctrl","v"]` |
| Cut | `ctrl+x` | `keys ["ctrl","x"]` |
| Focus Address Bar | `ctrl+l` | `keys ["ctrl","l"]` |
| New Tab | `ctrl+t` | `keys ["ctrl","t"]` |
| Close Tab | `ctrl+w` | `keys ["ctrl","w"]` |
| Close Window | `alt+f4` | `keys ["alt","f4"]` |
| Refresh | `ctrl+r` or `f5` | `keys ["ctrl","r"]` |
| Find | `ctrl+f` | `keys ["ctrl","f"]` |
| Page Down / Scroll down | `space` | `keys ["space"]` |
| Page Up / Scroll up | `shift+space` | `keys ["shift","space"]` |
| Scroll to bottom | `ctrl+end` | `keys ["ctrl","end"]` |
| Scroll to top | `ctrl+home` | `keys ["ctrl","home"]` |

Notes:
- Prefer shortcuts over clicking UI buttons.
- Use `ctrl+l` for address bar even when it has no index.
- **Scroll/page**: When focus is in a scrollable area, use `space` / `shift+space` for page down/up, or `ctrl+end` / `ctrl+home` to jump to bottom/top. Use **scroll_at_index** when you need to scroll a specific region by mouse position.

---

### Linux: Folders and file operations

**Common folders (for locating or opening files):**
- `~/Desktop` — Desktop
- `~/Documents` — Documents (common default save)
- `~/Downloads` — Downloads (browser and common save target)
- `~/Pictures`, `~/Videos`, `~/Music` — user media
- `~` is the user home (e.g. `/home/username`).
- File manager sidebar often shows “Places”: Home, Desktop, Documents, Downloads, etc.

**Efficient find and open:**
- **Location / address bar**: In file manager (Nautilus, Dolphin, Thunar, etc.) use `ctrl+l` to focus location bar, type path (e.g. `~/Downloads`) and Enter. Use when path is known.
- **Search in file manager**: `ctrl+f` to search by name in current folder; some managers have “Search in” to scope to a folder.
- **Open file**: Select file → Enter or double-click; right-click → “Open with” to choose app.
- **Places / sidebar**: Use “Places” or “Recent” in the sidebar to jump to common or recent locations.
- **Terminal**: If a terminal is available, `xdg-open ~/Downloads` or `xdg-open <path>` opens the path in the default app.
- Prefer **ctrl+l + path** in file manager when path is known; use **ctrl+f** in file manager to find by name in a folder.

**Upload / Open file dialog (when choosing a file to upload or open):**
- **Location bar**: In the file picker dialog, use **ctrl+l** (where supported) or click the path/location bar, type path (e.g. `~/Downloads`, `~/Documents`) and Enter to jump to that folder.
- **Sidebar / Places**: Use the left sidebar (Places: Home, Desktop, Documents, Downloads, or Recent) to go to common folders.
- **Search**: In some dialogs there is a search or filter box; use it to find a file by name after navigating to the right folder.
- If the dialog opens elsewhere, go to the location bar and enter `~/Downloads` or `~/Documents` to reach common upload locations quickly.

**When the target directory has subdirectories (get full file list without opening each folder):**
- **First**: At the start of the subtask, call **list_dir_structure** with the target path (e.g. `~/Downloads`) to get the full directory and file tree in one shot; use that to plan navigation or file choice.
- **File manager search**: Open the target folder, then use **search** (`ctrl+f` or the search icon) and enable **“Search in subfolders”** / **“Recursive”** (or equivalent in Nautilus, Dolphin, Thunar). Use a broad pattern (e.g. `*` or leave empty if supported) to list all files; the results show a flat list with paths. Use this instead of entering each subfolder.
- In an **Open/Upload dialog**: If it has a search or filter with a “search subfolders” option, use it to get all files under the current folder in one list with paths.
