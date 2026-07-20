# kagent

## Portfolio / Resume

KAgent can be presented as a local desktop Coding Agent and test-development automation assistant. Resume-ready project notes are available at [docs/resume-project.md](docs/resume-project.md).

## Current Update: Run Review Expansion

- Added `kagent/agent/run_review.py` as the first structured run-review analysis layer.
- `build_run_review(run_log_path)` now aggregates run status, workspace, task, changed paths, validation state, failed tools, model request/error metadata, symbol impacts, project-rule health, risk flags, and recommended next steps.
- `build_quality_gate(review)` now turns the same review payload into a pass/warn/fail gate with explicit checks.
- `format_run_review_markdown(review)` now formats the structured review into a compact Markdown report for future UI, bug-report, regression-plan, and quality-gate features.
- `format_quality_gate_markdown(review)` now renders the gate result as a compact Markdown panel.
- `format_bug_report_markdown(review)` now turns the same review payload into a compact bug report with title, reproduction steps, actual result, expected result, suspected cause, and validation evidence.
- `format_regression_plan_markdown(review)` now turns the same review payload into a regression-test plan with scope, risk focus, related tests, commands, and manual checks.
- Final trust checks now include a `quality_gate` result so final answers are prompted to disclose the gate status.
- Run log summaries now show the stored `quality_gate` status and summary from `final_trust`.
- Resume context now reads `quality_gate` checks and can prioritize recovery from gate failures or warnings.
- Self-improvement suggestions now treat recent quality-gate failures and warnings as dedicated improvement signals.
- Run history can now be filtered by `quality_gate_status`, and resume-history UI rows show `gate:fail` or `gate:warn` when relevant.
- Added focused tests for clean runs, validation/model/tool/rule risks, symbol-impact extraction, and unfinished logs.
- Run Debug now includes `Review`, `Quality Gate`, `Bug Report`, and `Regression Plan` actions that open structured run-review outputs from the same run log.
- The review views reuse the same run log source as summary and timeline, so the run review stays tied to the live debug surface.
- Run Debug now includes a `Resume Task` action.
- The action builds resume context from the selected run log and submits it to the Agent as the next turn.
- The chat header now includes a resume-history picker for recent failed, stopped, unverified, or validation-failed runs.
- Resume-history preview now includes related rollback diff context when available.
- Resume-history recovery now lets users edit or copy the generated resume prompt before submission.
- Diff, Resume, and History header actions now include clearer role tooltips so they do not feel like duplicate entry points.
- The chat header now uses one `Activity` entry that opens a shared panel for current diff review, resumable runs, and rollback history.
- The Activity panel now shows status summaries for current changed paths, resumable runs, and rollback records before opening details.
- The Activity panel now lists the most recent resumable runs directly under the resume summary.
- The Activity panel now lists recent current-diff paths directly under the diff summary.
- The Activity panel now has an explicit `Back` button for returning to the main chat view.
- Activity child panels now include `Back to Activity` navigation for diff review, resume history, and rollback history.
- Agent now has a read-only `suggest_self_improvements` tool that proposes small coding-agent improvement tasks from project structure and run history.
- The chat input now supports slash commands: type `/` to open command suggestions, including `/self` for self-improvement suggestions.
- Slash commands now include `/model ...` entries for switching the active chat and coding Agent model.
- Slash commands now include `/reasoning ...` entries for switching reasoning effort: Low, Medium, High, and Extra high.
- The selected model and reasoning effort are persisted locally and restored when the app starts again.
- Chat and coding Agent requests now inject runtime metadata so the assistant can answer the current model and reasoning effort from the actual request settings.
- Coding Agent run logs now record model request, response, error, fallback, duration, model, and reasoning metadata for easier debugging.
- Agent validation plans now prioritize syntax checks, related tests inferred from changed files, then full project validation, with selection reasons recorded in run logs.
- Edit change plans now include intent, target summary, risk summary, and validation hints before mutation tools run.
- Agent now has `find_symbol_context` for reading focused source excerpts around known symbols before editing.
- Agent now has `find_symbol_references` for finding imports, calls, references, and test usage before changing a symbol.
- Agent now has `symbol_change_plan` for summarizing symbol definition, references, related tests, validation commands, and risk before editing.
- Change plans now attach matching symbol impact summaries when a prior `symbol_change_plan` targets the edited file.
- Validation plans now prioritize symbol-impact tests and validation commands before falling back to file-level related tests.
- Final Agent replies and run summaries now include impacted symbol names, definition paths, reference counts, and related tests when available.
- Validation failure recovery now uses symbol impacts to focus repair prompts and read the changed symbol definition when related tests fail.
- Diff review and rollback history now show symbol impacts for rollbackable changes when available.
- Agent now supports project-level `KAGENT.md` rules that are automatically injected into coding runs.
- Agent now has read-only `read_project_rules` and `generate_project_rules` tools for inspecting or drafting project workflow rules.
- Agent now has `check_project_rules` to score `KAGENT.md` health and suggest missing validation, safety, documentation, or workflow rules.
- Agent now automatically injects `KAGENT.md` health warnings into coding runs when project rules are missing or incomplete.
- Run log summaries and timelines now show `KAGENT.md` rule health, score, and top missing-rule issues.
- Run Debug and the live Agent trace card now surface `KAGENT.md` rule health without opening raw log files.
- The desktop window now uses a frameless custom title bar with drag, double-click maximize, window controls, and a resize grip.
- Windows launch scripts prefer the project `.venv` instead of a hardcoded local Python path.
- UI option labels, dialogs, tool cards, rollback actions, diff review, and task resume text now follow the selected app language.
- Each chat session can now target its own workspace/project directory from the UI.
- The sidebar now has a folder-based new chat action that creates a separate chat bound to the selected folder.
- The current project button now sits next to the permission button and shows the selected folder name.
- The current project menu next to permissions can now switch to `No folder`, while the sidebar keeps only normal new chat and folder-based new chat.
- The main UI has been simplified with a calmer dark theme, fewer persistent badges, shorter input hints, and a cleaner empty state.
- The sidebar session list now shows clearer project/no-folder context, current-chat state, and creation time.
- The input action row now separates lightweight permission/project state pills from the primary send action.
- No-folder chats now surface `Normal chat` / no-file-access state in the chat header and mode chip.
- Empty chats now include three quick-start prompts for project inspection, test repair, and project explanation.
- Agent tool activity now uses a more compact timeline-style trace with per-tool status dots.
- Visual styling now uses shared button/menu/dialog/text-view helpers for more consistent cyan desktop UI.
- The separate settings button was merged into the permissions menu, and the status bar now shows permission scope instead of duplicating message count.
- The folder-based new chat action is now labeled `New project chat` with a folder-picker tooltip.
- `Ctrl+K` now opens a command palette for common chat, workspace, diff, history, permission, and resume actions.
- The project menu now shows recent workspace folders from previous sessions.
- Agent runs now surface a compact execution plan panel when plan events are available.
- Empty-state suggestions now use project-map context such as entry/config files when a workspace is selected.

