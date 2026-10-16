---
doc-id: test-plan
title: 测试与验收计划
status: active
authority-for:
  - test-matrix
  - quality-gates
  - acceptance-evidence
last-reviewed: 2026-10-07
---

# 测试与验收计划

## Linux 报告运行接线门

`scripts/deploy/check_report_runtime.py` 仅在无密钥、无网络、无生产数据挂载的镜像运行，输入 7 个合成 view：
验证实际隔离 launcher → ECharts SSR → sharp PNG → DOCX/PDF 字节、view hash、内嵌字体及 source/wheel 全报告资产一致。
同时实际断言 renderer socket 创建返回 EPERM、父应用仍可创建 socket、任意 Node 参数被拒绝、缺 renderer 不兜底。
验证时设置 `--memory 2g --memory-swap 2g --pids-limit 256 --cpus 2 --cap-drop ALL --security-opt no-new-privileges`
及 `--network none`；这证明受控本地渲染，不声称 RPC 连通、生产部署或新增逐页视觉审批。
实际 `/app` 初始入口另由 `scripts/deploy/check_image.py` 检查源码/wheel、AppTest exception 和品牌区，不能替代下载状态矩阵。
`scripts/deploy/check_report_downloads.py <synthetic.view.json> <synthetic.receipt.json>` 在同样隔离边界使用实际
app 单实例 renderer，主动触发五种格式生成，断言原 JSON 加五格式共六个下载入口、正确格式和完整 view 缓存。
它不使用预生成下载 bytes 或 mock exporter，不执行浏览器/HTTP 下载，也不声称完整真人可用性验收。

## 业务报告与导出验证

- 固定 ECharts worker 核验资源哈希、只接派生 JSON、拒绝未知键/image/code；测试缺依赖、超时、并发上限、回包 binding 错误与凭据环境不转发。
- 用独立 Linux Python 3.12 / Node 22.23.3 / sharp 0.34.5 无网络运行 SSR→PNG→DOCX/PDF，与 bundled 作者验证分别记录。
  Windows 成功不是部署就绪；全部页须另检查，缺 font/Node 不允许 Python 仿制回退。

- 12 份冻结案例投影必须保持原 outcome、最小单位总额与事件引用；报告不得改变 Receipt 字节或 schema。
- 覆盖 1 最小单位/18 精度、超大整数、零与有符号差额；未知精度、DECIMAL_ERROR、错误与混合资产不得伪装为可比正常金额。
- 完整性篡改、不同任务/attempt/金额的图、错误版本关系必须拒绝；两次交付保留原 FAIL，缺关系只写未核实。
- Finding 的私有备注、模型英文全文、凭据型 URL、签名和原件不得进入任何报告；HTML/SVG 转义、无外部请求；长度/规模超限拒绝。
- DOCX/PDF 由同一 view 输出，校验正文中文、精确金额、同一 spec/receipt hash、两次 outcome、全部 200 事件引用、嵌入字体和可打开结构。
- 使用 loader 选定的 bundled runtime authoring，并在首次创建产物前执行对应 artifact marker；Windows 缺 bundled LibreOffice 时禁止回退桌面安装版。
- 文档必须渲染为逐页 PNG 并检查所有页：中文字体、分页、图例、长地址/哈希、微小金额、200 条记录、三态和双 attempt；文本或 magic bytes 检查不代替视觉门。
- 隔离 QA 容器是独立验收工具链，不是生产依赖或 bundled LibreOffice；生成代码不能硬编码本机 Office、bundled runtime 或 QA 容器路径。

## 测试目标

证明系统能在限定范围内完整、精确、可重复地核对报表，并能把供应商错误、基础设施故障和证据不足区分开。

## 测试层级

### 单元测试

- 地址和哈希规范化。
- 区块范围边界。
- 内部互转排除。
- `tx_hash + log_index` 去重。
- 最小单位整数加减与展示格式。
- 交付集合和参考集合差集。
- 三态结果判定。
- canonical JSON 与稳定哈希。
- attempt 不可覆盖。

### 契约测试

- RPC `eth_getLogs` 请求、返回和错误映射。
- `tests/m5/test_historical_rpc_failure.py` 验证受限历史拒绝一次读取、其他方法/未知 4444/畸形响应不误分类，
  普通超时与连接重试不变、供应商正文不进入新诊断或异常链、后页失败不完整与成功空页仍完整。
- Blockscout MCP 工具参数和分页终止条件。
- Agent0 身份读取和服务标识。
- ERC-8004 提交、receipt 和读回字段。
- IPFS/文件发布后的内容哈希一致性。

