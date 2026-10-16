---
doc-id: project-readme
title: TreasuryTally 项目入口
status: active
authority-for:
  - documentation-routing
  - repository-entrypoint
last-reviewed: 2026-10-07
---

# TreasuryTally

TreasuryTally 是链上报表验收工具：上传服务商报表后，系统把报表声明与真实链上资金流放在同一张对账图中，定位漏报、
重复和内部互转，并生成能够说明“哪里不符合约定、如何复现”的验收回执。

首版是约 40 小时开发窗口内的可运行原型，不是完整交易市场或通用会计系统。

M1–M7 构成原 MVP；后续扩展沿用同一业务闭环：锁定链上任务与交付承诺，以资金流图完成修复前后验收，
再把公开回执和 ERC-8004 历史用于下一次服务选择。功能、发布和未验收项以 [STATUS.md](STATUS.md) 为准。
本轮不要求真实用户测试；技术自动化不等于真实用户验证，不能据此宣称商业化就绪。

## 文档导航

| 需要了解 | 权威文档 |
|---|---|
| 产品目标、范围、非目标和验收标准 | [PRODUCT.md](PRODUCT.md) |
| 前端页面、交互层级、黑金主题与设计变量 | [FRONTEND_SPEC.md](FRONTEND_SPEC.md) |
| 系统组成、边界和数据流 | [ARCHITECTURE.md](ARCHITECTURE.md) |
| RPC、Blockscout、Agent0、ERC-8004 集成约定 | [INTEGRATIONS.md](INTEGRATIONS.md) |
| 核心对象、字段与计算不变量 | [DATA_CONTRACTS.md](DATA_CONTRACTS.md) |
| 开发顺序、里程碑和降级策略 | [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) |
| M1 并行岗位、分支边界和 AI 交接 | [M1_HANDOFF.md](M1_HANDOFF.md) |
| 测试矩阵与质量门槛 | [TEST_PLAN.md](TEST_PLAN.md) |
| 密钥、隐私和威胁边界 | [SECURITY.md](SECURITY.md) |
| 安装、启动、故障恢复 | [OPERATIONS.md](OPERATIONS.md) |
| 已作出的架构与产品决定 | [DECISIONS.md](DECISIONS.md) |
| 当前真实进展和待办 | [STATUS.md](STATUS.md) |
| 文档权威、生命周期和更新规则 | [DOCS_GOVERNANCE.md](DOCS_GOVERNANCE.md) |
| 人工和 AI 开发协作规则 | [CONTRIBUTING.md](CONTRIBUTING.md)、[AGENTS.md](AGENTS.md) |
| 原始立项背景 | [立项.md](立项.md) |

## 快速开始

```powershell
cd D:\HACKTHON
Copy-Item .env.example .env
.\.venv\Scripts\Activate.ps1
```

无需外部密钥的一条命令 MVP 演示会执行“服务 A 漏项 `FAIL` → 切换服务 B `PASS`”，保存两个 attempt 与两份回执，
再以新会话路径恢复并独立重放两份回执：

```powershell
.\.venv\Scripts\python.exe scripts\run_mvp_demo.py
```

命令成功时输出 `"valid": true`、确定性算式 `120000 - 30000 + 20000 = 110000`、两个 attempt 和两次有效重放。
它明确使用离线 fixture，不上传公共文件或写链。需要保留演示数据库与私有回执时，传入一个空目录：

```powershell
.\.venv\Scripts\python.exe scripts\run_mvp_demo.py --output-directory .tmp\mvp-demo
```

M5 页面入口为：

```powershell
streamlit run app\streamlit_app.py
```

默认选择“离线 fixture 演示”，不需要模型密钥，并在页面中明确标注为非真实模型调用。也可以选择 OpenAI 或
DeepSeek 真实模型，并把独立证据切换为真实 Sepolia RPC；缺少对应 key、固定模型名或 RPC URL 时页面会显示配置阻塞，
不会用 mock 冒充。页面支持任务候选修改与确认、服务 A/B、一次补交或换源、独立 attempt 历史、三态结果、证据来源诊断、
Finding、受限解释与本地回执预览。工作区 ID 可在进程重启后恢复 SQLite、本地回执和发布状态。M6 页面支持经显式授权发布
脱敏回执到 Pinata/IPFS 或内容寻址 HTTPS 公共目录，并在另一次显式授权后提交 ERC-8004；缺少配置时保持 `NOT_SUBMITTED`，
不会用本地 mock 冒充公开发布。
实际进展请查看 [STATUS.md](STATUS.md)。

## 完整验收

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not external"
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\export_schemas.py --check
.\.venv\Scripts\python.exe scripts\check_file_sizes.py
```

真实模型、RPC、Blockscout、公共回执和 ERC-8004 属于外部验收面，配置与命令见 [OPERATIONS.md](OPERATIONS.md)，
最新实测证据见 [STATUS.md](STATUS.md)。外部探针缺少凭据时明确跳过，不能用离线演示替代真实通过。

## 仓库边界

- `src/`：核心业务代码。
- `app/`：Streamlit 页面入口。
- `tests/`：单元、集成和端到端测试。
- `fixtures/`：人工标注的演示与测试数据。
- `schemas/`：可机器校验的 JSON Schema。
- `receipts/`：生成的公开回执；私密内容放在 `receipts/private/`。
- `data/`：本地数据库和运行数据，不提交版本库。
- `references/`：上游项目的只读参考副本，不属于本项目代码和文档权威体系。

## 核心原则

1. 确定性程序负责金额、集合和范围判断，AI 不拥有最终计算权。
2. 证据不足必须返回 `INCONCLUSIVE`，不能伪装成通过或失败。
3. 任务确认后必须固定范围并计算指纹，不能在执行中静默改变。
4. 每次服务交付分别留档，后一次成功不能覆盖前一次失败。
5. 公开前必须脱敏并获得授权；提交交易不等于链上确认。
