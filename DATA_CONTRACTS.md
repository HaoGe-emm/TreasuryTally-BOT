---
doc-id: data-contracts
title: 数据契约与计算不变量
status: active
authority-for:
  - domain-objects
  - event-identity
  - amount-arithmetic
  - receipt-contract
last-reviewed: 2026-10-07
---

# 数据契约与计算不变量

## 业务报告与本地导出读模型

`reporting.BusinessReportView` 是可重建的中文业务展示，不是新的签名 Receipt。输入必须是通过既有哈希与三态重放的
Receipt、与其 submission hash 和 submission ID 绑定的 ServiceSubmission，以及可选的既有 FundFlowProjection。
只投影已计算总额、Finding、来源和事件；不重新汇总转账、不调用 AI、不改变原验收结果。原 Receipt JSON 与 schema 不变。

`AttemptReport.uncertainties` 既有字段保持不变：INCONCLUSIVE 时第 1 条为合并去重后的安全中文证据原因，
随后才是精度未确认、缺少已存资金流及待核实线索等说明。主要原因只从原 Receipt 中不完整 RPC 来源的
`details.error_code` 按固定白名单映射；不复制 `details.error`、自由文本 `inconclusive_reason`、URL、密钥或任意异常。
未知/缺失/非字符串错误码统一安全泛化为需要查看诊断，不从精度标签推测网络故障。
`HISTORICAL_DATA_UNAVAILABLE` 仅按已存固定码说明节点无法提供所选区块的历史转账证据；
`UNAVAILABLE` 不推断成历史不可用或超时，不以修改报表/填写精度替代参考证据。
PASS/FAIL 不生成该不足原因；完整 RPC 的零事件成功不变成未知，补充 Blockscout 降级不覆盖 RPC 成功。
恢复缺快照时只用原回执的已存字段，不重取网络或生成历史；网页与 Word/PDF 使用同一读模型文字。

金额保留规范最小单位整数字符串；十进制展示用字符串移位，不经 float、不四舍五入为零。差额定义为报表声明减核验金额，
只在参考完整、证据充分且单位一致时用整数相减。参考缺失、精度冲突或币种冲突时不显示可比较差额，说明原因。
未知精度显示最小单位，不猜测币种名称。来源时点表示原证据取得时间，不表示导出时重新抓取链上数据。

修复对比必须保留第一次结果和两个不同回执，绑定同一 spec hash、连续 attempt 和已验证的 M9 parent/supersedes 关系。
缺少关系时只呈现未确认历史，不能把第二次 PASS 宣称为已证明 FIXED。图状态来自既有投影，并同时输出中文图例与引用。

HTML、SVG、PNG、DOCX 与 PDF 只消费同一只读 view 并返回本地下载字节；不接受任意模板、文件路径或外部图片地址。
导出不赋予公开发布或写链权限，报告明确说明它是业务阅读副本，原 JSON 回执仍为独立复核依据。

本文描述概念契约。实现后，字段类型和必填项的机器权威应落入 `schemas/` 中的 JSON Schema；本文继续解释语义、不变量和兼容策略。

## 通用规则

- ID 使用不可变字符串，推荐 UUIDv7 或同等可排序标识。
- 时间使用带时区的 ISO 8601 UTC 字符串。
- EVM 地址存储时保留校验和形式，比较时使用规范化 20 字节值。
- 哈希使用带 `0x` 的十六进制字符串，并记录算法；默认 `keccak256` 或 `sha256`，不得混用而不标注。
- 金额使用代币最小单位的十进制整数字符串，展示值不是计算权威。
- 规范化哈希使用稳定字段顺序、UTF-8 和明确的 canonical JSON 算法。
- 当前 canonical JSON 规则为：JSON 对象键按 Unicode 字符串排序、无非必要空白、UTF-8 编码、数组保留顺序，
  且递归拒绝二进制浮点值；稳定哈希为带 `0x` 前缀的小写 `sha256`。
- 新增字段应向后兼容；破坏性变更必须提升顶层 schema 版本。
- M1 的 Pydantic 领域模型使用严格输入、`extra=forbid` 和冻结实例；适配器必须在进入领域层前完成类型转换。
- M1 地址边界只校验 `0x` 加 40 个十六进制字符并保留输入大小写；地址集合去重和比较使用小写比较键，EIP-55
  校验和转换属于后续标准化层，不由领域模型依赖 Web3 完成。
- M1 的 32 字节交易、区块和内容哈希使用 `0x` 加 64 个十六进制字符；哈希算法仍由字段语义或相邻算法字段确定。
- 所有 `*_base_units` 字段只接受无符号、无前导零的十进制整数字符串（零写作 `"0"`）；适配器内可短暂使用
  Python `int`，但不得用 `float`，进入领域模型时必须转为上述字符串。
- 时间字段必须包含时区且 UTC 偏移为零。

## TaskSpec

```yaml
schema_version: "1.0"
task_id: string
chain_id: integer
token_address: address
treasury_addresses: [address]       # 1..2
recipient_addresses: [address]      # 已确认集合
start_block: integer                # inclusive
end_block: integer                  # inclusive
exclusion_rules: [rule]
max_records: integer                # MVP 固定上限 200
confirmed_at: datetime
spec_hash: hash
```

不变量：

