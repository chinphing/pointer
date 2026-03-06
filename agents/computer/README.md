# ComputerUse Agent

以多模态大模型为基础，通过视觉方式操作电脑（尤其是网页与桌面 UI）的自定义 Agent。每轮对话前自动注入当前屏幕截图与标注图，模型根据图中序号调用 `vision_actions` 工具执行点击、双击、输入等操作。

## 与 browser_agent 的区分（避免歧义）

框架里有两类与「浏览器/电脑操作」相关的能力，职责明确区分如下：

| 维度 | **browser_agent** | **ComputerUse（本 profile）** |
|------|-------------------|-------------------------------|
| **类型** | **工具**（tool_name：`browser_agent`） | **Agent 配置**（profile：`computer`） |
| **职责** | **仅简单搜索与网页纯文本提取**：打开搜索引擎输入关键词取结果、打开 URL 提取正文/链接等纯文本，**不做任何交互操作** | **有交互的操作与复杂任务**：点击、输入、滚动、表单填写、登录、多步流程、文件上传、操作真实桌面与已打开浏览器等 |
| **识别方式** | 主 Agent 在回复里填 `tool_name: "browser_agent"` | 启动或派发子任务时指定 `profile=computer` |
| **实现** | `python/tools/browser_agent.py`，browser-use + Playwright **无头浏览器** | `agents/computer/`：截图 + 标注 + `vision_actions`，控制**当前显示器的真实屏幕**（像素级点击） |
| **适用场景** | 仅需：搜一下、打开页面取文字；且**界面尚未打开**（无头浏览器新建会话） | 需要：在页面上点击、填表、登录、多步操作；或**界面已打开/已存在**（操作当前屏幕上的浏览器或任意可见 UI） |
| **是否独立 profile** | 否，作为工具挂载在任意 profile 下 | 是，profile 名 `computer`，标题 ComputerUse |

- **browser_agent**：不用于表单填写、登录流程、多步向导、文件上传等交互；**浏览器中但凡涉及复杂任务，一律优先使用 ComputerUse**。
- **ComputerUse**：用于一切「需要和界面交互」或「复杂多步」的任务，**包括在浏览器中的复杂操作**（登录、填表、多步流程等）；call_subordinate 传 `profile: "computer"`。

## 技术方案

1. **多模态输入**：每轮调用大模型前，通过扩展向 prompt 注入 2～n 张图片（原始截图、带序号标注图、可选的 2× 象限放大图），模型基于视觉理解与推理并生成下一步工具调用。
2. **截图**：使用本目录下 `screen.py` 的 `screenshot_current_monitor()` 获取当前光标所在显示器的截图及 bbox。
3. **标注与序号**：使用 `som_util.py` 的 `BoxAnnotator` 做元素检测，`sort_boxes_lrtb` 按从左到右、从上到下排序后标注序号；序号标签优先在 bbox 正上方居中，空间不足时在正下方居中。
4. **可选象限放大**：将标注图按 2×2 分为左上、右上、右下、左下四块；若用户或上一轮回复中出现方位词（如「左上」「top_left」等），则把对应象限裁剪并 2 倍放大后一并作为输入。
5. **工具**：`tools/vision_actions.py` 中的 `VisionActionsTool` 提供基于序号的 `vision_actions:click_index`、`vision_actions:double_click_index`、`vision_actions:type_text_at_index` 等，以及基于坐标的 `vision_actions:click_at`、`vision_actions:type_text_at`（x, y, text）等。优先用序号；若目标元素无序号，则用坐标（模型输出归一化坐标，由 `coord_convert.py` 按配置的坐标系还原为屏幕像素）。**数据提取**：`tools/extract_data.py` 中的 `ExtractDataTool` 提供 `extract_data:extract`，对当前屏幕截图并调用视觉大模型按指令提取结构化数据（如链接列表、表格 JSON）。

## 架构与数据流

```
用户消息 → message_loop_prompts_after 扩展（仅 profile=computer）
         → screenshot_current_monitor() → 图1 原图
         → BoxAnnotator.predict + sort_boxes_lrtb + annotate → 图2 标注图
         → 可选：根据方位词裁剪 2× 象限 → 图3..n
         → 构建 index_map（屏幕坐标）写入 agent.data["computer_vision_index_map"]
         → 将图1+图2+图3..n 以 RawMessage 追加到 loop_data.history_output
         → prepare_prompt() 拼出含图片的 messages → 调用大模型
         → 模型返回 tool_name + tool_args
         → get_tool("vision_actions", method, args) → VisionActionsTool.execute
         → _resolve_index(index_map, index) → ActionTools._click / _double_click / _type_text
```

