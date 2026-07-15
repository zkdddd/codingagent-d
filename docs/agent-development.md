# Agent Development Log

## 2026-07-15: Activity Recent Resume Runs

### What changed

- Activity panel now shows the most recent resumable runs under the resume summary.
- The list reuses existing resume-history candidate filtering and item labels.
- Empty state text is shown when no recent run needs resume attention.

### Why

The Activity panel already showed how many runs need attention, but users still had to open another dialog to know which runs they were. Showing the recent candidates inline makes the panel useful as a quick recovery dashboard.

### Verification

```text
22 targeted tests passed
```

Full validation:
```text
152 passed
```

## 2026-07-15: Activity Status Summaries

### What changed

- Activity panel now computes and displays the current rollbackable changed-path count.
- Activity panel now shows how many previous runs need resume attention.
- Activity panel now shows how many rollback records are available for the current session.
- Summary failures degrade to an unavailable state instead of blocking the panel.

### Why

The Activity entry was unified, but it still behaved mostly like a menu. This step turns it into a lightweight status panel so users can understand the coding session state before opening deeper detail views.

### Verification

```text
21 targeted tests passed
```

Full validation:
```text
151 passed
```

## 2026-07-15: Unified Activity Panel Entry

### What changed

- Replaced the separate header `Diff`, `Resume`, and `History` buttons with a single `Activity` entry.
- Added an Activity panel that groups current diff review, resumable run history, and rollback history actions.
- Kept the existing diff, resume, and rollback backends instead of creating duplicate data sources.
- Language switching now updates the Activity entry label and tooltip.

### Why

The previous step clarified the roles, but the header still looked like three overlapping recovery buttons. This step makes the product structure match the intent: one activity/recovery panel, three distinct actions inside it.

### Verification

```text
20 targeted tests passed
```

Full validation:
```text
150 passed
```

## 2026-07-15: Activity Entry Role Clarification

### What changed

- Added clearer tooltips for the header `Diff`, `Resume`, and `History` actions.
- Clarified that `Diff` reviews the current session's rollbackable change summary.
- Clarified that `Resume` continues a previous run from run logs with an editable prompt.
- Clarified that `History` inspects individual rollback records and can restore selected versions.

### Why

These three actions reuse related recovery data, but they serve different moments in the coding workflow. The UI now explains the boundary directly instead of making the user guess whether the entries are duplicates.

### Verification

```text
20 targeted tests passed
```

Full validation:
```text
150 passed
```

## 2026-07-15: Editable Resume Prompt

### What changed

- Resume-history picker now shows the final resume prompt in an editable text box.
- `Resume selected run` submits the edited prompt instead of always sending the generated default prompt.
- Added a `Copy prompt` action so users can copy the generated or edited resume prompt before submission.

### Verification

```text
22 targeted tests passed
```

Full validation:
```text
149 passed
```

## 2026-07-15: Resume Preview Diff Context

### What changed

- Resume-history preview now tries to include related rollback diff context.
- The picker first previews rollback states for the resumed run's changed paths.
- If changed-path preview is unavailable, it falls back to the active session rollback preview.
- Missing diff context does not block resume; the resume prompt remains available.

### Verification

```text
25 targeted tests passed
```

Full validation:
```text
148 passed
```

## 2026-07-14: Resume Run History Picker Merge

### What changed

- Pulled remote UI navigation updates from GitHub and kept the local resume-history picker work.
- The `Resume` action lists recent runs that need attention: stopped, failed, warn/fail health, unverified changes, validation failures, or failed tools.
- Selecting a run builds a `task_resume` context and previews it before submitting the generated resume prompt as the next Agent turn.

### Verification

```text
147 passed
```

## 2026-07-13: Command Palette, Recent Workspaces, And Plan UI

### What changed

- Added a `Ctrl+K` command palette for common actions: new chat, new project chat, switch project, no-folder mode, diff review, rollback history, permissions, and resume latest task.
- Added recent workspace entries to the current project menu using existing session workspace history.
- Added an Agent Plan panel that renders existing `agent_plan` stream events as compact status lines.
- Updated empty-state suggestions to use project-map context, including entry/config files when available.
- Added small design tokens for shared radius values and continued moving UI styling toward reusable helpers.

### Why

- Command palettes and recent workspaces reduce button hunting and repeated folder picking.
- A visible plan panel makes the coding agent feel more intentional than raw tool logs alone.
- Project-aware suggestions make the first screen more useful when a workspace is selected.

### Impacted modules

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### Verification

```text
.\run-tests.bat
```

## 2026-07-13: UI Consistency And Entry Simplification

### What changed

- Added shared style helpers for secondary/primary/pill/danger buttons, menus, dialogs, and text views.
- Merged the separate settings button into the permissions menu to reduce duplicate entry points.
- Changed the bottom status bar from message count to read/write/command permission scope.
- Shortened the folder-based sidebar action to `New project chat` and kept the folder picker explanation in the tooltip.
- Updated Run Debug, Diff Review, and permission settings dialogs with consistent spacing, title styling, and surface colors.

### Why

- The previous UI mixed older purple styles, repeated metadata, and exposed both settings and permissions as separate concepts.
- A coding-agent UI needs clearer hierarchy: one permissions entry, one primary send action, useful status-bar metadata, and consistent modal surfaces.

### Impacted modules

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### Verification

```text
.\run-tests.bat
```

## 2026-07-13: Product-Level UI Priority Pass

### What changed

- Added quick-start prompt buttons to the empty chat state: project inspection, test repair, and project explanation.
- Added a current-session dot marker to sidebar rows while keeping project/no-folder context and time metadata.
- Kept permission/project controls as lightweight input-row capsules and the send button as the primary action.
- Kept no-folder sessions explicit as normal chat with no file access.
- Changed Agent tool activity toward a compact timeline trace with status dots instead of large standalone cards.

### Why

- These changes align the desktop UI more closely with mature coding-agent products: faster first action, clearer workspace state, and less visual noise during tool execution.

### Impacted modules

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### Verification

```text
.\run-tests.bat
```

## 2026-07-13: UI Session And No-Folder Clarity

### What changed

- Sidebar session rows now show the chat title plus project/no-folder context, creation time, and current-chat marker.
- The input action row now treats permissions and current project as lightweight status pills, keeping Send as the primary action.
- No-folder chats now show `Normal chat` and `No file access` in the header/mode chip so users know the coding workspace tools are not active.
- README was updated to reflect the UI interaction changes.

### Why

- The previous UI had the right functions, but the visual hierarchy still made project state and action priority easy to miss.
- Coding-agent products need very clear workspace state because no-folder chat and project-bound agent sessions have different capabilities.

### Impacted modules

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### Verification

```text
.\run-tests.bat
```

这个文档用来记录 KAgent 的代码 Agent 能力是怎样一步步发展出来的。

记录原则：
- 每次新增功能或优化能力，都要写一条记录。
- 每条记录说明“做了什么、为什么做、影响哪些模块、怎么验证、下一步是什么”。
- 优先记录代码能力、上下文能力、工具能力、验证能力和稳定性能力。

## 当前阶段目标

当前阶段先把代码 Agent 的核心功能做好，不优先扩展产品化 UI、混合模型策略或复杂生态能力。