- `start_block <= end_block`。
- 地址集合去重后再计算指纹。
- `treasury_addresses` 必须包含 1..2 个地址；`recipient_addresses` 至少包含 1 个地址；两者分别按小写比较键去重。
- M1 唯一允许的排除规则类型为 `EXCLUDE_TREASURY_INTERNAL`；新增规则类型需要先修改本文并重新冻结契约。
- `max_records` 在 schema `1.0` 中固定为 `200`。
- 任务确认后除 `task_id` 外参与判断的字段不可变。
- 任何修改产生新的任务版本和新的 `spec_hash`。
- `spec_hash` 覆盖除 `spec_hash` 自身外的完整 canonical `TaskSpec`。

## TransferRecord

```yaml
chain_id: integer
token_address: address
transaction_hash: hash
log_index: integer
block_number: integer
block_hash: hash | null
from_address: address
to_address: address
amount_base_units: integer-string
token_decimals: integer
source: rpc | blockscout | service
```

事件身份键为：

```text
(chain_id, transaction_hash, log_index)
```

禁止只用交易哈希去重，因为一笔交易可以发出多个 `Transfer` 日志。

`source` 是事实来源标签：RPC、Blockscout 参考证据和服务自报记录必须保持可区分。模型不禁止多个记录拥有相同
事件键，因为重复项本身是必须被验收引擎识别的输入错误。

## ServiceSubmission

```yaml
schema_version: "1.0"
submission_id: string
task_id: string
service_id: string
service_version: string
attempt: integer                    # 从 1 开始，MVP 最大 2
claimed_total_base_units: integer-string
claimed_count: integer
transfers: [TransferRecord]
report_text: string
created_at: datetime
report_hash: hash
signature: string | null
```

原始文件必须先保存和哈希，再进行解析。解析产物不能替代原始交付。

`services.upload.retain_original` 的哈希目标仅在原字节完整写入、flush/fsync 并关闭后以同目录硬链接原子创建。
相同字节的线程/进程并发留档幂等；已有目标必须逐字节相同，否则拒绝且不覆盖。写入或发布失败不留下部分哈希目标，
只清理当前调用拥有的临时文件；进程突然退出可能留下私有临时孤立文件，不将其当作已留档原件。不支持硬链接的文件系统拒绝操作。

不变量：

- `attempt` 只能为 1 或 2。
- `transfers` 最多 200 条，且其中每条记录的 `source` 必须为 `service`。
- `claimed_count` 为非负整数；不得根据 `transfers` 长度静默改写服务声明。
- `report_hash` 覆盖除 `report_hash` 与 `signature` 外的完整 canonical `ServiceSubmission`；签名绑定
  `report_hash`，当前团队控制 adapter 使用 EVM personal-sign 消息恢复签名者地址。

## VerificationPlan

```yaml
schema_version: "1.0"
plan_id: string
task_id: string
claims: [claim]
queries: [approved_query]
filters: [approved_filter]
aggregation_rules: [approved_rule]
checks: [approved_check]
plan_version: string
```

所有操作必须来自代码定义的白名单。模型生成的未知操作导致计划校验失败，不得降级为任意代码执行。

M1 冻结的白名单枚举为：

- claim：`CLAIMED_TOTAL`、`CLAIMED_COUNT`、`TRANSFER_SET`。
- query：`FETCH_ERC20_TRANSFERS`。
- filter：`TOKEN_ADDRESS`、`BLOCK_RANGE`、`TREASURY_DIRECTION`、`EXCLUDE_INTERNAL_TRANSFER`、`RECIPIENT_SET`。
- aggregation：`SUM_BASE_UNITS`、`COUNT_TRANSFERS`。
- check：`COMPARE_EVENT_SET`、`COMPARE_TOTAL`、`DETECT_DUPLICATES`、`VALIDATE_SCOPE`、`VALIDATE_TOKEN_DECIMALS`。

每项计划操作包含稳定字符串 ID、枚举类型和 JSON 参数对象；未知类型或额外字段必须被拒绝。
`claims`、`queries`、`filters`、`aggregation_rules` 和 `checks` 在已形成的计划中都至少包含一项。

## M4 受限 AI 中间产物

M4 的模型输出是待校验候选，不是已确认任务、参考证据或验收结论。所有模型使用严格输入、`extra=forbid`
和冻结实例；供应商原始响应不得跨过 adapter 进入核心编排。

### TaskSpecCandidate

```yaml
schema_version: "1.0"
candidate_id: string
chain_id: integer | null
token_address: address | null
treasury_addresses: [address] | null
recipient_addresses: [address] | null
start_block: integer | null
end_block: integer | null
exclusion_rules: [rule] | null
max_records: 200
ambiguities: [clarification_issue]
missing_fields: [task_field]
clarification_questions: [string]
```

`missing_fields` 必须与值为 `null` 的必填任务字段精确一致；地址数量、范围顺序和排除规则仍受 `TaskSpec`
同等约束。存在缺失或歧义时必须给出确认问题，且不得生成 `TaskSpec`。只有无缺失、无歧义的候选才能由确定性代码
注入 `task_id`、`confirmed_at`，计算 `spec_hash` 并形成已确认任务；模型不得提供或覆盖这些字段。

### ClaimExtraction

