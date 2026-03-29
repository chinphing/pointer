# Pointer

[English](README.md) | **简体中文**

> 基于多模态大模型的**真屏幕**电脑使用智能体。基于 **Agent Zero**，使用 **Computer（Pointer）** 配置：像人一样看显示器、操作界面、填表并在各应用间完成任务。

**模型支持：** 目前仅验证 **DashScope `qwen3.5-plus`**。除 API 密钥外，还必须将 **`api_base`** 设为正确的区域端点——见下文 **§4.4**。

---

## 1. Pointer 是什么、能做什么

**Pointer** 面向**真实桌面与浏览器界面**。它不依赖在无头浏览器里单独开一页；而是**截取显示器上可见内容**，理解界面元素，并通过**鼠标、键盘、快捷键与组合操作**执行动作——与人使用电脑的方式一致。

**能力包括：**

- **交互**：网页与桌面应用中的点击、输入、滚动、多选、拖拽等  
- **多步流程**：登录向导、表单、文件选择器、分页阅读与采集  
- **视觉**：带编号的界面叠加层，以及可选的放大区域以减少误点  
- **结构化记忆**：按任务的屏幕抽取与合并、`task_done:checkpoint` / `read`、持久化执行状态（详见 `agents/computer/` 文档）

Pointer 以 **Agent Zero 配置（`computer`）** 运行，因此工具编排、对话与扩展机制一致。产品名为 **Pointer**。

---

## 2. 使用场景与演示

**目标：** 我们致力于**用可靠的自动化，全面替代重复的、体力型的电脑操作**——即人们每天在键盘鼠标与界面间完成的例行点击、输入与导航。这既包括**个人日常任务**（您自己的桌面与浏览器工作流），也包括**企业员工的日常工作**（标准业务应用与 Web 管理后台中的重复操作步骤），凡需要视觉、判断与多步控制的场景均适用。

**示例场景：**

- 复杂网页流程（登录、检索、表单、管理后台、多页采集）  
- 桌面应用与混合办公（真实前台窗口，与您的其他工作并存）  
- 需要**视觉 + 推理 + 长程规划**的重复人机任务  

