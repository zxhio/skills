---
name: workflow
description: "Design implementation specs, plan dependency-aware tasks, execute and commit changes, and deploy builds. Supports independent spec:plan, task:plan, task:run, and deploy:run workflows."
---

# Workflow

按用户指定路由或同义意图进入对应流程，按需调用本 skill 的脚本：

| 路由 | 入口 |
| --- | --- |
| `spec:plan` | [设计流程](references/spec-plan.md) |
| `task:plan` | [任务规划](references/task-plan.md) |
| `task:run` | [任务执行](references/task-run.md) |
| `deploy:run` | [部署流程](references/deploy.md) |

各流程独立使用，执行范围和授权沿用当前会话。
