### Windows Shortcuts Reference

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

### Windows: Folders and file operations

**Common folders (for locating or opening files):**
- `%USERPROFILE%\Desktop` — Desktop (often `C:\Users\<username>\Desktop`)
- `%USERPROFILE%\Documents` — Documents (default save for many apps)
- `%USERPROFILE%\Downloads` — Downloads (browser and common save target)
- `%USERPROFILE%\Pictures`, `%USERPROFILE%\Videos`, `%USERPROFILE%\Music` — user media
- `%USERPROFILE%` — user profile folder (e.g. `C:\Users\username`).
- “This PC” in File Explorer lists Desktop, Documents, Downloads, etc.

**Efficient find and open:**
- **File Explorer**: `Win+e` to open; address bar can take a path (e.g. `C:\Users\...\Downloads`) — type or paste, then Enter.
- **Windows Search**: `Win+s` or taskbar search → type file or app name → open result. Good when name is known.
- **Run / path**: `Win+r` → type path (e.g. `%USERPROFILE%\Downloads`) or `explorer C:\path` → Enter.
- **In File Explorer**: `ctrl+f` or search box to search current folder; use “Search in” or filters to narrow.
- **Quick access**: Left sidebar “Quick access” and “Recent files” for fast reuse of recent locations.
- Prefer **Win+e + address bar** when path is known; use **Win+s** for “find and open by name”.

**Upload / Open file dialog (when choosing a file to upload or open):**
- **Address bar**: Click the path/address bar at the top of the dialog (or use Tab to focus it), type or paste path (e.g. `C:\Users\<username>\Downloads`, `%USERPROFILE%\Documents`) and press Enter to jump to that folder.
- **Sidebar**: Use the left side (Quick access, This PC, Desktop, Documents, Downloads) to go to common folders without typing.
- **Search in dialog**: Use the search box in the dialog if present, or navigate to the folder first then use **ctrl+f** to find a file by name.
- If the dialog opens in an unfamiliar location, use the address bar to enter `%USERPROFILE%\Downloads` or `%USERPROFILE%\Documents` for common upload locations.

**When the target directory has subdirectories (get full file list without opening each folder):**
- **First**: At the start of the subtask, call **list_dir_structure** with the target path (e.g. `~/Downloads` or `%USERPROFILE%\\Downloads`) to get the full directory and file tree in one shot; use that to plan navigation or file choice.
- **File Explorer search**: Navigate to the target folder, then use the **search box** (top right). Type `*` or `*.*` — Windows searches **this folder and all subfolders** by default. The results list shows all files; you can add the “Folder path” or “Path” column in the details view to see full paths. Use this to get a single list of all files instead of opening each subfolder.
- In an **Open/Upload dialog**: Use the dialog’s search box the same way (often it searches the current folder and subfolders), so you get a flat list of files with paths without navigating into every subfolder.