```yaml
schema_version: "1.0"
report_id: string
claims: [claim]
ambiguities: [clarification_issue]
clarification_questions: [string]
source_summary: string
```

主张类型仍只允许 `CLAIMED_TOTAL`、`CLAIMED_COUNT` 和 `TRANSFER_SET`。总额必须是规范十进制整数字符串，
数量必须是非负整数，转账集合必须是 JSON 数组；重复 `claim_id`、重复主张类型或未知类型直接拒绝，冲突主张必须转为
歧义。存在歧义时不得生成执行计划。

### FollowUpAdvice 与 ResultExplanation

补查动作只允许 `NO_ACTION`、`REFRESH_REFERENCE_EVIDENCE`、`CROSS_CHECK_REFERENCE_SOURCE`、
`CONFIRM_TASK_SCOPE`、`REQUEST_RESUBMISSION`、`SWITCH_SERVICE` 和 `MANUAL_REVIEW`。建议只表达下一步，不包含
Shell、文件、SQL、Python、数据库写入、发布或写链调用。

结果解释必须逐字绑定确定性 `VerificationResult` 的 `outcome`、`calculated_total_base_units`、
`calculated_count` 和 Finding ID；模型只能解释，不能改写金额、数量、Finding 或三态结论。

## Finding

允许的首版类型：

- `MISSING_TRANSFER`
- `EXTRA_TRANSFER`
- `DUPLICATE_TRANSFER`
- `EXCLUDED_INTERNAL_TRANSFER`
- `OUT_OF_RANGE`
- `WRONG_TOKEN`
- `WRONG_DIRECTION`
- `AMOUNT_MISMATCH`
- `DECIMAL_ERROR`
- `INSUFFICIENT_EVIDENCE`

每项 Finding 至少包含：

```yaml
finding_id: string
finding_type: enum
severity: info | warning | error
expected: object | null
actual: object | null
violated_rule: string
evidence_refs: [string]
explanation: string
status: confirmed | hypothesis
```

只有 `confirmed` 且证据充分的错误才能导致 `FAIL`；`hypothesis` 只能触发补查或人工确认。
`evidence_refs` 至少包含一个稳定引用。

## VerificationResult

RPC 来源诊断可使用固定 `HISTORICAL_DATA_UNAVAILABLE`：仅表示节点明确拒绝所请求历史日志，
不是报表错误、空转账集合或超时。来源保持 `complete=false`、证据不足，金额/数量不由空集合补零，
结果仍为 `INCONCLUSIVE`。该码是内部集成枚举和来源 details 字符串，不改变 Receipt 1.0 或公共 Schema。

```yaml
run_id: string
task_id: string
submission_id: string
verifier_version: string
reference_sources: [source_descriptor]
reference_complete: boolean
evidence_sufficient: boolean
calculated_total_base_units: integer-string | null
calculated_count: integer | null
findings: [Finding]
outcome: PASS | FAIL | INCONCLUSIVE
inconclusive_reason: string | null
started_at: datetime
finished_at: datetime
```

判定顺序：

1. `reference_complete=false` 或 `evidence_sufficient=false` 时结果为 `INCONCLUSIVE`，并要求非空
   `inconclusive_reason`；此时金额和数量可以为空。
2. 否则存在确认错误，结果为 `FAIL`。
3. 否则所有必需检查完成，结果为 `PASS`。

`PASS` 和 `FAIL` 要求参考完整、证据充分、金额与数量非空且 `inconclusive_reason=null`。只有
`status=confirmed` 且 `severity=error` 的 Finding 属于确认错误；hypothesis 不得单独导致 `FAIL`。
`reference_sources` 只能包含 `rpc` 或 `blockscout`；`reference_complete=true` 要求每个来源描述符也标记完整。

## Receipt

```yaml
receipt_version: "1.0"
receipt_id: string
task_spec: TaskSpec
service_identity: object
submission_hash: hash
verification_plan: VerificationPlan
verification_result: VerificationResult
evidence_manifest: [evidence_descriptor]
created_at: datetime
receipt_hash: hash
publication:
  authorized: boolean
  uri: string | null
  content_hash: hash | null
  transaction_hash: hash | null
  chain_status: NOT_SUBMITTED | SUBMITTED | CONFIRMED | FAILED
  chain_id: integer | null
  reviewer_address: address | null
  transaction_nonce: integer | null
  feedback_index: integer | null
  block_number: integer | null
  error_code: string | null
  error_message: string | null
```

公开回执不得包含私钥、API 密钥、未授权个人信息或未脱敏的私有报告正文。

公开上传对象是 `authorized=true`、尚未绑定 URI 的不可变回执快照。上传后以实际下载字节的 SHA-256 作为
`publication.content_hash`，重新下载并验证一致后，本地发布状态才绑定 URI 与内容哈希。这样避免让文件自带的 URI/内容哈希
形成循环哈希，同时公共文件本身仍可独立校验 `receipt_hash` 并重放确定性结论。

链上状态不把广播等同于确认：`NOT_SUBMITTED` 可表示已公开但未写链；`SUBMITTED` 必须记录 chain、Reviewer 和 nonce，
交易哈希在广播结果未知时可以为空；`CONFIRMED` 还必须包含交易哈希、feedback index 和区块，并已从 `NewFeedback` 事件读回
服务 ID、Reviewer、URI、内容哈希及结果标签；`FAILED` 必须记录脱敏错误码。`SUBMITTED` 的未知写入禁止自动重发。
`FAILED` 只有在用户核对原因并显式授权后才能清除交易字段回到 `NOT_SUBMITTED`；该恢复路径不得接受
`TRANSACTION_UNKNOWN`。

