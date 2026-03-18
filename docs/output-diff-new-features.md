# output.diff 新增功能清单

根据 `output.diff`（当前分支相对 main）整理的新增/变更项，便于区分「与消息显示无关」和「需恢复为 main 的消息显示逻辑」。

---

## 一、与「界面消息显示」相关的变更（已恢复为 main 行为）

以下仅在**消息同步与渲染**上恢复为 main，其它新功能保留。

| 序号 | 文件 | 变更内容 | 恢复方式 |
|------|------|----------|----------|
| M1 | `webui/index.js` | `lastProgressActive`、logGap 检测、progressJustEnded、对 logs 按 no 排序、poll 里 progressJustEnded 触发 forceFull | 移除上述逻辑，仅保留「版本变化则 setMessages(snapshot.logs)」 |
| M2 | `webui/components/sync/sync-store.js` | push 后根据 `result.logGap` / `result.progressJustEnded` 再调 forceFull | 移除该分支，push 后只做 applySnapshot + 设 HEALTHY |

---

## 二、与消息显示无关的新增功能（保留）

### 1. 右侧截图面板（Computer 配置）

- **computer-screen-store.js**（新）：截图 blob、鼠标位置、定时刷新、收起/展开
- **index.html**：right-panel 布局（right-panel-top、chat-area、screenshot-and-input-column、right-panel-bottom）、截图列与 cursor 叠加
- **index.css**：`.right-panel-with-screenshot`、`.chat-area`、`.screenshot-and-input-column`、截图面板样式
- **index.js**：引入 computerScreenStore、applySnapshot 里写 computer_screen_raw/mouse、Alpine `screenshotWithCursor`
- **cursor-pointer.svg**（新）：指针图标
- **captcha.html**：设置项 `computer_screen_preview_auto_refresh`、`computer_screen_preview_interval_sec`

### 2. 停止 Agent 按钮

- **bottom-actions.html**：Stop 按钮（running 时显示）
- **input-store.js**：`stopAgent()` 调 `/chat_stop`

### 3. CAPTCHA / DaTi 设置

- **agent-settings.html**：导航增加「CAPTCHA / DaTi」、`#section-captcha`
- **captcha.html**（新）：DaTi API URL、Authcode、Typeno、Author、Slider offset、自动刷新截图、预览间隔

### 4. 聊天模型设置文案

- **chat_model.html**：Chat model additional parameters 说明与 placeholder（含 `extra_body` 示例）

### 5. 设置加载错误提示

- **settings-store.js**：空/非法 JSON 时更明确的错误文案与 toast

### 6. 消息区域样式（仅样式）

- **messages.css**：`#chat-history` padding 从 `var(--spacing-sm/md)` 改为 `10px`

### 7. Process Group / Step 展示增强（非同步逻辑）

- **process-group.css**：`.step-timestamp` 样式
- **messages.js**：`formatStepTimestamp`、step 头时间戳、kvps 中 snapshot 按钮、drawMessageAgent 的 displayKvps（thoughts/plans/snapshot）、drawKvpsIncremental 过滤 snapshot、plans 用 markdown、addValue 的 useMarkdown、convertHTML/escapeHTML 的 null 防护
- **time-utils.js**：`formatStepTimestamp(ts)`（mm:ss + title 完整时间）

### 8. API 与 WebSocket 稳健性（与消息显示无关）

- **api.js**：`responseJson()` 处理空 body，避免 "Unexpected end of JSON input"；callJsonApi / getCsrfToken 使用 responseJson
- **websocket.js**：连接前必须拿到 CSRF（重试、失败抛错）；auth 重试 3 次；disconnect 时 invalidateCsrfToken
- **index.js DOMContentLoaded**：预拉取 `api.getCsrfToken()` 便于 state_sync 首次连接

---

## 三、恢复「界面消息显示」到 main 的修改摘要

- **index.js**
  - 删除 `lastProgressActive` 及所有使用（含 log_guid 重置处、return 处）。
  - 删除 logGap 相关：logVersion/logsArray/expectedNew/hasLogGap 及注释。
  - `lastLogVersion != snapshot.log_version` 时：直接 `setMessages(snapshot.logs)`、`afterMessagesUpdate(snapshot.logs)`，不再对 logs 排序。
  - 末尾只 `return { updated }`，不再返回 progressJustEnded、logGap。
  - **poll()**：删除根据 progressJustEnded 调用 `syncStore.sendStateRequest({ forceFull: true })` 的逻辑。
- **sync-store.js**
  - 在 push 的 `applySnapshot` 之后，删除对 `result.logGap`、`result.progressJustEnded` 的判断及由此触发的 forceFull（含 cooldown、setTimeout）。
  - 保留：`await applySnapshot(...)`，然后 `_setMode(SYNC_MODES.HEALTHY, "push applied")` 与 `_flushPendingReconnectToast()`。

以上恢复后，消息的更新与展示行为与 main 一致；其余新功能（截图面板、Stop、CAPTCHA 设置、step 时间戳与 snapshot 按钮、API/WS 加固等）均保留。
