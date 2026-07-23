# Agent Development Log

## 2026-07-20: Validation Selection In Run Review

### What changed

- Run Review now extracts the latest `validation_plan.selection` from run logs.
- Run Review Markdown now shows validation selection rationale under the Validation section.
- Regression Test Plan now includes the same selection rationale after validation commands.
- Selection rows include tier, command, reason, success rate, failure rate, average duration, selection score, related test, and symbol when available.
- Added tests for validation selection payload extraction and Markdown rendering.

### Why

Validation command ranking should be explainable after the run. Showing selection rationale in review artifacts makes it clear why the Agent chose each validation command and whether learned metrics influenced the decision.

### Verification

```text
Targeted validation passed: 49 tests.
```

## 2026-07-20: Learned Validation Command Ranking

### What changed

- Learned validation commands now participate in final validation-command selection instead of being appended after built-in commands.
- Validation selection ranks full and learned commands using success rate, failure rate, average duration, validation coverage tier, and learned-command confidence.
- Fast syntax checks and related tests still stay ahead of broader validation commands.
- `validation_plan.selection.tiers` now records success rate, failure rate, average duration, and selection score for each selected command.
- Added tests that promote reliable learned commands and demote unreliable learned commands.

### Why

Recording validation metrics is only useful if those metrics affect behavior. This step makes the Agent prefer validation commands that are historically reliable and efficient while keeping focused checks first.

### Verification

```text
Targeted validation passed: 21 tests.
```

## 2026-07-20: Validation Command Learning Metrics

### What changed

- Learned validation commands now track attempt count, success rate, failure rate, average duration, and last failure summary.
- Learned command explanations now include success percentage, average runtime when available, and the most recent failure summary.
- Learned command sorting now considers success rate, pass count, failure rate, runtime, recency, and command text.
- Added focused tests for learned validation metrics and failure summaries.

### Why

Validation command learning needs more than pass/fail counts to choose useful checks. Recording reliability, speed, and recent failure context gives the Agent enough signal to prefer commands that are both relevant and efficient.

### Verification

```text
Targeted validation passed: 20 tests.
```

## 2026-07-20: Symbol Impact Scoring

### What changed

- `symbol_change_plan` now returns a structured `impact_summary`.
- Added `risk_level` and `impact_score` so symbol changes can be ranked by blast radius.
- The impact summary now separates definition paths, production reference files, and test reference files.
- Added affected-file count, production/test reference counts, related-test count, and reference-type counts.
- Updated risk summaries to include risk level and impact score.
- Added focused tests for the new impact fields.

### Why

The Agent already found symbol definitions, references, related tests, and validation commands. This step turns those raw lookup results into measurable impact analysis, which is easier to use for planning edits, explaining risk, and presenting the project as a code-intelligence tool.

### Verification

```text
Targeted validation passed: 23 tests.
```

## 2026-07-20: Quality Gate In Run History UI

### What changed

- `list_run_history()` now supports `quality_gate_status` filtering.
- Run history rows now expose stored quality-gate status, pass state, and summary from the run finish payload.
- Resume-history candidate selection now treats `gate:fail` and `gate:warn` runs as runs that need attention.
- Resume-history labels now show `gate:fail` or `gate:warn` next to validation, unverified, and failed-tool signals.
- Added targeted tests for gate-status filtering and UI resume-history labeling.

### Why

Quality Gate should be searchable from history, not only visible after opening a single run. Filtering and labeling make it faster to find runs that need follow-up and separate self-check health from gate status.

### Verification

```text
Targeted validation passed: 43 tests.
```

## 2026-07-20: Quality Gate In Resume And Self-Improve

### What changed

- `build_resume_context()` now reads stored `quality_gate` data and includes gate checks in the resume prompt.
- Resume priority can now become `resolve_quality_gate_failure` or `review_quality_gate_warnings` when no higher-priority validation/tool issue exists.
- `suggest_self_improvements()` now surfaces recent quality-gate failures and warnings as dedicated improvement candidates.
- Added tests for gate-driven resume priority, gate checks in resume prompts, and gate-driven self-improvement suggestions.

### Why

Quality gate data is only useful if it changes the next action. Routing it into resume and self-improvement makes the gate part of the agent's learning loop instead of a passive report.

### Verification

```text
Targeted validation passed: 13 tests.
```

## 2026-07-20: Quality Gate In Final Trust And Run Logs

### What changed

- Final trust summaries now include a `quality_gate` result with pass/warn/fail status, check list, and compact summary.
- Final response prompts now instruct the model to include the quality gate result alongside validation and residual-risk disclosures.
- Run log summaries now expose the stored `quality_gate` status from `final_trust`.
- `summarize_run_log()` now returns `final_trust` and `quality_gate` from the run finish payload.
- Added focused tests for final-trust prompts, CodeAgent final prompts, run-log summary data, and Run Debug summary display.

### Why

The Quality Gate was available from Run Debug, but final answers also need the same decision signal. Recording and displaying it in final trust and run summaries makes the gate visible at the end of each task and after the run is reopened.

### Verification

```text
Targeted validation passed: 22 tests.
```

## 2026-07-20: Run Review Quality Gate

### What changed

- Added `build_quality_gate(review)` to convert a run review into explicit pass/warn/fail checks.
- Added `format_quality_gate_markdown(review)` to render the gate result as a standalone Markdown panel.
- Wired the Run Debug surface to open `Quality Gate` from the same run log as Review, Bug Report, and Regression Plan.
- Added gate checks for run completion, validation, tool failures, model errors, project-rule health, symbol-impact presence, and review risk flags.
- Added tests for gate pass/fail behavior and the new Run Debug markdown mode.

### Why

Review output is useful, but engineering workflows need a decision layer. Quality gates make the run review actionable by turning the evidence into an explicit pass/warn/fail result.

### Verification

```text
Targeted validation passed: 34 tests.
```

## 2026-07-20: Run Review Bug Report And Regression Plan

### What changed

- Added `format_bug_report_markdown(review)` to turn a run review into a bug report with title, reproduction steps, actual result, expected result, affected files, impacted symbols, suspected cause, suggested fix, and validation evidence.
- Added `format_regression_plan_markdown(review)` to turn a run review into a regression plan with changed-file scope, risk focus, related tests, validation commands, manual checks, and exit criteria.
- Added `Bug Report` and `Regression Plan` actions to the Run Debug trace card next to Summary, Timeline, and Review.
- Routed `_run_debug_markdown(..., "bug_report")` and `_run_debug_markdown(..., "regression_plan")` through the same review payload used by the Review panel.
- Added targeted tests for the new formatters and UI markdown modes.

### Why

Run Review should produce actionable testing artifacts, not only a diagnostic summary. Bug reports and regression plans make each Agent run easier to hand off, review in an interview, or use as test-development evidence.

### Verification

```text
Targeted validation passed: 34 tests.
```

## 2026-07-20: Run Review UI Entry

### What changed

- Added a `Review` action to Run Debug so the structured run review report can be opened from the same debug surface as summary and timeline.
- Wired `_run_debug_markdown(..., "review")` to `build_run_review(run_log_path)` and `format_run_review_markdown(review)`.
- Added UI text for the review action and kept the trace-card buttons in sync with language changes.
- Added a targeted test that verifies the review markdown includes the report title, task, changed path, and model-request summary.

### Why

The structured review layer was already available in code, but it was not reachable from the UI. Exposing it in Run Debug turns the analysis into a usable operator workflow instead of a library function.

### Verification

```text
Targeted validation passed: 32 tests.
```

## 2026-07-18: Run Review Core

### What changed

