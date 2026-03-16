### macOS Shortcuts Reference

Primary modifier: `command`

| Action | Shortcut | Tool Usage |
|---|---|---|
| Select All | `command+a` | `press_keys ["command","a"]` |
| Copy | `command+c` | `press_keys ["command","c"]` |
| Paste | `command+v` | `press_keys ["command","v"]` |
| Cut | `command+x` | `press_keys ["command","x"]` |
| Focus Address Bar | `command+l` | `press_keys ["command","l"]` |
| New Tab | `command+t` | `press_keys ["command","t"]` |
| Close Tab | `command+w` | `press_keys ["command","w"]` |
| Close Window | `command+w` | `press_keys ["command","w"]` |
| Refresh | `command+r` | `press_keys ["command","r"]` |
| Find | `command+f` | `press_keys ["command","f"]` |
| Page Down / Scroll down | `space` | `press_keys ["space"]` |
| Page Up / Scroll up | `shift+space` | `press_keys ["shift","space"]` |
| Scroll to bottom | `command+down` | `press_keys ["command","down"]` |
| Scroll to top | `command+up` | `press_keys ["command","up"]` |

Notes:
- Prefer shortcuts over clicking UI buttons.
- Use `command+l` for address bar even when it has no index.
- **Scroll/page**: When the focus is already in a scrollable area (e.g. document, list, or page), use `space` / `shift+space` for page down/up, or `command+down` / `command+up` to jump to bottom/top. Use **scroll_at_index** when you need to scroll a specific region by mouse position.

---

### macOS: Folders and file operations

**Common folders (for locating or opening files):**
- `~/Desktop` — Desktop
- `~/Documents` — Documents (default save for many apps)
- `~/Downloads` — Downloads (browser and common save target)
- `~/Pictures`, `~/Movies`, `~/Music` — user media
- `/Applications` — installed apps
- `~` is the user home folder (e.g. `/Users/username`).

**Efficient find and open:**
- **Spotlight**: `command+space` → type file or app name → Enter to open. Fastest for “open file X” when name is known.
- **Finder “Go to Folder”**: `command+shift+g` → type path (e.g. `~/Downloads`) → Enter. Use when path is known.
- **Finder search**: Open Finder, then `command+f` to search by name, kind, or date; narrow by location (e.g. This Mac / current folder).
- **Open from Finder**: Select file → `command+o` or double-click. Use “Open With” from context menu if default app is wrong.
- **Recent places**: Finder sidebar “Recents” or “Recent Tags”; many apps have File → Open Recent.
- Prefer **Spotlight** for “find and open by name”; use **Go to Folder** when the user gives a path or folder name.

**Upload / Open file dialog (when choosing a file to upload or open):**
- **Go to Folder** in dialog: `command+shift+g` → type path (e.g. `~/Downloads`, `~/Documents`) → Enter. Fastest when path is known.
- **Sidebar**: Use the left sidebar in the dialog (e.g. Favorites: Desktop, Documents, Downloads, Recent) to jump to common folders.
- **Search in dialog**: Some dialogs support `command+f` or a search field; use to filter by file name in the current folder.
- If the dialog starts in an unfamiliar location, use **command+shift+g** and enter `~/Downloads` or `~/Documents` to reach the usual upload/save locations quickly.

**When the target directory has subdirectories (get full file list without opening each folder):**
- **First**: At the start of the subtask, call **list_dir_structure** with the target path (e.g. `~/Downloads`) to get the full directory and file tree in one shot; use that to plan navigation or file choice.
- **Finder search**: Open the target folder in Finder, press `command+f`, set the search scope to **“Search: This folder”** (or the folder name) so results include all files inside that folder and its subfolders. Use a broad criterion (e.g. Kind: Any, or leave name empty) to list everything; the results list shows items and you can see path/location. Use this instead of drilling into each subfolder one by one.
- In an **Open/Upload dialog**: If the dialog has a search field, use it with scope set to the current folder so results include subfolders and you get a flat list of files with paths.
