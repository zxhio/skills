---
name: gitlab-repo-workflow
description: "Drive GitLab repository tasks end to end: plan the goal, pick a simple or complex plan, create or resume a task worktree, execute and review code, verify results, commit, push, create a merge request (MR) via glab or the GitLab API, and after merge close the plan and release the worktree. Only for repositories whose origin is GitLab; trigger when the user asks to plan, resume a plan, commit per task or as a whole, create a GitLab MR, or manage the Git worktree lifecycle. Do not use for GitHub or other platforms."
---

# GitLab Repo Workflow

按计划、worktree 和 GitLab 交付的顺序驱动仓库任务。明确指定 `brief` 时使用复杂计划；未指定时使用简单计划，不创建 brief。

## 0. 确认适用范围

开始前确认主 checkout 的 `git remote get-url origin` 指向 GitLab。origin 为 GitHub 或其他平台时，不使用本流程，告知用户后停止。

## 1. 创建计划并判断类型

- **简单计划**：记录目标、范围和验收条件，不创建 brief。
- **复杂计划**：创建或恢复 brief；brief 的路径、模板、task、review、状态和提交范围见 [`references/plan.md`](references/plan.md)。
- 规划动作完成 `Planned` 后结束；继续动作从首个未完成步骤恢复。
- 规划前读取仓库根 `AGENTS.md`、本次范围文档和相关代码约定。

## 2. 规划分支和 worktree

- 确定合入线、需求分支和 worktree slot。
- 复杂计划将执行信息写入 brief；简单计划以需求分支和 slot 作为执行记录。
- worktree 分配和恢复规则见 [`references/workspace.md`](references/workspace.md)。

## 3. Checkout

按 [`references/workspace.md`](references/workspace.md) 的路由从主 checkout 启动、挂载或恢复需求 worktree，并使用返回的 path 执行后续命令。代码编辑、构建、测试、review 和提交都在需求 worktree 中完成。

## 4. 执行计划

- **简单计划**：直接实现、review、验证并修复 findings。
- **复杂计划**：按 [`references/plan.md`](references/plan.md) 设计和更新 brief，按依赖执行 task、任务级验证和 review，再进行整体 review 和最终验证。

## 5. 提交

- 简单计划创建一个任务 commit。
- 复杂计划按 brief 中声明的提交范围创建 commit。
- 提交规则和结果记录见 [`references/git-lifecycle.md`](references/git-lifecycle.md)。

## 6. 推送

将已提交的需求分支推送到远端，并记录推送结果。

## 7. 创建 MR

按 [`references/git-lifecycle.md`](references/git-lifecycle.md) 创建 MR，并记录 MR 结果。

## 8. 关闭计划

确认 MR 已合并且 worktree 干净后，按 [`references/git-lifecycle.md`](references/git-lifecycle.md) 关闭计划，再按 [`references/workspace.md`](references/workspace.md) 释放 worktree。

## 参考

- brief、task、review 和计划状态：[`references/plan.md`](references/plan.md)
- worktree 创建、恢复和释放：[`references/workspace.md`](references/workspace.md)
- commit、push、MR 和关闭：[`references/git-lifecycle.md`](references/git-lifecycle.md)
