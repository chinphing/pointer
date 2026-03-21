# ComputerUse Agent

以多模态大模型为基础，通过视觉方式操作电脑（尤其是网页与桌面 UI）的自定义 Agent。每轮对话前自动注入当前屏幕截图与标注图，模型根据图中序号调用 **mouse**、**hotkey**、**modified_click**、**composite_action**、**wait** 等工具执行点击、双击、输入等操作。

## 与 browser_agent 的区分（避免歧义）

框架里有两类与「浏览器/电脑操作」相关的能力，职责明确区分如下：

| 维度 | **browser_agent** | **ComputerUse（本 profile）** |
|------|-------------------|-------------------------------|
| **类型** | **工具**（tool_name：`browser_agent`） | **Agent 配置**（profile：`computer`） |
| **职责** | **仅简单搜索与网页纯文本提取**：打开搜索引擎输入关键词取结果、打开 URL 提取正文/链接等纯文本，**不做任何交互操作** | **有交互的操作与复杂任务**：点击、输入、滚动、表单填写、登录、多步流程、文件上传、操作真实桌面与已打开浏览器等 |
| **识别方式** | 主 Agent 在回复里填 `tool_name: "browser_agent"` | 启动或派发子任务时指定 `profile=computer` |
| **实现** | `python/tools/browser_agent.py`，browser-use + Playwright **无头浏览器** | `agents/computer/`：截图 + 标注 + mouse/hotkey/modified_click/composite_action/wait，控制**当前显示器的真实屏幕**（像素级点击） |
| **适用场景** | 仅需：搜一下、打开页面取文字；且**界面尚未打开**（无头浏览器新建会话） | 需要：在页面上点击、填表、登录、多步操作；或**界面已打开/已存在**（操作当前屏幕上的浏览器或任意可见 UI） |
| **是否独立 profile** | 否，作为工具挂载在任意 profile 下 | 是，profile 名 `computer`，标题 ComputerUse |

- **browser_agent**：不用于表单填写、登录流程、多步向导、文件上传等交互；**浏览器中但凡涉及复杂任务，一律优先使用 ComputerUse**。
- **ComputerUse**：用于一切「需要和界面交互」或「复杂多步」的任务，**包括在浏览器中的复杂操作**（登录、填表、多步流程等）；call_subordinate 传 `profile: "computer"`。

## 技术方案

1. **多模态输入**：每轮调用大模型前，通过扩展向 prompt 注入 2～n 张图片（原始截图、带序号标注图、可选的 2× 象限放大图），模型基于视觉理解与推理并生成下一步工具调用。
2. **截图**：使用本目录下 `screen.py` 的 `screenshot_current_monitor()` 获取当前光标所在显示器的截图及 bbox。
3. **标注与序号**：`som_util.py` 的 `BoxAnnotator` 通过 **HTTP** 调用 `POST /api/v1/annotate/all`（RF-DETR + 可选 OCR、去重与排序由服务端完成），返回带序号的标注图与 `boxes`；本仓库不再加载本地检测模型。基址由环境变量 `COMPUTER_ANNOTATE_API_BASE` 配置（默认 `http://127.0.0.1:8000`）。
4. **可选象限放大**：将标注图按 2×2 分为左上、右上、右下、左下四块；若用户或上一轮回复中出现方位词（如「左上」「top_left」等），则把对应象限裁剪并 2 倍放大后一并作为输入。
5. **工具**：拆分为 **mouse**（click_index、double_click_index、click_at、scroll_at_current 等）、**hotkey**（`goal` + `keys`）、**modified_click**（modified_click_index、modified_click_at）、**composite_action**（type_text_at_index、type_text_at、scroll_at_index）、**wait**。优先用序号；若目标元素无序号，则用坐标（模型输出归一化坐标，由 `coord_convert.py` 按配置的坐标系还原为屏幕像素）。**调用优先级**：尽量少调用 → 优先 composite_action，其次 hotkey/modified_click，再次 mouse；需要延迟时用 wait。**阅读与数据**：在每次滚动前用 **extract_data:extract**（instruction + task_index）将当前可见内容追加到任务临时文件；当某子任务的全部片段提取完毕，调用 **task_done**（task_index）；有碎片时会自动合并并保存为正式文件。

