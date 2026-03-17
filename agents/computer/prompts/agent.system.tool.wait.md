### wait

Use when a **delay** is needed (e.g. page loading, animation, dialog appearing).

Method:
- `wait` (`goal`, `seconds`) — Pause for the given number of seconds. `seconds`: 0–60.

Parameter constraints:
- **`goal`** is required. Describe what is being waited for and the expected result (e.g. "Wait for page load", "Wait for dialog to appear"). If waiting for a specific element, describe it: **text** — exact visible text; **other** — brief description of features.

Use **wait** when you need to pause before the next action; combine with other tools as needed (e.g. navigate then wait then click).