- Added `kagent/agent/run_review.py` as a structured analysis layer above raw run logs.
- Added `build_run_review(run_log_path)` to aggregate run status, workspace, task, changed paths, validation state, failed tools, model request/error metadata, symbol impacts, project-rule health, risk flags, and recommended next steps.
- Added `format_run_review_markdown(review)` so the same review payload can be exported or shown in future UI panels.
- Added tests for clean completed runs, risk-heavy runs, symbol-impact extraction, and unfinished logs.

### Why

Run logs, self-checks, model metadata, symbol impacts, and project-rule health were useful but scattered. Run Review Core turns one Agent run into a single reusable quality payload, which can support future bug-report generation, regression-test planning, quality gates, UI review panels, and success-rate analytics.

### Verification

```text
Targeted validation passed: 3 tests.
Full validation passed: 202 tests.
```

## 2026-07-17: Project Rules Health In UI Debug

### What changed

- Run Debug summary and timeline now surface `KAGENT.md` rule health through the existing run-log markdown helpers.
- The live Agent trace card now handles `project_rules_check` events and shows a `KAGENT.md rules` entry during a run.
- Tool/event summaries now compact rule health as `health <status>, score <score>, <n> issue(s)`.
- Added UI tests for Run Debug project-rule visibility and trace-summary formatting.

### Why

Rule health was already written to run logs, but users should not need to inspect raw JSONL or plain log summaries to know whether the Agent started with a healthy rules file. Surfacing it in Run Debug and the live trace makes project rules visible in normal UI workflow.

### Verification

```text
Targeted validation passed: 49 tests.
Full validation passed: 199 tests.
```

## 2026-07-17: Project Rules Health In Run Logs

### What changed

- Run log timelines now show `project_rules_check` as `Project rules: <health> score <score>`.
- Timeline details include the top rule issues, such as missing validation commands or missing safety sections.
- Run log summaries now include `project_rules` health, score, issue count, and top issue kinds.
- Extended run-log viewer tests to cover project-rule timeline and summary display.

### Why

The Agent now reads, checks, and injects `KAGENT.md` guidance, but users also need to audit whether a run started with healthy project rules. Surfacing rule health in run logs makes the rules system observable and easier to debug from Activity / Run Debug surfaces.

### Verification

```text
Targeted validation passed: 21 tests.
Full validation passed: 197 tests.
```

## 2026-07-17: Automatic Project Rules Health Warnings

### What changed

- Added `format_project_rules_health_for_prompt` to produce compact model guidance from `check_project_rules`.
- CodeAgent now runs a lightweight `KAGENT.md` health check at startup and injects a warning system message only when rules are missing or incomplete.
- CodeAgent emits a `project_rules_check` event with health, score, issue count, and top issues for run logs and future UI/debug surfaces.
- Added tests for prompt formatting, no-op healthy rules, automatic model-message injection, and event emission.

### Why

The previous step made rules checkable, but the Agent still had to choose to call the tool. Automatic health warnings make the rules system part of planning: incomplete project rules become visible before coding starts, while healthy rules stay quiet and do not waste context.

### Verification

```text
Targeted validation passed: 16 tests.
Full validation passed: 197 tests.
```

## 2026-07-17: KAGENT.md Rules Health Check

### What changed

- Added `check_project_rules` in `kagent/agent/project_rules.py`.
- The checker detects missing `KAGENT.md`, missing required sections, missing concrete validation commands, missing documentation rules, and missing dirty-worktree protection.
- Added a read-only Agent tool `check_project_rules` through `WorkspaceTools`, `tool_schema`, and `CodeAgent._dispatch_tool`.
- The checker returns a health status, numeric score, issue list, and suggested additions instead of editing the rules file automatically.
- Extended project-rules tests to cover missing files, incomplete rules, complete rules, and tool dispatch.

### Why

Reading `KAGENT.md` is useful, but the Agent also needs to know whether the rules file is strong enough to guide real coding work. A health check makes project rules maintainable: future runs can detect missing validation, safety, or documentation guidance before a task drifts.

### Verification

```text
Targeted validation passed: 15 tests.
Full validation passed: 196 tests.
```

## 2026-07-17: KAGENT.md Project Rules System

### What changed

- Added `kagent/agent/project_rules.py` for loading, formatting, clipping, and drafting project-level `KAGENT.md` rules.
- CodeAgent now automatically injects existing `KAGENT.md` content into model system messages before long-term project memory.
- Added read-only Agent tools: `read_project_rules` and `generate_project_rules`.
- The generated rules draft uses project facts, detected validation commands, safety rules, and stable project preferences.
- Added tests for missing rules, prompt formatting, clipping, draft generation, tool dispatch, and model-message injection.

### Why

Long-term project memory is useful for discovered facts, but a coding Agent also needs explicit project rules: coding style, validation workflow, safety constraints, and user/team preferences. `KAGENT.md` gives the project a durable instruction file similar to `AGENTS.md`, making future Agent runs more stable and easier to explain in a resume or interview.

### Verification

```text
Targeted validation passed: 12 tests.
Full validation passed: 193 tests.
```

## 2026-07-17: Symbol Impact In Diff Review And Rollback

### What changed

- CodeAgent now annotates rollback records with matching `symbol_impacts` after symbol-aware edits.
- Rollback history, single rollback previews, session diff previews, and path previews can return impacted symbols.
- Diff Review and rollback detail UI show symbol names alongside changed paths and rollback diffs.
- Rollback preview diff entries include per-file symbol impact metadata.

### Why

Symbol impact already covered planning, validation, repair, and final summaries. Diff review and rollback were the remaining code-review surfaces. Connecting symbol metadata here makes it clear which function/class a rollbackable change belongs to before reviewing or restoring it.

### Verification

```text
72 targeted tests passed.
Full validation passed: 187 tests.
```

## 2026-07-17: Frameless Desktop Window

### What changed

- The main PyQt window now uses a frameless custom title bar.
- Added custom minimize, maximize/restore, and close buttons.
- The custom title bar supports dragging and double-click maximize/restore.
- Added a bottom-right resize grip so the frameless window can still be resized.

### Why

For portfolio and resume demos, the application should feel closer to a polished desktop product instead of a raw Python window with the default OS frame. Removing the system border while keeping expected window controls improves presentation without changing the Agent core.

### Verification

```text
Python syntax check passed for kagent/ui/main_window.py.
UI targeted tests passed: 26 tests.
Full validation passed: 185 tests.
```

## 2026-07-17: Resume Project Showcase

### What changed

- Added `docs/resume-project.md` as a resume-ready project showcase.
- Documented KAgent's positioning, architecture, core workflow, technical highlights, test-development angle, resume bullets, and interview explanation.
- Linked the showcase from the README so the project can be presented more clearly on GitHub and in interviews.

### Why

The user wants KAgent to be strong enough to replace a RenderDoc automation project on a game test-development resume. A dedicated showcase document makes the engineering value easier to understand: local Coding Agent, symbol-level code intelligence, validation automation, failure repair, rollback, run logs, and task resume.

### Verification

```text
Documentation-only change.
```

## 2026-07-17: Symbol Impact Guided Repair

### What changed

- Failure focus can now receive `symbol_impacts`.
- When a failing test is one of a changed symbol's related tests, the Agent also focuses the changed symbol definition.
- Failure focus prompts include symbol repair hints, such as which changed symbol the failing test covers.
- Validation failure prompts now list impacted symbols, definition paths, reference counts, and related tests during repair attempts.

### Why

The Agent could already use symbol impact to plan edits, choose validation, and summarize the run. Repair was still mostly driven by raw failure output. Connecting symbol impact to repair makes failures more targeted: if a related test fails, the Agent is nudged to inspect the changed symbol and its direct test before broad search.