重点方向：
- 让 Agent 能稳定理解项目结构。
- 让 Agent 能安全读写文件、运行命令并验证结果。
- 让 Agent 的上下文不容易爆掉。
- 让 Agent 失败后能自己判断原因并恢复。
- 让每一次运行都能被追踪和复盘。

## 2026-07-09: 上下文管理

### 做了什么

新增上下文管理模块，用来控制发给模型的历史消息长度。

主要能力：
- 估算消息 token 数。
- 保留最近关键对话。
- 将较早上下文压缩成摘要。
- 限制单条消息最大字符数。
- 支持会话级持久化摘要。

### 为什么做

之前上下文容易越积越大，导致压缩失败、请求失败或模型注意力被旧内容干扰。

这个阶段先保证 Agent 长时间工作时不会被历史消息拖垮。

### 影响模块

- `kagent/context.py`
- `kagent/db.py`
- `kagent/llm.py`
- `kagent/ui/agent_worker.py`
- `kagent/agent/code_agent.py`

### 验证

新增 `tests/test_context.py`，验证旧消息会被压缩，最近消息会保留。

## 2026-07-09: Agent 状态机

### 做了什么

给代码 Agent 增加运行阶段状态。

主要阶段：
- `starting`
- `inspecting`
- `planning`
- `editing`
- `validating`
- `repairing`
- `finalizing`
- `stopped`

### 为什么做

之前 Agent 在做什么不够清楚。状态机可以让 UI、日志和后续调试都知道 Agent 当前处于哪个阶段。

### 影响模块

- `kagent/agent/code_agent.py`

### 验证

通过现有 Agent 流程测试和完整测试脚本验证状态切换不破坏主流程。

## 2026-07-09: Agent 模块拆分

### 做了什么

把原本过大的 `code_agent.py` 拆成多个职责更清晰的模块。

拆分模块：
- `kagent/agent/tool_schema.py`
- `kagent/agent/risk_policy.py`
- `kagent/agent/validation.py`
- `kagent/agent/tool_view.py`
- `kagent/agent/run_log.py`

### 为什么做

`code_agent.py` 承担了太多职责，后续继续加能力会越来越难维护。

模块拆分后，每块能力可以独立测试、独立演进。

### 验证

新增多组单元测试：
- `tests/test_risk_policy.py`
- `tests/test_validation.py`
- `tests/test_run_log.py`

## 2026-07-09: 自动验证流程

### 做了什么

新增自动验证计划和执行流程。

主要能力：
- 根据项目类型和变更文件生成验证计划。
- Python 项目优先做语法检查。
- 如果存在 `scripts/verify.ps1`，优先运行项目统一验证脚本。
- 支持 pytest 验证。
- 验证失败后进入 repair 流程，最多自动修复多轮。

### 为什么做

代码 Agent 不能只改文件，还要尽量确认改动没有破坏项目。

验证流程是代码能力的核心闭环：改动 -> 验证 -> 失败修复 -> 再验证 -> 最终答复。

### 影响模块

- `kagent/agent/validation.py`
- `kagent/agent/code_agent.py`
- `scripts/verify.ps1`
- `run-tests.bat`

### 验证

新增 `tests/test_validation.py`。

运行结果曾达到：

```text
14 passed
```

## 2026-07-09: 运行日志

### 做了什么

新增 JSONL 运行日志。

主要能力：
- 每次 Agent 运行生成独立 `run_id`。
- 记录 `run_start`、`agent_status`、`tool_start`、`tool_result`、`run_finish` 等事件。
- 日志保存到 `.kagent_state/runs/`。
- `agent_start` 事件包含 `run_id` 和 `run_log_path`。
- 新增日志读取和摘要能力。

### 为什么做

Agent 一旦失败、卡住或行为异常，需要能复盘它每一步做了什么。

只写日志还不够，还要能读回来并生成摘要。

### 影响模块

- `kagent/agent/run_log.py`
- `kagent/agent/code_agent.py`

### 验证

新增 `tests/test_run_log.py`。

覆盖：
- JSONL 写入。
- 日志读取。
- 日志摘要。
- 最新日志选择。
- 坏 JSON 报错。

## 2026-07-09: 工具展示优化

### 做了什么

优化工具调用报告展示。

主要能力：
- 工具报告展示输入、预览、结果。
- 修复部分历史乱码标题，让报告更容易看懂。

### 为什么做

工具调用是 Agent 行为的核心证据，展示不清楚会影响调试和信任感。

### 影响模块

- `kagent/agent/tool_view.py`
- `kagent/agent/code_agent.py`

### 验证

新增 `tests/test_tool_view.py`。

## 2026-07-09: 工具输出压缩

### 做了什么

新增工具结果上下文压缩模块。

主要能力：
- UI 和日志保留完整工具结果。
- 发送给模型的工具结果使用压缩版。
- `read_file` 大内容保留头尾。
- `search_file` 限制匹配数量。
- `list_files` 限制文件条目数量。
- `run_command` 保留退出码、摘要、头尾输出，并提取关键错误行。

### 为什么做

工具输出很容易撑爆上下文，尤其是大文件、大目录、测试输出和错误堆栈。

压缩工具结果可以显著降低上下文压力，同时保留模型继续推理需要的关键信息。

### 影响模块

- `kagent/agent/tool_result_context.py`
- `kagent/agent/code_agent.py`

### 验证

新增 `tests/test_tool_result_context.py`。

运行结果达到：

```text
24 passed
```

## 2026-07-09: 工具失败恢复提示

### 做了什么

新增工具失败分类和恢复建议。

主要分类：
- `invalid_arguments`
- `missing_required_argument`
- `path_not_found`
- `permission_scope`
- `expected_file`
- `expected_directory`
- `non_text_file`
- `timeout`
- `missing_dependency`
- `command_not_found`
- `code_error`
- `validation_failed`
- `user_rejected`

失败工具结果会在给模型的上下文中附带 `recovery` 字段。

### 为什么做

Agent 工具调用失败后，不能只是看到一坨错误文本。它需要知道下一步应该怎么恢复。

例如：
- 路径不存在时，先搜索或列目录。
- 命令缺依赖时，不要盲目重试。
- 代码语法错误时，打开对应文件修复再验证。
- 用户拒绝高风险操作时，不要自动重复执行。

### 影响模块

- `kagent/agent/tool_recovery.py`
- `kagent/agent/tool_result_context.py`

### 验证

新增 `tests/test_tool_recovery.py`。

运行结果达到：

```text
31 passed
```

## 2026-07-09: 任务规划和检查清单

### 做了什么

新增轻量任务规划模块。

主要能力：
- Agent 运行前生成执行检查清单。
- 检查清单会根据任务类型包含不同步骤。
- 代码任务通常包含理解任务、检查上下文、修改文件、验证改动、总结结果。
- 普通回答任务只保留理解任务和最终回答。
- 每个步骤支持 `pending`、`active`、`done`、`skipped`、`failed` 状态。
- 工具调用、自动验证、修复流程和最终回答会更新对应步骤状态。
- 计划状态会写入 `agent_plan` 日志事件。
- 最终回答提示会带上计划状态，帮助模型基于实际执行过程总结。

### 为什么做