## 架构与数据流

```
用户消息 → message_loop_prompts_after 扩展（仅 profile=computer）
         → screenshot_current_monitor() → 图1 原图
         → BoxAnnotator (HTTP annotate API) → 图2 标注图（带序号）
         → 可选：根据方位词裁剪 2× 象限 → 图3..n
         → 构建 index_map（屏幕坐标）写入 agent.data
         → 将图1+图2..n 以 RawMessage 追加到 loop_data.history_output
         → prepare_prompt() 拼出含图片的 messages → 调用大模型
         → 模型返回 tool_name + tool_args
         → get_tool(tool_name, method, args) → MouseTool / HotkeyTool / ModifiedClickTool / CompositeActionTool / WaitTool
         → _resolve_index(index_map, index) → ActionTools._click / _double_click / _type_text
```

## 目录与文件说明

| 路径 | 说明 |
|------|------|
| `agent.json` | Agent 元信息：title ComputerUse，description、context。 |
| `prompts/agent.system.main.role.md` | 角色与操作规范（基于截图与序号行动）。 |
| `prompts/agent.system.main.communication.md` | 沟通格式：JSON（thoughts / tool_name / tool_args）、vision 工具说明与调用优先级。 |
| `prompts/agent.system.tool.mouse.md` 等 | 工具说明：mouse、hotkey、modified_click、composite_action、wait 的用法、参数与示例。 |
| `prompts/agent.system.os.macos.md` | **macOS 专用**：快捷键参考（Command 修饰键、地址栏/标签/刷新等快捷键）。 |
| `prompts/agent.system.os.windows.md` | **Windows 专用**：快捷键参考（Ctrl 修饰键、地址栏/标签/刷新等快捷键）。 |
| `prompts/agent.system.os.linux.md` | **Linux 专用**：快捷键参考（Ctrl 修饰键、地址栏/标签/刷新等快捷键）。 |
| `os_prompts.py` | OS 提示词加载器：根据当前操作系统动态加载对应的快捷键参考文件。 |
| `screen.py` | 截图：`screenshot_current_monitor()` 返回 (PIL Image, (left, top, width, height))；`encode_image` 等。 |
| `som_util.py` | `SomAnnotator` 协议 + `BoxAnnotator`：multipart 调用 `/api/v1/annotate/all`，解析 `boxes` 与 PNG `image_base64`；响应 `width`/`height` 或解码图尺寸须与输入截图一致，否则抛 `AnnotateApiError`。 |
| `actions.py` | `ActionTools`：`_click`、`_double_click`、`_type_text` 等底层操作（pyautogui / pyperclip）。 |
| `extensions/message_loop_prompts_after/_10_computer_screen_inject.py` | 屏幕注入扩展：截图、predict_and_annotate_all（单张标注图）、可选象限、写 index_map。历史截图管理：保留原始图用于对比，剔除标注图与放大图以节省 token。 |
| `tools/vision_common.py` | 共享逻辑：index_map/screen_info、resolve_index、get_coord_pos、scroll  clamping、LAST_VISION_ACTION_KEY、after_execution 钩子。 |
| `tools/mouse.py`、`hotkey.py`、`modified_click.py`、`composite_action.py`、`wait.py` | 五个 vision 工具：从 vision_common 与 actions 执行点击、快捷键、修饰键+点击、组合操作、等待。 |
| `coord_convert.py` | 可扩展的坐标还原：将模型输出的归一化坐标转为屏幕像素。内置 `qwen`（1000×1000）、`kimi`（1×1）、`pixel`；通过 `vision_coordinate_system` 配置项选择。 |
| `storage_paths.py` | 统一解析 **工作目录**（Settings 中的 `workdir_path`，默认 `usr/workdir`）下的 `computer/snapshots`、`computer/extract_data`、`computer/task_done`。**不再**写入仓库内 `agents/computer/` 下同名目录。 |
| `snapshots/`（数据目录） | 实际路径：`{workdir}/computer/snapshots/<context_id>/`。每轮注入保存 raw / annotated / zoom 的 PNG。History 里图片消息的 `preview` 仅含 **`文件名`**（省 token；磁盘上仍按 context 分目录）。旧数据若在 `agents/computer/snapshots/` 可手动迁入对应 `workdir` 路径。 |
| `extract_data/`、`task_done/`（数据目录） | 实际路径：`{workdir}/computer/extract_data/<context_id>/` 与 `{workdir}/computer/task_done/<context_id>/`，由 `task_data_memory.py` 使用。 |