Agent 功能演进记录见：[docs/agent-development.md](docs/agent-development.md)

## 当前核心能力

KAgent 当前阶段重点在代码 Agent 能力，不优先做复杂产品化扩展。

已具备的核心能力：
- 桌面端 PyQt 应用，支持多轮对话、会话持久化和 Markdown 渲染。
- 普通聊天和代码 Agent 都支持流式文本输出；代码 Agent 会聚合完整 tool-call 参数后再执行工具。
- Agent 可以读取项目结构、搜索文件、读取文件、写入文件、应用补丁、运行命令。
- Agent 支持基础风险策略，会对删除、移动、命令执行等操作做风险判断和审批控制。
- Agent 支持更细的命令风险分类，会标记验证命令、依赖变更、Git 写操作、网络命令、删除命令、链式 shell 和重定向等风险。
- Agent 支持上下文管理，会压缩旧消息、保留近期关键对话，并持久化会话摘要。
- Agent 支持自动验证流程，会根据项目类型生成验证计划，优先运行 `scripts/verify.ps1` 或测试命令。
- Agent 支持验证命令学习，会从历史运行日志中学习稳定通过的验证命令，并在后续验证计划和长期项目记忆中优先复用。
- Agent 支持验证失败后的自动修复流程，会根据失败结果继续调整代码并重新验证。
- Agent 支持增强任务拆解，会在运行前生成带目标、候选文件、风险、验证方式和下一步快照的检查清单，并在检查、修改、验证、总结时更新步骤状态。
- Agent 支持长任务恢复，可以基于历史 run log 的计划快照、变更文件、验证结果和失败工具生成继续执行提示。
- Agent 支持测试失败定位，会从 pytest、Python traceback、语法错误中提取失败文件、行号和测试节点。
- Agent 支持失败位置自动聚焦读取，验证失败后会读取相关文件片段，再进入修复流程。
- Agent 支持小范围增量验证，修复后会优先跑失败单测、相关测试文件或 `py_compile`，通过后再跑完整验证。
- Agent 支持代码变更影响分析，会根据修改文件推断相关测试文件，并优先运行相关测试。
- Agent 支持引用级影响分析，会识别 Python import、函数/类符号引用和引用源文件对应测试，让相关测试推断更精准。
- Agent 支持轻量项目文件地图，会分类源码、测试、配置、入口文件，并建立源码到测试的对应关系。
- Agent 支持多语言符号级搜索，Python 使用 AST，JS/TS、Go、Rust、Java 使用轻量语法扫描查找 class、function、method、import、type 等定义位置。
- Agent 支持编辑前变更计划，会在写文件、补丁、删除、移动等操作前记录路径、操作类型、风险和预览摘要。
- Agent 支持 Patch 失败恢复，补丁失败后会读取相关文件上下文，并提示生成更小、更精确的 patch。
- Agent 支持测试失败修复策略分类，会区分断言失败、导入失败、语法错误、缺依赖、超时、命令不存在等。
- Agent 支持工具调用去重和防循环，会识别重复失败工具调用或重复检查，并提示模型换策略。
- Agent 支持增强回滚能力，可以预览本会话可回滚改动、按指定路径预览回滚 diff，并选择性回滚单个或多个文件。
- Agent 支持代码 Agent 流式输出，模型文本 delta 会更早展示，工具调用参数会在流结束后安全聚合再执行。
- Agent 会写入 JSONL 运行日志，记录运行开始、阶段变化、工具调用、工具结果和运行结束。
- Agent 支持运行日志查看器，可以按 `run_id` 或最新日志生成运行摘要和事件时间线，方便复盘失败工具、验证结果和变更路径。
- Agent 支持历史运行搜索和导出，可以按状态、健康度、验证失败、未验证变更、失败工具筛选多次运行，并导出单次运行 Markdown 复盘报告。
- Agent 支持运行自检报告，可以基于日志判断本次运行是否可信，并标记未完成、未验证变更、验证失败、失败工具和循环风险。
- Agent 支持最终回复可信度接入，最终回答会根据自检结果明确提示未验证变更、验证失败、失败工具或循环风险。
- UI 支持运行调试入口，可以在 Agent 执行日志卡片中查看本次运行日志摘要、自检结果和事件时间线。
- UI 支持恢复运行历史选择器，可以列出最近需要关注的运行并预览恢复上下文后继续任务。
- UI 支持恢复前差异联动，恢复历史预览会在可用时展示相关 rollback diff。
- UI 支持恢复提示编辑和复制，提交恢复任务前可以调整最终发给 Agent 的提示。
- UI 支持当前会话 Diff Review，可以直接查看本轮 active rollback 记录汇总出的文件列表和 diff 预览。
- UI 对 Diff、Resume、History 三个入口增加职责提示：Diff 用于审查当前改动，Resume 用于继续历史任务，History 用于逐条查看和恢复 rollback 版本。
- UI 已把 Diff、Resume、History 收敛到统一 Activity 面板入口，顶部不再展示三个并列恢复类按钮。
- UI 的 Activity 面板会直接展示当前差异文件数、需要恢复的运行数和 rollback 记录数，让入口从按钮集合升级为状态面板。
- UI 的 Activity 面板会在恢复任务区直接列出最近需要恢复的运行，方便先判断是哪次任务需要继续。
- UI 的 Activity 面板会在当前差异区直接列出最近改动文件，超过限制时显示剩余数量。
- UI 的 Activity 面板新增明确的返回按钮，关闭面板后回到主聊天界面。
- UI 的 Activity 子面板新增返回 Activity 导航，当前差异、恢复历史和 rollback 历史都可以回到活动面板。
- Agent 支持只读自优化建议工具 `suggest_self_improvements`，会基于项目结构、测试映射、长文件、TODO 和历史运行状态生成低风险优化候选。
- 聊天输入框支持 `/` 唤醒命令面板，可以用 `/self` 快速填入自优化建议提示。
- 聊天输入框支持 `/model` 模型切换命令，当前已内置 GPT-5.5、GPT-5.4、GPT-5.4-Mini、GPT-5.3-Codex 和 GPT-5.2。
- 聊天输入框支持 `/reasoning` 推理强度切换命令，当前支持低、中、高、超高四档，并会作用于普通聊天、标题生成和代码 Agent 请求。
- `/model` 和 `/reasoning` 的选择会保存到本地状态文件，应用下次启动会自动恢复上次选择。
- 普通聊天和代码 Agent 请求会注入当前运行时模型和推理强度元信息，因此询问“当前用的是什么模型”时会优先按实际请求设置回答。
- 代码 Agent 运行日志会记录模型请求、响应、错误、降级重试、耗时、模型和推理强度，方便排查“实际用了哪个模型”和“为什么失败”。
- Agent 验证计划会优先按“语法检查 -> 相关测试 -> 完整验证”的顺序执行，并把相关测试选择原因写入运行日志。
- Agent 在执行写入、补丁、删除、回滚等变更工具前，会记录更完整的编辑计划，包括修改意图、目标文件、风险摘要和验证建议。
- Agent 支持 `find_symbol_context`，可以按函数、类、方法、import 等符号名读取精准代码片段，减少盲目全文搜索和整文件读取。
- Agent 支持 `find_symbol_references`，可以在修改函数或类之前查找 import、调用、普通引用和测试引用，帮助判断影响范围。
- Agent 支持 `symbol_change_plan`，可以在修改符号前汇总定义位置、引用位置、相关测试、建议验证命令和风险摘要。
- Agent 会压缩喂给模型的工具输出，避免大文件、大目录和长命令输出撑爆上下文。
- Agent 支持长期项目记忆，会按工作区保存项目结构摘要、入口文件、配置文件、常用验证命令和稳定偏好，下次运行自动注入上下文。
- Agent 会给工具失败结果附带恢复建议，例如路径不存在、参数错误、缺依赖、命令超时、代码错误等。
- 项目已加入测试入口 `run-tests.bat`，当前覆盖上下文、长期项目记忆、风险策略、命令风险分类、验证计划、验证命令学习、运行日志、运行日志查看器、历史运行搜索导出、运行自检、最终回复可信度、UI 运行调试入口、Agent 流式聚合、工具展示、工具输出压缩、错误恢复、增强任务拆解、长任务恢复、失败定位、失败聚焦读取、增量验证、文件级影响分析、引用级影响分析、项目地图、多语言符号搜索、变更计划、Patch 失败恢复、修复策略、防循环和增强回滚。