之前 Agent 已经有上下文、工具、验证、日志和错误恢复，但还缺一个执行中枢。

任务规划可以让 Agent 在动手前先明确路径，执行中减少乱调用工具、重复调用工具和漏验证。

### 影响模块

- `kagent/agent/task_plan.py`
- `kagent/agent/code_agent.py`
- `README.md`

### 验证

新增 `tests/test_task_plan.py`。

运行结果达到：

```text
35 passed
```

## 2026-07-09: 测试失败定位能力

### 做了什么

新增失败诊断解析模块。

主要能力：
- 从 `run_command` 的 stdout、stderr、summary、error 中提取失败位置。
- 支持 Python traceback 的 `File "...", line ...`。
- 支持 `SyntaxError` 附近的文件和行号。
- 支持 pytest 的 `FAILED tests/test_x.py::test_name` 节点。
- 支持通用 `file.py:line` 格式。
- 压缩后的命令结果会带上 `diagnostics` 字段。
- 验证失败摘要会追加 `Failure locations`，帮助 repair prompt 聚焦失败位置。

### 为什么做

之前 Agent 能看到验证失败，但需要自己从长输出里猜哪里坏了。

失败定位能力可以让 Agent 更快找到要读的文件、要看的行号和失败测试名，减少盲目搜索和重复运行全量测试。

### 影响模块

- `kagent/agent/failure_diagnostics.py`
- `kagent/agent/tool_result_context.py`
- `kagent/agent/validation.py`
- `README.md`

### 验证

新增 `tests/test_failure_diagnostics.py`。

扩展测试：
- `tests/test_tool_result_context.py`
- `tests/test_validation.py`

运行结果达到：

```text
41 passed
```

## 2026-07-09: 失败位置自动聚焦读取

### 做了什么

新增失败聚焦读取模块。

主要能力：
- 根据 `diagnostics` 生成具体 `read_file` 目标。
- 对 traceback、语法错误、`file.py:line` 读取失败行附近上下文。
- 对 pytest nodeid 自动读取对应测试文件。
- 自动验证失败后，会先读取最多 3 个失败位置片段。
- 聚焦读取结果会进入模型上下文和工具报告。
- 聚焦目标会写入 `failure_focus` 日志事件。
- 读取完成后再进入 repair 流程，让模型基于失败位置附近代码修复。

### 为什么做

之前 Agent 已经能知道失败位置，但还需要下一轮模型主动决定读取哪里。

自动聚焦读取把“知道哪里坏了”推进到“已经把坏的位置附近代码拿到手”，可以减少盲目搜索和重复工具调用。

### 影响模块

- `kagent/agent/failure_focus.py`
- `kagent/agent/code_agent.py`
- `README.md`

### 验证

新增 `tests/test_failure_focus.py`。

运行结果达到：

```text
45 passed
```

## 2026-07-09: 小范围验证和增量验证

### 做了什么

新增 focused validation 命令生成和执行流程。

主要能力：
- 验证失败后，根据 `diagnostics` 生成小范围验证命令。
- pytest nodeid 会生成单个测试命令。
- 测试文件失败会生成对应测试文件命令。
- 普通 Python 源文件失败会生成 `py_compile` 命令。
- 修复后先运行 focused validation。
- focused validation 通过后不会直接结束，而是继续运行完整验证计划。
- 完整验证通过后清空 focused validation 状态。

### 为什么做

之前每次修复后都会直接回到完整验证计划。对大项目来说，这会让迭代速度变慢。

增量验证让 Agent 先确认刚才失败的位置是否修好，再做完整验证，能更快反馈修复是否有效，同时保留最终完整验证的安全性。

### 影响模块

- `kagent/agent/validation.py`
- `kagent/agent/code_agent.py`
- `README.md`

### 验证

扩展 `tests/test_validation.py`。

运行结果达到：

```text
48 passed
```

## 2026-07-09: 代码变更影响分析

### 做了什么

新增影响分析模块。

主要能力：
- 根据变更文件推断相关测试文件。
- 支持常见 Python 测试命名约定，例如 `context.py` -> `tests/test_context.py`。
- 支持嵌套模块路径，例如 `kagent/agent/validation.py` -> `tests/agent/test_validation.py`。
- 如果变更文件本身就是测试文件，会直接把该测试文件作为相关测试。
- Python 验证计划会把相关测试插入到语法检查之后、完整 pytest 或项目验证之前。
- 默认验证计划命令数从 2 提升到 3，以容纳“语法检查 + 相关测试 + 完整验证”。

### 为什么做

之前增量验证主要依赖失败诊断。对于尚未失败的普通改动，Agent 仍然只能直接跑完整验证。

影响分析让 Agent 能在改动后先运行最可能受影响的测试文件，尽早发现局部问题，再进入完整验证。

### 影响模块

- `kagent/agent/impact_analysis.py`
- `kagent/agent/validation.py`
- `README.md`

### 验证

新增 `tests/test_impact_analysis.py`。

扩展 `tests/test_validation.py`。

运行结果达到：

```text
52 passed
```

## 2026-07-09: 项目索引和文件地图

### 做了什么

新增轻量项目地图模块。

主要能力：
- 扫描项目文件并跳过 `.git`、虚拟环境、`node_modules`、构建目录等无关目录。
- 分类源码文件、测试文件、配置文件和入口文件。
- 建立源码文件到测试文件的命名映射。
- 支持常见 Python 测试命名约定。
- 提供项目地图摘要，包含源码数量、测试数量、配置文件、入口文件、已映射源码数量。
- 影响分析模块开始复用项目地图。
- 如果变更文件尚未在文件地图中出现，影响分析仍会用命名约定做兜底推断。

### 为什么做

之前影响分析内部自己维护文件命名规则。随着后续符号搜索、验证计划、测试选择能力增强，这类项目结构信息需要统一来源。

项目地图是后续能力的底座：搜索、测试选择、影响分析、入口识别、项目理解都可以复用它。

### 影响模块

- `kagent/agent/project_map.py`
- `kagent/agent/impact_analysis.py`
- `README.md`

### 验证

新增 `tests/test_project_map.py`。

扩展影响分析测试。

运行结果达到：

```text
55 passed
```

## 2026-07-09: 符号级搜索能力

### 做了什么

新增 Python 符号索引模块，并暴露为 Agent 工具。

主要能力：
- 使用 Python AST 解析源码文件。
- 提取 class、function、method、import。
- 支持按符号名精确查找。
- 支持按符号名模糊查找。
- 支持按符号类型过滤。
- 返回符号所在文件、起始行、结束行、容器和导入模块。
- 新增 `find_symbol` 工具，Agent 可以直接按符号定位代码。
- 工具结果会被压缩，避免大量符号结果撑爆上下文。

### 为什么做

之前 Agent 定位代码主要依赖全文搜索和读取文件。对于函数、类、方法这类结构化目标，全文搜索噪声较多。

符号级搜索让 Agent 能更快找到定义位置，减少盲目搜索，也为后续引用分析和影响范围分析打基础。

### 影响模块

- `kagent/agent/symbol_index.py`
- `kagent/agent/tool_schema.py`
- `kagent/agent/code_agent.py`
- `kagent/agent/tool_result_context.py`
- `README.md`

### 验证

