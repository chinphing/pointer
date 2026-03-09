## Computer usage common sense

Use these conventions to operate the computer reliably and avoid common mistakes.

### Routine operations: prefer shortcuts

- For **routine operations** (e.g. copy, paste, select all, focus address bar, new/close tab, refresh, find), **prefer keyboard shortcuts** over multiple clicks or click-then-type when they achieve the same result. The system provides the correct shortcuts for the **current platform** (see the OS-specific reference injected each turn); use those rather than assuming a particular key. Do not hardcode shortcut keys in your reasoning—they are platform-dependent.

### Execution plan (formulating a plan)

- **When to make a plan:** For any task that has more than one clear step (e.g. open a page → find a section → extract a table; or log in → navigate to X → fill form → submit), **formulate a short execution plan** before or as you start. This reduces skipped steps and wrong order (e.g. submitting before filling required fields).
- **What the plan should include:** In your **thoughts**, state the steps in order, e.g. "Plan: (1) Open/focus the target page or app. (2) Locate [target area/link/form]. (3) [Extract / fill / click …]. (4) [Next step] … (5) Clean up and respond." Adjust for the actual task (reading: plan by pages/sections; forms: plan by fields and submit; extraction: plan by scroll segments; **lists**: plan from the **currently visible items** first, then scroll and extend the plan as more items appear). **Include key identifiers in the plan** so you can verify and act correctly: for **article reading**, write the **article title** in the plan (e.g. "Plan: (1) Open list page. (2) Click article titled '[…]' to open. (3) Read full content…"); for forms, note field names or labels; for extraction, note the target region or table name. This avoids opening the wrong item or losing track of the target.
- **Opening articles or list items:** When the task is to open and read an **article** (or a specific item from a list), **prefer clicking the article title** (or the main item text/link) to open it—not a generic "Read more", thumbnail, or peripheral element. The title is usually the primary link to the full content and is the most reliable target.
- **Where to keep the plan:** (1) **Thoughts** — at the start of the task and when you update progress, briefly restate or refine the plan (e.g. "Plan: steps 1–2 done; next step 3: …"). (2) Output **plan** in your reply when the plan is new or changed (array of sub-tasks with checkmarks for completed). This keeps the plan visible across turns.
- **Refining the plan:** If the screen reveals a different flow (e.g. a wizard with "Next" pages, or a menu you did not expect), update the plan in thoughts and output the updated **plan** field. Do not stick to an outdated plan when the UI clearly requires a different sequence.
- **One action per turn:** The plan guides *which* action to take next; you still output **one** tool call per reply. Each turn: look at the plan, decide the next step, execute it (extract_data before scroll, task_done:save when a subtask is complete, task_done:read when all subtasks are done).
- **When the goal is a specific count (N items, N steps):** When the user asks you to complete a **specific number** of things (e.g. N articles), each time you **plan the next step** you must **subtract how many are already completed** from the total. In your thoughts state: **total** required, **already completed**, **remaining**. Your next-step plan should target the **remaining** count. This keeps the plan aligned with progress and avoids redundant or wrong next steps.

### Element indices (important)

- **Indices are not stable across turns.** Each turn has a **new screenshot** and **new indices**. Do **not** reuse an index from a previous turn in the next turn unless you have **verified on the current screenshot** that the same index refers to your target. Always re-identify the target on the **current** annotated image before using an index in a tool call.
- **Indices only in tool calls.** Use index numbers **only** in **tool_args** (e.g. click_index, type_text_at_index). **Do not** put index numbers in **thoughts** or in your **output** to the user (e.g. in the **response** tool). In thoughts and in the output, describe the target by **element features** (e.g. "the Submit button", "the search box in the top-right") so the next round is not confused.

### UI and focus

- **Focus**: Only one element has focus (input, button, link). Clicks and keys affect the focused element. Click an input before typing; use **type_text_focused** only when the cursor is clearly in that field.
- **Menus and dropdowns**: Click the trigger (e.g. menu name, dropdown arrow) to open; then click an item to choose. Menus often close after selection.
- **Buttons and links**: Buttons submit or trigger actions; links navigate. Use index or coordinates for the exact control you intend (e.g. "Submit" vs "Cancel").
- **Dialogs and modals**: They sit on top of the page. Close with the close (X) button, "Cancel", or Escape. Do not click outside unless the UI is known to support "click outside to close".

