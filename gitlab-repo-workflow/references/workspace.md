# Worktree 规则

本文件只负责 checkout、worktree、分支和 slot 的创建、恢复与释放；计划状态和 Git 交付规则分别见其他 references。

主 checkout 承担调度职责；代码编辑、构建、测试、review 和提交在需求 worktree 中完成。

从主 checkout 执行：

```text
gitlab-repo-workflow/scripts/workspace.py start <topic-branch> --json
```

脚本会同步 origin、选择最新合法的 `origin/dev/vX.Y.Z` 基线，并返回：

- 需求分支；
- 基线和 Base SHA；
- worktree path；
- slot。

将返回值写入 brief，并使用返回的 `path` 执行后续命令；当前分支保持为返回的需求分支。

活动 brief 或简单任务独占其 worktree；简单任务以需求分支和 slot 作为执行记录。新的任务使用干净的空闲 slot。有效提交分支是需求分支，`main`、`dev/*` 和 `release/*` 承担控制分支职责。继续计划时，从 brief 或当前任务记录的 worktree 恢复。

MR 合并后，使用 brief 或当前任务记录的 slot 执行：

```text
gitlab-repo-workflow/scripts/workspace.py close --slot <slot> --confirm-merged --json
```

成功结果是 detached worktree、已删除的本地需求分支和空闲 slot；失败结果保留现场并记录恢复步骤。工作树根目录使用 `WORKFLOW_WORKTREE_ROOT` 覆盖。
