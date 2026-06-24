---
name: memory
description: 双域记忆系统 — 用户事实记忆与 Agent 策略记忆。
always: true
---

# 记忆

DesktopClaw 使用 **两套记忆域**：

| 域 | 存储 | 用途 |
|--------|---------|---------|
| 用户事实 | `MEMORY.md`、`HISTORY.md` | 偏好、项目上下文、事件日志 |
| Agent 策略 | `reasoning_bank.json`、`graph.db` | 蒸馏的推理模式与避坑准则 |

**记忆库统一使用中文（简体）** — 写入 `MEMORY.md`、`HISTORY.md`、`reasoning_bank.json` 的内容均须中文。

## 用户事实记忆

- `memory/MEMORY.md` — 长期事实（偏好、项目上下文、关系等）。始终加载到上下文中。须使用中文。
- `memory/HISTORY.md` — 仅追加的事件日志。不加载到上下文。用 grep 类工具检索。每条以 `[YYYY-MM-DD HH:MM]` 开头。须使用中文。

### 检索历史事件

根据文件大小选择检索方式：

- 较小的 `memory/HISTORY.md`：用 `read_file` 读入后在内存中搜索
- 较大或长期使用的文件：用 `exec` 做定向搜索

示例：
- **Linux/macOS:** `grep -i "关键词" memory/HISTORY.md`
- **Windows:** `findstr /i "关键词" memory\HISTORY.md`
- **跨平台 Python:** `python -c "from pathlib import Path; text = Path('memory/HISTORY.md').read_text(encoding='utf-8'); print('\n'.join([l for l in text.splitlines() if '关键词' in l][-20:]))"`

大文件优先用命令行定向搜索。

### 何时更新 MEMORY.md

发现重要事实时立即用 `edit_file` 或 `write_file` 写入（中文）：
- 用户偏好（如「我喜欢深色模式」）
- 项目上下文（如「API 使用 OAuth2」）
- 人物关系（如「Alice 是项目负责人」）

### 自动归档

会话过长时，旧对话会自动摘要写入 `HISTORY.md`，长期事实提取到 `MEMORY.md`。无需手动管理。

## Agent 策略记忆

- `memory/reasoning_bank.json` — 结构化策略单元（title、description、content，kind: strategy/pitfall）。**须使用中文。** 任务开始与工具失败时自动检索。可手动读写以修正。
- `memory/graph.db` — 内部图索引（Cue-Tag-Content）。自动维护，勿手改。
- `memory/.embeddings_model/` — 缓存的 Qwen3 嵌入模型（首次使用时下载）。

复杂任务结束后，系统会从成败中蒸馏可复用策略。检索结果以 **Agent 策略记忆（检索结果）** 注入上下文 — 作决策参考，勿当作逐字命令。

### 异步后台索引

策略索引为 **异步** — 蒸馏不阻塞回复：

- 蒸馏先写入 `pending` 单元（尚无向量），立即返回。
- 后台 `MemoryIndexWorker` 批量构建向量与图，完成后标记 `ready`。
- 检索始终可用：`ready` 单元走向量相似度；`pending`/`failed` 单元仍可通过关键词兜底。

可能观察到：
- 刚蒸馏的策略在索引完成前数秒内可能 **仅能关键词检索**。
- 嵌入模型不可用时（未安装 `desktopclaw[memory]` 或模型下载中），检索降级为关键词搜索，对话照常进行。
- 启动时会自动重试上次未完成的 `pending`/`failed` 单元。

### 嵌入模型

默认：`Qwen/Qwen3-Embedding-0.6B`（指令感知，Matryoshka 截断至 512 维）。

- 首次使用会下载到 `memory/.embeddings_model/`。请先安装可选依赖：
  ```bash
  pip install 'desktopclaw[memory]'
  ```
- 修改 `agents.memory.embedding_model` 后，下次启动会一次性重索引全部单元。

关闭策略记忆：在配置中将 `agents.memory.enabled` 设为 `false`。