新增 `tests/test_symbol_index.py`。

扩展 `tests/test_tool_result_context.py`。

运行结果达到：

```text
59 passed
```

## 2026-07-09: 编辑前 diff 规划能力

### 做了什么

新增变更计划模块。

主要能力：
- 对写文件、应用补丁、重命名、复制、删除、创建目录、回滚等变更工具生成结构化计划。
- 计划包含工具名、操作类型、涉及路径、路径数量、风险级别、是否破坏性、是否需要审批。
- 如果存在 diff 或预览，会记录预览摘要。
- 工具执行前会发出 `change_plan` 日志事件。
- 工具报告中新增“变更计划”区块。
- 工具结果压缩后仍会保留 `change_plan`，让模型上下文能看到执行前计划。

### 为什么做

之前工具已经有 preview，但 preview 主要是文本，不方便日志分析和后续审批。

结构化变更计划可以让 Agent 在执行改动前明确“要改什么、风险是什么、会影响哪些路径”，后续可以用于审批、回滚说明、提交摘要和安全策略。

### 影响模块

- `kagent/agent/change_plan.py`
- `kagent/agent/code_agent.py`
- `kagent/agent/tool_view.py`
- `kagent/agent/tool_result_context.py`
- `README.md`

### 验证

新增 `tests/test_change_plan.py`。

扩展测试：
- `tests/test_tool_view.py`
- `tests/test_tool_result_context.py`

运行结果达到：

```text
64 passed
```

## 2026-07-09: Patch 失败恢复能力

### 做了什么

新增 Patch 失败恢复模块。

主要能力：
- 当 `apply_patch` 失败时，识别为 `patch_failed`。
- 从 `change_plan` 和错误文本中提取相关文件路径。
- 自动读取相关文件当前上下文。
- 生成恢复提示，要求下一轮使用当前真实上下文生成更小、更精确的 patch。
- 写入 `patch_recovery` 日志事件。
- 恢复建议会进入工具结果压缩上下文。

### 为什么做

补丁失败是代码 Agent 常见问题。失败后如果只把错误文本给模型，模型很容易重复生成同样无法应用的 patch。

自动读取当前文件上下文后，模型能基于真实内容重新生成更小 patch，成功率更高。

### 影响模块

- `kagent/agent/patch_recovery.py`
- `kagent/agent/tool_recovery.py`
- `kagent/agent/code_agent.py`
- `README.md`

### 验证

新增 `tests/test_patch_recovery.py`。

扩展 `tests/test_tool_recovery.py`。

运行结果达到：

```text
68 passed
```

## 2026-07-09: 测试失败修复策略升级

### 做了什么

新增修复策略分类模块。

主要能力：
- 将命令和验证失败进一步分类。
- 支持识别缺依赖、命令不存在、超时、语法错误、导入错误、断言失败、运行时错误、普通测试失败。
- `tool_recovery` 复用统一分类策略。
- `validation_failure_prompt` 会附带 failure category 和 repair strategy。
- 模型在修复时能收到更具体的策略，而不是泛泛地“检查失败并修复”。

### 为什么做

不同失败类型需要不同修复方式。

例如断言失败应该比较 expected vs actual，导入失败应该检查模块路径和循环导入，语法错误应该先打开具体行并运行 `py_compile`。

更细的修复策略能减少盲目重试，提升自动修复质量。

### 影响模块

- `kagent/agent/repair_strategy.py`
- `kagent/agent/tool_recovery.py`
- `kagent/agent/validation.py`
- `README.md`

### 验证

新增 `tests/test_repair_strategy.py`。

扩展测试：
- `tests/test_tool_recovery.py`
- `tests/test_tool_result_context.py`
- `tests/test_validation.py`

运行结果达到：

```text
74 passed
```

## 2026-07-09: 工具调用去重和防循环

### 做了什么

新增工具循环检测模块。

主要能力：
- 为工具调用生成稳定签名。
- 记录最近工具调用历史。
- 识别重复失败的同一工具调用。
- 识别重复读取、搜索、符号查找、文件列表等检查动作。
- 触发循环风险时写入 `tool_loop_warning` 日志事件。
- 向模型上下文追加提示，要求不要原样重试，要换策略或换参数。

### 为什么做

Agent 在复杂任务里容易卡在同一个失败命令、同一个补丁或重复读取同一文件上。

防循环能力可以及时打断重复动作，让模型改变策略，比如读取不同上下文、缩小命令范围、换 patch 方式。

### 影响模块

- `kagent/agent/tool_loop_guard.py`
- `kagent/agent/code_agent.py`
- `README.md`

### 验证

新增 `tests/test_tool_loop_guard.py`。

运行结果达到：

```text
78 passed
```

## 2026-07-09: 运行日志查看器

### 做了什么

新增运行日志查看器模块。

主要能力：
- 根据 `run_id` 在 `.kagent_state/runs/` 中查找对应 JSONL 日志。
- 读取运行日志并生成事件时间线。
- 生成人类可读的运行摘要。
- 摘要中展示 run id、状态、工作区、开始/结束时间、事件数量和最后阶段。
- 汇总工具调用次数、失败工具、验证结果、变更路径。
- 汇总防循环警告、Patch 恢复和失败聚焦读取等调试信号。
- 支持读取最新一条运行日志并生成摘要，方便后续接入 UI 或调试命令。

### 为什么做

前面已经让 Agent 写入 JSONL 运行日志，但原始 JSONL 更适合机器读，不适合人快速复盘。

运行日志查看器把日志变成“可读的运行报告”，后续可以用来排查 Agent 为什么失败、卡在哪里、是否验证过、改了哪些文件，也能作为 UI 里的运行详情面板基础。

### 影响模块

- `kagent/agent/run_log_viewer.py`
- `tests/test_run_log_viewer.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 `tests/test_run_log_viewer.py`。

覆盖内容：
- 按 `run_id` 查找日志。
- 生成事件时间线。
- 摘要展示失败工具、验证结果、变更路径和调试信号。
- 最新日志为空时返回 `None`。
- 查找时跳过损坏的 JSONL 文件。

运行结果达到：

```text
83 passed
```

## 2026-07-09: Agent 自检报告

### 做了什么

新增 Agent 运行自检模块。

主要能力：
- 基于 JSONL 运行日志分析本次 Agent 运行健康度。
- 输出 `pass`、`warn`、`fail` 三档健康状态。
- 判断本次运行是否可信。
- 标记运行未结束、非正常完成、代码变更未验证、验证失败。
- 汇总失败工具调用和循环风险。
- 统计 Patch 恢复和失败聚焦读取次数，方便复盘 Agent 是否经历过恢复流程。
- 支持分析最新运行日志或根据 `run_id` 分析指定运行。
- 生成可读的自检报告，后续可接入最终回复或调试面板。

### 为什么做

运行日志查看器解决了“人能看懂日志”的问题，但还没有明确告诉用户“这次 Agent 执行能不能信”。

自检报告把日志里的关键信号转成健康度判断，尤其关注代码 Agent 最重要的几个风险：任务没跑完、改了文件但没验证、验证仍失败、工具反复失败或出现循环。

这一步能让后续最终回复更诚实，也能为 UI 里的运行详情、历史复盘和自动调试打基础。

### 影响模块

- `kagent/agent/run_self_check.py`
- `tests/test_run_self_check.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 `tests/test_run_self_check.py`。