### Verification

```text
58 targeted tests passed.
Full validation passed: 185 tests.
```

## 2026-07-17: Symbol Impact In Final Summaries

### What changed

- Final trust summaries now carry `symbol_impacts`.
- CodeAgent run-finish payloads include impacted symbols for the changed paths.
- Final response prompts now tell the model which symbols were impacted, where they are defined, how many references were found, and which related tests were selected.
- Run-log summaries and display text now include impacted symbol names, definition paths, reference counts, and related tests.

### Why

The Agent could already analyze symbol impact, attach it to change plans, and use it to select validation. The last missing piece was user-facing trust: the final answer and run summary should show that the Agent understood the affected function or class, not just the changed file.

### Verification

```text
34 targeted tests passed.
Full validation passed: 181 tests.
```

## 2026-07-17: Symbol Impact Driven Validation

### What changed

- Validation plans can now receive `symbol_impacts` from recent symbol-aware change plans.
- Python validation commands place symbol-impact validation after syntax checks and before full-suite validation.
- Symbol validation commands preserve the impacted symbol name and `related_reason`, so run logs can explain why a test was selected.
- CodeAgent now passes matching symbol impacts into `build_validation_plan` after content edits.

### Why

The previous step made mutation logs aware of symbol impact, but validation still mostly used changed-file heuristics. This step lets the Agent use symbol-level analysis to choose the most relevant tests first, making coding iterations faster and less blind.

### Verification

```text
52 targeted tests passed.
Full validation passed: 179 tests.
```

## 2026-07-17: Symbol Impact Attached To Change Plans

### What changed

- `AgentRunState` now keeps recent `symbol_change_plan` results during a coding run.
- Mutation change plans match edited paths against symbol definition paths from recent symbol plans.
- Matching plans attach `symbol_impacts` with symbol name, kind, definition path, reference count, related tests, validation commands, and risk summary.
- Run-log timeline titles show the impacted symbol on matching change plans.

### Why

`symbol_change_plan` gave the Agent a focused impact map before editing, but the later mutation log did not show whether that analysis was actually connected to the edit. Attaching symbol impact metadata to `change_plan` links the pre-edit analysis with the real file mutation, making logs easier to audit and making future rollback/test-selection work more precise.

### Verification

```text
37 targeted tests passed.
Full validation passed: 178 tests.
```

## 2026-07-17: Symbol Change Plan Tool

### What changed

- Added `symbol_change_plan` as an Agent tool.
- The plan combines symbol definitions, focused definition contexts, symbol references, test references, related tests, validation commands, and a risk summary.
- The tool helps the Agent move from file-level planning toward function/class-level planning before edits.
- Tool result compaction keeps the primary definition, limited contexts, limited references, related tests, validation commands, summary, and risk metadata.
- The Agent workflow hint now recommends `symbol_change_plan` before changing a known symbol.

### Why

After adding symbol context and symbol references, the next coding improvement is to connect them into a single edit-planning step. This gives the Agent a compact impact map before changing a function or class, improving targeted edits and test selection.

### Verification

```text
Targeted tests cover plan generation, missing-symbol behavior, Agent tool dispatch, schema exposure, and compaction.
```

## 2026-07-16: Symbol Reference Tool

### What changed

- Added `find_symbol_references` as an Agent tool.
- Python references are detected with AST visitors and classified as `import`, `call`, `name_reference`, or `attribute_reference`.
- JavaScript/TypeScript/Go/Rust/Java files use lightweight line scanning for import/call/name/attribute reference hints.
- Reference results mark whether each hit comes from a test file.
- Tool result compaction limits large reference lists and reports total references, omitted references, and test reference count.
- The Agent workflow hint now recommends checking symbol references before changing a known function/class/method.

### Why

`find_symbol_context` helps the Agent read the code it wants to edit. The next step is knowing what depends on that code. Symbol references give the Agent a lightweight impact map before editing, making it easier to choose related tests and avoid breaking callers.

### Verification

```text
Targeted tests cover Python reference classification, test-file marking, Agent tool dispatch, schema exposure, and compaction.
```

## 2026-07-16: Symbol Context Tool

### What changed

- Added `find_symbol_context` as an Agent tool.
- The tool finds class, function, method, import, and language-specific symbols, then returns focused source excerpts around each match.
- Python symbols use AST `end_lineno` when available, so function and class contexts can include the full symbol body plus nearby lines.
- Tool result compaction now clips large symbol excerpts while preserving path, line numbers, container, module, and symbol metadata.
- The Agent workflow hint now recommends `find_symbol_context` before broad file reads when a known symbol is involved.

### Why

The Agent already had symbol search, but it still had to call `read_file` separately to inspect the actual code. Symbol context lookup gives the model precise edit context faster and reduces blind text search or large whole-file reads.

### Verification

```text
Targeted tests cover symbol context extraction, Agent tool dispatch, schema exposure, and tool-result compaction.
```

## 2026-07-16: Rich Edit Change Plans

### What changed

- Mutation tool change plans now include a target summary, intent, risk summary, and validation hint.
- Change plan timeline titles now show the operation and target, for example `Change plan: patch -> kagent/context.py`.
- Change plan timeline details now surface risk or validation guidance instead of only the generic operation.
- Existing pre-mutation behavior is preserved: the plan is emitted before approval and before the tool actually mutates the workspace.

### Why

The Agent already emitted basic `change_plan` events, but they were too terse for review and future selective rollback workflows. Richer plans make edits easier to audit before and after execution, and they create a clearer foundation for human approval, diff previews, and file-level rollback controls.

### Verification

```text
28 targeted tests passed
```

## 2026-07-16: Layered Related-Test Validation

### What changed

- Validation plans now keep a stable command order: syntax check, related tests, then full project validation when available.
- The default validation plan can include four commands, allowing learned validation commands to supplement without replacing the core validation ladder.
- Related test inference now carries a reason, such as matching a changed source file or referencing a changed module/symbol.
- Validation plans include a `selection` object describing the strategy, changed paths, command tiers, related tests, and reasons.
- The run log timeline can show the validation selection strategy for `validation_plan` results.

### Why

The Agent already had related-test inference, but command limits and learned validation commands could make the plan less predictable. This change makes validation more Codex-like: run the fastest relevant checks first, then targeted tests, then full verification, while leaving an audit trail explaining why each test was chosen.

### Verification

```text
22 targeted tests passed
```

## 2026-07-16: Model Request Observability

### What changed

- `create_chat_completion_with_reasoning` can now emit model request lifecycle events.
- CodeAgent writes `model_request`, `model_response`, and `model_error` events into the existing run log.
- Model log events include model name, reasoning effort, stream/tool flags, duration, errors, and whether the request fell back without `reasoning_effort`.
- Run log summaries now show model request counts, fallback counts, and model errors.
- Run log timelines now render model request/response/error entries in readable form.

### Why

After adding model and reasoning controls, the next debugging problem is visibility: the user needs to know what model was actually requested, whether reasoning was sent, and whether the API forced a fallback. Recording this in the existing Agent run log improves trust and makes model-routing issues much easier to diagnose.

### Verification

```text
41 targeted tests passed
```

## 2026-07-16: Persistent Runtime Model Preferences

### What changed

- Added `kagent.ui_preferences` for lightweight UI preference persistence.
- `/model` and `/reasoning` selections are saved to `.kagent_state/ui_preferences.json`.
- The main window restores the saved model and reasoning effort on startup before falling back to `.env` defaults.
- Preference loading tolerates missing files, invalid JSON, unknown models, and invalid reasoning values.

### Why

Model and reasoning switching worked, but the selection was only held in the current window. Persisting the runtime preferences avoids confusing resets after restarting the app and makes model switching feel like a real setting rather than a temporary command.