`receipt_hash` 覆盖除 `receipt_hash` 自身外的完整 canonical `Receipt`。publication 状态变化会产生新的回执内容和
新哈希，不得沿用旧哈希。

## Attempt 持久化不变量

- SQLite 分别保存 `TaskSpec`、每个 `ServiceSubmission`/故障注入元数据和每个 `VerificationResult`。
- `(task_id, attempt)` 与 `submission_id` 唯一；attempt 只能追加，禁止 UPSERT 或覆盖。
- attempt 从 1 连续增长到 2；只有第一次结果为 `FAIL` 或 `INCONCLUSIVE` 时才能请求第二次。
- 故障注入元数据只描述团队控制模拟行为，不属于服务声明或 RPC/Blockscout 参考事实。

内部只读 `AttemptStatus` 投影包含 `task_id`、持久化 `state`、`persisted_attempts`、`completed_attempts`、
`in_flight_attempt`、`next_attempt` 和 `blocking_reason`；不增加 Receipt 字段或公共 Schema。
数据库一次快照读取任务状态、交付和结果，不能从 UI session 的回执数量猜测 attempt。
REQUESTED / SUBMITTED / VERIFYING 或状态冲突时不得给出新的执行许可；首次仅 CONFIRMED 且无交付可请求，
补交仅在第一轮终态 FAIL / INCONCLUSIVE 后可请求，最多两次。原始回执缺失或冲突时页面投影阻塞，
不删除交付、不自动取消旧请求、不重跑、不把未知当成功。状态查询不生成历史回执或调用外部服务；
实际执行仍须通过事务内的状态机校验，查询结果不是可重复使用的授权令牌。

## M8–M9 已实现契约与 M10 计划契约

ADR-032 统一上传：严格 JSON 直接校验；CSV / 单工作表 XLSX 由受限模型识别表头，内部确定性适配为同一
`UploadedReport 1.0`，公共 Schema 不变。正常路径不要求用户手动转换、逐列映射或采纳 JSON。
识别产物为版本化 `HeaderRecognition`：每个可发送列仅提供真实原表列索引、受限领域角色与是否歧义，
必须覆盖全部可发送列且不能重复索引/角色、越界、生成字段值、忽略或改配已知规范字段。
模型只接收有界安全表头，不接收明细行、原文件名、私有备注、金额/地址/hash/log_index 或声明值。
未知/疑似隐私或提示指令的列名过滤；未消除歧义、缺模型配置、调用超时或无效输出阻塞，不回退模拟数据。
普通金额列没有明确单位时只询问最小单位/代币单位；缺链/代币/精度允许用户显式补充整表条件，
其他必要事件字段缺失要求修正原表。模型不得补造交易、金额、地址、事件身份、声明或任何数据行。
识别成功后原文件、规范数据与识别 provenance 自动私有留档，然后仍须用户确认核验范围并主动执行。
内部 ready 只表示输入满足契约，不表示 PASS；识别 mode 必须区分真实模型与显式离线测试。

内部表格适配约束：
列名映射与用户显式补充的全表 chain_id/token_address/token_decimals 保存在私有转换记录；不得由 AI 或参考 RPC 猜填原交付字段。
交易哈希、日志序号、区块、付款/收款地址和金额必须来自上传表格；block_hash 缺失可为 null，不伪造哈希。
金额列须明确为最小单位整数字符串或代币单位十进制文本；后者按明确精度用整数运算转换，拒绝浮点、科学记数法与精度损失。
XLSX 金额单元格必须为文本，数值单元格仅支持 General；拒绝公式、宏、日期、外部关系、合并单元格及多工作表，
未知行/单元格命名空间拒绝，防止执行或默默省略交付数据。
保留输入行序和重复事件，不替用户修复或去重。提供的 claimed_total_base_units / claimed_count 必须原样保留，即使与明细不符；
未提供时只生成并明确标注“由明细计算的摘要”，范围确认时仍说明来源，不冒充服务商已声明总数。
原始文件、规范 JSON 与绑定两者哈希/映射/补充字段/警告的转换记录分别私有留档；不修改历史签名或已确认任务。

M8 收尾约定：上传入口支持严格 UTF-8 JSON `UploadedReport`（声称金额、声称数量、最多 200 条 service 来源转账），
原始字节先按 SHA-256 保存于工作区私有目录，解析失败也不能替换为服务 A/B。无外部签名的上传文件由本地
`uploaded-report-intake` 接收器留档签名，身份标签必须为 `local-upload-intake`，不表示原报表作者或 ERC-8004 owner 已签名。
上传文件中的金额和数量声明保持原值，不由 AI、解析器或接收器重算。

承诺、完整证据与提交关联通过工作区私有的只追加 M8 SQLite 表保存；恢复时重新验证签名、任务/交付链接、
证据 manifest 哈希与确定性结果，缺少旧版本快照必须明确显示不可恢复，不能伪造历史承诺。
服务接单和交付签名同时绑定完整任务承诺摘要与 `spec_hash`，防止复用同一 commitment ID 替换任务内容；时间签名
绑定完整 UTC ISO 值，包含微秒精度。投影新增非颜色问题标签与双侧明细，金额/方向不一致不得写成链上不存在。