## 依赖

- **截图与操作**：`mss`、`pyautogui`、`PIL`、`pyperclip`
- **标注**：`requests`（`som_util.BoxAnnotator` 调用外部 annotate 服务；服务需单独部署并监听 `COMPUTER_ANNOTATE_API_BASE`）
- **滚动/热力图等**：`cv2`、`numpy`、`scipy`（如 `scroll_heatmap.py`、`mouse_path.py` 中 `mouse_path_spline`）

### Annotate 服务环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `COMPUTER_ANNOTATE_API_BASE` | `http://127.0.0.1:8000` | 仅基址；路径固定为 `/api/v1/annotate/all` |
| `COMPUTER_ANNOTATE_TIMEOUT` | `120` | 请求超时（秒，浮点可解析） |

屏幕注入在异步上下文中通过 `asyncio.to_thread` 调用阻塞式 `requests.post`，避免卡住事件循环。

- **rtree**：`_10_computer_screen_inject.py` 用 rtree 在提示词中列出「距鼠标最近的若干已标注元素」的归一化 bbox。`pip install rtree` 需系统先安装 libspatialindex（macOS: `brew install spatialindex`）。

## 标注图与序号

检测、去重、排序与绘制均由 **annotate 服务端**完成（与本仓库旧版本地 `BoxAnnotator.annotate` 行为可能略有差异）。客户端要求返回图与 JSON 宽高与输入截图一致；再在本地叠加鼠标/焦点图层后发往模型。模型侧阅读方式仍以注入扩展中的说明为准（按颜色与位置匹配序号与目标元素）。

## 运行前准备

运行前请确保使用 **profile=computer**，且 **chat 模型已开启 vision**。下面分两点说明。

### 1. 使用 profile=computer

**profile** 决定当前 Agent 从哪个目录加载配置：prompts、tools、extensions 会按 `agents/<profile>/` 优先查找（如 `agents/computer/prompts`、`agents/computer/tools`）。只有 profile 为 `computer` 时，才会加载本目录的屏幕注入扩展和 vision 工具（mouse、hotkey、modified_click、composite_action、wait），并用到 `agent.json` 与 computer 的 system prompt。

- **方式一：直接以 computer 为主 Agent 启动**  
  在配置里把 **agent_profile** 设为 `computer`（例如在 settings/配置文件中设置 `agent_profile: computer`）。`initialize_agent()` 会读取该值并赋给 `config.profile`，主 Agent 从启动起就是 computer profile。

- **方式二：通过 call_subordinate 派发子任务**  
  主 Agent（如 agent0）在对话中调用 `call_subordinate` 工具时，在 `tool_args` 里传入 `"profile": "computer"`（以及 `message`、必要时 `reset`）。框架会创建一个子 Agent，并把其 `config.profile` 设为 `computer`，该子 Agent 执行 monologue 时就会使用 computer 的扩展和工具；主 Agent 拿到子 Agent 的回复后再继续。适合「主 Agent 把需要看屏操作的那一步交给 ComputerUse 做」的流程。

