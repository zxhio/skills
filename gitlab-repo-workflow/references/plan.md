# Brief 规则

本文件只负责复杂计划的 brief、task、review、验证、计划状态和提交范围；不定义 worktree 命令或 Git 交付命令。

brief 是复杂计划的 task、review、验收和交付状态记录。简单任务直接使用 Git 生命周期。

## 内容

- [路径和查找](#路径和查找)
- [模板](#模板)
- [Task 和 review 规则](#task-和-review-规则)
- [提交规则](#提交规则)
- [计划状态](#计划状态)

## 路径和查找

```text
~/.workflow/<repo>/<line>/<topic>/<YYYYMMDD>-<goal-slug>.md
```

- `repo` 使用主 checkout 的仓库名；同名仓库追加 origin 项目路径。
- `line` 使用 `main`、`dev/<ver>` 或 `release/<ver>`。
- `topic` 使用完整需求分支路径；合入线上的维护任务可以省略。
- 日期使用 `YYYYMMDD`，goal slug 使用稳定的小写短横线文本。

按用户指定路径、目标匹配、当前 line/topic 下唯一活动 brief 的顺序选择记录。多个候选由用户选择。复杂任务执行缺少 brief 时先创建，规划结果为 `Planned`。

## 模板

```markdown
# <Goal title>

- Repo: `<repo>`
- Line: `<line>`
- Branch: `<working-branch>`
- Task: `<task-id>`
- Status: `Planned`
- Worktree: pending
- Base: pending
- Base SHA: pending
- Slot: pending
- Commit Scope: `plan`
- Commit Status: `Pending`

## Goal

<完成后的可观察结果>

## Execution Boundary

- <包含的范围>
- <保持稳定的范围>

## Tasks

### T01 — <task>

- Status: `Pending`
- Owner: <责任人>
- Dependencies: none
- Priority: `P0`
- Risk: `Medium`
- Review: `required`
- Review Group: `R01`

Completion:

- <可验证的完成条件>

## Verification

- <任务级验证>
- <整体验证>

## Review Groups

### R01 — <review 范围>

- Tasks: T01, T02
- Status: `Pending`
- Reviewer: <责任人>

Completion:

- <review 通过条件和 finding 闭环条件>

## Execution Order

- T01 完成后执行 T02。

## Commits

- Scope: `plan`
- plan: pending

## Review Findings

- None

## Delivery

- Push: pending
- MR: pending
- Merge: pending
- Cleanup: pending

## Result

<完成后填写结果>
```

## Task 和 review 规则

- 简单任务跳过 brief；复杂目标按可独立实现和验收的责任边界拆分。
- 每个 task 记录责任、依赖、Priority、Risk、Review 和可观察完成条件。
- Priority 使用 `P0`、`P1`、`P2`；Risk 使用 `High`、`Medium`、`Low`。
- 共享文件或状态的 task 串行执行；依赖满足且责任独立的 task 可以并行。
- task 依次经过 `Pending`、`In Progress`、`Review`、`Completed`。
- review group 依次经过 `Pending`、`In Progress`、`Completed`；group 完成后，其 task 一起更新为 `Completed`。
- `Review: none` 在任务级验证通过后完成；`Review: optional` 由 lead 自检，也可以加入 review group；`Review: required` 进入 review group 并完成独立 review。
- review group 可以包含一个或多个 task。
- 跨 task 验收写入最终验证，整体 review 作为计划级 `Review` 阶段。

## 提交规则

- `Commit Scope: plan` 将所有 task 的改动合并为一个 commit，使用 `plan` 记录 SHA。
- `Commit Scope: task` 为每个 task 创建独立 commit，使用 task ID 记录 SHA。
- `Commit Status` 使用 `Pending`、`Partial`、`Complete`。

## 计划状态

```text
Draft -> Planned -> In Progress -> Review -> Verified -> Committed
     -> Pushed -> MR Created -> Merged -> Closed
```

- 所有 task review group 完成后进入计划级 `Review`。
- 整体 review、最终验证和 findings 闭环后进入 `Verified`。
- `Commit Status: Complete` 且提交范围满足后进入 `Committed`。
- 需求分支推送、MR 创建、MR 合并和 worktree 释放后，依次进入 `Pushed`、`MR Created`、`Merged`、`Closed`。
- `Blocked` 记录阻塞条件、剩余 task 和恢复步骤；解除后回到原阶段。
- `Cancelled` 表示用户取消计划。