`TaskCommitment`、`DeliveryCommitment` 与 `FundFlowProjection` 已以 `1.0` 进入 Pydantic 与 `schemas/v1/`。
链上承载尚未实现：真实 Sepolia 只读探针确认当前 Validation Registry 是服务 owner/operator 发起、指定 validator
响应的验证接口，不是 requester 通用任务锚；因此 M8 承诺保持 EIP-712 可验证且 anchor=`NOT_SUBMITTED`。

M9 的 `ReworkPackage`、`ReceiptRevision`、`RepairComparison` 和 `PublicVerificationResult` 使用独立
`1.0` 契约并进入 `schemas/v1/`。它们只引用既有 `Receipt 1.0`，不向旧回执内增加字段，因此不会改变
已生成回执的 canonical JSON 或 `receipt_hash`。M9 通过稳定端口消费 M8 承诺核验结果；缺少承诺快照时必须标记为
`UNVERIFIED`，不得伪造链上确认。M10 使用下述只读历史契约，不改写公共回执。

### TaskCommitment

```yaml
commitment_version: string
commitment_id: string
task_id: string
spec_hash: hash
requester_address: address
service_id: string
created_at: datetime
expires_at: datetime | null
signature_scheme: EIP712
signature: string
anchor:
  chain_id: integer
  status: NOT_SUBMITTED | SUBMITTED | CONFIRMED | FAILED
  transaction_hash: hash | null
  block_number: integer | null
```

任务承诺只绑定已确认 `TaskSpec.spec_hash`，不得把 restricted 组织标签、私有报告正文或凭据直接写链。`CONFIRMED` 必须读回
与 `spec_hash`、requester 和 service 一致的链上记录。当前只读探针已确定现有 Validation Registry 不适合作为该锚，
因此状态保持 `NOT_SUBMITTED`。

### DeliveryCommitment

```yaml
commitment_version: string
task_commitment_id: string
submission_id: string
service_id: string
attempt: integer
report_hash: hash
accepted_at: datetime
submitted_at: datetime
signer_address: address
signature_scheme: EIP712
acceptance_signature: string
signature: string
```

接单与交付使用同一对象中的两个 EIP-712 签名阶段，分别证明服务接受了哪个任务以及提交了哪个报告。签名者必须解析到
预配置服务签名者；接入 ERC-8004 服务时还必须核对 owner 或明确授权者。`report_hash` 继续绑定原始交付而不是解析后的
展示模型。EIP-712 domain 固定应用名、版本与 chain ID，防止跨链和跨用途重放。

### FundFlowProjection

```yaml
task_id: string
attempt: integer
claimed_total_base_units: integer-string
calculated_total_base_units: integer-string | null
outcome: PASS | FAIL | INCONCLUSIVE
nodes: [fund_flow_node]
edges: [fund_flow_edge]
```

每条 edge 必须保留完整事件键、服务声明引用、参考证据引用和视觉状态。视觉状态只允许 `MATCHED`、`MISSING_FROM_REPORT`、
`NOT_FOUND_ON_CHAIN`、`INTERNAL_TRANSFER`、`DUPLICATE`、`INCONCLUSIVE`、`MISMATCH`、`INVALID_SCOPE`；后两者分别表示
同一事件的金额/方向/精度/区块声明不一致，以及确定范围违规，不能误标为链上不存在。它由确定性 Finding 投影产生，不能反向决定
`VerificationResult`。颜色属于 UI，不进入领域权威。

### ReceiptRevisionLink

```yaml
receipt_hash: hash
parent_receipt_hash: hash | null
supersedes_receipt_hash: hash | null
resolution: ORIGINAL | RESUBMITTED | FIXED | UNRESOLVED
```

替代关系只能追加，不能撤销或覆盖旧回执。`FIXED` 必须引用同一任务的早期 FAIL/INCONCLUSIVE 回执以及后续 PASS 回执；
服务切换时仍保留两个不同的 service identity。

M9 实现使用完整的 `ReceiptRevision`：

```yaml
revision_version: "1.0"
task_id: string
service_id: string
attempt: 1 | 2
receipt_hash: hash
outcome: PASS | FAIL | INCONCLUSIVE
resolution: ORIGINAL | RESUBMITTED | FIXED | UNRESOLVED
parent_receipt_hash: hash | null
supersedes_receipt_hash: hash | null
evidence_refs: [string]
created_at: datetime
revision_hash: hash
```

attempt 1 必须为 `ORIGINAL` 且不带父关系。attempt 2 必须同时把 attempt 1 记为 parent 和 superseded；后续
`PASS` 记为 `FIXED`，否则记为 `UNRESOLVED`。每条记录必须与其引用回执的 task、service、outcome 一致。
`revision_hash` 覆盖除自身外的完整 canonical 对象，用于检测关系记录被改写。

### ReworkPackage

