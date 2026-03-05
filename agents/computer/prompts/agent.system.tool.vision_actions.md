### vision_actions

Operate the current screen by index or by keyboard/scroll. Each turn you receive an annotated screenshot where interactive elements are numbered from 1 to N (left-to-right, top-to-bottom). Use index-based tools with the **index** shown on the image; use press_keys and scroll without an index.

When reasoning about which index to use, **describe the element's position** (e.g. top-left, center, bottom-right, above the header, in the middle) so the vision model can target it more reliably. This is especially helpful when several elements look similar.

- **vision_actions:click_index** — Single click on the element at the given index. Use for buttons, links, icons.
- **vision_actions:double_click_index** — Double-click on the element at the given index. Use for opening files or selecting words.
- **vision_actions:type_text_at_index** — Click the element (e.g. input field) and type the given text. Use for search boxes, forms, text fields.
- **vision_actions:press_keys** — Press a key combination. Use for shortcuts (copy, paste, enter, escape, etc.). **tool_args**: `keys` (array of strings, e.g. `["ctrl", "c"]` or `["command", "v"]` on macOS).
- **vision_actions:scroll** — Scroll the mouse wheel at current position. **tool_args**: `amount` (integer: positive = scroll up, negative = scroll down).

**tool_args** (by tool):
- `index` (integer, required for click_index / double_click_index / type_text_at_index): The number labeled on the element in the annotated screenshot.
- `text` (string, required only for type_text_at_index): The text to type after clicking.
- `keys` (array of strings, required for press_keys): Key names in order, e.g. `["ctrl", "c"]`, `["alt", "tab"]`, `["enter"]`.
- `amount` (integer, required for scroll): Scroll units; positive = up, negative = down.

**Example**

~~~json
{
    "thoughts": ["Submit button in the bottom-right is index 4.", "I will click it."],
    "tool_name": "vision_actions:click_index",
    "tool_args": { "index": 4 }
}
~~~

~~~json
{
    "thoughts": ["Search box in the top-left (index 1). Typing the query."],
    "tool_name": "vision_actions:type_text_at_index",
    "tool_args": { "index": 1, "text": "agent zero" }
}
~~~

~~~json
{
    "thoughts": ["Copy selection with Ctrl+C."],
    "tool_name": "vision_actions:press_keys",
    "tool_args": { "keys": ["ctrl", "c"] }
}
~~~

~~~json
{
    "thoughts": ["Scroll down to see more content."],
    "tool_name": "vision_actions:scroll",
    "tool_args": { "amount": -3 }
}
~~~
