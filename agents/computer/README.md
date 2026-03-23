# ComputerUse Agent

A custom Agent that operates the computer through vision: before each LLM turn it injects a screenshot and an annotated UI image; the model calls **mouse**, **hotkey**, **modified_click**, **composite_action**, and **wait** by element index to click, double-click, type, and more.

## How this differs from `browser_agent`

The framework exposes two different “browser / desktop” capabilities:

| Aspect | **browser_agent** | **ComputerUse (this profile)** |
|--------|-------------------|--------------------------------|
| **Type** | **Tool** (`tool_name`: `browser_agent`) | **Agent config** (profile: `computer`) |
| **Role** | **Search and plain text only**: open a search engine, open a URL, extract body/links as text—**no real UI interaction** | **Interactive, complex tasks**: click, type, scroll, forms, login, multi-step flows, uploads, **real desktop** and **already visible browser** windows |
| **How it’s selected** | Main Agent sets `tool_name: "browser_agent"` | Start or delegate with `profile=computer` |
| **Implementation** | `python/tools/browser_agent.py`, browser-use + Playwright **headless** | `agents/computer/`: capture + annotate + mouse/hotkey/modified_click/composite_action/wait on the **physical display** (pixel-accurate) |
| **When to use** | “Search / open page / grab text” and **no UI open yet** (new headless session) | “Click, fill, log in, multi-step” or **UI already on screen** (any visible window) |
| **Standalone profile?** | No—tool on any profile | Yes—profile name `computer`, title ComputerUse |

- **browser_agent**: not for forms, login, wizards, uploads, or interactive flows; **for complex browser work, prefer ComputerUse**.
- **ComputerUse**: any task that needs **UI interaction** or **multi-step** work, **including heavy browser use**; use `call_subordinate` with `profile: "computer"`.

## Technical approach

1. **Multimodal input**: the `message_loop_prompts_after` extension injects 2–n images per turn (raw screenshot, numbered overlay, optional 2×2 quadrant zoom); the model reasons visually and returns the next tool call.
2. **Capture**: `screen.py` → `screenshot_current_monitor()` for the monitor under the cursor and its bbox.
3. **Annotation**: `som_util.py` `BoxAnnotator` calls **`POST /api/v1/annotate/all`** over HTTP (RF-DETR + optional OCR, dedup/sort on the server); returns the overlay image and `boxes`. No local detector in this repo. Base URL: env **`COMPUTER_ANNOTATE_API_BASE`** (default `http://127.0.0.1:8000`).
4. **Optional quadrant zoom**: split the annotated frame 2×2; if the user or last reply mentions a quadrant (e.g. “top left”, `top_left`), crop and 2× magnify that patch for the model.
5. **Tools**: **mouse** (click_index, double_click_index, click_at, scroll_at_current, …), **hotkey** (`goal` + `keys`), **modified_click**, **composite_action** (type_text_at_index, type_text_at, scroll_at_index), **wait**. Prefer indices; if there is no index, use coordinates (normalized per model, converted to pixels in `coord_convert.py`). **Call priority**: minimize calls → prefer **composite_action**, then hotkey/modified_click, then **mouse**; use **wait** for delays. **Reading / data**: **`extract_data:extract`** appends fragments only; **`task_done:checkpoint`** runs only when the inject shows **Mandatory (task_done reminder)** (N assistant turns since last checkpoint/read, **N** configurable in Settings, default 20)—merge + truncate history; **best practice** is to checkpoint right after finishing the current subtask’s read/extract when near the threshold. Otherwise use **`extract_data:load`** / **`task_done:read`** to merge on demand. **execution_checkpoint** stores plans/progress/experience and is re-injected after truncation.

## Architecture and data flow

```
User message → message_loop_prompts_after (profile=computer only)
            → screenshot_current_monitor() → image 1 raw
            → BoxAnnotator (HTTP annotate API) → image 2 numbered overlay
            → optional quadrant crop → images 3..n
            → build index_map (screen coords) → agent.data
            → append images 1+2..n to loop_data.history_output as RawMessage
            → prepare_prompt() builds multimodal messages → LLM
            → model returns tool_name + tool_args
            → get_tool(...) → MouseTool / HotkeyTool / …
            → _resolve_index(index_map, index) → ActionTools._click / _type_text / …
```

