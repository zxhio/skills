# spec:plan

1. 读取仓库和目标目录的 AGENTS.md、相关代码与已有 Spec，在会话中收敛方案。
2. 按 [Spec 编写规则](spec.md)，将本主题当前粒度的结论整理成最小文档，保存前逐段核对内容范围。
3. 用户要求保存时，按 [存储规则](records.md#路径与保存) 以方案内容命名；简单需求保存一份文档，需独立维护的 SQL、API、部署方案分别保存到同一日期主题目录：

```sh
python3 <skill>/scripts/records.py save spec --repo <repo> --topic <topic> --name <name> --input <draft.md>
```

本流程交付方案；任务规划和实施分别由 `task:plan`、`task:run` 推进。
