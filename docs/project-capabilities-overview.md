# kagent 项目能力全景导览

> 给项目 owner 的完整能力地图：每个能力**做什么 + 怎么实现（file:line）+ 解决什么问题 + 面试怎么讲**。
> 按"能力支柱"组织，而非按文件，最适合面试讲解和简历叙事。
> 生成于 2026-07-23，基于真实代码核验。当前 250 tests passed。

---

## 总览：项目定位

kagent 是一个 **PyQt6 本地桌面 Coding Agent + 测试开发自动化助手**。单项目同时服务两个求职方向：

- **测试开发纵深**：symbol-impact 变更分析 → per-test 遥测 → flaky/timing 检测 → 可视化看板 → JUnit XML 导出接 CI → 真实覆盖率 + gate → 测试生成
- **AI 工程广度**：ReAct Agent 循环 + 工具调用 → 多语言符号级 code intelligence → 上下文工程 → 测试失败记忆(RAG)

**核心一句话**：不是"调了大模型 API"，而是搭了一个能改代码、跑验证、自己诊断失败、可审计可回滚的工程闭环——这是大多数作品集没有的工程深度。

**规模**：`kagent/` ~19000 LOC（43 模块）+ `tests/` ~5000 LOC（37+ 测试文件），250 passed。

---

## 支柱一：Agent 核心循环（ReAct + 状态机）

### 能力：把一条任务跑成有状态、可观测、可审批、带验证-修复闭环的 ReAct Coding Agent

**核心文件**：`kagent/agent/code_agent.py`（~2009 行，整个项目的中枢）

#### AgentPhase 状态机（code_agent.py:79-99）
8 个阶段：`STARTING / INSPECTING / PLANNING / EDITING / VALIDATING / REPAIRING / FINALIZING / STOPPED`。`AgentRunState`（:102）是贯穿全程的可变状态：inspected/mutated/content_changed/validated/validation_failed/changed_paths/plan/symbol_change_plans/tool_call_history/failed_tool_count/loop_warning_count。

#### Tool loop 怎么循环（code_agent.py:1556）
`for round_idx in range(max_rounds=12)`，每轮四件事：
1. **停止检查**（:1557）：`should_stop()` → STOPPED + trust check
2. **自动验证闸门**（:1563-1694）：`content_changed and not state.validated` 时**绕过模型**直接跑验证
3. **模型调用**（:1696）：`_stream_assistant_message` 流式取 assistant 消息
4. **工具分发**（:1709-1998）：逐个 tool_call 执行 + 回填

**强制重试阶梯**（:1744-1813）是闭环关键护栏：模型不调工具→注入"别光说不练"；改了不验证→注入验证 prompt；验证失败→注入修复 prompt；都做了→注入最终回复 prompt。每个闸门一次性 flag 防死循环。

#### 工具 dispatch + 结果回填（code_agent.py:688-826, 1216-1412）
`_execute_tool_action` 是单个工具完整生命周期：算风险策略→构造变更计划→发事件→**审批闸门**（approval_required 调 confirm_tool，被拒则不执行）→`_dispatch_tool` 执行→**结果回填 messages**（`{role:tool, tool_call_id, content}`，这是 ReAct 的 Observation 回灌）→发 tool_result 事件。`_dispatch_tool` 是 22+ 工具的大 switch。

#### 验证流程怎么触发 per-test 遥测（code_agent.py:946-1111）
`_run_auto_validation` 逐条验证命令执行：`prepare_pytest_junit_command`（:976）把 pytest 命令包上 `--junitxml`，跑完调 `_emit_test_case_telemetry`（:1071）解析 JUnit XML → **逐个 case 发 test_case_result 事件**。这是 Run Analytics 仪表盘的 per-test 数据源。

#### 修复循环（code_agent.py:1770-1799）
验证失败→`validation_repair_attempts += 1`→phase=REPAIRING→注入 `validation_failure_prompt` 让模型改代码。上限 `MAX_VALIDATION_REPAIR_ROUNDS=3`（:207）。每次 content edit 成功会**重置** repair attempts（因为代码又变了，验证要重来）。