```yaml
package_version: "1.0"
package_id: string
task_id: string
source_submission_id: string
source_receipt_hash: hash
created_at: datetime
items:
  - finding_id: string
    finding_type: enum
    violated_rule: string
    expected: object | null
    actual: object | null
    evidence_refs: [string]
    required_action: ADD_MISSING_TRANSFER | REMOVE_EXTRA_TRANSFER | REMOVE_DUPLICATE_TRANSFER |
                     REMOVE_EXCLUDED_INTERNAL_TRANSFER | CORRECT_SCOPE | CORRECT_TOKEN |
                     CORRECT_DIRECTION | CORRECT_AMOUNT | CORRECT_DECIMALS
package_hash: hash
```

只有 `FAIL` 回执中 `confirmed + error` 的 Finding 能进入返工包。`hypothesis`、warning 和
`INSUFFICIENT_EVIDENCE` 不能变成确定返工指令。`package_hash` 覆盖除自身外的完整 canonical 对象。

### RepairComparison

```yaml
comparison_version: "1.0"
task_id: string
before: attempt_snapshot
after: attempt_snapshot
resolved_finding_ids: [string]
remaining_finding_ids: [string]
resolution: FIXED | UNRESOLVED
```

`before.attempt=1`、`after.attempt=2`，两者必须引用同一 task 的不同回执，并与追加版本关系一致。快照保留
task/service/attempt/receipt hash/outcome/resolution、整数金额字符串和证据引用；对比不重新决定验收结论。

### PublicVerificationResult

```yaml
verification_version: "1.0"
reference_kind: URI | RECEIPT_HASH | TASK_HASH | FEEDBACK_TRANSACTION
reference_value: string
status: VERIFIED | INCONCLUSIVE | INVALID
task_id: string | null
service_id: string | null
attempt: 1 | 2 | null
receipt_hash: hash | null
outcome: PASS | FAIL | INCONCLUSIVE | null
resolution: ORIGINAL | RESUBMITTED | FIXED | UNRESOLVED | null
evidence_refs: [string]
commitment_status: VERIFIED | UNVERIFIED | INVALID
checks: [verification_check]
reason: string | null
```

独立验证从解析端口取得公开字节和版本记录，重新校验内容哈希、`receipt_hash`、`spec_hash`、对象链接和三态重放。
必要公开证据缺失返回 `INCONCLUSIVE`，内容或关系冲突返回 `INVALID`。旧 v1 单回执仍可独立重放；未提供 M8 承诺
核验端口时仅将 `commitment_status` 记为 `UNVERIFIED`，不伪造已验证承诺。

### PublicVerificationBundle

`bundle_version="1.0"`、`receipts`（按 attempt 排序的 1–2 份已授权公开 Receipt）、`revisions`（对应 1–2 条
外置版本记录）和 `bundle_hash` 构成可移交的公开验证包。`bundle_hash` 覆盖除自身外的 canonical 对象。
包不包含原报告、ServiceSubmission、私有签名、SQLite 路径或模型文本；生成、下载和公开发布均须授权完整历史。
公开快照的 receipt hash 与私有 attempt hash 可不同，包内版本关系必须重新绑定公开快照，不能复用私有版本记录。
验证必须检查所有回执授权、哈希、确定性重放、同一不可变 spec hash、连续 attempt 和 parent/supersedes 链。
第三方从包 URI 或包内 receipt/task hash 定位回执；task hash 默认定位最新 attempt。仅有反馈交易文本不算链上证据，
缺少独立反馈读回不能验证交易关联。未提供公开承诺证据时 commitment_status 保持 UNVERIFIED。

### ServiceHistoryProjection

```yaml
service_id: string
task_type: string
verified_task_count: integer
first_pass_count: integer
fixed_pass_count: integer
fail_count: integer
inconclusive_count: integer
verifiable_receipt_count: integer
latest_verified_at: datetime | null
receipt_refs: [hash]
```

所有计数必须能由 `receipt_refs` 重算；不同任务类型不得合并成永久综合评分，`INCONCLUSIVE` 不进入负面计数，AI 文本不得
成为任何计数的权威来源。

M10 当前读模型通过 `ReceiptHistoryInput` 接收现有 `Receipt`、显式 `task_type` 与可选来源引用。`task_type` 不从地址、报告文本
或 AI 解释猜测；只有 `receipt_hash`、`spec_hash`、对象链接和确定性三态重放全部有效的回执才进入统计。实现中的投影另保留
`service_name`、`latest_delivery_at`、`latest_verified_at`、完整 `ReceiptSourceRef[]` 与按任务分组的 `ServiceTaskFact[]`，以便每个
计数直接下钻和重算；这些字段属于 M10 只读模型，尚不增加 `schemas/v1/` 的公共回执 schema。

计数按 `(service_id, task_type, task_id)` 归类，每个已核验任务只进入以下一种类别：

- 最新已核验回执为 `PASS`，且没有更早的非 PASS 回执或 M9 修复关系时，计为 `first_pass_count`。
- 最新已核验回执为 `PASS`，且存在更早的 `FAIL` / `INCONCLUSIVE`，或 M9 关系标记为 `FIXED` / `RESUBMITTED` 时，计为
  `fixed_pass_count`；来源下钻保留修复前后的全部已核验回执。
- 没有后续 PASS 且最新已核验结论为 `FAIL` 时，计为 `fail_count`。
- 没有后续 PASS 且最新已核验结论为 `INCONCLUSIVE` 时，只计为 `inconclusive_count`，不增加 `fail_count`。