### 2. chat 模型已开启 vision

ComputerUse 每轮都会把截图（及标注图等）作为**图片消息**塞进发给大模型的 messages 里。只有「支持多模态输入」的 chat 模型才能正确处理这些图片并做视觉推理。

### 3. 坐标还原（使用 click_at 等时）

当目标元素无序号时，模型可输出坐标类工具（如 **mouse:click_at**）并传入 `x`, `y`。不同模型使用的归一化坐标系不同，需在配置中指定 `vision_coordinate_system`，以便正确还原为屏幕像素：

- **qwen**（默认）：模型坐标范围为 0～1000（1000×1000）。
- **kimi**：模型坐标范围为 0～1（1×1）。
- **pixel**：模型直接输出截图像素坐标（仅做边界裁剪）。

在运行 ComputerUse 的 agent 配置里设置 `vision_coordinate_system: "kimi"` 即可切换；不设置时默认为 `"qwen"`。

### 4. 验证码 (captcha_verify) 配置

使用 `captcha_verify` 工具前需配置 DaTi 打码参数，为**系统级设置**（与 Chat/Util/Browser 模型配置同级）。**方式一**：在设置界面 **Settings → Agent Settings → CAPTCHA / DaTi** 中填写 `dati_api_url`、`dati_authcode`、`dati_typeno`、`dati_author`；或直接编辑 `usr/settings.json`。**方式二**：设置环境变量 `A0_SET_dati_api_url`、`A0_SET_dati_authcode`、`A0_SET_dati_typeno`、`A0_SET_dati_author`（或项目根目录 `.env`）。未填项由环境变量与默认值补充。

### 5. 操作系统特定快捷键

ComputerUse 支持 macOS、Windows 和 Linux，每轮屏幕注入时会自动检测当前操作系统，并加载对应的快捷键参考文件：

- **macOS**: `prompts/agent.system.os.macos.md` — 使用 `command` (⌘) 作为主要修饰键
- **Windows**: `prompts/agent.system.os.windows.md` — 使用 `ctrl` 作为主要修饰键  
- **Linux**: `prompts/agent.system.os.linux.md` — 使用 `ctrl` 作为主要修饰键

模型在生成快捷键时会根据当前 OS 自动选择正确的修饰键（在 **hotkey** 的 `tool_args` 中填写 `keys`，例如 `["command", "c"]` 或 `["ctrl", "c"]`），确保操作兼容性。

- **配置层面**：在项目配置中把 **chat_model_vision** 设为 `true`（默认多为 true）。`initialize_agent()` 会把它赋给主 chat 模型的 `ModelConfig.vision`。若为 false，系统不会在 system prompt 里追加 vision 相关说明，且实际调用时通常也不会传图。
- **模型能力**：所用 chat 模型本身必须支持图像输入（例如 GPT-4o、Claude 3、Gemini 等多模态模型）。若选用纯文本模型，即使 `chat_model_vision=true`，接口也可能报错或忽略图片。

总结：**profile=computer** 保证「用这一套 ComputerUse 的扩展和工具」；**chat 模型开启 vision** 保证「当前对话用的主模型能接收并理解截图」。两者都满足后，ComputerUse 才能按设计工作。

## 使用说明

1. 启动或切换到 computer profile 后，每轮都会在构建 prompt 时执行屏幕注入（截图 + 检测 + 标注 + 可选象限），模型会看到当前屏幕的图与序号。
2. 模型应输出 `tool_name` 如 `mouse:click_index`、`composite_action:type_text_at_index`，以及 `tool_args`（`index` 必填，`type_text_at_index` 需带 `text`）。
3. 任务完成后，模型需**先清理环境**（关闭任务过程中弹出的界面、多开的标签页或为任务打开的 app），再调用 `response` 工具返回最终结果，避免留下多余窗口。