#### final trust 收尾（code_agent.py:467-483, 607-662）
`_finish_run_with_trust_check`：`build_final_trust_summary` 汇总→发 final_trust_check 事件→写进 run log。最终回复 prompt（:660）**显式禁止"validation 没过却声称过了"**。

### 面试怎么讲
- **max_rounds=12 + 一次性 force flags**：防 LLM 陷入"光说不练"或"忘记验证"死循环
- **验证是硬闸门不是建议**：`content_changed && !validated` 在循环顶部拦截，不依赖模型自觉——这是测试开发背景能讲的核心工程取舍，把 validation 从 prompt hint 升级成 state machine 约束
- **ReAct 闭环的 messages 自洽**：自动验证、patch 恢复、failure-focus 读文件都用 `append_assistant_stub` 合成 assistant tool_call，让 OpenAI API 的 tool_call_id 配对不被破坏

### 辅助模块
- **`agent_worker.py`**：QThread + 5 信号把 agent 跑后台；审批用 `threading.Event + 0.1s 轮询`阻塞 agent 线程同时响应 stop；`_final_answer_from_report` 只截 `### 结果` 段入库避免历史膨胀
- **`llm.py`**：OpenAI 流式封装；`reasoning_effort` 不支持时按错误关键字嗅探**自动降级重试**；全程 model_request/response 事件下沉可观测性；超时按用途分级（title 10s / agent 45s）
- **`tool_schema.py`**：22+ 工具的 JSON-Schema 契约（模型能做的 = schema 里有的）；description 内嵌 read-only 标注 + 参数上界防上下文爆炸

---

## 支柱二：符号级代码智能

### 能力：改一个符号前知道牵连谁；改完只跑相关测试

**核心文件**：`symbol_index.py` / `symbol_change_plan.py` / `impact_analysis.py` / `project_map.py`

#### project_map.py — 全局文件地图（基础层）
`build_project_map`（:50）os.walk 遍历，剪掉 .git/.venv 等；`_is_test_file`（:116）四条判定（tests/ 目录、test_ 前缀、_test.py、.test./.spec.）；`source_to_tests` 纯约定式映射（foo/bar.py → tests/test_bar.py）。**路径启发式，不读内容**——所以上层 impact_analysis 用 AST 引用分析兜底。

#### symbol_index.py — 符号定义与引用索引（核心层）
- **Python：AST 双 visitor**。`_SymbolVisitor`（:341）维护 containers 栈，嵌套函数的 container 字段是 `"OuterClass.method"` 形式，靠容器栈区分 method/function。`_ReferenceVisitor`（:186）四类引用：import/call/name_reference/attribute_reference——语义级引用类型，正则做不到。SyntaxError 降级走 `_line_references`（解析失败不丢文件）。
- **非 Python：正则**。JS/Go/Rust/Java 各有 pattern 表（:415-464），逐行扫抽名字+kind，但**不抽 container/范围/引用类型**。

**AST vs 正则取舍**：Python 用 stdlib ast 拿语义（零依赖），其它语言退成逐行正则——"核心语言深做、周边浅做"，避免为每种语言引第三方 parser。

#### symbol_change_plan.py — 改动影响计划 + 风险评分（决策层）
`build_symbol_change_plan`（:11）聚合定义/引用/相关测试/验证命令/风险。**`_impact_score` 加权公式**（:147）：
- 定义未找到 +25（改不存在的符号最危险）/ 定义多于 1 个 +15（同名歧义）
- 生产引用数×4（上限 35）/ 受影响文件数×3（上限 20）/ 测试引用数×2（上限 12）
- **有生产引用却无相关测试 +15**——直接量化"改动没有安全网"

`_risk_level`（:168）：≥65 high / ≥25 medium / 否则 low。把"改符号有多危险"从模糊感觉变成 0-100 可解释分数。

