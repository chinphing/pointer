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
3. **标注与序号**：使用 `som_util.py` 的 `BoxAnnotator` 做元素检测，`sort_boxes_lrtb` 按从左到右、从上到下排序后标注序号；序号标签优先在 bbox 正上方居中，空间不足时在正下方居中。
4. **可选象限放大**：将标注图按 2×2 分为左上、右上、右下、左下四块；若用户或上一轮回复中出现方位词（如「左上」「top_left」等），则把对应象限裁剪并 2 倍放大后一并作为输入。
5. **工具**：拆分为 **mouse**（click_index、double_click_index、click_at、scroll_at_current 等）、**hotkey**（press_keys）、**modified_click**（modified_click_index、modified_click_at）、**composite_action**（type_text_at_index、type_text_at、scroll_at_index）、**wait**。优先用序号；若目标元素无序号，则用坐标（模型输出归一化坐标，由 `coord_convert.py` 按配置的坐标系还原为屏幕像素）。**调用优先级**：尽量少调用 → 优先 composite_action，其次 hotkey/modified_click，再次 mouse；需要延迟时用 wait。**阅读与数据**：在每次滚动前用 **extract_data:extract**（instruction + task_index）将当前可见内容追加到任务临时文件；当某子任务的全部片段提取完毕，调用 **task_done**（task_index）；有碎片时会自动合并并保存为正式文件。

## 架构与数据流

```
用户消息 → message_loop_prompts_after 扩展（仅 profile=computer）
         → screenshot_current_monitor() → 图1 原图
         → BoxAnnotator.predict_and_annotate_all → 图2 标注图（带序号）
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
| `som_util.py` | `sort_boxes_lrtb(boxes, height)` 按左→右、上→下排序；`BoxAnnotator` 预测并标注，标签位置上/下居中。 |
| `actions.py` | `ActionTools`：`_click`、`_double_click`、`_type_text` 等底层操作（pyautogui / pyperclip）。 |
| `extensions/message_loop_prompts_after/_10_computer_screen_inject.py` | 屏幕注入扩展：截图、predict_and_annotate_all（单张标注图）、可选象限、写 index_map。历史截图管理：保留原始图用于对比，剔除标注图与放大图以节省 token。 |
| `tools/vision_common.py` | 共享逻辑：index_map/screen_info、resolve_index、get_coord_pos、scroll  clamping、LAST_VISION_ACTION_KEY、after_execution 钩子。 |
| `tools/mouse.py`、`hotkey.py`、`modified_click.py`、`composite_action.py`、`wait.py` | 五个 vision 工具：从 vision_common 与 actions 执行点击、快捷键、修饰键+点击、组合操作、等待。 |
| `coord_convert.py` | 可扩展的坐标还原：将模型输出的归一化坐标转为屏幕像素。内置 `qwen`（1000×1000）、`kimi`（1×1）、`pixel`；通过 `vision_coordinate_system` 配置项选择。 |
| `snapshots/` | 调试用：每轮注入时会把当次的 raw、annotated、以及可选 zoom 图按 `snapshots/<context_id>/<timestamp>_raw.png` 等命名保存，便于排查问题；目录已加入 .gitignore。 |

## 依赖

- **截图与操作**：`mss`、`pyautogui`、`PIL`、`pyperclip`
- **标注与检测**：`cv2`、`numpy`、`rfdetr`、`paddle`/`paddleocr`（som_util 中的 RF-DETR 权重路径见 `BoxAnnotator`）

### macOS：pyharp / libnetcdf 报错

若出现 `Library not loaded: ... libnetcdf.22.dylib`（来自 `pyharp`，多为 paddle/paddleocr 的传递依赖），需安装 Homebrew 的 netcdf 并视情况做符号链接：

```bash
brew install netcdf
```

若安装后是 `libnetcdf.23.dylib` 等其它版本，而程序仍找 `libnetcdf.22.dylib`，可在 netcdf 的 lib 目录下为当前版本创建 22 的符号链接（以 23 为例）：

```bash
cd "$(brew --prefix netcdf)/lib" && ln -sf libnetcdf.23.dylib libnetcdf.22.dylib
```

（将 `23` 换成你本机 `ls libnetcdf.*.dylib` 看到的版本号。）

- **rtree**：标签放置时用 rtree 快速查询重叠/最近邻。`pip install rtree` 需系统先安装 libspatialindex（macOS: `brew install spatialindex`）。

## 标注与标签放置策略

`som_util.py` 中的 `BoxAnnotator` 负责检测交互元素并标注序号。标签放置采用「按重叠面积选方向 + 50% 过挤兜底 + rtree 加速」：

1. **四方向按覆盖比例选**：对每个方向计算该方向标签对「其他元素」的覆盖比例之和（覆盖比例 = 交集面积/该其它元素面积），在**边界内**的候选中选取**总覆盖比例最小**的方向；同分时保持上→下→右→左顺序。
2. **50% 过挤则框内**：每个方向记录「对单个其它元素的最大覆盖比例」（分母为其它元素面积）。若四个方向该最大比例均 > 50%，则在当前元素框内左上角放置标签。
3. **边界**：标签背景不得超出图像范围。
4. **颜色差异化**：相邻序号使用色相间隔较大的颜色。
5. **rtree 性能优化**：重叠面积累加时不遍历全部元素，仅用 rtree 取「与标签相交的至多 5 个」+「最近邻 5 个」参与计算（依赖 `rtree`，需安装 libspatialindex）。

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
2. 模型应输出 `tool_name` 如 `mouse:click_index`、`composite_action:type_text_at_index`，以及 `tool_args`（`index` 必填，`type_text_at_index` 需带 `text`）。
3. 任务完成后，模型需**先清理环境**（关闭任务过程中弹出的界面、多开的标签页或为任务打开的 app），再调用 `response` 工具返回最终结果，避免留下多余窗口。
