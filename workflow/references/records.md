# 记录存储、格式与命令

`scripts/records.py` 使用 Python 3 和 PyYAML（`python3 -m pip install pyyaml`），管理本地文档并输出 JSON。以下命令从仓库运行，也可用 `--repo <path>` 指定仓库。

## 路径与保存

配置文件：`~/.workflow/<plug_name>/config.yaml`，支持两个字段：

| 字段 | 默认值 |
| --- | --- |
| `spec_dir` | `~/.workflow/spec/` |
| `task_dir` | `~/.workflow/` |

插件名从安装目录的 `.codex-plugin/plugin.json` 读取，独立安装使用 `workflow`。相对路径以配置目录为基准。

内部路径固定：

```text
Task：<task_dir>/<repo>/<line>/<branch>/<YYYYMMDD>-<topic>.md
Spec：<spec_dir>/<repo>/<YYYYMMDD>-<topic>/<name>.md
```

repo 从 Git common dir 识别，worktree 共享项目名。topic 使用英文 kebab-case；line 为目标合入线，branch 为需求分支，两者均保留完整 `/` 层级，由 agent 按需求和仓库约定填入。Spec 可在确定分支前独立保存。

方案文件按内容命名，`--name` 使用英文 kebab-case，默认与 topic 同名。简单需求保存一份 `<topic>.md`；需要独立维护时，同一日期主题目录可分别保存 `sql.md`、`api.md`、`deploy.md`。Task 可关联方案目录或具体文件。

```sh
python3 <skill>/scripts/records.py paths --topic cert-renewal --line dev-0.8.1 --branch feat/cert-renewal
python3 <skill>/scripts/records.py save spec --topic cert-renewal --input /tmp/cert-renewal.md
python3 <skill>/scripts/records.py save spec --topic cert-renewal --name sql --input /tmp/sql.md
python3 <skill>/scripts/records.py save spec --topic cert-renewal --name api --input /tmp/api.md
python3 <skill>/scripts/records.py save spec --topic cert-renewal --name deploy --input /tmp/deploy.md
python3 <skill>/scripts/records.py save task --topic cert-renewal --line dev-0.8.1 --branch feat/cert-renewal --input /tmp/tasks.md
```

`paths` 返回配置、仓库身份、日期、方案目录和文件及记录候选。日期为首次规划的本地日期；同主题方案文件和所选 line/branch 的 Task 有唯一日期时复用，跨日更新保持名称。多个日期时用 `--date YYYYMMDD` 选择；新一轮同名需求也用该参数指定新日期。关联已有文件时沿用其日期，并在 Task 中保存方案链接。

更新原文件使用 `--replace`，已有记录按原路径恢复。旧 brief 由 agent 读取并恢复现场；脚本状态命令适用于下述 Task 格式。保存到 notes 时遵守目标目录规则，在仓库级 README 维护索引及所需 todo 关联；正式文档通过引用关联。

## Task 格式

YAML frontmatter 保存任务清单，正文保存执行现场和整体结果。脚本补充仓库身份、line、branch 和创建日期，更新状态时保留正文。

```markdown
---
tasks:
  - id: T01
    subject: 实现证书有效期判断
    acceptance: 正确识别有效、临近到期及过期证书
    depends_on: []
    status: pending
  - id: T02
    subject: 实现更新请求
    acceptance: 成功获取并校验新证书
    depends_on: [T01]
    status: pending
  - id: T03
    subject: 实现退避调度
    acceptance: 失败后按约定间隔重试
    depends_on: [T01]
    status: pending
  - id: T04
    subject: 汇合并完成集成验证
    acceptance: 证书切换和失败恢复通过验证
    depends_on: [T02, T03]
    status: pending
---
# 证书自动更新

- 目标：客户端在证书到期前自动更新。
- Spec：对应文档链接（如有）
- 提交：本次要求的提交方式

## 执行现场

Remote、目标合入线、worktree、Base SHA，以及并发任务各自的范围和工作区。

## 整体结果与恢复

整体验证、交付/部署引用、阻塞和下一步。
```

依赖决定执行顺序，示例为 `T01 → [T02 ∥ T03] → T04`。每项明确独立验收边界，按需补充修改范围、Spec、负责人等字段。

## 状态命令

```sh
python3 <skill>/scripts/records.py ready <task.md> [--only T02 T03]
python3 <skill>/scripts/records.py status <task.md> T01 in_progress
python3 <skill>/scripts/records.py status <task.md> T01 completed --result '有效期边界测试通过' --commit <sha>
```

- `ready` 校验依赖图，返回就绪、运行、阻塞及已结束任务；`--only` 将查询限定到指定任务。
- `status` 支持 `pending`、`in_progress`、`completed`、`blocked`、`cancelled`。开始和完成时要求前置任务已完成；完成或阻塞时填写 `--result`，提交 SHA 用 `--commit` 记录。正文由 agent 原地更新。