#### impact_analysis.py — 跨文件引用分析（兜底层）
`analyze_reference_impact`（:94）用 AST 反向分析：改了 foo.py，谁 import 了它？这些引用者又映射到哪些测试？补 project_map 路径启发式的盲区。`related_test_commands_for_changes`（:15）拼成 pytest 命令，带 `reason` 字段解释"为什么跑这个"。

### 面试怎么讲
- **双层测试映射**：project_map 约定（快、免费）+ impact_analysis AST 引用（精、补漏），全程保留 reason 字段做到可解释选型
- **_impact_score 加权**：生产引用权重 4 > 测试 2，"有生产引用但零测试"+15 直接量化"无安全网"，risk_level 三档驱动 agent 决策
- **AST vs 正则**：核心语言深做、周边浅做、零第三方依赖

---

## 支柱三：验证与失败修复自动化

### 能力：改完自动验证；失败后自动定位+分类+驱动修复

**核心文件**：`validation.py` / `failure_diagnostics.py` / `failure_focus.py` / `repair_strategy.py` / `patch_recovery.py` / `tool_recovery.py` / `tool_loop_guard.py`

#### validation.py — 验证计划与执行
`build_validation_plan` 基于 changed_paths + symbol_impacts 生成验证命令集，优先级：语法检查 → 符号相关测试 → 文件相关测试 → 学习到的命令 → 全量验证。`_validation_command_rank`（:508）按 success_rate×0.58 + (1-failure_rate)×0.22 + speed×0.12 + coverage_bonus + learned_bonus 排序。**coverage_bonus 已从写死标签换成真实 line_rate**（覆盖率真实化成果）。

#### failure_diagnostics.py — 失败位置解析
`extract_failure_diagnostics`（:10）四档抽取：pytest nodeid（`___ node ___`/`FAILED <nodeid>`）→ Python traceback（`File "path", line N`）→ SyntaxError（回溯找上文路径）→ 通用 `path.py:line`。按"最具体→最通用"排序，`_normalize_path` 统一 Windows 路径。

#### failure_focus.py — 失败聚焦读取
`focus_targets_from_diagnostics`（:11）算 top-3 读取目标（失败行 ±40 行）。**`_symbol_focus_targets`（:135）符号联动**：若失败测试覆盖了被改符号，把符号定义也加进聚焦目标——"失败在测试里，根因可能在被改的生产符号定义处"。code_agent 验证失败后**自动 read_file 这些目标**，agent 还没决定读什么，系统已经把失败现场读进来了。

#### repair_strategy.py — 失败分类驱动修复
`classify_failure`（:7）8 类顺序 if 链：missing_dependency / command_not_found / timeout / syntax_error / import_error / assertion_failure / runtime_error / test_failure / unknown。每类配针对性 next_step。顺序=优先级（importerror 必须在 runtime_error 前，否则被 traceback 吞掉）。**一个分类函数服务两个入口**：验证失败修复 + 工具失败重试。

#### patch_recovery.py — patch 失败专项恢复
patch 失败→`patch_failure_recovery`（:7）从 change_plan + 错误正则双来源提取目标文件→**主动重新 read_file 刷新上下文**→模型基于真实内容重写更小 patch。解决"patch 上下文对不上→失败→模型凭记忆再写还是对不上"。

#### tool_recovery.py — 工具失败恢复提示
`recovery_hint_for_tool`（:21）分析错误文本，给 `{category, retryable, next_step}`。retryable=False 的几类（user_rejected/permission_scope/non_text_file）是明确的"别再试了"信号，避免模型对被拒/越权反复硬撞。

#### tool_loop_guard.py — 防循环
`record_tool_call`（:22）记录最近 20 条，`tool_call_signature`（:12）只取语义关键参数（patch 用 sha1 前 12 位）算签名。`loop_warning`（:43）两类检测：repeated_failed_tool（同签名失败≥2 → 硬警告）/ repeated_inspection（只读重复≥3 → 软警告）。警告注入 system 消息干预模型，是 soft guardrail。

