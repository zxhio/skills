---
name: task-workflow
description: "Lead repository work through a persistent task brief with separate planning, execution, continuation, review, and optional commit phases. Use when the user asks to plan or split a goal into tasks, create or update a task brief, act as lead agent, execute or continue a planned goal, coordinate builders and reviewers, close review findings, or execute and commit. Trigger phrases include 规划这个目标, 执行这个目标, 继续这个目标, 执行并提交这个目标, task brief, 拆分 task, and lead agent."
---

# Task Workflow

以 task brief 作为目标、任务状态和验收结果的单一工作记录。保持规划与执行分离，按任务风险动态安排 builder 和 reviewer，并让 review 发现的问题形成闭环。

## 选择动作

按用户的明确措辞选择动作：

| 动作 | 行为 | 结束状态 |
| --- | --- | --- |
| 规划 | 创建或更新 task brief，拆分任务，不实现目标 | brief 为 `Planned` |
| 执行 | 按 brief 实现、更新状态并完成 review | 不创建 Git 提交 |
| 继续 | 查找当前未完成 brief，从已有状态继续执行 | 不创建 Git 提交 |
| 执行并提交 | 执行、review 闭环并完成提交前检查 | 创建 Git 提交 |

- 用户明确指定 brief 路径或动作时，以该指令为准。
- 用户只要求“规划”或“先拆任务”时，写完 brief 后停止。
- 用户没有明确要求提交时，在 review 完成后交付结果，保留工作区变更。
- 用户同时要求规划和执行时，可以在同一轮先完成 brief，再进入执行。

## 定位 task brief

1. 读取当前仓库指令和工作区状态。
2. 获取当前 Git 分支，并优先搜索 `.workflow/local/<branch>/`；遵循仓库已有的分支目录和文件命名方式。
3. 按以下优先级选择 brief：用户给出的路径、与目标名称匹配的 brief、当前分支下唯一未完成的 brief。
4. 多个未完成 brief 都可能匹配时，列出候选并请用户选择。
5. 执行动作没有可匹配的 brief 时，先创建 brief；若用户未同时授权执行，停在规划结果。

`.workflow/local/` 被 Git 忽略时仍正常读写；brief 是本地工作状态，不因忽略提交而改换位置。

## 规划

先检查与目标相关的代码、配置、文档、脚本和现有约定，再编写 brief。使用仓库现有格式；新 brief 默认放在：

```text
.workflow/local/<branch>/<YYYYMMDD>-<goal-slug>.md
```

brief 至少包含：

```markdown
# <Goal title>

- Branch: `<branch>`
- Task: `<task-id>`
- Status: Planned

## Goal

<完成后的可观察结果>

## Execution Boundary

- <包含的范围>
- <保持不变的边界>

## Tasks

### T01 — <task>

- Status: Pending
- <实现责任>

Completion:

- <可验证完成条件>

## Verification

- <与风险和改动直接相关的检查>

## Execution Order

<依赖或可并行关系>
```

- 按可独立实现和验收的责任边界拆分 task，不为简单目标制造额外层级。
- 每个 task 写清责任、依赖和完成条件；把跨任务整体验收作为独立 task 或最终 review。
- brief 记录目标、约束、决定和结果，不记录中间推理或临时探索过程。
- 规划阶段只修改 brief，不实现产品代码、配置或正式文档。

## 执行

1. 将 brief 总状态更新为 `In Progress`。
2. 按依赖顺序选择可执行 task；互不依赖且文件责任清晰的 task 可以并行。
3. 为每个 task 标记 `In Progress`，实现后执行与其改动直接相关的检查。
4. 对完成实现的 task 进行 review。相关 task 可以合并 review；高风险、边界复杂或相互影响的变更使用独立 reviewer。
5. review 有 finding 时，将问题交回合适的 builder 修正，然后复审受影响范围。
6. 实现、检查和 review 均通过后，才将 task 标记为 `Completed`。
7. 所有 task 完成后执行整体 review 和 brief 中的最终验证，再将 brief 总状态更新为 `Completed`。

发现阻塞时，在 brief 中记录可观察的阻塞条件和剩余 task；能够继续其他独立 task 时继续推进。

## 协作

- Lead 负责拆分任务、分配文件责任、维护 brief、处理依赖和汇总结果。
- Builder 只负责边界明确的实现任务；说明其文件或模块责任，并提醒其保留其他人的并行改动。
- Reviewer 独立检查具体 diff 或一组已完成 task，按严重度报告 findings；默认不代替 builder 修改代码。
- 根据任务规模选择本地完成或委派。简单 task 不强制启动子 agent；复杂目标可以形成多轮 builder → reviewer → builder。
- Review 以 finding 闭环为目标，不以固定 agent 数量或固定轮次为目标。
- 只有 Lead 更新 task brief，避免并行写入产生状态冲突。

## 提交

仅在“执行并提交”或用户另行明确要求时提交：

1. 确认所有 task 和 review findings 已闭环。
2. 执行仓库规定的提交前检查，并复核最终 diff 和提交范围。
3. 保留用户已有及无关变更，不把它们混入提交。
4. 创建与完成目标对应的 Git 提交，并在交付中报告 commit。

## 交付

简要报告：

- task brief 路径与最终状态；
- 完成的 task 和 review 结果；
- 执行的验证及未执行项；
- 工作区是否保留未提交变更，或已创建的 commit。