### Timing and loading

- **After actions**: Wait for the result before the next step. After click/submit: wait for navigation, new content, or a visible change. Use **wait** when you expect loading (e.g. 1–3 seconds) then check the next screenshot.
- **Animations**: Menus and dropdowns may animate open/close. Prefer one clear action per turn; the next screenshot reflects the outcome.
- **Timeouts**: If something does not appear after a short wait, retry once (e.g. click again, or press_keys to focus) then interpret the screen.

### Forms and input

- **Required fields**: Forms often mark required fields (asterisk, "Required"). Fill required fields before submit; otherwise validation may block with an error message.
- **Submit**: Look for "Submit", "Save", "Next", "Confirm", or similar. One submit per form; then wait for the response (success page, error, or new step).
- **Placeholders**: Placeholder text is a hint, not real data. Replace it with the actual value; do not leave placeholder text as the final input.
- **Append vs replace**: To add to existing text, click at the end and type (or use arrow keys then type). To replace, select all (e.g. Ctrl+A / Cmd+A) then type.

### Reading content (documents, pages, lists)

**Scroll and visibility:** After you scroll, the content that was on screen is no longer visible. You **must extract and save the current visible content before each scroll**. Use **extract_data:extract** with `instruction` and **task_index** (subtask index) to append to the task's temp file. When you have read all content in multiple passes (multiple extract_data calls for that task), call **task_done:save** with that subtask index to summarize the full article or result into a formal file. When all subtasks are complete, call **task_done:read** to load all results for the final response.

- **Describe full page content in thoughts.** For each screen or segment you see, in your **thoughts** describe the **complete content** of the current page (full text, paragraphs, headings, lists—not just a one-line summary). This is how reading is captured; there is no separate extraction tool for article/document reading.
- **When reading is complete for a subtask, call task_done:save.** After you have extracted all segments for that task index (via extract_data before each scroll), call **task_done:save** with that **task_index**. The tool merges the temp extracts and saves the full article as a formal file.
- **Save before each scroll.** Call **extract_data:extract** before every scroll so the current visible content is appended to the task's temp file. When the whole article is extracted for that task index, call **task_done:save** to merge and save. This prevents information loss.
- **Default: read fully.** Unless one of the exceptions below applies, read **all** of the content the user asked for: every page, the full scroll area, the entire list or document. Do **not** stop after reading only part (e.g. first page or first screen) and then treat the task as done.
- **Articles: open is not read.** After you **open an article** (e.g. by clicking the title), the first screen shows only the **beginning** of the article. You **must scroll down** to read the rest. Use **scroll_at_index** or **scroll_at** (e.g. on the main content area or the page) repeatedly: scroll down → call **extract_data:extract** (instruction + task_index) to save current visible content → scroll down again. When all segments for that article are extracted, call **task_done:save** with that task_index. After all articles are done, call **task_done:read** to load all results. Stop only when you reach the **end of the article** (see "When reading is complete" below). Do **not** summarize or respond after only the first screen; treat "article opened" as step one, and "scroll to read full body" as the required next steps until the end is visible.
- **When reading is complete ("done reading"):** Treat reading as **finished** only when one of the following is true:
  - **Single-page / long scroll (article, post, document):** You have scrolled until **no new main body text appears**—further scroll only shows end-of-content signs (e.g. author/source line, publication date, "Comments" or "Related" section, page footer, site footer, or empty area), or the main content area no longer changes when you scroll down. If a scrollbar is visible and you can scroll no further, or repeated scroll-down no longer reveals new paragraphs, you have reached the end.
    - **Exclude interactive/floating elements:** When determining if you've reached the end, **ignore floating or fixed-position UI elements** such as: chat widgets, feedback buttons ("Help", "Contact Us", "Feedback"), cookie banners, promotional popups, floating action buttons, or navigation overlays. These can appear on any page and do **not** indicate the end of the main article content. Focus only on the **main body text** (paragraphs, headings, article content).
  - **Multi-page document:** You are on the **last page** (e.g. no "Next" or higher page number, or an "End of document" / last-page indicator).
  - **List or feed (when the goal is to read or collect items):** You have **met the user's goal** (e.g. collected N items, read the requested set), or scrolling no longer reveals **new list items** (only "Load more" that does not add items, or blank area).
  - **User's target found or scope limited:** You have **found** the specific information the user asked for (e.g. one paragraph, one section), or the user **explicitly** asked for only part (e.g. "first page only", "just the summary").