### 面试怎么讲
- **失败分类驱动修复**：把"测试工程师排错经验"硬编码成 8 类决策树，而非无差别"再试一次"；importerror 优先于 runtime_error 匹配的顺序设计
- **主动失败聚焦**：失败后不让 LLM 自由找文件，诊断+符号计划算出 top-3 位置自动 read_file——把符号智能和失败修复接到一起
- **patch 失败先刷新上下文**：确定性代码先读真实文件，模型再基于真实内容重写——把"记忆漂移"交给读文件解决
- **分层防御**：作用域沙箱 → 风险分级审批 → 变更计划 → 执行+快照回滚 → 失败恢复 → patch 专项 → 循环检测，每层兜上层的漏

---

## 支柱四：测试遥测与质量分析（测试开发主线）

### 能力：per-test 粒度追踪稳定性、flaky、耗时回归、覆盖率、测试生成

**核心文件**：`test_telemetry.py` / `run_analytics.py` / `junit_export.py` / `test_gen.py` / `coverage.py` / `failure_memory.py`

#### test_telemetry.py — per-test 事件地基
`prepare_pytest_junit_command`（:10）给直接 pytest 命令追加 `--junitxml=<workspace>/.kagent/test-results/<run>-<seq>-<idx>.xml`；`parse_junit_xml`（:45）解析每条用例 {nodeid, status, duration_ms, message, failure_type, file, classname, name}；`normalize_pytest_command`（:36）去掉临时 junitxml 避免污染历史命令。code_agent 的 `_emit_test_case_telemetry` 把每条用例写成 `test_case_result` JSONL 事件。

#### run_analytics.py — 跨 run 聚合（最重，~340 行）
`build_run_analytics`（:23）聚合最近 N run：run 级（status/health/gate/各 rate）+ per-test（test_case_count/top_failed_tests/slowest_tests）+ **flaky 检测**（`_flaky_tests`：跨 run per-nodeid pass/fail 历史，失败优先避免重跑抹信号，pass+fail 都>0 且 run_count≥3 判 flaky，区分持续回归/间歇 flaky/稳定）+ **timing 回归**（`_timing_regressions`：per-nodeid 跨 run 耗时历史，中位数基线，ratio≥1.5 且 +200ms 判回归，slower/faster/stable 趋势）+ `run_pass_rate_series`（per-run pass-rate 供看板折线）+ `validation_command_trends`。

**核心设计**：rows 是 newest-first，内部反转为 oldest-first 取尾部作"最新"——不依赖时间戳精度。

#### junit_export.py — JUnit XML 导出
`build_junit_xml`（:25）读 run log 的 test_case_result 事件，组装标准 `<testsuite>`：每条用例一个 testcase（failure/error/skipped 子元素），按 nodeid 去重，计数自动重算；无 per-test 数据时回退运行级摘要 testcase。**任何情况都产出合法 CI 可消费文档**。

#### test_gen.py — 测试生成
`find_untested_symbols`（:30）用 build_symbol_index + project_map.source_to_tests 做 file-level 覆盖缺口扫描（O(项目大小)），返回"无对应测试文件的源文件里的产线函数/类/方法"。`generate_test_scaffold`（:90）读源文件 AST，生成 pytest 脚手架（导入被测模块 + 占位 `def test_x` + TODO 标记，**不编造假断言**）。验证回路：生成后用 pytest --collect-only 确认可发现。

#### coverage.py — 真实覆盖率
`measure_coverage`（:32）用 `coverage run -m pytest` + `coverage json` 拿真实 line_rate/branch_rate（无测试返回 None）；`save_coverage_snapshot` 持久化到 `.kagent_state/coverage_history.json`；`coverage_trend` 比最近 vs 历史均值；`coverage_regression_gate` 在最近比基线低 ≥3% 时判 warn。validation 的 coverage_bonus 已换成真实 line_rate。

