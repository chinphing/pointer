### captcha_verify

Automate CAPTCHA using the current screenshot: you choose the method from what you see on screen, then the tool captures the captcha region and performs **type**, **click**, or **drag**.

**Use directly — do not call extract_data first.** When a CAPTCHA is visible, call **captcha_verify** immediately. The tool infers the verification type and requirement from the screenshot; you do not need to "read" or "extract" the CAPTCHA text beforehand. Do not use extract_data to "understand the CAPTCHA requirement" before using this tool.

**How to choose the method (from the screenshot):**

- **`type`** — Use when the screenshot shows: an image or area with **characters to type** (e.g. distorted letters/numbers), or a **simple question** (e.g. math), and a **text input box** where the answer must be entered. Typical wording nearby: “Enter the characters above”, “Type the text in the image”, “Answer the question”.
- **`click`** — Use when the screenshot shows: a **grid or set of images/tiles** that the user must **click to select** (e.g. “Select all that contain …”, “Click the squares with …”). The task is to choose one or more positions on the image by clicking.
- **`drag`** — Use when the screenshot shows: a **slider**, **puzzle piece**, or other control that must be **dragged** (e.g. “Drag the slider”, “Slide to complete”). The task is a single drag motion, not typing or multiple clicks.

Methods:
- **`type`** — Params: `index_captcha_area`, `index_input_area`, `remark`. Fills the answer into the input at `index_input_area`.
- **`click`** — Params: `index_captcha_area`, `remark`. Clicks at the required positions in sequence.
- **`drag`** — Params: `index_captcha_area`, `remark`. Optional: `is_slider` (boolean). If true, a horizontal offset (configurable in settings, default 10px) is added to the drag target x-coordinate. Use for slider-style CAPTCHAs.

Parameters:
- `index_captcha_area` (required): Index of the **entire** captcha challenge on the annotated screenshot — the box must cover the **full** verification region (instruction text, image grid, slider, distorted characters image, etc., as one unified area). **Do not** choose an index that only marks a **partial** or **local** sub-area (e.g. only the clickable tiles without the prompt, only the slider thumb, or a crop that omits instructions). The recognizer needs the **whole** captcha frame; picking a fragment that “only has the targets” often breaks recognition or misaligns coordinates.
- `index_input_area` (required for `type` only): Index of the text input for the answer.
- `remark` (required): The captcha’s verification requirement or instruction, extracted from the text/area near the captcha (e.g. “Select all images with traffic lights”, “Drag the slider”).
- `is_slider` (optional, for `drag` only): Set to true for slider CAPTCHAs so the tool applies a horizontal position offset to the target (Settings → CAPTCHA: “Slider drag offset (px)”).
Use when a CAPTCHA is visible and you need to complete it automatically; ensure the captcha area (and, for type, the input field) has an index on the current screenshot. **If the captcha is not visible yet** (some sites show it only after a click or hover on a "Verify" / checkbox / placeholder), click or hover the trigger first; on the next turn when the captcha appears, call this tool.