外部契约测试默认可跳过，但必须有明确 marker 和跳过原因，不能悄悄通过。

外部测试执行规则：

- 统一使用 `external` marker，文件放在 `tests/external/`。
- 普通本地测试可以排除 `external`；M0 验收命令必须执行它，缺少配置时明确失败或报告阻塞，不得自动伪装成通过。
- 单次外部请求默认超时 30 秒，单个探针总时限 120 秒；供应商明确要求更长时间时需在集成记录中说明。
- 只读幂等请求最多自动重试两次，并采用退避；交易广播响应不确定时不得自动重发。
- 外部测试输出只保留脱敏摘要、公开地址、交易哈希、区块和错误分类，不打印密钥、认证头或环境变量全集。
- Mock 测试只能验证 adapter 行为，不能作为“外部能力已实测”的证据。
- OpenAI 与 DeepSeek 模型探针分别要求 API key 和固定模型名；缺少任一项时必须以 `external` skip 原因明确报告阻塞。

### 集成测试

- TaskSpec → 服务交付 → 验收 → SQLite 保存。
- 首次 FAIL → 一次补交 → PASS，两个 attempt 都可读取。
- 服务 A FAIL → 切换服务 B → 新交付单独记录。
- 参考节点故障 → `INCONCLUSIVE`，不产生负面反馈。
- 回执创建 → 发布 → 链上提交 → 确认状态。

### 端到端测试

- 正确报告直接通过。
- 120000 报告包含 30000 内部互转并漏掉 20000，正确总额为 110000。
- 全新进程只读取公共回执，校验哈希并复现至少一项确定性检查。
- Streamlit 页面在任务确认前不提供执行入口，首次 FAIL 后可完成唯一一次补交或换源，并同时保留两个 attempt。
- 真实 DeepSeek、Sepolia RPC 与 Blockscout 组合探针必须完成候选生成、A `FAIL`、B `PASS`、两个 `SAMPLED` 补充诊断、
  无 AI 产物校验错误和两个独立回执。
- 同一工作区 ID 在 Streamlit 进程重启后必须恢复已确认任务及两个 attempt，不重新生成历史 AI 文本。
- 桌面宽屏可并排显示编辑与指标；760px 及以下强制单列，长地址、Finding、回执 JSON 和主要按钮不产生不可操作的水平溢出。
- M7 无凭据演示必须完成服务 A `FAIL`、切换服务 B `PASS`、两个 attempt 留档、两份回执独立重放及新进程路径恢复；
  输出必须显式标注 `publication_mode=not-executed`，不得冒充 M6 外部验收。

### M8–M10 计划验收

- M8：上传固定错误报表后，资金流图必须把匹配、漏报、内部互转、重复和证据不足映射到稳定文本/图标状态；每条边能下钻到
  完整事件键和证据引用，图的颜色不能是唯一信息载体。
- M8：任务、接单和交付签名被篡改、签名者不属于服务或链上锚定读回不一致时必须拒绝；提交未知时保持 `SUBMITTED`，
  不得自动重发。
- M8：上传原文件声明参与核验，不能改写为 fixture；修复报表可以使用第二个 attempt，原文件和原 FAIL 不覆盖。
  JSON 重复 key、错误编码、浮点金额和超限输入必须拒绝。恢复必须重验完整 task digest、微秒时间戳、签名、manifest 与结果，
  私有证据被篡改时停止恢复。专用锚候选的本地合约测试不等于真实部署验收。
- M9：首次 FAIL 自动形成只包含已确认 Finding 的返工包；第二次 PASS 与首次结果并排存在，父回执和 supersedes 链可重放。
- M9：独立验证入口从 URI、receipt hash、task hash 或 feedback transaction 进入时得到一致对象关系；缺失任何必要证据返回
  `INCONCLUSIVE`，不能显示绿色有效。
- M9：完整公开历史包按公开快照重新绑定版本链；新进程、新浏览器仅凭包验证两次回执、同一 spec 和 FIXED 关系。
  交换 attempt、篡改父回执/哈希、重复 JSON key、浮点或超限公开文件必须拒绝；发布下载字节不符不得保存成功元数据。
  真实反馈读回必须校验 Registry 发出地址、canonical block、确认数、reviewer、值/标签、URI 与内容哈希；仅给交易文本
  不能通过。独立页面在缺少模型/私有工作区时仍可验证公开包，网络请求不得重定向到私有地址。
