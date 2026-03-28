# Pointer

[简体中文](README.zh-CN.md)

> A **real-screen** computer-use agent powered by multimodal LLMs. Built on **Agent Zero** with the **Computer (Pointer)** profile: see the display like a human, interact with UIs, fill forms, and complete tasks across applications.

**Model support:** Only **DashScope `qwen3.5-plus`** is verified so far. You must set **`api_base`** to the correct regional endpoint as well as the API key—see [§4.4](#44-api-keys-and-models).

---

## 1. What Pointer Is and What It Does

**Pointer** is an AI assistant for **real desktop and browser UIs**. It does not rely on spinning up a separate page in a headless browser; it **captures what is visible on your monitor**, understands on-screen elements, and acts through **mouse, keyboard, shortcuts, and composite actions**—the same inputs a person uses.

**Capabilities include:**

- **Interactions** in web and desktop apps: click, type, scroll, multi-select, drag, and more
- **Multi-step flows**: login wizards, forms, file pickers, paginated reading and extraction
- **Vision**: numbered UI overlays plus optional zoomed regions to reduce mis-clicks
- **Structured memory**: per-task screen extraction, merge, `task_done:checkpoint` / `read`, and persisted execution state (see `agents/computer/` docs)

Pointer runs as an **Agent Zero profile (`computer`)**, so tool orchestration, dialogue, and extensions work the same way. The product name is **Pointer**.

---

## 2. Use Cases and Demos

**Goal:** We aim to **fully replace repetitive, physical computer work**—the routine clicking, typing, and screen navigation that people do every day—with capable automation. That includes **personal daily tasks** (your own desktop and browser workflows) and **enterprise employees’ day-to-day work** (repeated operational steps across standard business apps and web consoles), wherever vision, judgment, and multi-step control are needed.

**Example use cases:**

- Complex web workflows (login, search, forms, admin consoles, multi-page collection)
- Desktop apps and hybrid work (real windows in the foreground, coexisting with your workflow)
- Repetitive human–computer tasks that need **vision + reasoning + long horizons**

**Video demo:**  
- [Verifying 21 Scenarios Across 7 CAPTCHA Categories](https://youtu.be/jliYPZphTWE)
- [1h teaching a vision Agent to buy AliCloud: No more "CLI Everything"!](https://youtu.be/zWOtxBAZ5GQ)

**Try it online / pilot access:**  
Contact **starphinliu@gmail.com** for trials, demos, or partnerships.

---

## 3. Core Features

| Area | Description |
|------|-------------|
| **Human-like operation** | Live screenshots and UI annotation; prefer element indices, fall back to coordinates; OS-specific shortcut hints for macOS, Windows, and Linux. |
| **Credential safety** | Dedicated login and credential handling to avoid putting plaintext passwords in model-visible prompts; guided secure fill (see Computer Agent tool specs). |
| **CAPTCHA handling** | **captcha_verify** and related flows: when a CAPTCHA-like UI is detected, choose click / type / drag per protocol (exact behavior depends on implementation and model). |
| **Full Agent Zero stack** | Skills, memory and learning, code execution, subordinate agents, MCP integrations, and more—usable alongside Pointer as your task requires. |
| **Long-horizon tasks** | Screen extraction, merge by task index, `task_done:checkpoint` / `read`, and persisted plans / progress / learnings to bound context and improve recoverability. |

For architecture, file layout, env vars, and tools, see **[agents/computer/README.md](agents/computer/README.md)**.

---

## 4. Installation and Deployment

### 4.1 Requirements

- **Python:** 3.10+ recommended (match project dependencies)
- **OS:** **macOS**, **Windows**, and **Linux**; Pointer injects OS-specific shortcut references
- **Permissions:** Screen capture and accessibility / assistive APIs may be required for screenshots and input—grant them per your OS settings

### 4.2 Install dependencies

From the repository root:

```bash
pip install -r requirements.txt
pip install -r requirements2.txt
```

`requirements2.txt` includes **LiteLLM** and the **OpenAI SDK** (model calling). Install both files.

Optional for development / tests:

```bash
pip install -r requirements.dev.txt
```

### 4.3 OS notes

| OS | Notes |
|----|--------|
| **macOS** | Allow your terminal or Python process **Screen Recording** and **Accessibility**; otherwise capture and control may fail. |
| **Windows** | Mind HiDPI scaling; run under a normal interactive desktop session (not a headless session without a desktop). |
| **Linux** | Needs a display server (e.g. X11). Headless hosts need a virtual display (e.g. Xvfb)—*(TBD: recommended distros and minimal setup)* |

### 4.4 API keys and models

1. Copy or create an env file (e.g. `.env`) if your workflow uses one.
2. In the **Web UI settings** or `.env`, set keys for your **provider** (see [`conf/model_providers.yaml`](conf/model_providers.yaml)), e.g.:
   - OpenAI, OpenRouter, Anthropic, etc.  
- **DashScope (Qwen):** `DASHSCOPE_API_KEY` or `API_KEY_DASHSCOPE` (provider id: `dashscope`)
3. **Set `api_base` for DashScope (required).** LiteLLM does **not** auto-pick China vs international. In **Settings**, fill **API base** for each role that uses DashScope (**Chat**, **Utility**, etc.—field names such as *chat model API base*, *utility model API base*), or ensure the value is merged from [`conf/model_providers.yaml`](conf/model_providers.yaml) defaults. Use the URL that matches where your key was issued:

   | Region | `api_base` |
   |--------|------------|
   | **China (Beijing)** | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
   | **International** | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |

   Wrong region + key combination typically causes auth or routing errors.

4. Pick models for **Chat**, **Utility**, **Browser**, etc. Computer use typically needs a **vision-capable Utility** model for screenshot understanding and extraction.  

**Tested models (today):** Only **Qwen 3.5 Plus** on **DashScope** has been validated end-to-end with Pointer. Use provider **`dashscope`**, the **correct regional `api_base`** (see table above), **`DASHSCOPE_API_KEY`** (or **`API_KEY_DASHSCOPE`**), and model name **`qwen3.5-plus`** (or the exact id from your DashScope console). **Chat**, **Utility**, and other roles may all need this stack until broader compatibility is confirmed. Other providers and model IDs are **untested** and may not work.

### 4.5 Work directory (workdir)

Set **Settings → workdir**. Pointer writes under it:

- `computer/snapshots/` — screenshots and debug images  
- `computer/extract_data/`, `computer/task_done/`, `computer/execution_checkpoint/` — extraction and task state  

Avoid pointing workdir at read-only or ephemeral locations unless intentional.

### 4.6 Annotation service (required for Computer)

Pointer calls an **HTTP annotation service** to produce numbered UI boxes (default `COMPUTER_ANNOTATE_API_BASE`, path `/api/v1/annotate/all`).  

*(TBD: how to deploy the service, Docker image, or doc links)*

Common environment variables (details in `agents/computer/README.md`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `COMPUTER_ANNOTATE_API_BASE` | `http://127.0.0.1:8000` | Annotation API base URL |
| `COMPUTER_ANNOTATE_TIMEOUT` | `120` | Request timeout (seconds) |

### 4.7 Start the Web UI

```bash
python run_ui.py
```

*(TBD: default port, HTTPS, reverse-proxy examples)*

---

## 5. Roadmap

1. **Lightweight RPA** — Web data extraction, chat-driven tasks, and visiting social or content sites (e.g. Xiaohongshu, X, Facebook) where work stays mostly in the browser or a small set of familiar UIs.

2. **Cross-application work** — Uploading and downloading files across apps, delivering results in chat when a task completes, and auto-filling forms that span multiple programs or sites.

3. **Research** — Work on professional or domain data that is public but **requires login** to access; produce and hand off research outputs—for example, **legal case research** and similar deep dives.

4. **Digital coworkers** — Full loop: **receive a task → plan → execute on the machine → deliver results**, aimed at recurring operational work patterned after roles such as **developers**, **HR**, and **finance**.

---

## 6. Important warning

**Pointer has full control of the computer** (mouse, keyboard, system-level shortcuts). With bad prompts, model errors, or ambiguous goals, it may:

- Delete or corrupt files and important data  
- Trigger unintended payments, emails, or account changes  
- Leak privacy (screen content is sent to your model provider)  

**Use only in controlled environments, with backups and least privilege; high-stakes production use requires human oversight and auditing.**  
You are solely responsible for any direct or indirect damage from using this software.

---

## 7. Contact

- **Email:** [starphinliu@gmail.com](mailto:starphinliu@gmail.com)  
- Feedback, trial requests, partnerships, custom work: **starphinliu@gmail.com**

---

## License and acknowledgments

See **[LICENSE](LICENSE)** in the repository root (if it differs from upstream Agent Zero, the file in this repo prevails).

Pointer builds on **Agent Zero**; Computer / Pointer code lives under `agents/computer/`. Thanks to Agent Zero and the broader open-source ecosystem.