### Verification

```text
Preference round-trip and fallback tests added.
```

## 2026-07-16: Runtime Model Metadata Prompt

### What changed

- Normal chat requests now add a system metadata message with the actual runtime model and reasoning effort.
- Coding Agent requests now include the same metadata inside the main system context.
- The metadata tells the model to answer model/reasoning questions from the current request settings instead of guessing from defaults or training data.

### Why

After switching models, asking the assistant "what model are you using" could still produce the old default model name because model self-identification is unreliable. The reliable source is the application runtime setting, so kagent now injects that setting into every model request.

### Verification

```text
Targeted tests cover runtime metadata injection for normal chat and CodeAgent.
```

## 2026-07-16: Slash Reasoning Effort Switcher

### What changed

- Added a two-level `/reasoning` slash command for switching reasoning effort.
- The second-level menu exposes `Low`, `Medium`, `High`, and `Extra high` labels, mapped to `low`, `medium`, `high`, and `xhigh`.
- The selected reasoning effort is shown together with the selected model in the chat header/status chip.
- `AgentWorker`, normal chat streaming, title generation, and `CodeAgent` now receive the selected reasoning effort.
- Model requests now retry without `reasoning_effort` if the current API endpoint rejects that parameter, so chat and coding runs keep working.

### Why

The user wanted reasoning intensity to work like model selection, but without crowding the slash command list. A second-level `/reasoning` menu keeps the main command panel readable while making the runtime setting explicit and easy to change.

### API availability check

Using the current configured API endpoint and default model:

```text
gpt-5.4-mini low: OK
gpt-5.4-mini medium: OK
gpt-5.4-mini high: OK
gpt-5.4-mini xhigh: OK
```

### Verification

```text
34 targeted tests passed
```

## 2026-07-15: Two-Level Slash Model Menu

### What changed

- Slash command panel now shows five top-level commands at once.
- `/model` opens a second-level model selection list instead of mixing all models into the top-level command list.
- The slash command panel is taller and uses a scrollbar style consistent with the chat scroll area.

### Why

The model commands made the first slash menu crowded. A two-level menu keeps the main command list readable while still making all model choices accessible.

### Verification

```text
28 targeted tests passed
```

Full validation:
```text
157 passed
```

## 2026-07-15: Slash Model Switcher

### What changed

- Added built-in model options for `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex`, and `gpt-5.2`.
- Slash commands now expose `/model ...` entries using display labels such as `GPT-5.5`.
- Selecting a `/model` command switches the runtime model for both normal chat and coding Agent runs.
- `AgentWorker`, normal chat streaming, title generation, and `CodeAgent` now receive the selected model.

### Model availability check

Using the current configured API endpoint:

```text
gpt-5.5: OK
gpt-5.4: OK
gpt-5.4-mini: OK
gpt-5.3-codex: OK
gpt-5.2: 400 unsupported for the current ChatGPT/Codex account path
```

### Verification

```text
28 targeted tests passed
```

Full validation:
```text
157 passed
```

## 2026-07-15: Slash Command Compact Rows

### What changed

- Slash command suggestions now render each command on one compact row.
- Command descriptions are shown after the command label instead of on a second line.
- The list disables horizontal scrolling and uses tooltips for longer descriptions.

### Why

The first slash command panel could only show about one command at a time. Compact rows make multiple commands visible immediately after typing `/`.

### Verification

```text
24 targeted tests passed
```

Full validation:
```text
156 passed
```

## 2026-07-15: Slash Command Panel Layout Fix

### What changed

- Slash command suggestions now expand the input bar while visible.
- The input bar returns to normal height when commands are hidden, selected, or sent.
- The command list height is capped so it fits above the input box.

### Why

The slash command list could be created but clipped by the fixed-height input bar, making it look like `/` did nothing.

### Verification

```text
24 targeted tests passed
```

Full validation:
```text
156 passed
```

## 2026-07-15: Slash Command Input

### What changed

- Chat input now shows a slash-command suggestion list when the user types `/`.
- Added `/self` to fill the self-improvement suggestion prompt.
- Added `/check`, `/test`, and `/explain` shortcuts for common project prompts.
- Slash suggestions support click selection plus keyboard Enter, Escape, Up, and Down handling.

### Why

Self-improvement should be easy to discover and repeat. Slash commands make coding-agent workflows faster without adding another permanent toolbar button.

### How to use

```text
/
/self
```

Selecting `/self` fills the prompt that asks the Agent to call `suggest_self_improvements`.

### Verification

```text
26 targeted tests passed
```

Full validation:
```text
156 passed
```

## 2026-07-15: Self-Improvement Suggestions Tool

### What changed

- Added a read-only `suggest_self_improvements` Agent tool.
- The tool scans project map data, test mapping, long files, TODO/FIXME markers, and recent run history.
- Suggestions include title, rationale, affected files, recommended action, validation commands, risk, and score.
- The tool is exposed through `WorkspaceTools`, `tool_schema`, and `CodeAgent._dispatch_tool`.

### Why

Before allowing the Agent to modify itself automatically, it needs a safe way to identify small, high-value improvements. This creates the first step of a self-improvement workflow without changing code automatically.

### How to use

```text
请调用 suggest_self_improvements，列出 5 个当前项目最值得做的代码能力优化建议。
```

### Verification

```text
9 targeted tests passed
```

Full validation:
```text
155 passed
```

## 2026-07-15: Activity Child Panel Back Navigation

### What changed

- Added `Back to Activity` navigation to the current diff review dialog.
- Added `Back to Activity` navigation to the resume history dialog.
- Added `Back to Activity` navigation to the rollback history side panel.
- Returning from rollback history first hides the side panel, then reopens Activity.

### Why

Activity is now the parent surface for recovery and review workflows. Child panels should be able to return to that parent instead of forcing users back through the main chat header.

### Verification

```text
23 targeted tests passed
```

Full validation:
```text
153 passed
```

## 2026-07-15: Activity Panel Back Button

### What changed

- Replaced the default Activity dialog close control with an explicit `Back` button.
- Added localized Activity back-button text.
- The button closes the Activity panel and returns the user to the main chat view.

### Why

Activity is becoming a real panel instead of a throwaway dialog. A clear back action makes the navigation model easier to understand before adding deeper in-panel pages.

### Verification

```text
23 targeted tests passed
```

Full validation:
```text
153 passed
```

## 2026-07-15: Activity Current Diff Paths

### What changed

- Activity panel now shows recent current-diff paths under the diff summary.
- The path list reuses `preview_rollback_session` data from the existing rollback preview backend.
- Long path lists are capped and show a `+N more` overflow line.
- Empty diff state now has a direct inline message.

### Why

Activity already showed how many current paths changed. Showing the first few paths makes it usable as a quick change dashboard without forcing users to open the full diff review dialog first.

### Verification

```text
23 targeted tests passed
```

Full validation:
```text
153 passed
```

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

## 2026-07-20: Run Analytics / Failure Trends

### 做了什么

- 新增 `kagent/agent/run_analytics.py`，把多次 run log 汇总成运行趋势分析。
- 统计最近运行的状态分布、健康度分布、质量门禁分布、验证失败率、未验证率、失败工具率和模型错误率。
- 汇总高频 issue code、失败质量门禁检查、失败工具、模型错误、验证命令和最近问题运行。
- 支持按当前 workspace 过滤，避免不同项目的运行趋势混在一起。
- Activity 面板新增运行趋势入口，可以和当前差异、任务恢复、rollback 历史放在同一个活动面板里查看。

### 为什么做

单次 Run Review 能解释“这一次为什么失败”，但项目变大后还需要回答“最近经常失败在哪里”。