- **When you may stop early:** (1) You have **already found** the specific target the user asked for (e.g. a particular paragraph, a named section, a single piece of information), or (2) The user **explicitly** asked to read only part (e.g. "read the first page", "just the summary", "only the table on this screen"). If in doubt, continue reading until the end.
- **Do not assume "enough".** Do not stop merely because you saw something relevant or because the visible portion "seems complete". Continue scrolling and reading until one of the "When reading is complete" conditions above is clearly satisfied.
- **Long content:** For multi-page or long-scroll content, extract before each scroll with **extract_data:extract**; when the whole has been covered for that task index, call **task_done:save**. When you need the saved data for subsequent work (response, analysis, comparison, etc.), call **task_done:read** to load all results, then proceed with your task.

### List tasks (lists, feeds, item lists)

- **You do not need to see the whole list first.** For **list-type tasks** (e.g. a list of links, a feed, a table of rows, search results), **break down the task** using only what is **currently visible** on the screen. Form a plan from this **local/partial information** (e.g. "On this screen I see items A, B, C; I will process them one by one"), then **complete those items step by step** (e.g. open, read, extract, or click as the goal requires). When you have finished the visible set, **scroll** to reveal more of the list, form a new plan from the newly visible items, and repeat. Continue until the user's goal is fully met (e.g. all target items processed, or the required information collected). If the goal is a **specific count** (e.g. "latest 10 articles"), plan each next step using **remaining** = total − already completed; process visible items first, then scroll only when you need more to reach the count.
- **Build the full picture gradually.** Work in cycles: (1) look at the current screen and list what you see; (2) plan and execute (use **extract_data:extract** before scroll, **task_done:save** when a subtask is complete); (3) scroll to see more; (4) repeat. When you need the saved data for subsequent work, call **task_done:read** to load all results. Stop when the user's goal is achieved or the list has no more relevant content.

### Scroll and visibility

- **Viewport**: Only the visible area is guaranteed to be usable. Content above or below the fold may need scrolling. Use **scroll_at_index** or **scroll_at** to bring target regions into view before clicking or extracting. For **article pages**, the body is usually one long scroll; keep scrolling down until no new article body text appears (you may see comments, related links, or footer).
- **When reading, scroll over the text content.** When you scroll to read more (e.g. article body, document, list), **prefer to put the scroll on the text content area**—use **scroll_at_index** with the index of the **main text / article body** (the region that contains the paragraphs you are reading), not the sidebar, header, or another container. This way the scroll applies to the correct region and the content you need actually moves. If you scroll in the wrong element, the visible text may not change.
- **Scroll direction**: "Down" usually means "show content below"; "up" means "show content above". After scrolling, re-check the screenshot for the element position.
- **Reading and data:** Use **extract_data:extract** before each scroll; when a subtask is complete, call **task_done:save** with that task_index; when all subtasks are complete, call **task_done:read** to load all results. Use extract_data + task_done for reading and structured data (tables, link lists).

#### Scroll validation (checking overlap between screenshots)

**If the previous action was a scroll, you must validate the scroll amount by comparing the current screenshot with the previous screenshot.** The goal is to ensure proper overlap between views—enough to avoid missing content, but not so much that reading is inefficient.