#### failure_memory.py — 测试失败记忆（RAG 变体）
`collect_failure_corpus`（:55）扫 run log，把 test_case_result(失败) 与同 run 的 symbol_impacts + change_plan 关联成 FailureRecord。`FailureMemoryIndex`（:99）用 **TF-IDF + 余弦相似度**（纯 Python，无外部 embedding 依赖）索引，`recall_similar_failures` 召回 top-k 历史相似失败 + 当时变更意图。语料 <3 条诚实返回 `insufficient_corpus`。

### 面试怎么讲
- **per-test 遥测是关键一跳**：从"run-level（命令退出码）"升级到"per-test（哪条用例失败/flaky/变慢）"，这是测试平台的核心
- **flaky 中位数基线抗 outlier** + **timing 双阈值**（ratio + 绝对 delta，避免快用例微小波动误报）
- **gentest 不编造假断言**：脚手架只生成结构 + TODO，假断言会带来虚假信心
- **TF-IDF vs embedding 取舍**：语料小、离线可复现、无 API 依赖；语料上来再升级；insufficient_corpus 守卫避免 toy RAG
- **JUnit 导出闭合 CI**：从"只消费 --junitxml"到"也产出 JUnit XML"，接 Jenkins/GitLab/Unity-CI

---

## 支柱五：运行审计与复盘

### 能力：每次 run 可追溯、可复盘、有质量门、能自优化

**核心文件**：`run_log.py` / `run_log_viewer.py` / `run_self_check.py` / `run_review.py` / `final_trust.py` / `self_improve.py` / `run_history.py`

#### run_log.py — JSONL 事件流（唯一事实来源）
`RunLogger`（:13）构造时生成 run_id，落盘 `STATE_DIR/runs/{date}-{run_id}.jsonl`，立即写 run_start。每条事件 `{timestamp, run_id, event, data}`，append-only 保证崩溃不丢前序。`_sanitize`（:148）限长（字符串 >4000 截断、list 截 100 项）防日志撑爆。所有判定都从 `read_run_events` 派生。

#### run_self_check.py — 运行健康判定
`analyze_run_health`（:17）5 条规则：run_not_finished/run_not_completed/unverified_changes/validation_failed（FAIL）+ failed_tools/loop_warning（WARN）。`_overall_health`（:196）FAIL>WARN>PASS 优先级归并。

#### run_review.py — 结构化复盘（最重，~792 行）
`build_run_review`（:11）聚合 11 维度（status/changed_paths/validation/failed_tools/model_requests/model_errors/symbol_impacts/validation_selection/project_rules/health/risk_flags）。`build_quality_gate`（:119）**9 个检查**：run_completed/changes_validated/validation_passed/tool_failures_recovered/model_errors_absent/project_rules_checked-healthy/symbol_impact_present/risk_unverified_changes/risk_validation_failed。产出 4 种 markdown：review / bug_report（含 Suspected Cause 根因推断）/ regression_plan / quality_gate。

#### final_trust.py — 最终回复信任注入
`build_final_trust_summary`（:6）参数化薄判定，`build_quality_gate_summary`（:88）**4 个基础检查**。`final_trust_prompt`（:147）把 gate 结果**注入 system prompt**，强制 Agent 最终答复披露 fail 项 + "不得在 validated=no 时声称验证通过"。**这是唯一回到 Agent 上下文的审计节点**。

#### ⚠️ 两套 Quality Gate（已知技术债）
| | run_review.build_quality_gate | final_trust.build_quality_gate_summary |
|---|---|---|
| 检查数 | 9 | 4 基础 + 动态 issues |
| 输入 | 完整 review dict | 标量参数，不读 log |
| 何时算 | 事后复盘 | 运行结束、写 run_finish 前 |
| 用在哪 | 复盘 markdown，不回 prompt | 写 run_finish → 历史表回显 → 注入最终回复 |