Run Analytics 把复盘能力从单次日志扩展到跨运行趋势，后续可以继续接自动改进建议、失败归因、验证命令排序和简历展示。

### 影响模块

- `kagent/agent/run_analytics.py`
- `kagent/ui/main_window.py`
- `tests/test_run_analytics.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证：

```text
python -m pytest -q tests/test_run_analytics.py tests/test_run_history.py
6 passed
```

全量验证：

```text
python -m pytest -q
214 passed
```

### 后续

下一步建议把趋势建议继续接入更具体的失败归因模板，让 Agent 能从“发现趋势”升级到“生成修复计划”。

## 2026-07-20: Self-Improve Trend Signals

### 做了什么

- `suggest_self_improvements` 接入 Run Analytics 聚合结果。
- 自优化建议现在会根据验证失败率、未验证率、失败工具率和模型错误率生成趋势类候选。
- 趋势候选会带上高频质量门禁检查、失败工具、模型错误、最近问题文件和建议验证命令。
- 趋势候选参与统一排序，优先暴露最近反复出现、最影响代码 Agent 稳定性的改进点。

### 为什么做

原来的自优化建议主要看项目结构、TODO、长文件和单次历史运行状态，能发现静态问题，但不够像一个会复盘自己的 Agent。

接入 Run Analytics 后，`/self` 可以基于最近多次运行的失败模式提出优化建议，更适合写成简历亮点：Agent 不只执行任务，还能从运行日志中学习自己的薄弱环节。

### 影响模块

- `kagent/agent/self_improve.py`
- `tests/test_self_improve.py`
- `README.md`
- `docs/agent-development.md`

### 验证

已补充自优化趋势信号测试，覆盖验证失败趋势、失败工具趋势和模型错误趋势。

```text
python -m pytest -q tests/test_self_improve.py tests/test_run_analytics.py tests/test_ui_run_debug.py
39 passed

python -m pytest -q
214 passed
```

### 后续

下一步建议做 Failure Attribution Templates，把常见失败趋势映射成更具体的修复计划模板，例如验证失败、工具失败、模型错误分别生成不同执行方案。

## 2026-07-21: Per-Test Telemetry Foundation

### 做了什么

- 新增 `kagent/agent/test_telemetry.py`，负责 pytest JUnit XML 命令注入、解析和命令归一化。
- 自动验证遇到直接 pytest 命令时，会追加临时 `--junitxml` 输出。
- 验证命令执行结束后会解析 JUnit XML，并为每条用例写入 `test_case_result` 运行日志事件。
- 每条用例记录 `nodeid`、`status`、`duration_ms`、`message`、`failure_type`、`file`、`classname` 和 `name`。
- 额外写入 `test_case_telemetry` 汇总事件，记录本次命令解析到的用例数量、JUnit XML 路径和命令耗时。
- `validation_learning` 和 `run_analytics` 会归一化临时 `--junitxml` 参数，避免历史学习和趋势统计被临时文件路径污染。
- Run Analytics 新增用例总数、用例状态分布、失败用例 Top 和慢用例 Top。

### 为什么做

之前 KAgent 的验证判断主要停留在命令级：只知道 `pytest` 是否返回 0、命令耗时多少、输出摘要是什么。

测试开发岗更看重的是用例级质量数据：哪条用例失败、失败是否重复、哪条用例变慢、是否存在 flaky。Per-Test Telemetry 是后续 flaky 检测、耗时回归和测试看板的地基。

### 影响模块

- `kagent/agent/test_telemetry.py`
- `kagent/agent/code_agent.py`
- `kagent/agent/run_analytics.py`
- `kagent/agent/validation_learning.py`
- `tests/test_test_telemetry.py`
- `tests/test_run_analytics.py`
- `tests/test_validation_learning.py`
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证：

```text
python -m pytest -q tests/test_test_telemetry.py tests/test_run_analytics.py --basetemp C:\tmp\kagent-pytest-telemetry
6 passed

python -m pytest -q tests/test_test_telemetry.py tests/test_validation_learning.py tests/test_run_analytics.py --basetemp C:\tmp\kagent-pytest-telemetry
12 passed

python -m pytest -q --basetemp C:\tmp\kagent-pytest-all
219 passed
```

### 后续

下一步建议做耗时回归检测：基于 `test_case_result.duration_ms` 和命令级 `duration_ms` 计算慢用例、耗时异常上升和验证耗时趋势。

## 2026-07-21: Timing Regression Detection

### 做了什么

- `run_analytics` 新增跨运行 per-nodeid 用例耗时历史聚合：按 nodeid 收集每次 run 的 `duration_ms` 和 `status`，构建跨 run 序列（rows 按最新在前读入，内部反转为最旧在前，再取尾部作为"最新一次"）。
- 新增耗时回归检测 `timing_regressions`：按 nodeid 取最近 `_TIMING_BASELINE_WINDOW`（默认 5）次的中位数作为基线，当最新一次耗时同时满足 `ratio >= 1.5` 且绝对增量 `>= 200ms` 时判定为回归，避免快用例的微小波动被误报。
- 新增趋势方向 `_duration_trend`：把每个 nodeid 的耗时序列分前后两段比中位数，输出 `slower`/`faster`/`stable`，区分"单次尖峰"与"持续变慢"。
- 新增验证命令耗时趋势 `validation_command_trends`：按命令（归一化去掉临时 `--junitxml`）跨 run 收集 `run_command` 的 `duration_ms`，输出样本数、平均、最近平均和趋势。
- 新增 `test_duration_trends`：保留每个用例的耗时序列（截最近 12 个），为后续 pyqtgraph 看板留好数据。
- `format_run_analytics_markdown` 新增 `## Timing Regressions` 和 `## Validation Command Trends` 两节。

### 为什么做

- 测试开发岗看重"耗时回归"这种可量化的质量信号，比单点"最慢用例"更能讲故事：有基线、有倍数、有趋势方向，能回答"哪条用例变慢了、是偶发还是持续"。
- 这是 Per-Test Telemetry 地基的第一个消费方，证明用例级 `duration_ms` 能驱动跨 run 判断，也为 flaky 检测铺路：两者都基于 per-nodeid 跨 run 历史，只是判据从"耗时方差"换成"pass/fail 抖动"。本次顺带在每个样本里存了 `status`，下一步 flaky 可直接复用。

### 影响模块

- `kagent/agent/run_analytics.py`
- `tests/test_run_analytics.py`
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_run_analytics.py
5 passed

python -m pytest -q --basetemp C:\tmp\kagent-pytest-all
221 passed
```

### 后续

下一步建议做 flaky 检测：复用本次建好的 per-nodeid 跨 run 历史 + `status` 序列，判定 pass/fail 抖动（区分持续失败=回归、间歇失败=flaky），以及用 pyqtgraph 把 Run Analytics 从 markdown 文本报告升级为 pass-rate 时序看板 + flaky/耗时回归表。

## 2026-07-21: Flaky Test Detection

### 做了什么

- `run_analytics` 新增 per-nodeid 跨 run pass/fail 历史聚合 `_test_case_run_statuses`：把同一 run 内同一用例的多次结果折叠成一条 run 级 status，**失败优先**（同一 run 内出现失败即记该 run 为 failed），避免重跑通过抹掉 flaky 信号。
- 新增 flaky 判定 `_flaky_tests`：按 nodeid 跨 run 算 pass_count/fail_count/run_count，把"既通过又失败"且 `run_count >= 3` 的用例判为 flaky；全部失败=回归（不算 flaky）、全部通过=稳定（不算 flaky）。
- 每个 flaky 用例输出 pass_rate、最近窗口失败数、最近状态、首次失败 run，便于定位"从第几次开始抖"。
- `format_run_analytics_markdown` 新增 `## Flaky Tests` 节。
- 复用 Step 2 已建好的跨 run per-nodeid 基础设施，flaky 是薄薄一层增量。