覆盖内容：
- 干净完成的运行返回 `pass`。
- 代码变更未验证返回 `fail`。
- 验证失败、失败工具和循环风险会被识别。
- 已恢复的工具失败返回 `warn`。
- 未结束或被中止的运行返回 `fail`。
- 支持分析最新日志和按 `run_id` 分析。

运行结果达到：

```text
89 passed
```

## 2026-07-10: 回滚能力增强

### 做了什么

增强工作区回滚能力。

主要能力：
- 新增本会话可回滚改动预览，可以汇总当前 active rollback 记录涉及的路径。
- 新增按路径回滚预览，可以只查看某些文件回滚后会变成什么样。
- 新增选择性回滚能力，可以只回滚指定文件或多个文件。
- `rollback_paths` 支持可选 `rollback_id`，既可以从最新匹配记录回滚，也可以限定在某条历史记录中回滚。
- 对多文件 rollback 记录做部分回滚时，会保留未回滚路径的剩余 rollback 记录。
- 选择性回滚本身也会生成 undo rollback 记录，避免回滚操作不可撤销。
- 新增 Agent 工具：`preview_rollback_session`、`preview_rollback_paths`、`rollback_paths`。
- 工具展示、风险策略、变更计划和 Agent 工具分组都已接入新回滚能力。

### 为什么做

之前已经有 rollback 基础，但主要是“回滚最后一次”或“回滚指定记录”，对于一次会话中改了多个文件的情况还不够细。

代码 Agent 的安全感不只来自“能撤销”，还来自“撤销前能看清楚会撤什么”以及“只撤错的那一部分”。选择性回滚可以减少误伤，让 Agent 在复杂任务里更敢于迭代，也让用户更容易复盘和控制改动范围。

### 影响模块

- `kagent/agent/workspace.py`
- `kagent/agent/tool_schema.py`
- `kagent/agent/tool_view.py`
- `kagent/agent/risk_policy.py`
- `kagent/agent/change_plan.py`
- `kagent/agent/code_agent.py`
- `tests/test_workspace_rollback.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 `tests/test_workspace_rollback.py`。

覆盖内容：
- 本会话回滚预览能列出 active rollback 路径。
- `rollback_paths` 只回滚指定文件，不误动其他文件。
- 多文件 rollback 记录可以只回滚其中一个文件，并保留剩余路径的 rollback 记录。
- 指定不存在路径时，预览会报告 missing path。

运行结果达到：

```text
93 passed
```

## 2026-07-10: 代码 Agent 流式输出

### 做了什么

新增代码 Agent 流式模型响应能力。

主要能力：
- 新增 `agent_stream.py`，专门聚合 Chat Completions streaming chunk。
- 模型文本 delta 会实时写入 Agent 输出，让 UI 更早看到模型正在生成的内容。
- tool-call streaming 会按 index 聚合完整 `id`、`name` 和 `arguments`。
- 工具调用只会在流结束、参数聚合完整后执行，避免半截 JSON 被执行。
- CodeAgent 的主模型请求从同步响应改为 `stream=True`。
- 最终答案保存逻辑兼容新的 `### 模型输出` 区块，仍然只保存 `### 结果` 后的最终答案。
- 回滚路径变更统计补充支持 `rollback_paths`，让选择性回滚后也能进入验证流程。

### 为什么做

之前代码 Agent 的工具状态和执行报告会逐段展示，但模型本身的响应要等整次请求结束后才显示。

真正的 Agent 体验需要更早反馈：用户能看到模型正在生成文本、准备工具调用，而不是一直等到模型完整返回。

不过工具调用和普通文本不同，streaming 时参数会分多段返回。如果半截参数就执行工具，会带来安全和稳定性风险。所以这一版只实时展示文本，工具调用必须等完整聚合后再执行。

### 影响模块

- `kagent/agent/agent_stream.py`
- `kagent/agent/code_agent.py`
- `kagent/ui/agent_worker.py`
- `tests/test_agent_stream.py`
- `tests/test_agent_worker.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增测试：
- `tests/test_agent_stream.py`
- `tests/test_agent_worker.py`

覆盖内容：
- 文本 delta 会按顺序聚合并回调输出。
- tool-call arguments 会跨 chunk 拼成完整 JSON。
- 多个 tool-call index 会按顺序聚合。
- 带 `### 模型输出` 的 Agent 报告仍能提取最终答案。

运行结果达到：

```text
98 passed
```

## 2026-07-10: 长期项目记忆

### 做了什么

新增长期项目记忆能力。

主要能力：
- 新增 `project_memories` 数据表，按工作区路径保存项目级记忆。
- 新增项目记忆模块，可以自动生成稳定项目事实。
- 记忆内容包括项目类型、项目结构摘要、入口文件、配置文件、常用验证命令和稳定偏好。
- CodeAgent 每次运行会加载或生成项目记忆，并注入模型系统上下文。
- 记忆按工作区复用，新的会话也能继承同一个项目的稳定背景。
- 记忆写入保持保守，不保存临时工具错误、长日志或敏感命令输出。

### 为什么做

之前 Agent 每次运行都需要重新理解项目结构、验证入口和用户偏好，容易重复扫描、重复试错。

长期项目记忆让 Agent 能记住“这个项目是什么、怎么验证、当前阶段重点是什么”，下次运行可以更快进入任务本身。

这一版先保存稳定事实，不做复杂向量记忆和自动事实抽取，避免把临时错误、失败输出或敏感信息长期保存。

### 影响模块

