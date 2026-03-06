### Linux Shortcuts Reference

Use these Linux-specific keyboard shortcuts for efficient operation.

#### Modifier Keys
- **Primary modifier**: `ctrl`
- **Secondary modifier**: `alt`, `shift`, `super` (Win/Command key)

#### Common Shortcuts

| Action | Shortcut | Tool Usage |
|--------|----------|------------|
| Select All | `ctrl+a` | `press_keys ["ctrl", "a"]` |
| Copy | `ctrl+c` | `press_keys ["ctrl", "c"]` |
| Paste | `ctrl+v` | `press_keys ["ctrl", "v"]` |
| Cut | `ctrl+x` | `press_keys ["ctrl", "x"]` |
| Focus Address Bar | `ctrl+l` | `press_keys ["ctrl", "l"]` |
| New Tab | `ctrl+t` | `press_keys ["ctrl", "t"]` |
| Close Tab | `ctrl+w` | `press_keys ["ctrl", "w"]` |
| Refresh Page | `ctrl+r` or `f5` | `press_keys ["ctrl", "r"]` |
| Find | `ctrl+f` | `press_keys ["ctrl", "f"]` |

---

### Basic Computer Knowledge

#### Text Input Field Operations

**1. Typing**
- First input: Click the field to focus, then type
- Continuing input: If cursor is blinking (already focused), type directly without clicking
- Tool selection:
  - Has index → `type_text_at_index` (clicks + types)
  - No index → `type_text_at` (clicks at x,y + types)
  - Confirmed focused → `type_text_focused` (types only)

**2. Clearing**
- Use `press_keys ["ctrl", "a"]` to select all, then type to replace
- Or select all → Delete/Backspace → type

**3. Select All**
- Shortcut: `ctrl+a`
- Usage: Replace entire content, copy all text, or delete all

**4. Append vs Replace**
- Append: Add text after existing content, type directly
- Replace: Overwrite existing content, select all first then type
- Keywords: "add"/"append" → append; "change"/"replace"/"search for" → replace (clear first)

**5. Common Mistakes**
- Don't type without clicking (unless confirmed focused)
- Don't append unless user explicitly requests
- Don't keep placeholder text as real input

#### Browser Basics

**1. Address Bar**
- Shows current URL; click to select all, then type new URL or search query
- Use `press_keys ["ctrl", "l"]` to focus address bar instantly
- When focused, existing URL is auto-selected; typing replaces it directly
- **New tab pages**: Address bar may be empty and unnumbered; always use `press_keys ["ctrl", "l"]` instead of trying to click by index

**2. Tab Bar**
- Shows open tabs; click tab to switch; click X to close
- To open new tab: click `+` button, or use `press_keys ["ctrl", "t"]`
- To close current tab: use `press_keys ["ctrl", "w"]`
- Look for highlighted/active tab to know which page is current

**3. Page Navigation**
- Back/Forward buttons: use to navigate history
- Refresh button or `press_keys ["ctrl", "r"]` or `press_keys ["f5"]`

#### Efficiency Examples
```json
{
    "thoughts": ["Focus address bar with Ctrl+L to type URL"],
    "tool_name": "vision_actions:press_keys",
    "tool_args": { "keys": ["ctrl", "l"] }
}
```

```json
{
    "thoughts": ["Select all text with Ctrl+A and replace it"],
    "tool_name": "vision_actions:press_keys",
    "tool_args": { "keys": ["ctrl", "a"] }
}
```