### 为什么做

- flaky 检测是测试平台工程师的招牌交付物，测试开发/游戏测试开发招聘方会专门扫这个关键词。
- 它和耗时回归共享同一个 per-nodeid 跨 run 数据底座：耗时回归判"耗时方差"，flaky 判"pass/fail 抖动"，两者一起讲反而最强——耗时回归给即时信号，flaky 给招牌词。
- 复用用户 RenderDoc 的"采集→聚合→找不稳定信号"方法论，作用在测试用例上而非帧，互补不重复图形调试背景。

### 影响模块

- `kagent/agent/run_analytics.py`
- `tests/test_run_analytics.py`
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_run_analytics.py
8 passed

python -m pytest -q --basetemp C:\tmp\kagent-pytest-all
224 passed
```

### 后续

下一步建议用 pyqtgraph 把 Run Analytics 从 markdown 文本报告升级为可视化看板：`test_duration_trends`/`validation_command_trends` 已返回可绘制的耗时序列，再加 flaky 用例表和 pass-rate 时序曲线；之后可加 JUnit XML 导出供 CI（Jenkins/GitLab）消费，以及 mypy/ruff 工程门。

## 2026-07-22: Run Analytics Visual Dashboard

### 做了什么

- `run_analytics` 新增 `run_pass_rate_series`：在主循环复用已遍历的 `test_case_counts`，顺手记录每 run 的 `run_id`/`ts`/`total`/`passed`/`failed`/`pass_rate`（rows 本身是 newest-first，序列也保持 newest-first），不新增独立分析函数。
- `_show_run_analytics`（`main_window.py`）把原来的单个 `QTextBrowser.setHtml(markdown)` 替换为 pyqtgraph 看板：垂直 `QSplitter` 三组件——pass-rate 时序折线（x = run 索引，旧→新；y = pass_rate×100）、flaky 用例 `QTableWidget`（nodeid/pass/fail/runs/pass%/recent/首次失败 run）、耗时回归 `QTableWidget`（nodeid/current/baseline/ratio/+delta/trend），全部直接喂 `build_run_analytics(limit=80)` 已返回的 `run_pass_rate_series`/`top_flaky_tests`/`timing_regressions`，零新分析逻辑。
- pyqtgraph 用延迟 import，缺失时优雅回退到原 `QTextBrowser` markdown 视图，保证看板在任何环境都能打开。
- `requirements.txt` 新增 `pyqtgraph>=0.13.0`（纯 Python wheel，Qt 原生，已在当前 PyQt6 环境验证 PlotWidget 可用、无 native 依赖坑）。

### 为什么做

- 这是项目此前"最显眼且 5 秒内被识破的可见短板"：flaky/耗时回归/趋势分析算法都已落地，但 Run Analytics 打开就是一篇 markdown 文本（`QTextBrowser.setHtml`），与简历宣称的"测试分析平台"有可见落差。
- 一轮 5-agent workflow（2 个测试开发招聘视角 + AI portfolio 视角 + 专门质疑看板的红队 + 综合）裁定 do-now：底层数据已足够丰富（flaky 跨 run 历史 + per-nodeid 耗时时序 + timing 回归比率基线），"图表光靠计数器就是涂口红"的警示在此刻不成立，把 markdown 换成真看板是把已沉没的 Step1-3 投资变现成面试官 5 秒能 get 的可视化测试平台。
- 红队的两点反对意见（零新能力维度、极简依赖仓库加 pyqtgraph 偏重）被采纳为硬约束而非否决：3 组件上限、不加新分析/交互/配色、pyqtgraph 先验证 import 再加、缺失自动回退。

### 影响模块

- `kagent/agent/run_analytics.py`
- `kagent/ui/main_window.py`
- `requirements.txt`
- `tests/test_run_analytics.py`
- `tests/test_ui_run_debug.py`
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_run_analytics.py tests/test_ui_run_debug.py
42 passed

python -m pytest -q
227 passed
```

> 注：pyqtgraph 0.14 在 pytest 的 offscreen Qt 平台下，构建真实 PlotWidget 后进程退出会 segfault，因此看板 widget 构建用 offscreen 手动冒烟验证（已确认 QSplitter 三组件 + 行数据正确 + 回退路径），pytest 内只测 `_flaky_rows`/`_timing_regression_rows` 纯函数与回退条件，避免崩溃污染全量。

### 后续

下一步建议做 JUnit XML 导出：把 Step1 已解析的 per-test 数据反向导出标准 `<testsuite>` XML + 无头验证 runner，喂 Jenkins/GitLab/Unity-CI，形成"看得见的平台（可视化）+ 接得上的 CI（集成）"组合；之后可加 mypy/ruff 工程门、自动生成未测符号测试脚手架。

## 2026-07-23: JUnit XML Export

### 做了什么

- 新增 `kagent/agent/junit_export.py`：`build_junit_xml(run_log_path)` 读取 run log 的 `test_case_result` 事件，组装标准 JUnit XML `<testsuite>`——每条用例一个 `<testcase>`（classname/name/time），失败用例加 `<failure>`/`<error>` 子元素（带 type/message），skipped 加 `<skipped>`；按 nodeid 去重；suite 的 tests/failures/errors/skipped 计数按实际 testcase 重算。
- 无 per-test 事件时（验证未跑或用了非 pytest 脚本命令）回退为单个运行级 `<testcase>` 摘要：按 `validation_failed`/run status 决定是否 failure，使导出在任何情况下都是合法、CI 可消费的 JUnit 文档。
- `run_history.py` 新增 `export_run_junit_xml(run_id_or_path)` 和 `export_latest_run_junit_xml()`，与既有 `export_run_markdown` 平行；可按路径或 run id 解析。
- Run Analytics 看板新增「Export JUnit XML」按钮：弹保存对话框，写 `export_latest_run_junit_xml()` 结果并提示路径。
- 顺带修复了一个上轮看板提交埋下的结构 bug：4 个看板辅助函数（`_run_analytics_dashboard_widget` 等）误插在 `ChatWindow` 类中间，把 `_show_run_analytics` 等后半段方法截断成孤立嵌套函数（点 Run Analytics 会崩）。已将辅助函数移到文件末尾模块级区，ChatWindow 方法恢复连续。

### 为什么做

- 闭合 kagent「只消费 `--junitxml` 却不产出 JUnit XML」的单向不对称：`test_telemetry` 解析 junitxml，但没有对称导出，per-test 遥测无法接进 CI。
- 这是 per-test 遥测路线（Step 1-4）的自然下游、也是「看得见的平台（可视化）+ 接得上的 CI（集成）」组合的后半句。测试开发/游戏测试开发岗每天面对 JUnit/Unity-Test-Runner pipeline，导出层信号零歧义。
- RAG 评估还发现：269 条历史 run log 均无 `test_case_result`/`symbol_impacts` 事件（kagent 自身验证走 `verify.ps1`，被 `_looks_like_direct_pytest` 排除）。本步把导出能力建在「读 run log 的 test_case_result 事件」上，未来 run 触发 pytest 遥测即可自动有可导出数据；并为之后的 RAG failure-memory 预留了语料落盘路径。

### 影响模块

- `kagent/agent/junit_export.py`（新增）
- `kagent/agent/run_history.py`
- `kagent/ui/main_window.py`
- `tests/test_junit_export.py`（新增）
- `tests/test_run_history.py`
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_junit_export.py tests/test_run_history.py
12 passed

