# task:plan

1. 根据需求、相关实现和已有 Spec（如有），确定目标及验收范围。用户通过主题名称引用方案时，按 [存储规则](records.md#路径与保存) 定位方案目录，读取相关文件。
2. 按 [Task 格式](records.md#task-格式) 拆分可独立实施和验收的任务，以依赖表达顺序和并发汇合关系。逐任务提交时，按独立验证和提交边界划分。
3. 确定目标合入线和拟用分支，按 [存储规则](records.md#路径与保存) 关联 Spec、复用首次规划日期，保存任务清单并检查依赖：

```sh
python3 <skill>/scripts/records.py save task --repo <repo> --topic <topic> --line <line> --branch <branch> --input <draft.md>
python3 <skill>/scripts/records.py ready <task.md>
```

本流程交付任务清单，作为 `task:run` 的执行和恢复入口。