## 目录与文件说明

| 路径 | 说明 |
|------|------|
| `agent.json` | Agent 元信息：title ComputerUse，description、context。 |
| `prompts/agent.system.main.role.md` | 角色与操作规范（基于截图与序号行动）。 |
| `prompts/agent.system.main.communication.md` | 沟通格式：JSON（thoughts / tool_name / tool_args）、vision_actions 工具说明。 |
| `prompts/agent.system.tool.vision_actions.md` | 工具说明：所有 vision_actions（click、type、scroll 等）的用法、参数、**操作后校验方法**与示例。 |
| `prompts/agent.system.tool.extract_data.md` | 工具说明：extract_data:extract 的用法与示例（按 instruction 从屏幕提取数据）。 |
| `prompts/agent.system.os.macos.md` | **macOS 专用**：快捷键参考（Command 修饰键、地址栏/标签/刷新等快捷键）。 |
| `prompts/agent.system.os.windows.md` | **Windows 专用**：快捷键参考（Ctrl 修饰键、地址栏/标签/刷新等快捷键）。 |
| `prompts/agent.system.os.linux.md` | **Linux 专用**：快捷键参考（Ctrl 修饰键、地址栏/标签/刷新等快捷键）。 |
| `os_prompts.py` | OS 提示词加载器：根据当前操作系统动态加载对应的快捷键参考文件。 |
| `tools/extract_data.py` | `ExtractDataTool`：截屏后调用视觉模型按 instruction 提取数据并返回。 |
| `screen.py` | 截图：`screenshot_current_monitor()` 返回 (PIL Image, (left, top, width, height))；`encode_image` 等。 |
| `som_util.py` | `sort_boxes_lrtb(boxes, height)` 按左→右、上→下排序；`BoxAnnotator` 预测并标注，标签位置上/下居中。 |
| `actions.py` | `ActionTools`：`_click`、`_double_click`、`_type_text` 等底层操作（pyautogui / pyperclip）。 |
| `extensions/message_loop_prompts_after/_10_computer_screen_inject.py` | 屏幕注入扩展：截图、检测、排序、标注、可选象限、写 index_map。支持历史截图管理：保留原始截图用于对比，剔除标注图和放大图以节省 token。 |
| `tools/vision_actions.py` | `VisionActionsTool`：从 agent.data 读 index_map 与 screen_info，序号用 `_resolve_index`，坐标用 `_resolve_coord`（经 coord_convert 还原），按 method 调用 ActionTools。 |
| `coord_convert.py` | 可扩展的坐标还原：将模型输出的归一化坐标转为屏幕像素。内置 `qwen`（1000×1000）、`kimi`（1×1）、`pixel`；通过 `vision_coordinate_system` 配置项选择。 |
| `snapshots/` | 调试用：每轮注入时会把当次的 raw、annotated、以及可选 zoom 图按 `snapshots/<context_id>/<timestamp>_raw.png` 等命名保存，便于排查问题；目录已加入 .gitignore。 |

## 依赖

- **截图与操作**：`mss`、`pyautogui`、`PIL`、`pyperclip`
- **标注与检测**：`cv2`、`numpy`、`rfdetr`（som_util 中的 RF-DETR 权重路径见 `BoxAnnotator`）

## 标注与标签放置策略

`som_util.py` 中的 `BoxAnnotator` 负责检测交互元素并标注序号。标签放置遵循以下优先级规则：

1. **排序规则**：元素按左→右、上→下排序（`sort_boxes_lrtb`），确保相邻元素序号相邻
2. **位置优先级**：上 → 下 → 右 → 左（按视觉清晰度和阅读习惯）
3. **边界检测**：标签必须完全在图像边界内
4. **重叠避免**：标签矩形不能与任何其他元素 box 相交
5. **邻近降权**：若某方向 50px 内有其他元素，该方向优先级降低（避免标签挤在一起）
6. **颜色差异化**：相邻序号使用色相间隔较大的颜色，便于区分
7. **内部备选**：若四个方向都无法放置（都被占据或超出边界），标签放在元素框内左上角

### 行列标签冲突优化方案

针对上下两行或并列两列元素的标签重叠问题，可进一步优化：

- **行感知放置**：检测元素是否在同一行（y 坐标差 < 行高），如果是，优先上下放置标签，而非左右
- **列感知放置**：检测元素是否在同一列（x 坐标差 < 列宽），如果是，优先左右放置标签，而非上下
- **动态偏移**：当相邻元素标签可能冲突时，向远离相邻元素的方向微调标签位置（如 10-20px）
- **标签尺寸分级**：对密集区域使用更小的字号，或在元素 hover 时才显示大标签