- `kagent/db.py`
- `kagent/agent/project_memory.py`
- `kagent/agent/code_agent.py`
- `tests/test_project_memory.py`
- `tests/test_code_agent_memory.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增测试：
- `tests/test_project_memory.py`
- `tests/test_code_agent_memory.py`

覆盖内容：
- 可以从项目文件生成长期项目记忆。
- 项目记忆按工作区路径持久化并复用。
- 记忆格式化后包含项目类型、入口文件、验证命令和稳定偏好。
- CodeAgent 会把长期项目记忆注入模型上下文。

运行结果达到：

```text
102 passed
```

## 2026-07-10: 更安全的命令执行策略

### 做了什么

升级命令风险分类能力。

主要能力：
- 命令策略结果新增 `risk_categories` 和 `risk_factors` 结构化字段。
- 安全验证命令会标记为 `validation`，保持低风险、免审批。
- 只读命令会标记为 `read_only`。
- 依赖安装或卸载命令会标记为 `dependency_change`。
- Git 写操作会标记为 `git_write`。
- 网络命令会标记为 `network`。
- 删除命令会标记为 `destructive_delete`。
- 链式 shell 命令会标记为 `chained_shell`。
- shell 重定向会标记为 `redirection`。
- 未分类任意命令会标记为 `arbitrary_shell`。
- 工具报告会展示 `risk_categories`，方便 UI 和日志复盘。

### 为什么做

之前命令风险已经能分成 safe、low、medium、high、critical，但原因主要是自然语言，后续 UI、日志查看器和审批逻辑不容易精确消费。

结构化风险分类让 Agent 和用户更清楚“为什么这个命令危险”：是会改依赖、会写 Git、会联网、会删除，还是只是普通验证。

这样可以对验证命令保持低摩擦，同时对真正可能影响环境或仓库状态的命令要求更明确的审批。

### 影响模块

- `kagent/agent/risk_policy.py`
- `kagent/agent/tool_view.py`
- `tests/test_risk_policy.py`
- `README.md`
- `docs/agent-development.md`

### 验证

扩展 `tests/test_risk_policy.py`。

覆盖内容：
- 验证命令标记为 `validation`。
- 删除命令标记为 `destructive_delete`。
- 依赖安装命令标记为 `dependency_change`。
- Git 写操作标记为 `git_write`。
- 网络命令标记为 `network`。
- 链式命令标记为 `chained_shell`。

运行结果达到：

```text
106 passed
```

## 2026-07-10: 最终回复可信度接入

### 做了什么

把运行可信度检查接入 Agent 最终回复。

主要能力：
- 新增最终可信度模块，将当前运行状态转换为 `pass`、`warn`、`fail`。
- 最终回复 prompt 会包含 trust check，要求模型明确披露未验证变更、验证失败、失败工具或循环风险。
- 如果代码发生变更但没有完成验证，会标记 `unverified_changes`。
- 如果验证失败，会标记 `validation_failed`。
- 如果工具失败或出现循环风险，会作为 residual risk 提示。
- CodeAgent 会统计失败工具数量和循环警告数量。
- 运行结束时会写入 `final_trust_check` 日志事件，并把 `final_trust` 放入 run finish payload。

### 为什么做

之前 Agent 已经有运行自检报告，但最终回复仍主要依赖模型自己总结执行状态。

代码 Agent 最终回答必须非常诚实：改了什么、有没有验证、验证是否失败、还有什么风险，都不能模糊。

把可信度检查接入最终回复后，即使模型上下文很长，也会在收尾阶段收到明确约束，减少“没验证却说通过”的风险。

### 影响模块

- `kagent/agent/final_trust.py`
- `kagent/agent/code_agent.py`
- `tests/test_final_trust.py`
- `tests/test_code_agent_memory.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 `tests/test_final_trust.py`，扩展 `tests/test_code_agent_memory.py`。

覆盖内容：
- 未验证变更会生成 `fail` 和 `unverified_changes`。
- 已验证但存在工具失败或循环警告会生成 `warn`。
- 干净验证通过会生成 `pass`。
- CodeAgent 最终回复 prompt 会包含 trust check 和必须披露的问题。

运行结果达到：

```text
110 passed
```

## 2026-07-10: UI 调试面板和日志查看入口

### 做了什么

新增 UI 运行调试入口。

主要能力：
- Agent 执行日志卡片会显示本次 run id。
- 收到最终可信度检查后，会显示 health 和 validated 状态。
- 执行日志卡片新增“日志摘要”按钮。
- 执行日志卡片新增“时间线”按钮。
- 日志摘要弹窗会展示运行摘要和自检报告。
- 时间线弹窗会展示运行事件序列，包括阶段、工具调用、工具结果等。
- 日志展示复用底层 `run_log_viewer` 和 `run_self_check`，避免 UI 自己解析 JSONL。

### 为什么做

之前已经有 JSONL 运行日志、日志查看器、自检报告和最终回复可信度，但用户还需要打开文件或靠开发工具查看。

UI 调试入口让用户在一次 Agent 运行结束后，直接从界面复盘“这次做了什么、哪些工具失败、验证是否通过、可信度如何”。

这一步先做本次运行查看入口，不做复杂历史搜索，避免偏离当前阶段的代码 Agent 能力建设。

### 影响模块

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 `tests/test_ui_run_debug.py`。

覆盖内容：
- 运行日志摘要 Markdown 包含 run summary 和 self check。
- 时间线 Markdown 包含运行开始、阶段变化和事件详情。

运行结果达到：

```text
112 passed
```

## 2026-07-10: 历史运行搜索和导出

### 做了什么

新增历史运行查询和导出能力。

主要能力：
- 新增 `run_history` 模块，可以扫描 `.kagent_state/runs/` 下的多次 JSONL 运行日志。
- 支持按最新优先返回运行历史摘要。
- 历史摘要包含 `run_id`、运行状态、健康度、是否验证、是否验证失败、是否存在未验证变更、失败工具数量、变更文件数量、事件数量和问题码。
- 支持按 `status`、`health`、`validation_failed`、`unverified`、`failed_tools` 筛选历史运行。
- 支持把指定 `run_id` 或日志路径导出为 Markdown 报告。
- 导出报告包含运行摘要、自检结果和事件时间线。
- 支持导出最新一次运行报告。
- 遇到损坏的 JSONL 日志会跳过，不影响其他历史记录读取。

### 为什么做

之前已经能查看“本次运行”的摘要、时间线和自检，但还缺少跨多次运行的复盘能力。

代码 Agent 做大以后，调试重点不只是某一次是否成功，还要能快速回答：
- 最近哪些运行失败了。
- 哪些运行改了代码但没有验证。
- 哪些运行出现工具失败或循环风险。
- 某一次运行能不能导出成报告，方便后续定位、提交 issue 或做能力回顾。

这一阶段先做后端能力，不急着做复杂 UI，保证后面接历史面板时有稳定的数据层可以复用。

### 影响模块

