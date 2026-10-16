---
doc-id: documentation-governance
title: 文档治理规则
status: active
authority-for:
  - document-authority-map
  - document-lifecycle
  - documentation-update-policy
last-reviewed: 2026-10-07
---

# 文档治理规则

## 目标

让项目事实只有一个权威位置，让开发者和 AI 按任务读取最少但足够的上下文，并防止原始立项、当前状态、实现契约和上游参考互相覆盖。

## 当前分类

项目规模较小，开发前采用根目录扁平结构：

- 路由：`README.md`、`AGENTS.md`
- 产品：`PRODUCT.md`
- 前端展示：`FRONTEND_SPEC.md`
- 架构：`ARCHITECTURE.md`、`DECISIONS.md`、`INTEGRATIONS.md`
- 契约：`DATA_CONTRACTS.md`，以及未来的 `schemas/`
- 交付：`DEVELOPMENT_PLAN.md`、`M1_HANDOFF.md`、`TEST_PLAN.md`、`STATUS.md`
- 运维与安全：`OPERATIONS.md`、`SECURITY.md`
- 来源：`立项.md`
- 外部参考：`references/`

当根目录活跃治理文档超过约 15 份，或出现两个以上独立业务域时，再迁移到 `docs/` 分层；迁移前不得保留根目录和 `docs/` 两份活跃副本。

## 权威映射

| 事实类型 | 唯一权威 |
|---|---|
| 文档入口和阅读路径 | `README.md` |
| AI 读取和修改约束 | `AGENTS.md` |
| 产品范围、非目标、完成标准 | `PRODUCT.md` |
| 前端信息层级、交互展示和设计变量 | `FRONTEND_SPEC.md` |
| 组件、依赖方向、数据流 | `ARCHITECTURE.md` |
| 外部端点、网络、合约、探针和降级 | `INTEGRATIONS.md` |
| 核心对象语义和计算不变量 | `DATA_CONTRACTS.md` |
| 字段结构和必填规则 | 未来的 `schemas/` 文件 |
| 开发顺序和里程碑退出条件 | `DEVELOPMENT_PLAN.md` |
| M1 并行岗位、分支所有权和 AI 交接协议 | `M1_HANDOFF.md` |
| 测试矩阵和质量门槛 | `TEST_PLAN.md` |
| 密钥、隐私和安全边界 | `SECURITY.md` |
| 本地安装、启动和恢复 | `OPERATIONS.md` |
| 已接受的跨模块决定 | `DECISIONS.md` |
| 当前进展、阻塞和下一步 | `STATUS.md` |
| 原始需求背景和立项叙事 | `立项.md` |
| 精确依赖版本 | `requirements.lock.txt` 和各上游 lockfile |

## 生命周期

- `active`：当前权威或有效路由文档。
- `source`：保留的原始需求或证据，不自动代表当前实现。
- `superseded`：已由另一文档明确替代，必须注明替代者。
- `archived`：历史记录，只为审计和追溯保留。
- `generated`：由工具生成，禁止手工修改。

所有治理 Markdown 使用 YAML metadata，至少包含 `doc-id`、`title`、`status`、`authority-for` 和 `last-reviewed`。`doc-id` 全项目唯一且重命名文件时保持不变。

## 更新规则

1. 先修改拥有该事实的权威文件，再修改代码、schema 和测试。
2. 其他文档只链接权威来源，不复制易变状态或版本号。
3. `STATUS.md` 保持短小，只保留当前事实；已完成过程不形成逐会话日志。
4. 重大架构、契约、安全、基础设施或范围决定追加 ADR。
5. 原始证据不删除；需要替代时标记状态并建立双向说明。
6. `references/`、`.venv/` 和 `.venv-blockscout/` 不参与本项目文档索引和标题唯一性判断。

## AI 渐进读取

- 所有任务：`README.md`、`STATUS.md`。
- 产品任务：再读 `PRODUCT.md`。
- 前端任务：再读 `FRONTEND_SPEC.md`，按页面涉及的业务读取产品、架构和契约。
- 代码或架构任务：再读 `ARCHITECTURE.md` 和相关 ADR。
- 数据任务：再读 `DATA_CONTRACTS.md` 和目标 schema。
- M1 并行任务：再读 `M1_HANDOFF.md`，并确认唯一岗位和契约冻结 commit。
- 外部服务、链、合约或探针任务：再读 `INTEGRATIONS.md`。
- 发布、密钥或外部服务：再读 `SECURITY.md`、`OPERATIONS.md`。
- 只有需要来源依据时才读 `立项.md`；只有核实上游实现时才定向读 `references/`。

## 校验清单

- 所有根目录治理文档的 `doc-id` 唯一。
- 每种易变事实只有一个权威文件。
- 本地 Markdown 链接存在。
- README 与 AGENTS 保持路由性质，不逐步膨胀为设计文档。
- 文档声称的命令、测试和外部行为必须注明是否实际观察。
- 实现后，字段细节由 schema 负责，本文档只解释不变量和理由。

## 自动化策略

GitHub Actions 已运行非 external 测试、Ruff、`pip check`、Schema 漂移检查、1000 行限制和无凭据 MVP 演示。
契约测试同时检查根目录治理文档 metadata、`doc-id` 唯一性和本地 Markdown 链接。项目仍为单一业务域和扁平文档结构，
暂不生成文档索引；若迁移到多目录，生成物必须带禁止手改声明并在 CI 检查新鲜度。