## 常用开发命令

```powershell
.\run-tests.bat
```

自优化建议：

```text
/self
```

在聊天框输入 `/` 会打开命令建议，选择 `/self` 会自动填入：

```text
请调用 suggest_self_improvements，列出 5 个当前项目最值得做的代码能力优化建议。
```

这个工具只生成建议，不会自动修改文件。建议确认后，再让 Agent 选择其中一个小任务执行。

项目规则：

```text
KAGENT.md
```

代码 Agent 运行时会自动读取工作区根目录的 `KAGENT.md`，并把其中的编码规范、验证命令、安全要求和工作流偏好注入到模型上下文。Agent 也会在规则缺失或不完整时自动注入轻量健康提醒，但不会擅自修改规则文件。只读工具 `read_project_rules`、`generate_project_rules` 和 `check_project_rules` 可以检查当前规则、生成规则草稿，或评估规则文件是否缺少验证、安全、文档、工作流要求。

模型切换：

```text
/model
```

当前内置模型：
- `GPT-5.5` -> `gpt-5.5`，实测可用。
- `GPT-5.4` -> `gpt-5.4`，实测可用。
- `GPT-5.4-Mini` -> `gpt-5.4-mini`，实测可用。
- `GPT-5.3-Codex` -> `gpt-5.3-codex`，实测可用。
- `GPT-5.2` -> `gpt-5.2`，当前接口实测返回 400，不支持当前 ChatGPT/Codex 账户路径。