## Directory and file reference

| Path | Purpose |
|------|---------|
| `agent.json` | Agent metadata: title ComputerUse, description, context. |
| `prompts/agent.system.main.role.md` | Role and operating rules (screenshot + indices). |
| `prompts/agent.system.main.communication.md` | Response format (XML: thoughts / tool_name / tool_args), vision tools and priority. |
| `prompts/agent.system.tool.mouse.md` etc. | Tool specs for mouse, hotkey, modified_click, composite_action, wait. |
| `prompts/agent.system.os.macos.md` | **macOS**: shortcut reference (Command, address bar/tabs/refresh, …). |
| `prompts/agent.system.os.windows.md` | **Windows**: Ctrl-based shortcuts. |
| `prompts/agent.system.os.linux.md` | **Linux**: Ctrl-based shortcuts. |
| `os_prompts.py` | Loads the OS-specific shortcut file at runtime. |
| `screen.py` | Capture: `screenshot_current_monitor()` → (PIL Image, (left, top, width, height)); `encode_image`, etc. |
| `som_util.py` | `SomAnnotator` + `BoxAnnotator`: multipart `/api/v1/annotate/all`, parse `boxes` and PNG `image_base64`; width/height must match input or `AnnotateApiError`. |
| `actions.py` | `ActionTools`: `_click`, `_double_click`, `_type_text`, … (pyautogui / pyperclip). |
| `extensions/message_loop_prompts_after/_10_computer_screen_inject.py` | Screen inject: capture, annotate, optional quadrants, `index_map`. History: keep raw frames for comparison; drop overlay/zoom from history to save tokens. |
| `tools/vision_common.py` | Shared: index_map/screen_info, resolve_index, get_coord_pos, scroll clamping, LAST_VISION_ACTION_KEY, after_execution hook. |
| `tools/mouse.py`, `hotkey.py`, …, `account_login.py` | Vision tools + **account_login** (credential fill). |
| `coord_convert.py` | Normalized coordinates → pixels; built-ins `qwen` (1000×1000), `kimi` (0–1), `pixel`; select via `vision_coordinate_system`. |
| `storage_paths.py` | Resolves **`workdir`** paths: `computer/snapshots`, `extract_data`, `task_done`, `execution_checkpoint`. Data is **not** written under `agents/computer/` in-repo. |
| `snapshots/` (data) | `{workdir}/computer/snapshots/<context_id>/`; PNGs per inject. History `preview` may store **filename only** (tokens); files stay on disk per context. Legacy `agents/computer/snapshots/` can be moved manually into `workdir`. |
| `extract_data/`, `task_done/`, `execution_checkpoint/` | Fragments, merged outputs, persisted state: `{workdir}/computer/.../<context_id>/` via `task_data_memory.py`. |

## Dependencies

- **Capture & input**: `mss`, `pyautogui`, `PIL`, `pyperclip`
- **Annotation**: `requests` (`som_util.BoxAnnotator` → external service on `COMPUTER_ANNOTATE_API_BASE`)
- **Vision helpers**: `cv2`, `numpy`, `scipy` (e.g. `scroll_heatmap.py`, `mouse_path.py`)

### Annotate service environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `COMPUTER_ANNOTATE_API_BASE` | `http://127.0.0.1:8000` | Base URL only; path is fixed `/api/v1/annotate/all` |
| `COMPUTER_ANNOTATE_TIMEOUT` | `120` | HTTP timeout (seconds, float OK) |

Screen inject calls blocking `requests.post` via `asyncio.to_thread` so the event loop is not blocked.

- **rtree**: `_10_computer_screen_inject.py` uses rtree to list normalized bboxes of annotated elements nearest the mouse. `pip install rtree` needs **libspatialindex** (macOS: `brew install spatialindex`).

## Overlays and indices

Detection, dedup, ordering, and drawing are done by the **annotate server** (may differ from older in-repo `BoxAnnotator.annotate`). The client requires returned image/JSON dimensions to match the screenshot; mouse/focus layers are drawn locally before the model sees the frame. How the model maps colors/positions to indices follows the inject extension text.

## Before you run

You need **`profile=computer`** and a **vision-enabled chat model**. Details below.

### 1. Using `profile=computer`

