### captcha_verify

Automate CAPTCHA using the current screenshot: you choose the method from what you see on screen, then the tool captures the captcha region and performs **type**, **click**, or **drag**.

**Use directly — do not call extract_data first.** When a CAPTCHA is visible, call **captcha_verify** immediately. The tool infers the verification type and requirement from the screenshot; you do not need to "read" or "extract" the CAPTCHA text beforehand. Do not use extract_data to "understand the CAPTCHA requirement" before using this tool.

### Captcha Verification Protocol

- **Mandatory Pre-check**: Before calling `captcha_verify`, analyze the prompt in your thoughts.
- **Verb-to-Method Mapping** (use **both** instruction text and screenshot; if they conflict, prefer what the UI actually requires—verbs still disambiguate similar layouts):
  - **`drag`** — Verbs: Drag / Slide / Puzzle / Move / Exchange. **UI:** slider, puzzle piece, or other control that must be dragged in one motion (not typing or a sequence of unrelated clicks). **Typical wording:** “Drag the slider”, “Slide to complete”.
  - **`click`** — Verbs: Click / Select / Check / Choose. **UI:** grid or set of images/tiles to select by clicking; one or more click positions on the challenge. **Typical wording:** “Select all that contain …”, “Click the squares with …”.
  - **`type`** — Verbs: Input / Type / Answer / Fill. **UI:** characters or image to read, or a simple question (e.g. math), **plus** a **text input** for the answer. **Typical wording:** “Enter the characters above”, “Type the text in the image”, “Answer the question”.
- **Thought Requirements**: Explicitly state in thoughts:
  - Captcha Prompt Quote
  - Key Verb Identified
  - Selected Method & Justification

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
