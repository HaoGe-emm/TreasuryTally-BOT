# TreasuryTally M16 本机 MCP stdio

TreasuryTally M16 把既有候选、确定性验收、SQLite attempt 与回执重放组合为 headless facade，并用项目已固定的官方 Python SDK
`mcp==1.26.0` 暴露 stdio server。它不启动 HTTP 监听，不提供公共发布、写链、多租户、任意文件/URL、Shell、Python 或 SQL。

## 配置

复制 `mcp-workspaces.example.json` 为不提交 Git 的本机配置，为每个工作区生成独立随机 handle，并把 `directory` 指向独立私有目录。
默认 `LIVE_READ_ONLY` 只允许真实模型与只读 RPC；`.env` 缺少模型或 `ETH_RPC_URL` 时工具返回 `BLOCKED`，不会回退 fixture。
`FIXTURE_TEST_ONLY` 仅用于测试，要求 AI 与 evidence 都显式为 `fixture`，每个响应都标记 `fixture_test_only=true`。

客户端示例见 `codex-mcp.example.json`，显示别名为 `treasurytally-local`。为保持已安装客户端兼容，Python 包、模块和运行命令
继续使用稳定技术标识 `trust_receipt`；服务命令为：

```powershell
.\.venv\Scripts\python.exe -m trust_receipt.mcp_server.cli --config docs\m16\mcp-workspaces.local.json
```

stdio 的 stdout 专用于 JSON-RPC；诊断只写 stderr。配置文件路径只由本机进程启动参数提供，不是 MCP tool 参数。

## 授权流程

`prepare_task_confirmation` 和 `prepare_report_verification` 仅生成 15 分钟有效、绑定 payload digest 的 challenge。
`confirm_task` 或 `verify_report` 在批准前返回 `AUTHORIZATION_REQUIRED`。用户在另一个本机终端检查 challenge 后输入完整确认短语：

```powershell
.\.venv\Scripts\python.exe -m trust_receipt.headless.cli `
  --config docs\m16\mcp-workspaces.local.json `
  inspect --workspace ws_<opaque> --challenge ch_<id>

.\.venv\Scripts\python.exe -m trust_receipt.headless.cli `
  --config docs\m16\mcp-workspaces.local.json `
  approve --workspace ws_<opaque> --challenge ch_<id>
```

批准命令不是 MCP tool，也没有 `--yes`。批准只适用于对应 handle、动作、digest、task 与 attempt；消费结果持久化，客户端重试或
server 重启后返回同一 task/attempt 并标记 `idempotent_replay=true`。首次结果只有 `FAIL` 或 `INCONCLUSIVE` 才允许第二次，
第三次永远拒绝。

授权摘要还绑定确认任务的 `spec_hash`；`AttemptResultView` 同样返回该指纹。客户端比较两个 attempt 时必须核对
`workspace_handle + task_id + spec_hash`，不能只用 task ID 或 UI 当前选择推断范围相同。

facade 在准备和消费核验 challenge 时都会读取持久化 `AttemptStatus`。已有 `REQUESTED` / `SUBMITTED` / `VERIFYING`、缺失或冲突
回执时明确阻塞，不会把空恢复列表误判为 Attempt 1，也不会自动解除锁。并发消费由 SQLite `BEGIN IMMEDIATE` 原子预留裁决。

## 工具

- `draft_task_candidate`：只返回 `UNCONFIRMED` 候选。
- `prepare_task_confirmation` / `confirm_task`：准备挑战并在本机批准后固定任务。
- `prepare_report_verification` / `verify_report`：只接受最多 1 MB 的内联 `UploadedReport 1.0` JSON；不接受路径。
- `get_verification_result`：读取保存的三态结果。
- `get_receipt`：读取不含报告正文、签名、路径或密钥的便携回执。
- `replay_receipt`：不访问模型或链，重放哈希、对象链接和三态结论。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests\m16 -q
```

协议测试实际启动 stdio 子进程并执行 `initialize`、`tools/list`、`tools/call`，随后重启 server 检查幂等恢复；它还覆盖未授权、
跨工作区、路径/SQL/秘密注入、缺 RPC、并发预留、持久 in-flight、缺失回执、两次 attempt 上限及回执重放。fixture 路径只证明
本地协议与边界，不代表真实 RPC 已验收。