- `kagent/agent/run_history.py`
- `tests/test_run_history.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 `tests/test_run_history.py`。

覆盖内容：
- 历史运行按最新优先排序。
- 可按健康度、未验证变更、失败工具、验证失败筛选。
- 可按 `run_id` 导出 Markdown，报告包含 summary、self check 和 timeline。
- 可导出最新运行。
- 损坏 JSONL 日志会被跳过。

局部运行结果达到：
```text
4 passed
```

全量运行结果达到：
```text
116 passed
```

## 2026-07-10: 引用级影响分析

### 做了什么

在文件级影响分析基础上，新增轻量引用级影响分析。

主要能力：
- 新增 `analyze_reference_impact`，可以分析单个 Python 变更文件的引用影响。
- 会把变更文件路径转换成模块名，例如 `kagent/agent/validation.py` 转成 `kagent.agent.validation`。
- 会读取变更文件里的顶层 class、function、async function 名称，作为符号影响线索。
- 会扫描项目源码和测试文件里的 Python AST。
- 支持识别 `import changed.module`。
- 支持识别 `from changed.module import Symbol`。
- 支持识别 `from parent.module import leaf_module`。
- 支持识别简单函数/类名称引用和属性引用。
- 如果测试文件直接引用变更模块或符号，会把该测试加入相关测试。
- 如果源文件引用变更模块或符号，会继续映射到该源文件对应的测试。
- `related_tests_for_changes` 已自动合并文件名映射和引用级映射，现有验证流程不需要额外改调用方式。

### 为什么做

之前 Agent 的相关测试推断主要依赖文件名规则，例如 `kagent/context.py` 对应 `tests/test_context.py`。

这种方式简单稳定，但遇到下面情况会漏：
- 测试文件不是按同名规则命名。
- 一个模块被另一个源文件调用，真正需要跑的是调用方测试。
- 修改的是公共函数、类或工具模块，影响面不只当前文件的同名测试。

引用级影响分析让 Agent 在修改代码后能更像真实开发者一样先问：“谁 import 了它？谁调用了它？调用方有没有测试？”  
这一阶段先做轻量 AST 扫描，不引入 LSP 或复杂依赖，保持当前项目轻巧。

### 影响模块

- `kagent/agent/impact_analysis.py`
- `tests/test_impact_analysis.py`
- `README.md`
- `docs/agent-development.md`

### 验证

扩展 `tests/test_impact_analysis.py`。

覆盖内容：
- 测试文件直接 `from changed.module import Symbol` 时，会被识别为相关测试。
- 源文件引用变更模块时，会继续映射到该源文件对应测试。
- 原有文件级测试映射和 pytest 命令生成能力保持不变。

局部运行结果达到：
```text
9 passed
```

全量运行结果达到：
```text
118 passed
```

## 2026-07-10: 验证命令学习

### 做了什么

新增从历史运行日志学习验证命令的能力。

主要能力：
- 新增 `validation_learning` 模块。
- 会扫描 `.kagent_state/runs/` 下的 JSONL 运行日志。
- 只学习 `validation_plan` 中出现过、并且后续由 `run_command` 实际执行过的命令。
- 会统计每条验证命令的成功次数、失败次数、失败率、最近出现时间和置信度。
- 会忽略普通 shell 命令，避免把非验证命令误加入验证计划。
- 会跳过损坏日志，不影响其他历史记录学习。
- `build_validation_plan` 会优先合并历史稳定命令，再追加规则生成的验证命令。
- 合并时会按 `command + cwd` 去重，避免重复跑同一条命令。
- 项目长期记忆会吸收 learned validation commands，让后续 prompt 能看到项目真实跑通过的验证入口。

### 为什么做

之前验证计划主要靠规则检测，例如 Python 项目生成 `py_compile`、相关测试和 pytest，Node 项目读取 package scripts。

这套规则足够安全，但不够“熟悉项目”：
- 有些项目真正稳定的入口是 `run-tests.bat` 或 `scripts/verify.ps1`。
- 有些命令虽然存在，但历史上经常失败，不应该一直优先推荐。
- Agent 多次运行后应该越来越了解项目，而不是每次都从零开始猜验证命令。

验证命令学习让 Agent 能从自己的历史运行里沉淀经验：哪些命令真实通过过、哪些命令不稳定、下次应该优先跑什么。

### 影响模块

- `kagent/agent/validation_learning.py`
- `kagent/agent/validation.py`
- `kagent/agent/project_memory.py`
- `tests/test_validation_learning.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 `tests/test_validation_learning.py`。

覆盖内容：
- 能从成功的验证计划和命令结果中学习命令。
- 普通未规划 shell 命令不会被误学习。
- 生成 validation plan 时会优先使用 learned command。
- 原有 validation plan 和 project memory 测试保持通过。

## 2026-07-10: 多语言符号索引

### 做了什么

把符号级搜索从 Python-only 扩展为多语言轻量索引。

主要能力：
- Python 继续使用 AST 提取 class、function、method、import。
- JS/TS/JSX/TSX 支持提取 import、require、class、interface、type、enum、function、箭头函数、const。
- Go 支持提取 import、function、method、struct、interface、type、const。
- Rust 支持提取 use、fn、struct、enum、trait、type、const。
- Java 支持提取 import、class、interface、enum、method。
- `find_symbols` 继续复用统一索引结果，调用方式不变。

### 为什么做

项目后期不一定只有 Python。代码 Agent 如果只能查 Python 符号，遇到前端、Go 服务、Rust 工具或 Java 模块时，会退回普通文本搜索，定位能力明显下降。

这一阶段没有引入语言服务器，也没有做复杂语义分析，而是先用稳定语法形态做轻量索引。这样可以在不增加依赖和复杂度的前提下，让 Agent 具备跨语言“快速找定义”的能力。

### 影响模块

- `kagent/agent/symbol_index.py`
- `tests/test_symbol_index.py`
- `README.md`
- `docs/agent-development.md`

### 验证

扩展 `tests/test_symbol_index.py`。

覆盖内容：
- JS/TS 的 import、interface、type、class、function、箭头函数。
- Go 的 import、struct、function、method。
- Rust 的 use、struct、enum、fn。
- Java 的 import、class、method。

局部运行结果达到：
```text
21 passed
```

全量运行结果达到：
```text
123 passed
```

## 2026-07-10: 增强任务拆解

### 做了什么

把原来的轻量任务清单升级为带元数据的任务拆解。

主要能力：
- `PlanStep` 新增 `objective`，记录每个子任务的明确目标。
- `PlanStep` 新增 `files`，记录从用户需求中识别出的候选相关文件。
- `PlanStep` 新增 `risks`，记录该步骤可能引入的风险。
- `PlanStep` 新增 `validation`，记录建议验证方式。
- `plan_for_model` 会把目标、文件、风险、验证方式注入给模型，让 Agent 执行时更有方向。
- `plan_to_dicts` 会序列化完整任务拆解元数据，方便 UI 和 run log 展示。
- 新增 `next_plan_action`，可以根据当前状态返回下一步应该推进的子任务。
- 新增 `plan_progress_snapshot`，统计任务总数、各状态数量、下一步行动和完整步骤。
- CodeAgent 运行结束 payload 新增 `plan_snapshot`，为后续长任务恢复和复盘打基础。

### 为什么做

之前任务规划主要是固定步骤：理解、检查、修改、验证、总结。它能显示进度，但不够支撑更长的代码任务。

更强的代码 Agent 需要知道：
- 每一步为什么要做。
- 可能会动哪些文件。
- 哪些地方风险更高。
- 应该怎么验证。
- 如果任务中断，下一步应该从哪里继续。

这次增强先不做复杂多 Agent 编排，而是把单 Agent 的任务状态打厚，让后续“长任务恢复”“任务复盘”“UI 任务面板”都有可用的数据结构。

### 影响模块

- `kagent/agent/task_plan.py`
- `kagent/agent/code_agent.py`
- `tests/test_task_plan.py`
- `README.md`
- `docs/agent-development.md`

### 验证

扩展 `tests/test_task_plan.py`。

覆盖内容：
- 代码编辑任务仍然包含检查、修改、验证、总结步骤。
- 序列化结果包含目标、候选文件、风险和验证方式。
- 模型提示会展示增强后的任务拆解信息。
- `plan_progress_snapshot` 可以统计状态并返回下一步行动。

局部运行结果达到：
```text
6 passed
```

全量运行结果达到：
```text
125 passed
```

## 2026-07-10: 长任务恢复

### 做了什么

新增基于运行日志的长任务恢复能力。

主要能力：
- 新增 `task_resume` 模块。
- 支持根据 run log 路径生成恢复上下文。
- 支持根据 `run_id` 查找历史运行并生成恢复上下文。
- 支持读取最新一次运行并生成恢复上下文。
- 会读取 `plan_snapshot`，找到下一步 active、pending 或 failed 的任务。
- 如果旧日志没有 `plan_snapshot`，会从 `plan` 或最近的 `agent_plan` 事件重建快照。
- 会结合运行健康检查结果、变更文件、验证失败、未验证变更、失败工具和 issue code 判断恢复优先级。
- 恢复优先级包括 `fix_validation_failure`、`run_validation`、`recover_failed_tool`、`continue_incomplete_plan`、`continue_next_plan_step` 和 `summarize_or_confirm_done`。
- 会生成 `resume_prompt`，提示 Agent 从哪里继续，而不是重新从头检查。
- 提供 `format_resume_context`，可把恢复上下文格式化成可读报告，方便后续接 UI。