python -m pytest -q
235 passed
```

### 后续

下一步可选：真实覆盖率（替换 `validation.py:514-523` 硬编码 coverage_bonus）、测试生成（为 `related_test_count==0` 符号生成 pytest 脚手架）、mypy/ruff 工程门；以及排在这些之后的 rag-failure-memory（需先验证 JSONL「符号→失败→修复」三元组语料密度）。

## 2026-07-23: Test Generation Tools (gentest)

### 做了什么

- 新增 `kagent/agent/test_gen.py`：
  - `find_untested_symbols(root)` 用 `build_symbol_index` + `project_map.source_to_tests` 做 file-level 覆盖缺口扫描——返回"定义所在源文件没有对应测试文件"的产线函数/类/方法（O(项目大小)，不是 O(符号×引用)），附 `suggested_test_path`。跳过 dunder/私有符号和 `import`/`const` 等不适用 kind。
  - `generate_test_scaffold(root, symbol_info)` 读源文件 AST，取可测符号，生成 pytest 脚手架：导入被测模块（正确保留 `kagent` 包名、只剥 `src`/`app` 前缀）+ 每个符号一个占位 `def test_x`（带 TODO 提示 + `assert True` 占位，不编造假断言以免虚假信心）+ 建议测试路径。
- 注册两个只读 agent 工具（`INSPECTION_TOOLS`）：`list_untested_symbols` 列未测符号、`scaffold_test_for_symbol` 生成脚手架内容（不自动写文件，需 `write_file` 保存 + `run_command` 用 `pytest --collect-only` 验证可发现）。
- 验证回路：脚手架生成后用 `pytest --collect-only` 确认能被发现（见测试），保证不产出废脚手架。

### 为什么做

- 这是「双向共享」第一优先：测试开发岗读作"AI 帮你写测试 / 测试左移"，AI 岗读作"AI 代码生成"，是两个求职方向都打高分的能力。
- 信号现成：`symbol_change_plan.py:163` 已对单符号算 `related_test_count==0` 并惩罚"有产线引用但零测试"，但该信号从未被全项目暴露或利用。gentest 把它从"惩罚信号"升级为"生产动作"。
- 设计取舍：脚手架只生成结构 + TODO 占位，不编造具体断言——生成的假断言会带来虚假信心，不如让 Agent/人填真实预期行为。验证回路只验"可被发现"，不验"通过"。

### 影响模块

- `kagent/agent/test_gen.py`（新增）
- `kagent/agent/tool_schema.py`
- `kagent/agent/code_agent.py`
- `tests/test_test_gen.py`（新增）
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_test_gen.py
5 passed

python -m pytest -q
240 passed
```

### 后续

下一步做上下文工程叙事（零代码，把已有 context 压缩/工具输出截断/项目记忆/跨会话摘要重新框成「上下文工程」写进 README+简历），之后真实覆盖率，再 rag-failure-memory。

## 2026-07-23: Context Engineering Narrative

### 做了什么

- 纯文档变更，无代码改动。把 kagent 已有的四件上下文治理能力统一框成「上下文工程（context engineering）」叙事，写进 README 能力条。
- 四件能力及其代码锚点（均已存在，本次只是显性化）：
  1. 会话级压缩：`kagent/context.py:58 manage_context` 按 `CONTEXT_MAX_TOKENS`（`config.py:27`，默认 24000）水位压缩旧消息、保留近期关键对话，每次 LLM 请求触发并发出 "Context compacted (X -> Y tokens)" 事件。
  2. 按工具粒度截断：`kagent/agent/tool_result_context.py` 对 read/search/list/symbol/command 各设上限（DEFAULT_TEXT_LIMIT=8000、READ_FILE_CONTENT_LIMIT=12000、COMMAND_STREAM_LIMIT=6000、SEARCH_MATCH_LIMIT=20 等），带 omitted 计数与 `context_compacted` 标志。
  3. 长期项目记忆注入：`kagent/agent/project_memory.py` 按工作区保存项目结构摘要/入口/配置/常用验证命令/稳定偏好，每次运行注入 system prompt。
  4. 跨会话滚动摘要：`kagent/db.py context_summaries` 表 + `prepare_session_history` 在恢复时把持久化摘要折叠回 prompt。

### 为什么做

- 「上下文工程」是 2026 AI Agent 的核心议题（RAG 的议题已转向上下文工程），而 kagent 这四件能力本就是上下文工程——只是之前分散叫"上下文管理/工具输出压缩/长期记忆"，没有统一成这个热词叙事。
- 这是双向共享第二步、且零代码：测试开发岗读作"长任务稳定性"，AI 岗读作"上下文工程"（2026 热词）。把已有能力显性化即可拿到一个 AI 工程叙事点，无需新增依赖或逻辑。

### 影响模块

- `README.md`（能力条重写）
- `docs/agent-development.md`（本块）
- 简历草稿（见下）

### 简历草稿（中文）

> 实现上下文工程：会话级按水位压缩旧消息并保留近期关键对话、按工具粒度截断工具输出（带 omitted 计数）、按工作区注入长期项目记忆、跨会话持久化滚动摘要并在恢复时折叠回 prompt，避免长任务上下文膨胀与重复扫描。

### 后续

下一步做真实覆盖率（替换 `validation.py:514-523` 硬编码 coverage_bonus 为真 coverage.py + 趋势 + 回归 gate），再 rag-failure-memory。

## 2026-07-23: Real Coverage Measurement

### 做了什么

- 新增 `kagent/agent/coverage.py`：
  - `measure_coverage(root)` 用 `coverage run -m pytest` + `coverage json`（写临时文件再读，因 `-o=-` 不支持 stdout）拿真实 line_rate/branch_rate/covered_lines/num_statements/missing_lines；无测试或失败时返回 None 不崩。
  - `save_coverage_snapshot` 持久化到 `.kagent_state/coverage_history.json`（最多 50 条）；`coverage_trend` 比最近 vs 历史均值；`coverage_regression_gate` 在最近覆盖率比基线低 ≥3% 时判 warn。
- `validation.py` 修复假指标：`_validation_command_rank` 不再按 label 写死 `+0.18/+0.14/+0.08` 的 `coverage_bonus`，改为按模块级缓存的**真实 line_rate** 给全量/pytest suite 命令加分（`real_rate * 0.18`）；新增 `set_recent_coverage_rate` / `_coverage_rate_for_ranking` 缓存接口。
- 新增只读 agent 工具 `measure_coverage`：跑 coverage + 存 snapshot + 设缓存 + 返回 `{coverage, trend, gate}`，让 agent 按需触发并把真实覆盖率喂给后续验证排序。
- `requirements.txt` 加 `coverage>=7.4`。

### 为什么做

- 修一个真实存在的假指标：`validation.py:514-523` 旧 `coverage_bonus` 是写死的标签加分，根本没量真实覆盖率，面试官追问"覆盖率怎么算的"就露馅。换成真 coverage.py 是把假信号变真信号。
- 闭合测试平台叙事：per-test 遥测 → JUnit 导出 → 真实覆盖率 + 回归 gate，是测试开发岗的标准三件套。
- 这是双向共享第三步、偏测试开发纵深：测试开发岗看"覆盖率治理 + 回归 gate"，AI 岗看"agent 自我度量"。

### 影响模块

- `kagent/agent/coverage.py`（新增）
- `kagent/agent/validation.py`
- `kagent/agent/tool_schema.py`
- `kagent/agent/code_agent.py`
- `requirements.txt`
- `tests/test_coverage.py`（新增）
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_coverage.py
5 passed

