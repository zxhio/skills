# Git 生命周期规则

本文件只负责 commit、push、MR 和关闭动作；复杂计划的 brief 字段和 task 状态见 [`plan.md`](plan.md)，worktree 操作见 [`workspace.md`](workspace.md)。

简单任务和复杂计划都使用本流程完成 commit、push、MR 和 worktree 关闭。复杂计划额外更新 brief。

## 提交

提交输入：

- 需求 worktree 和需求分支；
- 当前 diff；
- 仓库规定的检查结果；
- 复杂计划的 task 状态、review findings 和 Commit Scope。

提交行为：

- 复杂计划的 `Commit Scope: plan` 创建一个累计 commit；
- 复杂计划的 `Commit Scope: task` 创建当前 task 的独立 commit；
- 简单任务创建一个任务 commit。

提交结果包括 commit SHA、提交范围和检查结果。复杂计划将这些信息写入 brief；简单任务在交付报告中记录。

## 推送和 MR

推送输入是当前需求分支：

```text
git push -u origin <topic-branch>
```

推送结果是远端分支和 `Pushed` 状态。

创建 MR 前，优先使用项目提供的 MR 模板或模块；项目未提供时，再使用通用 MR 描述。

创建 MR 输入 `Pushed` 分支和目标合入线，优先使用：

```text
glab mr create --source-branch <topic-branch> --target-branch <line> --title "<title>" --description-file <file>
```

MR 结果包括编号、地址、目标分支和 `MR Created` 状态。复杂计划写入 brief；简单任务在交付报告中记录。GitLab API 可替代 `glab`。

## 关闭计划或 worktree

关闭输入：

- GitLab 查询确认的已合并 MR；
- 当前需求 worktree 和 slot；
- 干净 worktree。

执行：

- 复杂计划更新 brief 为 `Closed`。
- worktree 和本地需求分支的释放按 [`workspace.md`](workspace.md) 执行。

成功结果是计划状态更新、worktree slot 释放和本地需求分支删除；失败结果保留现场和恢复步骤。
