# task:run

## 工作区

读取仓库规则、任务清单和 Spec（如有），核对分支、diff、已有提交及验证结果。直接执行需求时，先明确任务及验收条件；简单任务可在会话中维护，需持久化时使用 [Task 格式](records.md#task-格式)。

恢复符合任务归属的现有工作区；需要隔离时，明确需求分支和目标合入线：

```sh
python3 <skill>/scripts/workspace.py start <branch> --repo <repo> --base <remote/line>
python3 <skill>/scripts/workspace.py attach <branch> --repo <repo> --base <remote/line>
```

`start` 创建分支和 worktree，`attach` 挂载已有分支。脚本使用本地已获取的引用，需要同步时先按仓库规则执行 `git fetch <remote>`。记录返回的 path、branch、base、base_sha，后续操作在该 path 中完成。

## 执行与提交

1. 按 [状态命令](records.md#状态命令) 选择依赖就绪的任务，开始时标记 `in_progress`。
2. 范围和资源独立的任务可并发；共享文件、状态及暂存区的操作串行。并发 worktree 各用独立分支，明确汇合点，由协调者统一更新任务文件。
3. 实施、验证并完成项目要求的 review，保留他人改动。要求提交时检查 diff，按任务范围 `git add -- <files>`，核对暂存内容后提交并记录 SHA。逐任务提交在本项验证后完成，统一提交在整体验证后完成。
4. 验收通过后标记 `completed`，记录实际验证结果及提交。阻塞时标记 `blocked`，记录原因和恢复方式；其依赖任务等待，独立任务继续。
5. 汇合结果，处理冲突并整体验证，按实现核对 Spec，在任务正文更新执行现场、整体结果和下一步。

## Git 交付

按用户要求和仓库规则推进提交、推送、MR/PR、合并及清理，记录实际结果。推送前核对 remote 和源分支；建 MR/PR 时使用目标合入线及仓库模板，复用已有请求。按 origin 使用 `glab`、`gh` 或服务 API。

清理时确认远端请求已合并且工作区干净，再移除对应 worktree 和本地需求分支，保留任务记录与 Spec。