- M10：服务历史全部计数可由引用回执重算；任务类型隔离；`INCONCLUSIVE` 不增加失败数；任一指标都能下钻到来源回执。
- 可用性：首次访问只出现一句价值说明、三步主流程和一个主按钮；固定演示不依赖口头解释即可走通
  `FAIL → 返工 → PASS → 发布 → 验证`。

### M16 headless / MCP 验收

- 用真实 stdio 子进程执行 MCP `initialize`、`tools/list` 与每类 `tools/call`，不能只调用 adapter Python 函数。
- 未经本机外置批准的任务确认与报表核验返回 `AUTHORIZATION_REQUIRED`；MCP tool 不提供批准能力。
- 同一 challenge 重复调用和 server 重启后调用返回相同 task/attempt；第二次 attempt 后准备第三次必须拒绝。
- 授权摘要绑定 workspace/action/content/task/spec/attempt；同候选跨工作区摘要不同，challenge 不能跨工作区消费。
  AttemptResultView 必须携带与确认任务和回执一致的 `spec_hash`，供消费者拒绝范围漂移。
- 准备与消费 challenge 都读取持久化 AttemptStatus；REQUESTED/SUBMITTED/VERIFYING、缺失/冲突回执必须阻塞。两个并发、
  已批准且绑定同一 next attempt 的 challenge 只能有一个取得预留，另一方不得生成交付。
- 跨 workspace task/challenge、路径穿越、额外 path/SQL/code/secret 字段、重复 JSON key、浮点金额和超限报告全部拒绝且不回显输入。
- 默认 live profile 缺模型或 RPC 明确 `BLOCKED` 且不消费 attempt；fixture profile 在全部响应中标记测试来源。
- 结果、回执和重放只从固定 workspace 读取；不得输出原始报告、签名、底层路径、RPC URL、环境变量或密钥。

## 前端规范回归

- 字号 token 必须精确对应 `12/14/16/20/24px`；自定义 HTML、原生标题、输入、按钮、说明、JSON 与图节点均纳入检查。
- 在 `1440×1000`、`390×844`、760px 两侧与 200% 放大检查实际计算字号和溢出；移动端不得缩小字体，SVG 不随容器缩放文字。
- 保留炭黑材质、低对比本地区块链装饰、透明原图 logo；普通卡片/指标/折叠区无外框，状态统一中性灰。
- 关键结论与金额通过位置、字号、字重、分组与留白强调，不只改字体颜色；运行配置不重复为气泡，流程序号只保留顶部一套。
- 自动测试通过不等于全部视觉验收通过；浏览器实测视图和未测项分别记录在 [STATUS.md](STATUS.md)。

## 人工标注数据集

至少 12 份：

| 类型 | 最少数量 |
|---|---:|
| 完全正确 | 2 |
| 漏项 | 2 |
| 重复事件 | 2 |
| 内部互转误计 | 2 |
| 区块范围错误 | 1 |
| decimals/单位错误 | 1 |
| 多错误组合，开发期间隐藏 | 1 |
| 证据不足 | 1 |

每份 fixture 包含输入、期望结果、期望 Finding 和人工核验说明。故障注入必须与真实供应商数据明确隔离。

## AI 测试

- `tests/m4/test_task_draft_deadline.py` 用真实 OpenAI/DeepSeek SDK 加无网络 mock transport 检查
  超时、连接、429、5xx 与 401 分类、单次请求与关闭连接；挂起 transport 在独立操作预算到期后收到取消，
  不接纳迟到输出。此离线门不是供应商连通或真实延迟验收。
- 候选空输出/非法 schema 必须拒绝，非候选 AI 操作保留原 timeout/retry；候选额外输出预算不降低金额与范围校验。

- 对歧义任务必须提出确认，不得自行补全关键地址或区块。
- 输出必须通过 Pydantic 校验。
- 未知工具、过滤器或检查类型必须被拒绝。
- Prompt injection 文本不得取得文件、Shell、数据库或写链权限。
- 同一确定性输入允许解释措辞不同，但验证结果和金额必须一致。
- 任务候选缺失字段列表必须与空字段精确一致；存在缺失或歧义时不得确认任务。
- 计划中的查询、过滤、聚合和检查必须完整命中白名单，参数必须来自已确认任务。
- 补查建议只能使用封闭动作枚举；解释必须覆盖相同 Finding ID 和证据引用。
- OpenAI-compatible/DeepSeek adapter 的离线 mock 只证明协议映射，不计作真实模型调用。

## 质量门槛

