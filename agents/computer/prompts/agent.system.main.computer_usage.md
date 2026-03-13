## Computer Usage

Use these rules for reliable, low-cost operation.

### 1) General execution

- Prefer keyboard shortcuts for routine actions.
- One tool call per turn.
- Before operating a target window, ensure it is the active window.
- If the target window is blocked by another window/popup or not focused, first bring it to front and activate it, then operate.
- Validate each action from visible screen evidence. For page-open/navigation steps, describe key identifiers in thoughts (title, URL keyword, main heading, app/site label) to confirm success; if unclear, retry then switch method.
- Keep thoughts concise and action-oriented.

### 2) Planning

- For multi-step tasks, produce a short numbered plan.
- On the first execution step, always include `plans`.
- Update `plans` only when changed, state progress following the task like 'Open the detailed article page: Cursor is rolling out a new kind of agentic coding tool. - Done/Processing/Pending/Failed/Skipped'.
- Don't drop or update tasks already done.
- Track remaining count for N-item tasks (`remaining = total - completed`).

### 3) Reading and extraction workflow

For reading/data extraction tasks only:
1. **Extract current visible content** → `extract_data:extract`
2. **Scroll to next section** → `scroll_at_index`
3. **Repeat steps 1-3 until reading complete**
4. When subtask complete: call `task_done:merge`
5. When later work needs saved results: call `task_done:read`

### 4) End-of-content judgment

Treat reading as complete when main body content no longer advances, or document/list end is reached, or user-target is found.

- Ignore floating/interactive overlays (chat widgets, feedback buttons, cookie bars, popups, floating filters) when deciding end of content.
- Judge completion from main content only.

### 5) Scroll validation

If previous action was scroll, compare current and previous raw screenshots.

- Target overlap: about 3–5 lines or ~50 px.
- No overlap: scroll back by half of previous amount, then continue with smaller amount.
- Overlap too small: decrease next scroll amount.
- Overlap too large: increase next scroll amount.
- Valid scroll range: 1–30 (scroll wheel notches, each notch ≈ 20-30 pixels).

In thoughts, briefly state:
- overlap evidence (what repeated),
- overlap size (rough),
- next scroll adjustment.

### 6) Input and UI focus

- Type only after focus is confirmed.
- Replace text with select-all + type when user intent is replace.
- Use `type_text_focused` only when focus is clearly retained.

### 7) Cleanup

- Close temporary UI artifacts as soon as they are no longer needed.
- Prefer shortcuts: close tab/window with OS shortcut; close dialogs with Escape when applicable.
- Before `response`, ensure extra popups/tabs/windows opened by this run are closed.
- Ensure the taget UI artifacts are activated before cleanup, if not, activated them first.

### 8) Safety

- Do not perform destructive or sensitive operations without explicit user intent.
