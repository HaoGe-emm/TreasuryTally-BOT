---
doc-id: m1-parallel-handoff
title: M1 并行开发交接与 AI 岗位说明
status: active
authority-for:
  - m1-parallel-roles
  - m1-branch-ownership
  - m1-ai-handoff-protocol
last-reviewed: 2026-10-06
---

# M1 并行开发交接与 AI 岗位说明

## 使用方式

本文供主负责人和两位 AI 开发同事共同使用。把完整仓库和本文交给 AI 后，必须同时明确其身份是
“主负责人”“AI 同事 A”或“AI 同事 B”。AI 只能执行对应岗位章节，不得自行交换职责。

本文只安排 M1，不代表 M1 已经开始。A、B 必须等待主负责人提供契约冻结 commit SHA；没有该 SHA 时，
只能阅读、提问和报告阻塞，不得创建 M1 代码或样例。

## 当前基线

- M0 已完成 RPC、Blockscout MCP、Agent0 和 ERC-8004 四类真实外部探针。
- 最近一次完整验证为 13 项测试通过，Ruff 和两个 Python 环境的 `pip check` 通过。
- M1 目标由 [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) 定义：Pydantic 模型、JSON Schema 和
  12 份人工标注样例全部通过校验。
- 字段语义和计算不变量以 [DATA_CONTRACTS.md](DATA_CONTRACTS.md) 为唯一权威。
- 当前文档不授权任何主网操作、链上写入、公开上传或秘密使用。

## 分支拓扑

```text
main
  └─ codex/m1-integration       主负责人维护的 M1 集成分支
       ├─ codex/m1-core-models  主负责人：领域模型与契约冻结
       ├─ codex/m1-fixtures     AI 同事 A：12 份标注样例
       └─ codex/m1-schema-tests AI 同事 B：Schema 与契约测试
```

规则：

1. 禁止直接推送 `main` 和 `codex/m1-integration`。
2. A、B 从主负责人提供的契约冻结 commit 创建自己的分支。
3. A、B 的 PR 目标分支只能是 `codex/m1-integration`。
4. A、B 不得合并自己的 PR；主负责人拥有最终审查和合并权。
5. 个人分支需要整理历史时只允许 `git push --force-with-lease`，不得对共享分支强推。
6. 合并顺序默认是核心模型、Schema/测试、fixtures、主负责人集成修正；实际顺序由主负责人决定。

## 共同阅读顺序

所有 AI 开始前必须完整阅读：

1. [AGENTS.md](AGENTS.md)
2. [README.md](README.md)
3. [STATUS.md](STATUS.md)
4. [PRODUCT.md](PRODUCT.md)
5. [ARCHITECTURE.md](ARCHITECTURE.md)
6. [DATA_CONTRACTS.md](DATA_CONTRACTS.md)
7. [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) 的 M1 与第一纵向切片
8. [TEST_PLAN.md](TEST_PLAN.md) 的人工标注数据集与质量门槛
9. 本文对应的岗位章节

不得默认递归读取 `.venv/`、`.venv-blockscout/` 或 `references/`。

## 主负责人：我们这边

### 职责

- 维护 `codex/m1-integration`，决定契约冻结点并向 A、B 提供准确 commit SHA。
- 独占修改 `DATA_CONTRACTS.md`、`DECISIONS.md`、`STATUS.md` 和其他权威治理文档。
- 在 `src/trust_receipt/models/` 实现领域枚举、Pydantic 模型、跨字段校验和稳定导出边界。
- 决定字段命名、可空性、版本策略、地址/哈希规范化边界和模型之间的依赖方向。
- 审查 A、B 的 PR，处理共享导出文件和跨岗位集成测试。
- 最终运行全量验证，并决定是否向 `main` 提交 M1 PR。

### 契约冻结要求

主负责人只有在以下内容明确后才能宣布冻结：

- M1 涉及的模型和枚举列表。
- 每个字段的类型、必填性、默认值和主要约束。
- 金额使用最小单位整数或十进制整数字符串的明确边界。
- `TransferRecord` 事件键为 `chain_id + transaction_hash + log_index`。
- `PASS`、`FAIL`、`INCONCLUSIVE` 的判定语义。
- Fixture 文件布局、命名规则及期望结果表达方式。
- JSON Schema 文件名和 schema version。

冻结后应把 commit SHA 同时发给 A、B。任何破坏冻结契约的变更必须先更新
`DATA_CONTRACTS.md`，再由主负责人通知两位 AI 重新同步。

### 本轮冻结公共边界