当前实现已包含基础的距离检测和优先级调整；如需更强的行列感知，可在 `annotate()` 中增加行/列聚类逻辑。

## 运行前准备

运行前请确保使用 **profile=computer**，且 **chat 模型已开启 vision**。下面分两点说明。

### 1. 使用 profile=computer

**profile** 决定当前 Agent 从哪个目录加载配置：prompts、tools、extensions 会按 `agents/<profile>/` 优先查找（如 `agents/computer/prompts`、`agents/computer/tools`）。只有 profile 为 `computer` 时，才会加载本目录的屏幕注入扩展和 `vision_actions` 工具，并用到 `agent.json` 与 computer 的 system prompt。

- **方式一：直接以 computer 为主 Agent 启动**  
  在配置里把 **agent_profile** 设为 `computer`（例如在 settings/配置文件中设置 `agent_profile: computer`）。`initialize_agent()` 会读取该值并赋给 `config.profile`，主 Agent 从启动起就是 computer profile。

- **方式二：通过 call_subordinate 派发子任务**  
  主 Agent（如 agent0）在对话中调用 `call_subordinate` 工具时，在 `tool_args` 里传入 `"profile": "computer"`（以及 `message`、必要时 `reset`）。框架会创建一个子 Agent，并把其 `config.profile` 设为 `computer`，该子 Agent 执行 monologue 时就会使用 computer 的扩展和工具；主 Agent 拿到子 Agent 的回复后再继续。适合「主 Agent 把需要看屏操作的那一步交给 ComputerUse 做」的流程。

### 2. chat 模型已开启 vision

ComputerUse 每轮都会把截图（及标注图等）作为**图片消息**塞进发给大模型的 messages 里。只有「支持多模态输入」的 chat 模型才能正确处理这些图片并做视觉推理。

### 3. 坐标还原（使用 click_at 等时）

当目标元素无序号时，模型可输出坐标类工具（如 `vision_actions:click_at`）并传入 `x`, `y`。不同模型使用的归一化坐标系不同，需在配置中指定 `vision_coordinate_system`，以便正确还原为屏幕像素：

- **qwen**（默认）：模型坐标范围为 0～1000（1000×1000）。
- **kimi**：模型坐标范围为 0～1（1×1）。
- **pixel**：模型直接输出截图像素坐标（仅做边界裁剪）。

在运行 ComputerUse 的 agent 配置里设置 `vision_coordinate_system: "kimi"` 即可切换；不设置时默认为 `"qwen"`。

### 4. 操作系统特定快捷键

ComputerUse 支持 macOS、Windows 和 Linux，每轮屏幕注入时会自动检测当前操作系统，并加载对应的快捷键参考文件：

- **macOS**: `prompts/agent.system.os.macos.md` — 使用 `command` (⌘) 作为主要修饰键
- **Windows**: `prompts/agent.system.os.windows.md` — 使用 `ctrl` 作为主要修饰键  
- **Linux**: `prompts/agent.system.os.linux.md` — 使用 `ctrl` 作为主要修饰键

模型在生成快捷键时会根据当前 OS 自动选择正确的修饰键（如 `press_keys ["command", "c"]` vs `["ctrl", "c"]`），确保操作兼容性。

- **配置层面**：在项目配置中把 **chat_model_vision** 设为 `true`（默认多为 true）。`initialize_agent()` 会把它赋给主 chat 模型的 `ModelConfig.vision`。若为 false，系统不会在 system prompt 里追加 vision 相关说明，且实际调用时通常也不会传图。
- **模型能力**：所用 chat 模型本身必须支持图像输入（例如 GPT-4o、Claude 3、Gemini 等多模态模型）。若选用纯文本模型，即使 `chat_model_vision=true`，接口也可能报错或忽略图片。

总结：**profile=computer** 保证「用这一套 ComputerUse 的扩展和工具」；**chat 模型开启 vision** 保证「当前对话用的主模型能接收并理解截图」。两者都满足后，ComputerUse 才能按设计工作。

## 使用说明

1. 启动或切换到 computer profile 后，每轮都会在构建 prompt 时执行屏幕注入（截图 + 检测 + 标注 + 可选象限），模型会看到当前屏幕的图与序号。
2. 模型应输出 `tool_name` 如 `vision_actions:click_index`、`vision_actions:type_text_at_index`，以及 `tool_args`（`index` 必填，`type_text_at_index` 需带 `text`）。
3. 任务完成后，模型需**先清理环境**（关闭任务过程中弹出的界面、多开的标签页或为任务打开的 app），再调用 `response` 工具返回最终结果，避免留下多余窗口。