`verified_task_count` 是上述任务事实数量，`verifiable_receipt_count` 是其唯一有效回执哈希数量。M9 版本关系只通过
`ReceiptRevisionPort` 读取；M10 不修改关系、不覆盖原回执，也不从缺失或无效关系推导负面事实。两服务对比必须限定同一
`task_type`，最终服务选择由用户显式确认，投影不输出排名或综合分。

工作区读取固定 `erc20-grant-report-v1` 类型，仅使用原始不可变 `attempt-N.json`；M6 发布快照与公开历史包的哈希
不作为新的交付重复计数。读取时核对数据库任务、attempt、交付签名与确定性回执重放。M9 adapter 必须取得真实父回执，
校验完整 TaskSpec、版本自哈希、attempt、服务身份和确定性修复关系；缺父链或冲突将该任务排除并提示
`INCONCLUSIVE`，不凭父哈希字符串生成负面事实。旧任务没有版本文件时只在内存从原始回执重建关系，不写入历史。
跨服务 A FAIL → B PASS/FIXED 的成功属于 B，A 仍保留 FAIL。没有历史的候选显示零条记录与“暂无”，不暗示成功或失败。

## M1 fixture 契约

M1 人工标注数据放在：

```text
fixtures/m1/
├─ manifest.json
└─ cases/
   └─ <fixture_id>.json
```

`fixture_id` 和文件名必须一致，使用小写 kebab-case。每个 case 的顶层结构固定为：

```yaml
fixture_version: "1.0"
fixture_id: string
title: string
tags: [string]
task_spec: TaskSpec
submission: ServiceSubmission
reference:
  sources: [source_descriptor]
  reference_complete: boolean
  evidence_sufficient: boolean
  transfers: [TransferRecord]       # source 只能为 rpc 或 blockscout
  insufficiency_reason: string | null
expected:
  outcome: PASS | FAIL | INCONCLUSIVE
  calculated_total_base_units: integer-string | null
  calculated_count: integer | null
  findings: [expected_finding]
human_review:
  summary: string
  calculation: string
  reviewer: string
  verified_at: datetime
```

`expected_finding` 固定记录 `finding_type`、`severity`、`status`、`violated_rule` 和关联的三段式
`event_keys`。`INCONCLUSIVE` case 必须在 reference 中说明证据不足原因，不能用服务错误冒充。
`manifest.json` 使用 `FixtureManifest`，包含 `fixture_version` 和 12 个 `FixtureManifestEntry`；entry 固定记录
`fixture_id`、相对 `file`、`title`、`tags` 与 `expected_outcome`。

## M1 JSON Schema 命名

Schema version 为 `1.0`，稳定输出目录和文件名为：

```text
schemas/v1/task_spec.schema.json
schemas/v1/transfer_record.schema.json
schemas/v1/service_submission.schema.json
schemas/v1/verification_plan.schema.json
schemas/v1/verification_result.schema.json
schemas/v1/receipt.schema.json
schemas/v1/fixture_case.schema.json
schemas/v1/fixture_manifest.schema.json
schemas/v1/task_spec_candidate.schema.json
schemas/v1/claim_extraction.schema.json
schemas/v1/follow_up_advice.schema.json
schemas/v1/result_explanation.schema.json
schemas/v1/task_commitment.schema.json
schemas/v1/delivery_commitment.schema.json
schemas/v1/fund_flow_projection.schema.json
schemas/v1/uploaded_report.schema.json
schemas/v1/rework_package.schema.json
schemas/v1/receipt_revision.schema.json
schemas/v1/repair_comparison.schema.json
schemas/v1/public_verification_result.schema.json
schemas/v1/public_verification_bundle.schema.json
```

每个文件的 `$id` 使用 `urn:xinjv:schema:1.0:<kebab-name>`，标题使用对应 Pydantic 公共类名。生成入口为
`scripts/export_schemas.py`；前八份为冻结的 M1 顶层契约，随后四份为 M4 受限 AI 中间产物，再后四份为 M8 契约，最后五份为 M9 追加契约。
公开验证包 Schema 通过稳定 URN `$ref` 复用 Receipt 与 ReceiptRevision；独立 JSON Schema 验证器须将
`schemas/v1/` 契约按 `$id` 注册到本地 schema registry，不依赖网络解析，也不重复内嵌整份回执定义。
重复生成不得产生差异。

## 精确计算规则

## M16 headless 与 MCP 工具契约

M16 只在本机 `stdio` 进程中暴露现有确定性核心。客户端只能提交不透明 `workspace_handle`，不得提交数据库、回执目录、
任意文件路径、SQL、Python、Shell、环境变量名或密钥。handle 只由本机配置映射到一个工作区；未知 handle 与跨工作区对象引用
均拒绝。工具响应不得返回底层路径、原始报告正文、签名、认证头、RPC URL 或密钥。

M15 Skill 消费的冻结 facade 为 `HeadlessTrustReceiptPort`，版本 `1.0`，仅含下列方法：

```text
draft_task(workspace_handle, user_request) -> TaskCandidateView
prepare_task_confirmation(workspace_handle, candidate) -> AuthorizationChallenge
confirm_task(workspace_handle, challenge_id) -> ConfirmedTaskView
prepare_report_verification(workspace_handle, task_id, report_json) -> AuthorizationChallenge
verify_report(workspace_handle, challenge_id) -> AttemptResultView
get_result(workspace_handle, task_id, attempt) -> AttemptResultView
get_receipt(workspace_handle, task_id, attempt) -> ReceiptView
replay_receipt(workspace_handle, task_id, attempt) -> ReceiptReplayView
```