**视频演示：**  
-  [7类21种场景验证码验证](https://bilibili.com/video/BV1S6X4BsEjN/)
-  [当我花一个小时教会纯视觉Agent自动购买阿里云服务器之后，我要对“CLI一切”说不！](https://youtu.be/zWOtxBAZ5GQ)

**在线体验 / 试点：**  
试用、演示或合作请联系 **starphinliu@gmail.com**。

---

## 3. 核心特性

| 方面 | 说明 |
|------|------|
| **类人操作** | 实时截图与界面标注；优先使用元素索引，必要时回退到坐标；针对 macOS、Windows、Linux 注入各系统快捷键提示。 |
| **凭据安全** | 专用登录与凭据处理，避免将明文密码写入模型可见的提示；引导式安全填写（详见 Computer Agent 工具说明）。 |
| **验证码** | **captcha_verify** 及相关流程：检测到类验证码界面时，按协议选择点击 / 输入 / 拖拽（具体行为依实现与模型而定）。 |
| **完整 Agent Zero 能力** | 技能、记忆与学习、代码执行、从属智能体、MCP、浏览器工具等——可按任务与 Pointer 一并使用。 |
| **长程任务** | 屏幕抽取、按任务索引合并、`task_done:checkpoint` / `read`，以及持久化的计划 / 进度 / 经验，以控制上下文并提升可恢复性。 |

架构、目录、环境变量与工具说明见 **[agents/computer/README.md](agents/computer/README.md)**。

---

## 4. 安装与部署

### 4.1 环境要求

- **Python：** 建议 3.10+（与项目依赖一致）  
- **操作系统：** **macOS**、**Windows**、**Linux**；Pointer 会注入各系统快捷键说明
- **权限：** 截图与输入可能需屏幕录制、无障碍 / 辅助功能等权限——请在系统设置中按需授权

### 4.2 安装依赖

在仓库根目录执行：

```bash
pip install -r requirements.txt
pip install -r requirements2.txt
```

`requirements2.txt` 包含 **LiteLLM** 与 **OpenAI SDK**（模型调用）。两个文件都需要安装。

开发与测试可选：

```bash
pip install -r requirements.dev.txt
```

### 4.3 各系统说明

| 系统 | 说明 |
|------|------|
| **macOS** | 为终端或 Python 进程开启**屏幕录制**与**辅助功能**；否则可能无法截图或控制。 |
| **Windows** | 注意 HiDPI 缩放；请在正常交互式桌面会话中运行（非无桌面无头会话）。 |
| **Linux** | 需要显示服务器（如 X11）。无显示器主机需虚拟显示（如 Xvfb）—*（待定：推荐发行版与最小配置）* |

### 4.4 API 密钥与模型

1. 若工作流使用环境文件，可复制或创建（如 `.env`）。  
2. 在 **Web UI 设置**或 `.env` 中配置对应**服务商**的密钥（见 [`conf/model_providers.yaml`](conf/model_providers.yaml)），例如：
   - OpenAI、OpenRouter、Anthropic 等  
- **DashScope（通义）：** `DASHSCOPE_API_KEY` 或 `API_KEY_DASHSCOPE`（provider id：`dashscope`）
3. **必须为 DashScope 设置 `api_base`。** LiteLLM **不会**自动区分国内与国际。在**设置**中为使用 DashScope 的每个角色填写 **API base**（**Chat**、**Utility** 等——如 *chat model API base*、*utility model API base*），或确保从 [`conf/model_providers.yaml`](conf/model_providers.yaml) 默认合并。请使用与密钥签发区域一致的 URL：

   | 区域 | `api_base` |
   |--------|------------|
   | **中国（北京）** | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
   | **国际** | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |

   区域与密钥不匹配通常会导致认证或路由错误。

4. 为 **Chat**、**Utility**、**Browser** 等选择模型。电脑使用通常需要具备**视觉能力**的 **Utility** 模型以理解截图并做抽取。  

**当前实测模型：** 仅 **DashScope** 上的 **Qwen 3.5 Plus** 已与 Pointer 完成端到端验证。请使用服务商 **`dashscope`**、**正确的区域 `api_base`**（见上表）、**`DASHSCOPE_API_KEY`**（或 **`API_KEY_DASHSCOPE`**），以及模型名 **`qwen3.5-plus`**（或控制台中的准确 id）。在更广兼容性确认前，**Chat**、**Utility** 等角色可能均需该组合。其他服务商与模型 id **未测试**，可能不可用。

### 4.5 工作目录（workdir）

在 **设置 → workdir** 中指定。Pointer 会在其下写入：

- `computer/snapshots/` — 截图与调试图  
- `computer/extract_data/`、`computer/task_done/`、`computer/execution_checkpoint/` — 抽取与任务状态  

除非有意为之，请勿将 workdir 指向只读或易失目录。

### 4.6 标注服务（Computer 必需）

Pointer 调用 **HTTP 标注服务**生成带编号的界面框（默认 `COMPUTER_ANNOTATE_API_BASE`，路径 `/api/v1/annotate/all`）。  

*（待定：服务部署方式、Docker 镜像或文档链接）*

常用环境变量（详见 `agents/computer/README.md`）：

| 变量 | 默认值 | 含义 |
|----------|---------|---------|
| `COMPUTER_ANNOTATE_API_BASE` | `http://127.0.0.1:8000` | 标注 API 根 URL |
| `COMPUTER_ANNOTATE_TIMEOUT` | `120` | 请求超时（秒） |

### 4.7 启动 Web UI

```bash
python run_ui.py
```

*（待定：默认端口、HTTPS、反向代理示例）*

---

## 5. 路线图

1. **简单的 RPA 工作** — 网页数据提取、聊天类任务、访问社交与内容平台（如**小红书**、**X**、**脸书**等），流程主要停留在浏览器或少数常用界面中。

2. **跨应用工作** — 跨软件的文件上传与下载；任务结束后**通过聊天交付结果**；在多个应用或站点之间**自动填写表单**。

3. **做研究** — 针对**公开但需登录**才能获取的专业领域数据开展研究并**交付研究结论**，例如**司法案例研究**等深度检索与归纳场景。

4. **数字员工** — **接收任务 → 制定计划 → 执行任务 → 交付结果**的闭环，面向类似**程序员**、**人事**、**财务**等岗位中的重复性、可编排工作。

---

## 6. 重要提示

**Pointer 可完全控制本机**（鼠标、键盘、系统级快捷键）。在提示不当、模型错误或目标模糊时，可能导致：

- 删除或损坏文件与重要数据  
- 误触发支付、邮件或账户变更  
- 隐私泄露（屏幕内容会发往您配置的模型服务商）  

**请仅在可控环境中使用，做好备份并遵循最小权限；关键业务或生产场景必须有人类监督与审计。**  
因使用本软件造成的直接或间接损失，由使用者自行承担。

---

## 7. 联系方式

- **邮箱：** [starphinliu@gmail.com](mailto:starphinliu@gmail.com)  
- 反馈、试用、合作、定制：**starphinliu@gmail.com**

---

## 许可与致谢

请参阅仓库根目录 **[LICENSE](LICENSE)**（若与上游 Agent Zero 不同，以本仓库文件为准）。

Pointer 基于 **Agent Zero**；Computer / Pointer 相关代码位于 `agents/computer/`。感谢 Agent Zero 与更广泛的开源生态。