### 为什么做

增强任务拆解之后，Agent 已经能记录每一步目标、风险、验证方式和下一步快照。但如果任务中断或用户稍后继续，仍然需要一个恢复层来回答：
- 上次做到哪一步。
- 哪些文件已经改过。
- 是否已经验证。
- 如果验证失败，应该先修失败还是继续改代码。
- 如果工具失败，是否应该先换策略。

长任务恢复就是把 run log 从“复盘材料”变成“继续执行的入口”。这一步先做后端恢复上下文，不急着做 UI 按钮，保证后续接入时逻辑稳定。

### 影响模块

- `kagent/agent/task_resume.py`
- `tests/test_task_resume.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 `tests/test_task_resume.py`。

覆盖内容：
- 验证失败时恢复优先级为 `fix_validation_failure`。
- 有变更但未验证时恢复优先级为 `run_validation`。
- 可以从旧版 `plan` payload 重建任务快照。
- 可以按最新日志和 `run_id` 生成恢复上下文。
- 缺失 `run_id` 时返回 `None`。

局部运行结果达到：
```text
15 passed
```

全量运行结果达到：
```text
128 passed
```

## 2026-07-13: Task Resume UI Entry

### What changed

- Added a `Resume Task` action to the Run Debug dialog.
- The action reuses `task_resume.build_resume_context` and `format_resume_context`.
- The generated resume context is submitted as the next Agent turn, so the Agent can continue from the previous run instead of restarting from scratch.
- Added `_resume_task_prompt` as a small pure function so the UI resume prompt is testable.
- Kept the implementation scoped to the existing run debug flow; no new run-log database or duplicate resume data source was added.

### Affected modules

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### Verification

```text
131 passed
```

### Next

The next useful step is a dedicated run-history picker for resume:
- Show recent failed, stopped, unverified, and validation-failed runs.
- Let the user choose which run to resume instead of only resuming from an opened Run Debug dialog.
- Optionally show the generated resume prompt before submission.

## 2026-07-13: UI Language Option Coverage

### What changed

- Moved visible UI option text into the language dictionary for Chinese and English.
- Covered Run Debug, Diff Review, Task Resume, rollback actions, tool trace cards, approval controls, sidebar hints, input hints, empty states, status labels, and common dialogs.
- Chinese mode now uses Chinese labels for these controls instead of mixed English such as `Resume Task`, `Current Diff Review`, `Run Summary`, `Status`, `Files`, `Allow`, and `Reject`.
- English mode keeps the matching English labels.
- Added tests for Chinese and English markdown/action text generation.

### Affected modules

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### Verification

```text
133 passed
```

## 2026-07-13: Session Workspace Switching

### What changed

- Added `workspace_root` to the `sessions` table, with migration for existing databases.
- New sessions default to the configured `WORKSPACE_ROOT`.
- Each session can store a different target project directory.
- The chat header now includes a workspace selector button.
- Diff Review, rollback history, and Agent execution use the selected session workspace.
- `AgentWorker` now passes the session workspace into `CodeAgent`.

### Affected modules

- `kagent/db.py`
- `kagent/ui/main_window.py`
- `kagent/ui/agent_worker.py`
- `tests/test_session_workspace.py`
- `tests/test_agent_worker.py`
- `README.md`
- `docs/agent-development.md`

### Verification

```text
16 targeted tests passed
```

## 2026-07-13: Folder-Based New Chat Entry

### What changed

- Added a sidebar action for creating a new chat from a selected folder.
- The selected folder becomes the new session's `workspace_root`.
- The folder name becomes the initial session title.
- The app switches to the new session immediately after creation.
- Kept the existing normal new-chat action for continuing from the current workspace.

### Affected modules

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### Verification

```text
10 targeted tests passed
```

## 2026-07-13: Current Project Button Placement

### What changed

- Moved the current project/workspace button from the chat header to the input action row next to `Permissions`.
- The button label now uses `当前项目：<folder>` / `Project: <folder>` instead of only the raw folder name.
- Switching chats or creating a folder-based chat refreshes the displayed folder name.

### Verification

```text
138 passed
```

## 2026-07-13: Explicit Sidebar New Chat Labels

### What changed

- Kept the normal sidebar new-chat option as `新增会话`.
- Kept the folder-picker option as `选择文件夹新建会话`.
- The no-folder choice lives in the current project menu next to the permission button, not as a third sidebar entry.

### Verification

```text
139 passed
```

## 2026-07-13: No-Folder Option In Project Menu

### What changed

- Kept the sidebar to two entries only: normal new chat and folder-based new chat.
- Added `不选择文件夹` / `No folder` to the current project menu next to the permission button.
- A no-folder chat uses normal chat streaming and does not create the coding `CodeAgent` workspace/tool path.
- The UI shows `项目：未选择` / `Project: none` for no-folder chats.

### Verification

```text
140 passed
```

## 2026-07-12: 当前会话 Diff Review 入口

### 做了什么

在主界面聊天头部新增 `Diff` 入口，用来查看当前会话 active rollback 记录汇总出的变更预览。

主要能力：
- 复用已有 `preview_rollback_session` 后端能力，不新增重复 diff 数据源。
- 展示当前会话可回滚变更的文件列表。
- 展示聚合后的 diff 预览。
- 空状态会明确提示当前会话没有 active rollbackable changes。
- 保留原有 History 面板，继续用于逐条查看和恢复 rollback 记录。

### 为什么做

Agent 修改代码后，用户需要快速确认“本轮到底改了哪些文件、具体 diff 是什么”。之前 rollback history 已经能逐条查看，但入口偏向恢复操作，不够适合作为一次运行后的快速 review。

Diff Review 把已有 rollback 快照能力变成更直接的代码审查入口，先解决信任和可见性问题，再继续做任务恢复。

### 影响模块

- `kagent/ui/main_window.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### 验证

新增 UI Markdown 纯函数测试，覆盖有 diff 和空状态两种情况。

全量运行结果达到：
```text
130 passed
```

## 当前验证入口

推荐使用：

```powershell
.\run-tests.bat
```

这个脚本会执行：
- Python 语法检查。
- pytest 单元测试。

## 发展日志模板

以后每次添加 Agent 能力，都按这个模板追加。

```markdown
## YYYY-MM-DD: 功能或优化名称

### 做了什么

- ...

### 为什么做

- ...

### 影响模块

- `path/to/file.py`

### 验证

- 运行了什么命令。
- 结果是什么。

### 后续

- 下一步建议。
```

## 下一步建议

下一步建议做恢复运行历史选择器。

目标：
- 在 UI 中列出最近失败、中断、未验证或验证失败的运行记录。
- 允许用户选择一次历史运行继续，而不是只能从已打开的 Run Debug 弹窗恢复。
- 在提交前预览后端 `task_resume` 生成的恢复提示。