**profile** chooses which `agents/<profile>/` tree loads prompts, tools, and extensions. Only **`computer`** loads this screen inject extension and vision tools (mouse, hotkey, modified_click, composite_action, wait) plus `agent.json` / computer system prompts.

- **Option A — main Agent is ComputerUse**  
  Set **`agent_profile`** to `computer` in settings (e.g. `agent_profile: computer`). `initialize_agent()` sets `config.profile`; the main Agent starts as computer.

- **Option B — `call_subordinate`**  
  From another Agent (e.g. agent0), call `call_subordinate` with `"profile": "computer"` (plus `message`, `reset` if needed). A child Agent gets `config.profile = computer` and runs ComputerUse tools during its monologue.

### 2. Chat model vision enabled

ComputerUse sends screenshots (and overlays) as **image** parts in the chat payload. The chat model must be **multimodal**.

### 3. Coordinate systems (`click_at`, etc.)

When there is no element index, the model may use **mouse:click_at** with `x`, `y`. Normalization differs by model; set **`vision_coordinate_system`** so pixels are correct:

- **qwen** (default): roughly 0–1000 × 1000  
- **kimi**: 0–1 × 1  
- **pixel**: raw screenshot pixels (clamped)

Set `vision_coordinate_system: "kimi"` in the Agent config to switch; default is `"qwen"`.

### 4. CAPTCHA (`captcha_verify`)

Configure **DaTi** at system level (same tier as Chat/Util/Browser). **Option 1**: **Settings → Agent Settings → CAPTCHA / DaTi** for `dati_api_url`, `dati_authcode`, `dati_typeno`, `dati_author`, or edit `usr/settings.json`. **Option 2**: env `A0_SET_dati_*` or root `.env`. Missing fields fall back to env/defaults.

### 5. Logins (`account_login`)

When using **`account_login`**, **do not** put plaintext passwords or usernames in `tool_args`. Pass **`system`** (site/app name) and optional **`user_label`**, plus index or coordinate targets.

**Recommended (Web UI)**: **Settings → External Services → Computer logins** — maintain **`system`**, **`user_label`**, **`username`**, **`password`**, **Save accounts**. Each vision inject adds a **Saved login accounts** block (metadata only, no passwords) for the model.

**File format**: `usr/computer_credentials.json` uses **`{"version": 1, "accounts": [ ... ]}`**; legacy **`profiles: { id: {...} }`** is migrated in memory on read. Example: `agents/computer/computer_credentials.example.json` if present. Optional **`computer_credentials_path`** in `usr/settings.json`.

Methods: **`account_login:fill_at_indices`** or **`fill_at_coordinates`**; `fill` may be **`username`** / **`password`** or omitted to fill multiple fields. See `prompts/agent.system.tool.account_login.md`.

### 6. OS-specific shortcuts

ComputerUse supports macOS, Windows, and Linux; each inject loads the matching file:

- **macOS**: `prompts/agent.system.os.macos.md` — `command` (⌘) as primary modifier  
- **Windows**: `prompts/agent.system.os.windows.md` — `ctrl`  
- **Linux**: `prompts/agent.system.os.linux.md` — `ctrl`  

The model should emit `keys` in **hotkey** `tool_args` consistent with the current OS (e.g. `["command","c"]` vs `["ctrl","c"]`).

### Vision configuration recap

- Set **`chat_model_vision`** to `true` in project settings (usually default). `initialize_agent()` maps it to the main chat `ModelConfig.vision`. If false, vision system text and image payloads are typically omitted.
- The **model itself** must accept images (GPT-4o, Claude 3, Gemini, …). A text-only model will fail or ignore images even if `chat_model_vision=true`.

**Summary**: **`profile=computer`** enables ComputerUse tools/extensions; **vision chat** ensures the main model can consume screenshots. Both are required.

## Usage

1. After starting or switching to computer profile, each prompt build runs screen inject (capture + annotate + optional quadrants); the model sees the current screen and indices.
2. The model should return tools such as `mouse:click_index`, `composite_action:type_text_at_index`, `account_login:fill_at_indices`, with `tool_args` (`index` required; `type_text_at_index` needs `text`; logins use **`system`** + optional **`user_label`**, see §5).
3. Before **`response`**, clean up UI opened during the task (dialogs, extra tabs/apps) so nothing sensitive or noisy is left behind.