运行内容：
- Python 语法检查。
- pytest 单元测试。

运行日志位置：

```text
.kagent_state/runs/
```

最小化对话智能体桌面版 — PyQt6 单体应用，类似 codex 的本地软件形态。

## 功能

- 桌面 GUI（非网页），原生窗口
- 流式多轮对话（OpenAI Chat Completions）
- Agent 模式（读文件 / 改文件 / 跑命令）
- 多会话管理（侧边栏切换 / 新建 / 自动标题）
- 会话历史持久化（SQLite）
- Markdown 渲染 + 代码高亮
- 后台线程流式（UI 不卡顿）

## 技术栈

- **UI**：PyQt6（QThread 后台流式 + signal 推送主线程）
- **LLM**：OpenAI Python SDK（同步流式）
- **存储**：sqlite3 标准库（无需额外依赖）
- **Markdown**：markdown + pygments

## 快速开始

### 1. 安装依赖

```bash
cd D:/kd/pyproject/kagent
pip install -r requirements.txt
```

### 2. 配置 API

`.env` 已生成（基于 `.env.example`），如需修改 key 或换代理服务，编辑 `.env`：

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://jp-api.zhexueqi.xyz/v1
MODEL=gpt-5.4-mini
DB_PATH=./kagent.db
```

### 3. 启动

```bash
python main.py
```

### 4. 开发热重载

开发时可以用热重载模式，保存 `.py` 或 `.env` 后会自动重启进程：

```bash
python main.py --dev-reload
```

Windows 下也可以直接双击 `run-dev.bat`。

## 项目结构

```
kagent/
├── kagent/
│   ├── __init__.py
│   ├── config.py            # 配置加载
│   ├── db.py                # SQLite 同步访问
│   ├── llm.py               # OpenAI 流式封装
│   ├── agent/               # 本地代码 agent + 工作区工具
│   └── ui/
│       ├── agent_worker.py  # Agent 后台线程
│       ├── chat_worker.py   # QThread 流式 worker
│       ├── main_window.py   # 主窗口 + 侧边栏 + 输入区
│       └── markdown_view.py # Markdown 渲染 + 代码高亮
├── main.py                  # 入口
├── requirements.txt
├── .env.example
└── README.md
```

## 关键设计

### 1. QThread + Signal 流式架构
后台线程阻塞迭代 OpenAI stream，每个 chunk 通过 `pyqtSignal` 投递到主线程更新 UI，避免界面卡顿。

### 2. 单体应用（无 HTTP 服务层）
PyQt6 进程直接调用 OpenAI SDK，省去 FastAPI 中间层。后续若需 Web 端，可独立抽出 API 层。

### 3. 同步 SQLite
PyQt 与 asyncio 集成需要 qasync 等额外库，增加复杂度。改用标准库 `sqlite3` + `threading.Lock`，简洁稳定。

### 4. 本地工具型 Agent
Agent 模式会通过 OpenAI 的工具调用循环，按需读取文件、写入文件、并在工作区里运行命令。  
这让它不仅能聊天，还能真正帮你做代码修改和验证。

### 5. 流式块整页重渲染
每次 chunk 到达时，从 DB 取已完成消息 + 当前流式缓冲，整体重新渲染。代码简单，1000 字以内无明显性能问题。

## 常见问题

**Q: 启动报错 `Connection error`**
A: 检查 `.env` 中 `OPENAI_BASE_URL` 是否正确，末尾需带 `/v1`。

**Q: 模型名报错 `model not found`**
A: 代理服务支持的模型名与官方不同，确认 `MODEL` 与代理方文档一致。

**Q: PyQt6 启动闪退无报错**
A: 在命令行运行 `python main.py`，stderr 会打印堆栈。

## Slash Reasoning Command

推理强度切换：

```text
/reasoning
```

当前支持四档推理强度：
- `低` -> `low`，实测可用。
- `中` -> `medium`，实测可用。
- `高` -> `high`，实测可用。
- `超高` -> `xhigh`，实测可用。

选择后会作用于普通聊天、标题生成和代码 Agent 请求。若当前 API 或某个模型暂时不支持 `reasoning_effort` 参数，kagent 会自动重试不带该参数的请求，优先保证聊天和代码 Agent 不被打断。

## 下一步

- [ ] 长期记忆系统（mem0 风格，跨会话事实抽取）
- [ ] MCP 工具调用（搜索 / 文件 / 代码沙箱）
- [ ] RAG 知识库（文档上传 + 向量检索）
- [ ] 多智能体编排（LangGraph 风格）
- [ ] 系统托盘 + 全局快捷键