历史表看到的 quality_gate（薄版 4 检查）和复盘报告（9 检查）可能结论不一致。薄版不覆盖 project_rules/symbol_impact/model_errors。**后续应统一为一套以 9 检查为准**。

#### self_improve.py — 自优化闭环
`suggest_self_improvements` 5 类信号源：跨 50 run 趋势（run_analytics）/ 30 run 历史（run_history）/ 缺测试映射（project_map）/ 长文件 / TODO-FIXME。按优先级表 + 严重度加分排序，每条带 action + validation + risk。**显式只读不自动执行**。

#### run_history.py — 历史表 + 导出
`list_run_history` newest-first + 6 维过滤（status/health/gate/validation_failed/unverified/failed_tools）。`export_run_markdown` + `export_run_junit_xml` 两种导出。

### 面试怎么讲
- **JSONL 事件流作为单一事实来源**：所有判定从同一份 read_run_events 派生，append-only + 限长 + 带行号错误解析——审计可追溯、崩溃不丢、坏文件不拖垮
- **结构化复盘四件套**：一次 run 同时产出 review/bug_report/regression_plan/quality_gate，bug_report 的 Suspected Cause 是基于信号的半自动诊断（非模板填空）
- **final_trust 是审计→行为的闭环**：gate 结果硬塞进最终回复 prompt，强制披露——审计不只给人看，还强制改变 Agent 输出
- **两套 gate 差异是已知技术债**：讲清"事前薄 gate 注入 prompt 强制披露" vs "事后厚 gate 全面体检"的职责分工，体现对技术债的自觉

---

## 支柱六：上下文工程与记忆（2026 AI 核心议题）

### 能力：把无限增长的会话控制进有限 token 预算，且信息不丢

**核心文件**：`context.py` / `tool_result_context.py` / `project_memory.py` / `project_rules.py` / `db.py`

#### 上下文工程四件协作（code_agent.py:1474-1507 汇合）
1. **截断**（tool_result_context.py）：工具结果成形时按工具语义裁剪，设 `context_compacted` 标志。read_file 保头尾（`_clip_middle`）、search 保 20 条、run_command 保头尾 + `_important_command_lines` 抽错误行（**错误信息永不丢**）。最前置、per-tool。
2. **压缩**（context.py `manage_context`：:58）：发模型前按 token 水位（CONTEXT_MAX_TOKENS=24000）把旧消息折叠成摘要，保近期 24 条 + system 前缀。`_summarize_messages` 每条抽 role + 关键字段（summary/error/path/command/ok）。中游、会话内。
3. **记忆注入**（project_memory.py + project_rules.py）：项目结构 + KAGENT.md 规则作为 system 消息在 run 启动时注入。`load_or_refresh_project_memory`（:30）DB 缓存；`format_project_memory_for_prompt` 显式"prefer current files"防记忆漂移。最稳、跨会话。
4. **跨会话摘要**（context.py `prepare_session_history`：:115 + db.context_summaries）：把上次会话存盘摘要 + 本次新历史拼接再压缩，回写新摘要，带 `through_message_id` 水位增量。跨进程。

#### project_rules.py — KAGENT.md 规则系统
read/generate/check 三层：读现有规则 / 没有就生成草稿（人 review 后落盘，**agent 不擅自改**）/ 对规则本身做健康度体检打分（4 必需 section + 验证命令 + 文档规则，score = 100 - high×30 - medium×15）。健康度注入 prompt 让 agent 知道规则不全，但显式禁止 agent 自己改 KAGENT.md——**可见性 vs 写权限的边界**。

#### db.py — SQLite 持久化
5 张表：sessions / messages / context_summaries / rollback_entries / project_memories。`threading.Lock` + `check_same_thread=False` 线程安全。upsert 模式让"每会话/每工作区一条"天然成立。回滚条目三态状态机（active/applied/superseded）支持"回滚点之间后一个取代前一个"。