- 公共导入路径为 `trust_receipt.models`；A、B 不从模型内部模块导入。
- 冻结模型、枚举和字段以 `DATA_CONTRACTS.md` 与 `trust_receipt.models.__all__` 为准。
- 冻结的顶层 Schema 模型是 `TaskSpec`、`TransferRecord`、`ServiceSubmission`、`VerificationPlan`、
  `VerificationResult`、`Receipt`、`FixtureCase` 和 `FixtureManifest`。公共嵌套模型是 `ExclusionRule`、
  `Claim`、`ApprovedQuery`、`ApprovedFilter`、`ApprovedAggregationRule`、`ApprovedCheck`、`SourceDescriptor`、
  `Finding`、`ServiceIdentity`、`EvidenceDescriptor`、`Publication`、`FixtureReference`、`ExpectedFinding`、
  `FixtureExpectedResult`、`HumanReview` 和 `FixtureManifestEntry`。
- fixture 固定使用 `fixtures/m1/manifest.json` 与 `fixtures/m1/cases/<fixture_id>.json`，详细顶层字段见
  `DATA_CONTRACTS.md` 的“M1 fixture 契约”。
- Schema 固定输出到 `schemas/v1/`，共 8 个 `*.schema.json` 文件；唯一获准的导出脚本路径为
  `scripts/export_schemas.py`。
- Schema version 固定为 `1.0`，`$id` 固定使用 `urn:xinjv:schema:1.0:<kebab-name>`。

## AI 同事 A：标注样例负责人

### 启动输入

A 必须从主负责人获得：

- 契约冻结 commit SHA。
- 分支名 `codex/m1-fixtures`。
- 已冻结的 fixture 目录结构和 JSON 字段。

缺少任一项时停止编码并报告，不得猜测。

### 文件所有权

A 只允许创建或修改：

- `fixtures/m1/`
- 自己 PR 中与 fixture 内容直接相关的说明文件，且必须放在 `fixtures/m1/` 内。

A 不得修改：

- `src/`
- `schemas/`
- `tests/`
- 根目录治理 Markdown
- `.env`、依赖文件和 M0 探针

### 交付任务

创建 12 份独立、确定、可读的人工标注 fixture，并提供目录内 manifest。最低分布为：

| 场景 | 数量 |
|---|---:|
| 完全正确 | 2 |
| 漏项 | 2 |
| 重复事件 | 2 |
| 内部互转误计 | 2 |
| 区块范围错误 | 1 |
| decimals/单位错误 | 1 |
| 多错误组合，开发期间隐藏 | 1 |
| 证据不足 | 1 |

每份 fixture 必须包含已冻结格式要求的输入、预期 outcome、预期 Finding 和人工核验说明。
其中至少一份必须实现第一纵向切片：服务声称 `120000`，排除 `30000` 内部互转并补回漏计的
`20000` 对外拨款后，确定性正确结果为 `110000`。

### 数据约束

- 金额不得使用浮点数。
- 同一交易可包含多个日志，不得只按交易哈希去重。
- 链上参考记录和服务自报记录必须有不同来源标签。
- `INCONCLUSIVE` 样例必须来自证据不足、分页未知或关键元数据缺失，不能伪装成服务错误。
- 地址和交易哈希使用明显的测试数据；不得包含密钥、认证头、真实个人信息或未脱敏报告。
- 隐藏组合样例可以不在文件名暴露具体错误，但 manifest 必须给出稳定 ID 和用途标签。

### A 的停止条件

遇到以下情况立即停止相关文件的修改，在 PR 描述中提出问题：

- 冻结模型没有表达场景所需字段。
- `DATA_CONTRACTS.md` 与冻结模型冲突。
- 预期 Finding 需要新增枚举。
- 必须修改 `src/`、`schemas/` 或测试才能继续。

### A 的完成报告

PR 描述必须包含：

```text
岗位：AI 同事 A / M1 fixtures
基线 commit：<契约冻结 SHA>
修改文件：<列表>
场景覆盖：<12 份逐项列出>
验证命令与结果：<实际执行>
契约问题：<无或逐项说明>
未完成事项：<无或逐项说明>
```

## AI 同事 B：Schema 与契约测试负责人

### 启动输入

B 必须从主负责人获得：

- 契约冻结 commit SHA。
- 分支名 `codex/m1-schema-tests`。
- 已冻结的 Pydantic 公共导入路径、模型列表和 Schema 文件命名。

缺少任一项时停止编码并报告，不得自行创造公共接口。

### 文件所有权

B 只允许创建或修改：

- `schemas/`
- `tests/contracts/`
- 主负责人明确指定的单一 Schema 导出脚本路径

B 不得修改：