`user_request` 最多 4,000 个字符；`report_json` 是最多 1 MB 的内联 UTF-8 `UploadedReport 1.0`，不得替换为路径或 URI。
M16 不提供公共发布、写链、任意网络 URL 读取、任意代码或 SQL 工具。

### AuthorizationChallenge

```yaml
interface_version: "1.0"
challenge_id: opaque-string
workspace_handle: opaque-string
action: CONFIRM_TASK | VERIFY_REPORT
payload_digest: sha256-hash
task_id: string | null
task_spec_hash: sha256-hash | null
attempt: 1 | 2 | null
summary: string
authorization_state: PENDING | APPROVED | CONSUMED | EXPIRED
expires_at: datetime
```

`payload_digest` 是授权请求摘要，不只是报告内容哈希：它绑定 interface version、workspace handle、action、内容哈希以及可用时的
task ID、`spec_hash` 与 attempt。`prepare_*` 只生成待批准挑战，不确认任务、不消费 attempt、不执行 RPC。批准必须由未暴露为 MCP tool 的本机交互命令写入，
因此模型不能通过补造布尔值、确认短语或重复调用替代用户授权。`confirm_task` 与 `verify_report` 只消费同工作区、未过期且
payload digest 完全一致的已批准挑战。消费结果持久化；同一 challenge 重复调用返回原任务或原 attempt，不产生重复写入。
重启后仍维持该幂等语义。第二次 attempt 仍受既有 repository 状态机约束，第三次请求必须拒绝。
准备和消费报表 challenge 都必须读取 `AttemptStatus`；`REQUESTED`、`SUBMITTED`、`VERIFYING`、缺失回执、回执冲突或状态冲突
一律阻塞，不自动取消、回滚或重跑。并发消费者最终仍由 SQLite 原子 attempt 预留裁决，失败方不得生成第二份交付。

### Facade 视图

- `TaskCandidateView` 返回严格 `TaskSpecCandidate`、candidate digest 和 `UNCONFIRMED`，不返回确认状态。
- `ConfirmedTaskView` 返回 `task_id`、`spec_hash`、`CONFIRMED` 和 `idempotent_replay`；不接受客户端指定 task ID、确认时间或哈希。
- `AttemptResultView` 返回 task ID、不可变 `spec_hash`、submission/attempt、三态 outcome、整数金额字符串、数量、Finding 摘要、
  证据完整性、来源诊断、receipt hash 以及 `idempotent_replay`。消费者比较两次结果必须同时核对 workspace、task ID 与
  `spec_hash`；RPC 或配置不足必须显式为 `INCONCLUSIVE` 或 `BLOCKED`，不得用 fixture 结果代替。
- `ReceiptView` 返回可重放 Receipt 结构，但删除或拒绝原始报告正文、签名、路径和秘密字段。
- `ReceiptReplayView` 返回 recorded/recomputed outcome、哈希与对象链接检查及 `valid`；它只重放已保存回执，不重新抓链。

工作区 profile 必须显式标记 `LIVE_READ_ONLY` 或 `FIXTURE_TEST_ONLY`。默认是 `LIVE_READ_ONLY`，缺少模型或 RPC 配置时返回
`BLOCKED`；fixture profile 仅供本地测试并在每个候选、结果和回执响应中携带 `fixture_test_only=true`，不得表述为真实链上验收。

### 业务报告本地渲染绑定

只读 `RenderedDiagram` 保存完整冻结 view JSON 的 SHA-256、派生 option JSON 的 SHA-256、PNG bytes 与静态 SVG。
view 包含 spec/receipt hash；worker binding 是上述两个哈希拼接字符串的 SHA-256。导出自身调用 renderer，不接受用户 PNG。
这些本地字段不进入 Receipt、公有 Schema 或链上承诺，不重新决定金额/状态；图是局部预览，全部事件与精确单位保留在附录。

### M8 专用锚候选的读回绑定

专用最小锚只记录 requester 的完整 task commitment digest、spec hash、service ID hash 和指定 service signer，
以及 service signer 的 attempt、submission ID hash、report hash 和完整 delivery digest。摘要使用现有 canonical JSON SHA-256；
文本 ID 使用 UTF-8 SHA-256。合约不验证报表内容，不认证 ERC-8004 owner，不处理资金，也不替代离线 EIP-712 校验。
读回必须匹配配置 chain ID、合约 runtime bytecode SHA-256、成功交易、canonical block hash、确认深度、交易发送方和全部事件字段。
未知交易保持 `SUBMITTED`；读回不一致拒绝，不能按未知状态宣称成功。当前候选未部署，页面不接入写链。

- 所有加减在 `amount_base_units` 整数上完成。
- `decimals` 只影响显示格式；不得先转浮点数再汇总。
- 参考集合和交付集合在应用同一任务规则后进行比较。
- 分页完成条件由数据适配器显式报告；未知分页状态不能视为完整。
- 区块范围两端均包含在内。
- 超过 200 条相关事件时不抽样通过，返回需要分段的明确状态。