### 面试怎么讲
- **上下文工程为什么是 2026 核心议题**：模型窗口有限且越大越贵越慢，agent 长会话天然膨胀（工具结果几万行）。四道水位线把无限增长控制进有限预算，同时保信息密度（保近期、抽要点、错误不丢）——这是 agent 能不能跑长任务的生死线
- **压缩 vs 截断取舍**：截断单条内剪枝（结构不变、局部有损）、压缩多条折叠成摘要（丢逐字、保结构化要点、全局有损）。先截断再压缩再兜底删除，三道由轻到重
- **KAGENT.md 规则系统**：read/generate/check 闭环 + 健康度打分 + "可见性 vs 写权限"边界
- **"prefer current files" 定调**：记忆有保质期，注入时显式告诉模型以当前文件为准

---

## 支柱七：任务规划与长任务恢复

### 能力：显式执行清单防长任务漂移；中断后可从检查点恢复

**核心文件**：`task_plan.py` / `task_resume.py`

#### task_plan.py — 显式执行清单
`build_task_plan`（:23）硬编码 4-5 步模板：understand→inspect（条件）→make（条件）→validate（条件）→final。`_task_profile`（:168）关键词启发式抽 files/risks/validation 注入步骤。`set_plan_step`（:85）状态机推进。`plan_for_model`（:118）渲染成 markdown checklist 每轮注入 system 消息。骨架硬编码保证"先读后改后验后汇报"不可绕过（尤其 validate 不被跳过）。

#### task_resume.py — 长任务恢复
`build_resume_context`（:12）从 run log 聚合 5 数据源（事件流/summary/health/plan 快照/next action）。**`_resume_priority`（:171）优先级短路**：validation_failed → 有 changed_paths 待验证 → failed_tools → gate fail → 未完成 → warn → 下一步 → 完成。每种 priority 对应一句 "Start by ..." 指令。**恢复不是重放，是"诊断+检查点"**——先诊断为什么中断再决定第一步干什么，而非盲目从 plan 第一步重跑。

### 面试怎么讲
- **显式 plan vs 隐式 prompt**：先落清单再注入，降低长任务漂移；骨架硬编码保证 validate 不被跳过
- **长任务恢复是"优先级+检查点"**：把不可重入的 agent 变成可中断可恢复，run log 作为 single source of truth 跨进程边界

---

## 支柱八：安全与回滚

### 能力：每个写操作自带快照+回滚记录；高风险操作要审批

**核心文件**：`workspace.py` / `risk_policy.py` / `change_plan.py`

#### workspace.py — 工具实现 + 选择性回滚引擎
每个写工具执行前 `_capture_restore_states`（:196）抓快照到 `ROLLBACK_ROOT/<session>/<token>/`，记录 kind（file/dir/missing）。三档回滚：`rollback_last_change` / `rollback_change(rollback_id)` / `rollback_paths(paths)`（**只回退选中路径**，跨多条记录聚合）。`_apply_rollback_entry`（:1382）回滚前再抓快照（回滚本身可回滚）+ 标记被覆盖的更新记录为 superseded。**快照用文件复制而非依赖 git**，所以非 git 项目/脏工作区也能安全运行。

#### risk_policy.py — 风险分级 + 命令分类审批
五级 safe/low/medium/high/critical。`tool_policy`（:141）按工具名分支：safe=只读自动放行 / low=新建小改自动放行 / medium=覆写需审批 / high=大改删命令需审批 / critical=rm -rf 等标 destructive。**命令分类是"先匹配先返回"优先级链**（:353）：critical 破坏性模式优先于一切（`rm -rf foo && pytest` 判 critical 而非被 pytest safe 吞掉）→ 链式 shell → 重定向 → 依赖变更 → git 写 → 网络 → 验证/读 → 未分类 medium。`approval_required = destructive or risk_rank >= medium`。

#### change_plan.py — 编辑前变更计划
`build_change_plan`（:19）对写工具生成结构化计划（路径/操作/意图/风险/验证建议）。`symbol_impacts_for_paths`（:76）= 改动路径 ∩ 符号定义路径，把符号级 impact 绑定到具体这次变更。