- 首屏品牌/CSS 直接 HTML 渲染并保持 JavaScript 默认关闭；Logo eager、尺寸固定，复用 288px 媒体预览，反向代理路径正确，原图不得改绘。
  浏览器记录首屏标题、品牌图可见性及资源时序，区分冷请求与缓存请求，不凭最终截图推导速度。

- 发布镜像必须逐文件验证源码覆盖层与 wheel 一致，并从真实 `/app/app/streamlit_app.py` 执行隔离 AppTest，
  零 exception 且产品标题渲染；不得通过 PYTHONPATH、源码归档目录或健康端点替代。部署后用独立浏览器确认首页实际渲染。

- 核心纯函数单元测试全部通过。
- 12 份标注样例的确定性期望全部匹配。
- 对金额、分页和结果状态的测试不得使用宽松断言。
- Ruff 检查通过。
- `pip check` 无破损依赖。
- 涉及外部系统的能力必须报告“已实测”或“未实测”，不能用 mock 结果代替实测声明。
- GitHub Actions 的普通质量门运行 `not external` 测试、Ruff、`pip check`、Schema 重生成检查、1000 物理行限制和
  无凭据 MVP 演示；治理文档 metadata 与链接检查包含在契约测试中。外部探针没有显式密钥时保持跳过，不得以 mock 或
  空配置标记为外部成功。

## 标准命令

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
```

后续引入 marker 后建议：

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not external"
.\.venv\Scripts\python.exe -m pytest -m external
```

M0 验收使用：

```powershell
.\.venv\Scripts\python.exe -m pytest -m external -v
```

## 验收记录

### CSV/XLSX 首步转换

运行 `python -m pytest tests/test_report_conversion.py`。覆盖编码/分隔符、精确整数换算、超精度不舍入、Excel 数值金额拒绝、
重复行及错误声明不修复、缺字段不猜测、列映射冲突与显式常量、共享字符串与富文本、公式（含错误命名空间）、
宏/外部关系/多工作表、XML 实体与 UTF-16、日期/自定义数值格式、ZIP 展开/不支持的压缩方式与表格上限、确认前不留档、原件哈希绑定、
幂等追加与损坏留档拒绝。专项不调用网络或模型、不使用真实密钥、不替代外部核验。
UI 另测未采用候选不得形成正式上传、改文件/改映射使确认失效、JSON 旧路径和补交/恢复状态保持原约束。
集成测试 `tests/m8/test_conversion_recovery.py` 检查转换采纳不创建任务、原声明和本地身份不改写，
新工作流仅从持久化证据与签名恢复；原 CSV 私有备注/文件名及 provenance 不进入本地构造的授权公开包。
此测试只验证序列化与授权拒绝，不调用 publisher，不表示公开文件已上传。

### 执行记录位置

ADR-032 识别专项 `tests/test_report_recognition.py`：模型输入仅安全表头、私有/注入标签过滤，严格 JSON 不调用模型，
完整真实列绑定/索引/类型/额外字段检查、已有声明/source 不忽略、歧义/普通金额单位阻塞、显式整表条件、
缓存文件与模型绑定、错误脱敏、不回退 fixture、自动私有留档与原件变化拒绝。mock 测试不计真实 API 识别。
真实 OpenAI/DeepSeek 表头识别外部验收须单列，禁止自动发送真实敏感报表或私有样本。

受限真实探针 `tests/external/test_report_recognition_probe.py` 仅构造合成 CSV：正常字段绑定、
缺金额单位的局部问题两例。通过实际 factory/provider/recognize_report 路径，只发送业务表头与索引，
不发送合成行值或文件名。读取既有被忽略配置（可用 `M14_PROBE_ENV_FILE` 指向既有文件），
固定选择已有 DeepSeek，否则仅在 DeepSeek 未配置时选择已有 OpenAI；运行后不切换供应商重试。
每例最多一次真实请求、超时上限 30 秒、自动 retry=0；补单位使用已绑定缓存，不增加请求。
缺配置明确 skip、不回退 fixture；输出仅 mode/model_id、耗时、Schema/列角色与本地状态。
该门不执行 RPC、私有留档、任务创建、公开上传或写链，不代表真实 XLSX 或完整业务验收；
实际执行结果仅记录在 STATUS.md。
旧采纳 UI 测试仅为 ADR-031 历史实现；ADR-032 页面需另测直接上传、必要局部问题、缓存失效、显式重试、
非法输入不回退旧 service、范围确认和两 attempt 恢复，不继续要求采纳 JSON。

测试执行结果写入 CI 日志或发布检查记录；当前进度摘要写入 [STATUS.md](STATUS.md)。不要在本文复制瞬时通过数量。