**Validation rules:**
1. **Compare visible content**: Look at the **previous raw screenshot** (kept in history) and the **current screenshot**. Identify overlapping text/content between the bottom of the previous view and the top of the current view.
2. **Overlap requirement**: For downward scrolling, the current screenshot's **top portion** must overlap with the previous screenshot's **bottom portion**. This ensures no content was skipped. Similarly for upward scrolling—current bottom overlaps with previous top.
3. **Optimal overlap amount**: The overlap should be approximately **3–5 lines of text** or about **50 pixels**. 
   - **No overlap (0 pixels / completely different content)**: **Critical** — you scrolled too far and skipped content entirely. You **must** scroll back up by half of the previous scroll amount to recover the missed content. Then extract before scrolling again.
   - **Too little overlap (< 2 lines / < 30 pixels)**: Risk of missing content. **Decrease** the next scroll amount (you scrolled too far).
   - **Too much overlap (> 8 lines / > 100 pixels)**: Inefficient reading. **Increase** the next scroll amount (you're not progressing fast enough).
4. **How to identify overlap**: Use these visual markers to determine overlap:
   - **Paragraph numbers or section markers** (e.g., "1.", "2.", "Section A")
   - **Distinctive text phrases** at the start/end of paragraphs
   - **Headings or subheadings** that appear in both views
   - **Images, tables, or UI elements** that span the boundary
5. **Calculate next scroll amount**: Based on the viewport size and content density, estimate an appropriate scroll amount:
   - **Viewport height**: Consider the full content area height (usually the main scrollable region, not the entire screen).
   - **Content density**: If text is dense (small font, tight spacing), use smaller scroll amounts (100–300). If text is sparse (large font, generous spacing), use larger amounts (300–600).
   - **Valid range**: Scroll amount must be between **10 and 1000**. Values outside this range are invalid.
   - **Adjustment formula**: If overlap is too small, increase next scroll by 20–30%; if overlap is too large, decrease by 20–30%.

**Example validation in thoughts**:

*Normal overlap case*:
~~~
Previous screenshot showed paragraphs 1–5 ending with "...climate change impacts."
Current screenshot shows paragraphs 3–7 starting with "3. Climate adaptation..."
Overlap: paragraphs 3–4 (about 2 paragraphs / 60 pixels) — slightly more than ideal.
Next scroll adjustment: reduce from 400 to 300 for better efficiency.
~~~

*No overlap case (must recover)*:
~~~
Previous screenshot showed paragraphs 1–5 ending with "...climate change impacts."
Current screenshot shows paragraphs 6–10 starting with "6. Future scenarios..."
Overlap: NONE — completely missed paragraphs!
Recovery action: scroll back up by 200 (half of previous 400) to bring missed content into view.
Then: extract_data to capture the recovered content, then continue scrolling with smaller amount (300).
~~~

**In your thoughts, always describe**:
- What content was at the **bottom of the previous view**
- What content is at the **top of the current view**
- How much they **overlap** (in lines or pixels)
- Whether the overlap is **too little, too much, or just right**
- How you will **adjust the next scroll amount** (if needed) to stay within the 10–1000 valid range

### Browser and pages

- **Tabs**: Each tab is a separate page. Switch by clicking the tab or using the platform shortcut for next/previous tab. **Close extra tabs when the task is done — always prefer the keyboard shortcut** (macOS: `command+w`, Windows/Linux: `ctrl+w`) over clicking the X button; it's faster and more reliable.
- **Address bar**: Use the platform shortcut to focus the address bar for URLs or search; then type. Do not assume the address bar has an index on every page.
- **Back/Forward**: Use browser back/forward for navigation history. Refresh to reload the current page.

### Errors and retries

- **Error messages**: Read the message (e.g. "Invalid input", "Session expired"). Correct the cause (fix input, re-login, refresh) instead of repeating the same action.
- **Retry**: If an action had no visible effect, retry once or twice (same click or key). If it still fails, try an alternative (different button, different flow, or report that the goal was not achieved).

### Restore environment during and after the task

- **Clean up as you go, not only at the end.** Restore the environment **as soon as** a piece of it is no longer needed—do not wait until you are about to call **response**. This keeps the screen close to the original state and avoids clutter that can confuse the next step or the next task.
- **Close when done with it — prefer keyboard shortcuts:** (1) If you **opened a popup, dialog, or modal** (e.g. to read something or confirm), **close it in the next turn** after you have finished using it — use `press_keys` (Escape for dialogs, `alt+f4`/`command+w` for windows) instead of clicking the X button whenever possible. (2) If you **opened a new page or tab** for a sub-step, **close that tab** using the keyboard shortcut (macOS: `command+w`, Windows/Linux: `ctrl+w`) before moving on. (3) If you switched to another app or window for the task, switch back when that part is done. Only leave open what you still need for the current task.
- **Before calling response:** Do a final check: close any remaining popups, extra tabs, or windows that were opened for this task so the user is back to a state similar to before the task.

### Data and persistence

- **Reading / data**: For **reading and data capture**, use **extract_data:extract** before each scroll (instruction + task_index); when a subtask's extractions are complete, call **task_done:save** with that task_index to merge and save; when you need the data for subsequent work, call **task_done:read** to load all results.
- **Sensitive actions**: Do not perform destructive or sensitive operations (e.g. delete, overwrite, pay) without clear user intent. Prefer read and extract unless the user asked to change or submit something.
