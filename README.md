# Skills

Agent skills used to extend coding-agent workflows.

## gitlab-repo-workflow

Drive GitLab repository tasks end to end: plan the goal, create or attach a task worktree, execute and review code, commit, push, create a merge request via glab or the GitLab API, and release the worktree after merge.

### 适用前提：先对照你的 Git 工作流

这个 skill 绑定一套确定的工作流，全部满足才适用：

- 仓库 origin 托管在 **GitLab**（GitHub 或其他平台会直接拒绝）；
- 存在 **`dev` 集成分支**：需求分支从 `origin/dev` 切出，MR 合回 `dev`；
- 需求通过 **feature 分支 + MR** 交付，不直接提交到 `main`、`dev`、`release/*`（这些是受保护的控制分支）；
- 接受 **worktree 隔离**：每个任务在独立 worktree 中进行，主 checkout 只承担调度。

工作流不匹配（如 trunk-based、GitHub Flow、无 dev 集成分支）时不要使用。

### 使用方式

用自然语言说明目标即可，按措辞自动进入对应模式：

| 模式 | 说法示例 | 行为 |
| --- | --- | --- |
| 简单模式（默认） | “实现 XXX”“修复 XXX” | 从 `origin/dev` 新建需求分支，完成后 commit → push → MR |
| 复杂模式 | “先规划这个目标”“按 brief 执行”“继续这个目标” | 拆分 task、分级 review，状态记录在 `~/.workflow/` 的 brief，支持中断续做 |
| 分支续接 | “把 feat/xxx rebase 到最新 dev”“继续 feat/xxx”“处理这个 MR 的意见” | 挂载已有分支，**不新建**，报告分支与远端的同步状态 |
| 无分支操作 | “查一下 MR 状态”“清理已合并的 worktree” | 主 checkout 直接执行，不占用 worktree |

MR 合并后自动关闭计划、删除本地需求分支并释放 worktree。

See [gitlab-repo-workflow/SKILL.md](gitlab-repo-workflow/SKILL.md).
