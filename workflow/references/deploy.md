# deploy:run

1. 读取仓库 AGENTS.md、部署文档和构建/安装脚本，确定目标、制品来源及操作范围。接受“部署 MR !123 到测试机”“部署 feat/cert-renewal 到测试机”或本机制品，按项目约定补齐参数。
2. GitLab 来源先用 `inspect` 定位提交与制品，再用 `run` 下载并部署。本机制品直接交给 `run`；需要构建时使用项目 CI 或构建入口。
3. 安装及验证命令采用项目真实约定，验证实际版本、进程/容器、健康接口和关键行为。
4. Result 记录目标、制品/SHA、验证结果及恢复入口。关联任务时写回任务正文，独立部署在会话报告；Spec 维护部署约定。

## 命令

脚本使用 Python 标准库和系统 `sh`；远端使用 SSH、`sha256sum` 或 `shasum`。

```sh
python3 <skill>/scripts/deploy.py check --host root@test-host
python3 <skill>/scripts/deploy.py inspect --repo <repo> --mr 123
python3 <skill>/scripts/deploy.py inspect --repo <repo> --ref feat/cert-renewal
python3 <skill>/scripts/deploy.py run --repo <repo> --mr 123 --job package:ci \
  --host root@test-host \
  --install 'unzip -q "$WORKFLOW_ARTIFACT" -d "$WORKFLOW_STAGE/package"; sh "$WORKFLOW_STAGE/package/install.sh" update' \
  --verify 'curl --fail --silent http://127.0.0.1/health'
```

示例的包结构、安装参数和健康检查按项目替换，验证命令同时核对部署版本。

## 来源解析

- GitLab 项目从仓库 origin 识别，`--mr` 与 `--ref` 二选一。MR 固定源项目和源提交，支持 fork；`--ref` 接受分支、Tag 或 SHA。自托管实例用 `--gitlab-url` 指定网页地址。
- `inspect` 只读返回固定 SHA 的最新流水线、任务候选和制品可用性；`--pipeline` 指定同 SHA 的流水线，`--job` 按名称或 ID 选择打包任务。制品未就绪时报告状态，构建及重试按本次需求另行处理。
- `run` 下载选定任务的完整制品 ZIP，下载前复核 SHA、流水线和成功状态。安装命令解包后调用项目入口。
- 凭据依次读取 `GITLAB_TOKEN`、`GL_TOKEN`、`GLAB_TOKEN` 或本机 `glab` 登录信息，仅发送给原始 GitLab 源。
- 本机制品使用 `--artifact <file>`，可加 `--sha256 <expected>` 校验预期值，`--ref <label>` 标注来源。已有目录或镜像可直接通过安装、验证命令部署。

## 执行参数与结果

- `--host local` 在本机执行；远端支持 SSH alias、`user@host`、`--port`，沿用 SSH 配置和主机密钥验证。
- `run` 要求 `--install`、`--verify`，以 `sh` 执行。`$WORKFLOW_ARTIFACT` 指向无扩展名的暂存制品，`$WORKFLOW_STAGE` 指向暂存目录；服务运行所需文件在安装期间放入持久目录。`--cwd` 指定目标已有工作目录，缺省为目标启动目录。
- 制品传输后校验 SHA-256。日志写入 stderr，成功结果以 JSON 写入 stdout；失败以非零状态退出，并在 stderr 返回包含阶段和现场路径的 JSON。
- 成功后清理下载和暂存目录，`--keep-stage` 保留现场；失败保留现场用于诊断和恢复。`--timeout` 限制每阶段命令及单次 HTTP 请求时间。超时或中断后先核对目标状态，再确定后续操作。
