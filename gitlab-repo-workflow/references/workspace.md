# Worktree 规则

本文件只负责 checkout、worktree、分支和 slot 的创建、恢复与释放；计划状态和 Git 交付规则分别见其他 references。

主 checkout 承担调度职责；代码编辑、构建、测试、review 和提交在需求 worktree 中完成。

## 合入线

`line` 是本次 MR 的目标分支名，`branch` 是源分支名，`base` 是创建或比较需求分支使用的远端引用。普通需求使用 `<remote>/<line>` 作为基线；分支名和发布策略以仓库文档为准。

- 从用户当前指定的目标、已有 MR 或任务记录确定合入线；新任务缺少记录时结合仓库约定和远端分支确定。目标冲突或存在多个合理候选时，先澄清归属。
- 简单任务和 brief 都记录 remote、line、branch，以及脚本返回的 base、base_sha、path、slot。继续任务时恢复该记录；目标被删除时重新确定归属，不能自动迁移到另一个版本。
- `start`、`attach` 必须显式传入 `--base`；接受目标分支名、`<remote>/<line>` 或 `refs/remotes/<remote>/<line>`，均解析到同步后的远端分支。脚本不从当前 checkout、`VERSION` 或版本号大小推断目标。
- 主 checkout 可以停在合入线上；需求分支名必须与合入线不同。

例如 `feat/example → dev/v0.2.0 → main` 中，功能任务的 line 是 `dev/v0.2.0`，版本发布 MR 的 line 是 `main`。其他仓库可选择 `develop`、`main` 或自定义合入线，脚本不限制目标分支的命名格式。

## Checkout 路由

按分支存在性选择动作：

- 分支在本地和远端都不存在（新需求）→ `start`；
- 分支已存在于本地或远端（rebase、继续已有分支、处理 MR 意见等）→ `attach`；
- 无分支操作（查询 MR、关闭计划、清理 worktree 等）→ 不占用 slot，在主 checkout 直接执行。

`start` 拒绝已存在的分支，`attach` 拒绝不存在的分支，两者互斥，防止误建或误挂。

## Start

从主 checkout 执行：

```text
gitlab-repo-workflow/scripts/workspace.py start <topic-branch> --base <remote>/<line> --remote <remote> --json
```

脚本会同步指定 remote（默认 `origin`）、校验目标分支存在，并返回：

- remote 和目标合入线；
- 需求分支；
- 基线和 Base SHA；
- worktree path；
- slot。

将返回值写入任务记录或 brief，并使用返回的 `path` 执行后续命令；worktree 当前分支保持为返回的需求分支。

## Attach

从主 checkout 执行：

```text
gitlab-repo-workflow/scripts/workspace.py attach <topic-branch> --base <remote>/<line> --remote <remote> --json
```

脚本会同步指定 remote 并挂载已有分支：分支仅在远端时，从 `<remote>/<topic-branch>` 创建本地跟踪分支。返回字段与 `start` 一致，其中 Base SHA 是与基线的 merge-base；`sync` 报告分支与远端的同步状态（`up-to-date`、`ahead N`、`behind N`、`diverged`、`local-only`、`remote-only`）。分叉或落后时只报告状态，不擅自 rebase 或 reset；同步和 rebase 由 agent 在 worktree 内按需执行。

将返回值写入任务记录或 brief，并使用返回的 `path` 执行后续命令。分支已挂载时，核对记录中的 worktree 后直接恢复，不重复调用 `attach`。

## 占用与恢复

活动 brief 或简单任务独占其 worktree；新的任务使用干净的空闲 slot。需求 slot 用于普通需求分支；`main`、`dev/vX.Y.Z` 等集成或发布分支承担控制分支职责。脚本内置 `main`、`master`、`dev`、`dev/*`、`release/*` 的保护，仓库自定义控制分支由 agent 按仓库规则识别。继续计划时，从 brief 或当前任务记录的 worktree 恢复。

版本初始化、提交归一化和版本分支删除属于控制分支维护，按用户授权及仓库流程执行，涉及代码或历史整理时建立专用 worktree。需求 slot 的 `start`、`attach`、`close` 不承担控制分支维护。

MR 合并后，使用 brief 或当前任务记录的 slot 执行：

```text
gitlab-repo-workflow/scripts/workspace.py close --slot <slot> --confirm-merged --json
```

成功结果是 detached worktree、已删除的本地需求分支和空闲 slot；失败结果保留现场并记录恢复步骤。工作树根目录使用 `WORKFLOW_WORKTREE_ROOT` 覆盖。
