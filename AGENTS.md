---
doc-id: ai-agent-instructions
title: AI 开发代理指令
status: active
authority-for:
  - ai-reading-policy
  - ai-change-policy
last-reviewed: 2026-10-06
---

# AI 开发代理指令

本文件适用于 `D:\HACKTHON` 项目根目录及其子目录，但不覆盖 `references/` 内上游仓库自己的指令。

## 开始任务前

1. 先读 [README.md](README.md) 和 [STATUS.md](STATUS.md)。
2. 产品行为变更再读 [PRODUCT.md](PRODUCT.md)；架构或跨模块变更再读 [ARCHITECTURE.md](ARCHITECTURE.md) 和 [DECISIONS.md](DECISIONS.md)。
3. 数据字段、金额、事件身份或回执变更必须读 [DATA_CONTRACTS.md](DATA_CONTRACTS.md)。
4. 外部服务、链上合约或网络探针相关变更必须读 [INTEGRATIONS.md](INTEGRATIONS.md)。
5. 测试、安全或运行相关变更分别按需读取 [TEST_PLAN.md](TEST_PLAN.md)、[SECURITY.md](SECURITY.md)、[OPERATIONS.md](OPERATIONS.md)。
6. 不要默认递归读取 `.venv/`、`.venv-blockscout/` 或 `references/`。只有需要核实上游行为时才定向读取参考仓库。
7. 参与 M1 并行开发时必须再读 [M1_HANDOFF.md](M1_HANDOFF.md)，并且只执行主负责人、AI 同事 A
   或 AI 同事 B 中被明确分配的一个岗位。

## 实现约束

- Python 业务代码进入 `src/trust_receipt/`，页面代码进入 `app/`。
- 领域模型优先使用 Pydantic；持久化模型不得反向污染领域模型。
- 金额内部使用最小单位整数，禁止用 `float` 完成账务计算。
- ERC-20 事件主键至少为 `chain_id + transaction_hash + log_index`。
- 链上参考证据与服务自报数据必须保留来源标签，不得混为同一事实。
- AI 只能生成结构化主张、受限计划和解释；不得执行任意生成代码或决定最终金额。
- 外部失败、缺页、RPC 不一致或证据不足应得到 `INCONCLUSIVE`，不是负面信誉。
- 所有写链、上传公开文件和使用真实密钥的动作必须显式区分模拟、已提交与已确认状态。
- 除 Markdown 和 `.tmp/` 下明确不提交的临时测试文件外，任何单个代码、脚本、配置或永久测试文件不得超过 1000 个物理行；接近限制时按职责拆分，不得压缩格式规避限制。
- 模块必须高内聚、低耦合：一个模块只拥有一个明确领域职责，跨模块通过稳定模型、端口或 adapter 协作，禁止用循环导入、全局可变状态或 UI/供应商细节穿透领域层。

## 变更同步

- 产品范围变化：更新 `PRODUCT.md` 和 `DECISIONS.md`。
- 架构边界变化：更新 `ARCHITECTURE.md` 和 `DECISIONS.md`。
- 字段或不变量变化：先更新 `DATA_CONTRACTS.md`，随后更新 schema、代码和测试。
- 当前进展变化：只更新 `STATUS.md`；不要把状态复制到其他文档。
- 开发计划完成项只在 `STATUS.md` 记录，不逐日改写 `DEVELOPMENT_PLAN.md`。
- 凭据名称变化：同步 `.env.example`、`OPERATIONS.md` 和 `SECURITY.md`。
- 外部端点、网络、合约地址、探针和降级策略变化：更新 `INTEGRATIONS.md`。
- M1 并行岗位、分支所有权和 AI 交接流程变化：更新 `M1_HANDOFF.md`；当前进展仍只写 `STATUS.md`。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
```

只声称实际执行过的验证。需要网络、密钥、测试币或外部服务的检查必须单独标明是否完成。

## 禁止事项

- 不提交 `.env`、私钥、助记词、API 密钥或未脱敏回执。
- 不直接修改 `requirements.lock.txt`；依赖变化后由当前主环境重新生成。
- 不把 `references/` 中的代码当作本项目已实现能力。
- 不为通过测试而降低金额精度、跳过分页或将未知状态映射为成功。
- 不运行会自动大规模升级上游依赖的修复命令，尤其是参考仓库中的 `npm audit fix`。
