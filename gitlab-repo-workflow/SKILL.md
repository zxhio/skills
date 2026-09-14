---
name: gitlab-repo-workflow
description: "Drive GitLab repository tasks: plan the goal, pick a simple or complex plan, create or attach a task worktree, execute and review code, and verify results. By default stop after verification with changes left uncommitted; commit, push, create a merge request (MR) via glab or the GitLab API, and close the plan each require explicit user request. Only for repositories whose origin is GitLab; trigger when the user asks to plan, resume a plan, work on a new or existing branch, commit, push, create a GitLab MR, or manage the Git worktree lifecycle. Do not use for GitHub or other platforms."
---

# GitLab Repo Workflow

驱动 GitLab 仓库任务：按用户措辞确定执行范围，在独立 worktree 中实现，按授权逐级交付。

## 动作

| 动作 | 措辞 | 范围 |
| --- | --- | --- |
| 规划 | “规划”“先拆任务” | 步骤 1–2 |
| 执行（默认） | “实现”“修复”“继续” | 步骤 1–4 |
| 提交 | 加“提交” | +步骤 5 |
| 推送 | 加“推送” | +步骤 6 |
| 建 MR | 加“建 MR” | +步骤 7 |
| 关闭 | MR 合并后“关闭”“清理” | 步骤 8 |

未明确提及的动作不执行：默认停在未提交变更；推送以提交为前提，MR 以推送为前提；“交付”可一次授权多步。交付报告说明停在哪一步、剩余动作各需要什么措辞授权。

## 步骤

0. **适用范围**：主 checkout 的 origin 必须是 GitLab，否则告知用户后停止。
1. **计划**：默认简单计划，只记目标、范围和验收；用户提到 `brief` 时用复杂计划，按 [`references/plan.md`](references/plan.md) 创建或恢复 brief。规划前先读仓库根 `AGENTS.md`、本次范围文档和相关代码约定。“继续”从 brief 或任务记录恢复，自首个未完成步骤开始。
2. **分支**：确定合入线和需求分支；复杂计划写入 brief。
3. **Checkout**：按 [`references/workspace.md`](references/workspace.md) 路由——新需求 `start`、已有分支 `attach`、继续计划恢复记录的 slot。后续代码编辑、构建、测试、review、提交都在返回的 worktree path 中执行。
4. **执行**：实现、review、验证并闭环 findings；复杂计划按 brief 的 task 依赖推进，完成整体 review 和最终验证并更新状态。
5. **提交** → 6. **推送** → 7. **建 MR**：按 [`references/git-lifecycle.md`](references/git-lifecycle.md) 执行并记录结果。
8. **关闭**：确认 MR 已合并且 worktree 干净后，按 git-lifecycle.md 关闭计划，再按 workspace.md 释放 slot。
