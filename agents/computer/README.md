# ComputerUse Agent

以多模态大模型为基础，通过视觉方式操作电脑（尤其是网页与桌面 UI）的自定义 Agent。每轮对话前自动注入当前屏幕截图与标注图，模型根据图中序号调用 `vision_actions` 工具执行点击、双击、输入等操作。

## 与 browser_agent 的区分（避免歧义）

框架里有两类与「浏览器/电脑操作」相关的能力，容易在口语里都叫成「browser agent」，需要从机制上区分：

| 维度 | **browser_agent** | **ComputerUse（本 profile）** |
|------|-------------------|-------------------------------|
| **类型** | **工具**（tool_name：`browser_agent`） | **Agent 配置**（profile：`computer`） |
| **识别方式** | 主 Agent 在回复里填 `tool_name: "browser_agent"` | 启动或派发子任务时指定 `profile=computer` |
| **实现** | `python/tools/browser_agent.py`，内部用 browser-use + Playwright 控制**无头浏览器** | `agents/computer/`：截图 + 标注 + `vision_actions`，控制**当前显示器的真实屏幕**（像素级点击） |
| **适用场景** | 需要稳定 DOM、无头环境、可复现的网页自动化 | 需要操作真实桌面、已打开的浏览器窗口、本机任意可见 UI |
| **是否独立 profile** | 否，作为工具挂载在任意 profile（如 agent0）下 | 是，`agents/computer/` 对应 profile 名 `computer`，标题为 ComputerUse |

- **不会歧义的地方**：在代码和配置里，二者由不同字段区分——**工具**用 `tool_name`（如 `browser_agent`），**Agent 身份**用 `config.profile`（如 `computer`）。call_subordinate 的「可选 profile」列表来自 `agents/*/agent.json`，里面只有 profile 名（如 `computer`、`researcher`），没有 `browser_agent`（因为那是工具名）。
- **容易歧义的地方**：用户或文档里若笼统说「用 browser agent」，可能指 (1) 调用 `browser_agent` 工具，或 (2) 让某个 agent 去操作浏览器。若指「用视觉操作当前屏幕上的浏览器」，应明确说用 **ComputerUse** 或 **profile=computer**。

## 技术方案

1. **多模态输入**：每轮调用大模型前，通过扩展向 prompt 注入 2～n 张图片（原始截图、带序号标注图、可选的 2× 象限放大图），模型基于视觉理解与推理并生成下一步工具调用。
2. **截图**：使用本目录下 `screen.py` 的 `screenshot_current_monitor()` 获取当前光标所在显示器的截图及 bbox。
3. **标注与序号**：使用 `som_util.py` 的 `BoxAnnotator` 做元素检测，`sort_boxes_lrtb` 按从左到右、从上到下排序后标注序号；序号标签优先在 bbox 正上方居中，空间不足时在正下方居中。
4. **可选象限放大**：将标注图按 2×2 分为左上、右上、右下、左下四块；若用户或上一轮回复中出现方位词（如「左上」「top_left」等），则把对应象限裁剪并 2 倍放大后一并作为输入。
5. **工具**：`tools/vision_actions.py` 中的 `VisionActionsTool` 提供 `vision_actions:click_index`、`vision_actions:double_click_index`、`vision_actions:type_text_at_index`，根据扩展写入的 `index_map` 解析序号为屏幕坐标后委托 `actions.py` 的 `ActionTools` 执行。

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
| `prompts/agent.system.tool.vision_actions.md` | 工具说明：click_index、double_click_index、type_text_at_index 的用法与示例。 |
| `screen.py` | 截图：`screenshot_current_monitor()` 返回 (PIL Image, (left, top, width, height))；`encode_image` 等。 |
| `som_util.py` | `sort_boxes_lrtb(boxes, height)` 按左→右、上→下排序；`BoxAnnotator` 预测并标注，标签位置上/下居中。 |
| `actions.py` | `ActionTools`：`_click`、`_double_click`、`_type_text` 等底层操作（pyautogui / pyperclip）。 |
| `extensions/message_loop_prompts_after/_10_computer_screen_inject.py` | 屏幕注入扩展：截图、检测、排序、标注、可选象限、写 index_map、追加图片到 history_output。 |
| `tools/vision_actions.py` | `VisionActionsTool`：从 agent.data 读 index_map，`_resolve_index` 转序号为坐标，按 method 调用 ActionTools。 |
| `snapshots/` | 调试用：每轮注入时会把当次的 raw、annotated、以及可选 zoom 图按 `snapshots/<context_id>/<timestamp>_raw.png` 等命名保存，便于排查问题；目录已加入 .gitignore。 |

## 依赖

- **截图与操作**：`mss`、`pyautogui`、`PIL`、`pyperclip`
- **标注与检测**：`cv2`、`numpy`、`rfdetr`（som_util 中的 RF-DETR 权重路径见 `BoxAnnotator`）

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

- **配置层面**：在项目配置中把 **chat_model_vision** 设为 `true`（默认多为 true）。`initialize_agent()` 会把它赋给主 chat 模型的 `ModelConfig.vision`。若为 false，系统不会在 system prompt 里追加 vision 相关说明，且实际调用时通常也不会传图。
- **模型能力**：所用 chat 模型本身必须支持图像输入（例如 GPT-4o、Claude 3、Gemini 等多模态模型）。若选用纯文本模型，即使 `chat_model_vision=true`，接口也可能报错或忽略图片。

总结：**profile=computer** 保证「用这一套 ComputerUse 的扩展和工具」；**chat 模型开启 vision** 保证「当前对话用的主模型能接收并理解截图」。两者都满足后，ComputerUse 才能按设计工作。

## 使用说明

1. 启动或切换到 computer profile 后，每轮都会在构建 prompt 时执行屏幕注入（截图 + 检测 + 标注 + 可选象限），模型会看到当前屏幕的图与序号。
2. 模型应输出 `tool_name` 如 `vision_actions:click_index`、`vision_actions:type_text_at_index`，以及 `tool_args`（`index` 必填，`type_text_at_index` 需带 `text`）。
3. 任务完成后模型可调用 `response` 工具返回最终结果。