### 面试怎么讲
- **每个写操作自带快照+回滚**而非依赖 git：非 git 项目/脏工作区也能安全运行
- **选择性回滚 + superseded 机制**：路径级精准恢复，回滚本身可回滚
- **五级风险 + 命令优先级链**：safe/low 自动跑，medium/high/critical 拦截；`rm -rf && pytest` 判 critical 而非 safe，破坏性模式优先于一切
- **分层防御**：命令正则可被绕过，但底层有作用域限制、上层有审批和循环检测——不单靠正则

---

## 支柱九：UI 与可观测性

### 能力：agent 执行过程实时可见、可审批、可复盘

**核心文件**：`main_window.py`（~5500 行）/ `agent_worker.py` / `markdown_view.py`

- **ToolTraceCard**（:2178）：per-tool 折叠块 trace，每个工具一个卡片，实时 upsert
- **审批卡**（:1923-1953）：Allow/Reject 阻塞 worker 线程
- **token 流**：`on_text_delta` 实时渲染 assistant 输出
- **Run Analytics 看板**（`_show_run_analytics`）：pyqtgraph pass-rate 时序折线 + flaky 表 + timing 回归表（pyqtgraph 不可用回退 markdown）；**Export JUnit XML 按钮**
- **Run Debug**：Summary/Timeline/Review/Quality Gate/Bug Report/Regression Plan/Run Analytics/Resume Task 并列
- **Activity 面板**：当前 diff review / 可恢复 run / rollback 历史统一入口
- **slash 命令**：/model /reasoning /self 等

### 面试怎么讲
- **执行过程不是黑盒**：工具调用、审批、token 流、上下文水位都实时展示并可回放——这是"可观测 agent"
- **审批是策略与执行解耦**：tool_policy 产决策，confirm_tool 回调由 UI 注入，核心逻辑可单测

---

## 面试核心叙事（一句话版）

**测试开发**：kagent 是一个能改代码、跑验证、自己诊断失败的 agent，关键是把验证从 prompt 建议升级成状态机硬闸门，并补齐了 per-test 遥测→flaky/timing 检测→可视化看板→JUnit CI 导出→真实覆盖率 gate→测试生成的完整测试平台链路。

**AI 工程**：kagent 实现了 ReAct agent 循环 + 多语言符号级 code intelligence + 上下文工程（压缩/截断/记忆/摘要四道水位线）+ 测试失败记忆（TF-IDF 召回），每个能力都有真实代码和测试支撑，不是 buzzword 堆砌。

**最难的不是调 LLM**：是让 agent 在真实工作区安全行动——结构化工具、压缩上下文、风险控制、验证排序、失败诊断、回滚、审计日志，让"模型不能撒谎说验证过了"。

---

## 已知技术债 / 可追问的弱点（诚实准备）

1. **两套 Quality Gate 不一致**：run_review（9 检查）vs final_trust（4 检查），历史表回显薄版，可能和复盘结论不一致——后续统一
2. **task_plan 是硬编码模板**：4-5 步固定 + keyword 启发式，不是模型自主分解——诚实说"半自主"
3. **failure-memory 真实语料薄**：真实 run log 的 symbol_impacts/change_plan 事件少，召回主要靠测试构造的语料——已加 insufficient_corpus 守卫，语料随真实 run 积累后启用
4. **非 Python 符号是正则**：JS/TS/Go/Rust/Java 只抽名字+kind，无 container/引用类型——核心语言深做、周边浅做的取舍
5. **单进程 PyQt6**：无 daemon/多客户端/IPC，单用户桌面工具——按需才做，非过度工程
6. **命令风险靠正则**：可被绕过——分层防御之一，不单靠正则

**被问"是不是 AI 写的"**：讲清每个取舍的理由（flaky 中位数抗 outlier、timing 双阈值、gentest 不编造假断言、TF-IDF vs embedding、coverage_bonus 从假指标换真实），证明你懂每一段。