python -m pytest -q
245 passed
```

### 后续

下一步做 rag-failure-memory（需先验证 JSONL「符号→失败→修复」三元组语料密度）。

## 2026-07-23: Quality Gate Hardening

### 做了什么

- **统一两套 quality gate**：之前 `run_review.build_quality_gate`（9 检查、事后复盘）和 `final_trust.build_quality_gate_summary`（4 检查、runtime 写入 run_finish、被历史表/Run Analytics 趋势回显）使用不同的检查 code（复盘用 run_completed/changes_validated/validation_passed/tool_failures_recovered；runtime 用 run_completed/trustworthy/validation_recorded/validation_result），导致历史表 gate=pass 的 run 复盘报告可能出 warn。现将 runtime gate 的检查 code 对齐到复盘版（run_completed/changes_validated/validation_passed/tool_failures_recovered），去掉 misaligned 的 trustworthy/validation_recorded/validation_result，消除两套 gate 的命名与项数不一致。
- **coverage 进 gate**：`build_final_trust_summary` 新增 `coverage_gate` 参数；`build_quality_gate_summary` 新增 `coverage_regression` 检查——当 `coverage_regression_gate` 判 warn 时，gate 整体降为 warn 并附 message。`code_agent._final_trust_summary` 通过新增的 `_coverage_gate()` 从 `coverage_trend`+`coverage_regression_gate` 读取持久化的覆盖率趋势并传入。闭合了"覆盖率只量不门禁"的半成品：覆盖率回归现在真的能影响质量门状态，且经 final_trust 写入 run_finish → 历史表/趋势自动展示。

### 为什么做

- 这是 overview 文档自己点名的已知技术债：两套 gate 不一致会让面试官追问"为什么历史表说 pass、复盘说 warn"时答不上。统一它体现工程成熟度（能发现并修自己系统的内部不一致）。
- 覆盖率功能做完后只量不门禁，是半成品——"覆盖率 gate"没真 gate 任何东西。接进 quality gate 才让 coverage 这条线真正闭环。

### 影响模块

- `kagent/agent/final_trust.py`（build_final_trust_summary + build_quality_gate_summary）
- `kagent/agent/code_agent.py`（_final_trust_summary + _coverage_gate）
- `tests/test_final_trust.py`（gate code 对齐 + coverage warn 测试）
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_final_trust.py
8 passed

python -m pytest -q
253 passed
```

### 后续

下一步可选：tool 参数 JSON-Schema 运行时校验（code_agent.py 只 json.loads 不校验 schema）、mypy/ruff 工程门、gentest 验证回路增强。

## 2026-07-23: Tool Argument Schema Validation

### 做了什么

- `tool_schema.py` 新增 `validate_tool_args(name, args) -> list[str]`：用 `jsonschema.Draft202012Validator` 按工具声明的 `parameters` JSON-Schema 校验——required 缺失、类型错、additionalProperties 违反、min/max/enum 越界都能抓；未知工具不校验（返回 []，避免新工具没接 schema 时阻断 dispatch）；非 dict args 直接报错。用 `lru_cache` 缓存 name→schema，避免每次调用重算 22+ 工具 schema。
- `code_agent.py` 在 `json.loads` 成功后、`_execute_tool_action` 前插入校验：schema 校验失败则发 tool_start 事件 + 构造 `{ok: False, error: "Invalid tool arguments: ...", validation_errors: [...]}` 结果，**不执行工具**，复用现有 `invalid_arguments` 恢复提示路径让模型修参数重试。
- `requirements.txt` 加 `jsonschema>=4.20`。

### 为什么做

- 之前 `tool_schema.py` 声明了完整 JSON-Schema（type/required/additionalProperties/min/max/enum），但 `code_agent.py` 只 `json.loads` 解析、从不按 schema 校验——schema 是"声明但不强制"的死契约。模型瞎传参（缺 required、类型错、传未声明参数）会一路打到工具实现里才报错，错误信息不友好。
- 接 jsonschema 校验把"声明"变成"运行时强制"：失败在 dispatch 前拦截，给模型结构化的"哪个参数什么错"提示。叙事是"运行时输入契约校验 / 测试左移"——和测试开发的"契约测试 / 输入校验"同构，且强化"工具安全"支柱。

### 影响模块

- `kagent/agent/tool_schema.py`（validate_tool_args + lru_cache）
- `kagent/agent/code_agent.py`（json.loads 后插入校验）
- `requirements.txt`
- `tests/test_tool_schema_validation.py`（新增）
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_tool_schema_validation.py
9 passed

python -m pytest -q
262 passed
```

### 后续

下一步可选：mypy/ruff 工程门（替换 verify.ps1 的 compileall+pytest-only）、gentest 验证回路增强、真实 run 积累 failure-memory 语料。

## 2026-07-23: Test Failure Memory (RAG failure-memory)

### 做了什么

- 新增 `kagent/agent/failure_memory.py`：
  - `collect_failure_corpus(runs_dir)` 扫 run log，把每个 run 的 `test_case_result`(失败) 与同 run 的 `symbol_impacts` + `change_plan` 关联成 `FailureRecord`（run_id/nodeid/status/failure_type/message/symbols/fix_hint），按 nodeid 去重。
  - `FailureMemoryIndex` 用 TF-IDF + 余弦相似度（纯 Python，无外部 embedding 依赖、离线可复现）索引 FailureRecord 文本（nodeid + failure_type + message + symbols）。
  - `recall_similar_failures(query, k)` 召回 top-k 历史相似失败 + 当时变更意图；语料 < 3 条时诚实返回 `insufficient_corpus`，不假装召回。
- 语料发射层：`code_agent` 在 `symbol_change_plan` 成功后新增 `_emit_symbol_impacts_event`，把 symbol + related_tests + risk 落盘成独立 `symbol_impacts` 事件（之前只在 tool_result 里，不可索引），为 failure-memory 提供可检索语料。
- 注册只读 agent 工具 `recall_similar_failures`，验证失败修复循环中可调用注入"上次类似失败怎么处理"。

### 为什么做

- 这是「双向共享」第四步、偏 AI 工程维度：测试开发岗读作"测试失败知识库 / triage"，AI 岗读作"语义检索 / RAG"。是唯一能化解"RAG 通用、低 test-dev 价值"批评的 RAG 变体——语料是 kagent 自己的测试运行日志，召回目标是测试失败与修复。
- 诚实取舍：RAG 评估发现真实 run log 的「符号→失败→修复」三元组语料基本为空（269 条 run 里 symbol_impacts/change_plan=0，只有测试代码造的假失败数据）。所以本步先做**基础设施层**：补 symbol_impacts 发射层让未来真实 run 积累语料 + 建检索框架（含 insufficient_corpus 守卫），而非硬做一个会反伤简历的 toy RAG。语料随真实 run 积累后召回自动生效。
- 用文本相似度（TF-IDF）而非 embedding API 的取舍：单开发者工具语料小、要求离线可复现、无外部 API 依赖；待语料规模上来再评估是否升级 embedding。

### 影响模块

- `kagent/agent/failure_memory.py`（新增）
- `kagent/agent/code_agent.py`（symbol_impacts 发射层 + recall 工具）
- `kagent/agent/tool_schema.py`
- `tests/test_failure_memory.py`（新增）
- `README.md`
- `docs/agent-development.md`

### 验证

已完成针对性验证和全量验证：

```text
python -m pytest -q tests/test_failure_memory.py
5 passed

python -m pytest -q
250 passed
```

### 后续

四步路线（gentest → 上下文工程叙事 → 覆盖率真实化 → RAG failure-memory）全部完成。后续可：让真实 run 积累 failure-memory 语料后评估召回质量；mypy/ruff 工程门；coverage gate 接入 quality_gate。

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