- `src/trust_receipt/models/`
- `fixtures/m1/`
- 根目录治理 Markdown
- `.env`、依赖文件和 M0 探针

若现有项目结构导致导出脚本必须放入其他目录，B 必须先请求主负责人确定路径。

### 交付任务

- 为冻结模型生成或固化 JSON Schema，保留稳定 schema version 和 `$id`/标题约定。
- 验证 Pydantic 接受的数据也满足对应 JSON Schema。
- 验证必填字段、枚举、非负整数、区块范围、attempt 范围及记录上限。
- 验证金额拒绝浮点输入或任何会丢失精度的表示。
- 验证地址、哈希、时间和 source 字段的约束。
- 验证 `TransferRecord` 事件身份所需三字段不能缺失。
- 覆盖合法输入、缺字段、错误枚举、错误范围、错误金额和多余字段策略。
- 提供 fixture 校验入口，但不得为了让未知 fixture 通过而放宽 Schema。
- 确保 Schema 生成可重复；重复生成不得产生无意义 diff。

### B 的停止条件

遇到以下情况立即停止相关修改并向主负责人报告：

- Pydantic 模型与 `DATA_CONTRACTS.md` 不一致。
- 生成的 Schema 缺少表达核心不变量所需的信息。
- 测试需要更改领域字段、枚举或公共导入路径。
- 需要新增依赖或修改锁文件。

### B 的完成报告

PR 描述必须包含：

```text
岗位：AI 同事 B / M1 Schema 与契约测试
基线 commit：<契约冻结 SHA>
修改文件：<列表>
Schema 清单：<文件与对应模型>
测试覆盖：<合法与非法场景>
验证命令与结果：<实际执行>
契约问题：<无或逐项说明>
未完成事项：<无或逐项说明>
```

## 可直接交给 AI 的启动提示

给 A：

```text
你是本项目 M1 的 AI 同事 A，只负责 fixtures。完整阅读 AGENTS.md 和 M1_HANDOFF.md，严格执行
“AI 同事 A”章节。你的基线是主负责人提供的契约冻结 commit；没有准确 SHA 就停止并询问。
只修改 fixtures/m1/，不要修改 src、schemas、tests、依赖、根目录文档或任何秘密配置。
完成后按 A 的完成报告模板提交 PR，目标分支为 codex/m1-integration，不要自行合并。
```

给 B：

```text
你是本项目 M1 的 AI 同事 B，只负责 JSON Schema 和契约测试。完整阅读 AGENTS.md 和
M1_HANDOFF.md，严格执行“AI 同事 B”章节。你的基线是主负责人提供的契约冻结 commit；没有准确
SHA 就停止并询问。只修改 schemas/、tests/contracts/ 和主负责人明确指定的 Schema 导出脚本。
不要修改领域模型、fixtures、依赖、根目录文档或任何秘密配置。完成后按 B 的完成报告模板提交
PR，目标分支为 codex/m1-integration，不要自行合并。
```

## 同步、评审和冲突处理

- A、B 开工前记录 `git rev-parse HEAD`，确认与主负责人给出的冻结 SHA 一致。
- 每次同步只从 `codex/m1-integration` 获取主负责人已宣布的更新。
- 两位 AI 不直接依赖对方未合并的分支；跨岗位问题交给主负责人协调。
- 发现越权修改时，PR 不得合并，先拆回岗位拥有的目录。
- PR 至少包含一个可审查的逻辑提交；提交信息使用英文动词开头并描述可观察结果。
- 评审意见涉及契约时，以主负责人更新后的 `DATA_CONTRACTS.md` 和新冻结 SHA 为准。
- A、B 不得修改自己的岗位边界来消除冲突。

## 验证要求

A、B 至少执行适用于自身改动的离线检查：

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not external"
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
```

不得在缺少密钥时启动 M0 外部探针，也不得执行 ERC-8004 写入。主负责人合并全部工作后运行完整测试，
检查 12 份 fixture 全部通过 Schema 校验，并确认没有非豁免文件超过 1000 个物理行。

## M1 完成条件

- 主负责人实现并冻结 Pydantic 领域模型。
- JSON Schema 与模型一致且可重复生成。
- 12 份 fixture 数量和场景分布满足 [TEST_PLAN.md](TEST_PLAN.md)。
- 第一纵向切片的 `120000 → 110000` 数据完整存在，但本阶段不实现 M2 验收引擎。
- 所有离线测试、Ruff 和 `pip check` 通过。
- A、B 的 PR 已由主负责人审查并合入 `codex/m1-integration`。
- 主负责人更新 [STATUS.md](STATUS.md)；A、B 不自行宣布 M1 完成。
