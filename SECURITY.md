---
doc-id: security-policy
title: 安全、隐私与密钥规则
status: active
authority-for:
  - secret-handling
  - privacy-boundary
  - security-invariants
last-reviewed: 2026-10-07
---

# 安全、隐私与密钥规则

## 业务报告与本地导出

业务报告只列受控字段：任务范围、原确定性结果、公共账户/事件引用、来源类型与取得时间、回执/任务哈希。
不复制上传原件、report_text、签名、模型原文、任意 Finding explanation/expected/actual 字典、source details 或来源 URI。
Finding 数值说明仅选规范整数的既有 amount/count/decimals；证据引用只保留符合固定事件键语法的引用，凭据型 RPC URL 不进入报告。

HTML/SVG 必须转义文本且无脚本、外部图像/字体/样式请求；DOCX/PDF 只由固定模板及本包 OFL 字体生成。
字体是受审查的程序资源，不接受用户提供路径。导出直接返回 bytes，不持有 Shell、任意文件写入、网络、publisher 或链上端口。
固定 Node worker 使用 subprocess argv / shell=False，只接业务 view 派生 JSON，禁止用户 code/formatter/image URL。
不传入凭据、NODE_OPTIONS 或继承的 NODE_PATH；单实例 Node 并发 1、20 秒超时、128 MB JS 堆、256 KB stdin、512 KB SVG、
4 MB PNG、6 MB stdout、260 万像素，sharp 无缓存且线程为 1。JS 堆限不是 native 总内存硬限，部署必须另加 cgroup/Job、pids 和禁止网络出口。
回包 binding 必须匹配完整 view/option 哈希，导出不接受跨任务 PNG；stderr 不进入用户日志或报告。
Linux 部署通过受信 `REPORT_RENDERER_NODE` 启动器继承 seccomp 的 socket 拒绝规则，父应用仍可访问 RPC；
启动器仅允许固定包内脚本和固定 Node 参数，未知 ABI/无法启用隔离时拒绝。`REPORT_RENDERER_MODULES` 仅由运维设置。
compose 提供 app 与 renderer 合计 640 MiB native 内存硬限、无额外 swap、128 pids、1 CPU、no-new-privileges、drop ALL capabilities；
它不是每个 worker 独立的 native 内存保证，极端 OOM 可能影响同容器应用。单应用复用一个 renderer，
`export_slot()` 非阻塞预算覆盖 DOCX/PDF/HTML/PNG/SVG 完整构建生命周期及直接 render，最多一个线程导出；
同线程嵌套可重入，其他线程立即拒绝，异常时释放。Node 返回后字体嵌入、PDF 排版和 ZIP 打包仍占完整预算。
该串行预算不等于 native 内存硬限；原 JSON 下载不依赖 renderer 或该预算。
页面衍生导出缓存全应用最多 16 MiB、单文件最多 8 MiB，每会话只保留当前完整视图五格式；
会话状态不存格式 payload。框架媒体只释放自身精确 session/coordinate/fileID 引用，
其他控件仍持有的去重文件继续计预算，原 JSON、原件及业务历史不清理；兼容能力缺失时拒绝注册。
这些缓存常量是待低内存压力门确认的候选，不代表整机资源足够。
进程另有 20 秒 CPU、64 fd、8 MB file-size、禁 core dump。worker 网络限制不依赖“代码没有网络调用”的假设。
文档资源检查上限为每 attempt 400 条投影记录、1000 项 Finding、2 MB view 序列化与单文本 4096 字符、正文 6 万字符。
绘图独立上限为 200 条保存记录，超限明确不可用；主图最多四条，拥挤并行线仅首条，明确标出总数。
完整记录保留于明细附录。页面绑定当前工作区后才主动下载，不得从公开验证入口读取私有报告或把下载当成发布授权。

报告的资产/精度未知时显示原整数与未确认单位；不能给错误或混合资产总额套用任务代币精度。
INCONCLUSIVE 不能在任何格式中写成服务失败；两次交付关系缺证时不得声称已核实修复。
QA 容器仅挂载离线测试产物与专用工具，实际渲染使用 network=none、资源上限及超时，不挂载 .env、密钥或真实私有数据。

## 原型安全边界

本项目处理外部报告、链上地址、API 密钥和测试网签名。原型不应持有主网资金控制权，不提供托管、支付或自动转账能力。

## 密钥规则

- 只使用 `.env` 或运行环境注入密钥；`.env` 已被 `.gitignore` 排除。
- `OPENAI_API_KEY` 与 `DEEPSEEK_API_KEY` 必须分别配合固定的 `OPENAI_MODEL`、`DEEPSEEK_MODEL`；不得把供应商密钥
  放入 prompt、fixture、回执或测试快照。
- `.env.example` 只能包含变量名和无敏感示例。
- `SERVICE_A_PRIVATE_KEY`、`SERVICE_B_PRIVATE_KEY`、`REVIEWER_PRIVATE_KEY` 必须是测试网专用钱包。
- 团队控制报表服务使用测试钱包对 canonical `report_hash` 签名；repository 接收前必须恢复并比对预配置签名者地址。
  自动化测试只在运行时生成临时无资产账户，不得把测试或真实私钥提交到仓库。
- ERC-8004 写探针还必须显式设置 `M0_ENABLE_WRITES=true`；默认值为 `false`，未知提交状态禁止自动重发。
- M6 产品写入另由 `M6_ENABLE_WRITES=true` 显式开启；页面还必须分别取得公开文件与 ERC-8004 写入授权。匿名访问不赋予写权限。
- `AGENT0_SERVICE_ID` 必须配合公开的 `AGENT0_EXPECTED_OWNER` 校验，避免向非团队控制身份写入测试反馈。
- 禁止使用持有主网资产的钱包、个人常用钱包或复用助记词。
- 不在日志、异常、截图、回执、测试 fixture 或模型 prompt 中输出密钥。
- 如果密钥出现在提交或日志中，按已泄露处理并立即轮换。对话中出现的测试供应商密钥默认也应轮换；但项目所有者
  明确授权继续使用时，只能写入被 Git 忽略的本机 `.env`，不得复制到受版本控制文件、日志、fixture、回执或模型 prompt。

## 数据分类

| 数据 | 分类 | 处理方式 |
|---|---|---|
| 公共链上事件 | public | 可引用并保留来源 |
| 脱敏验收回执 | public-after-approval | 用户授权后发布 |
| 原始服务报告 | restricted | 默认本地保存，公开前审查 |
| 组织标签和排除规则 | restricted | 仅发布必要部分 |
| API 密钥、私钥、JWT | secret | 只存在安全运行环境 |
| 模型输入输出 | internal | 不默认作为公开证据 |

## 主要威胁与控制

### 恶意或错误报告

控制：所有服务交付视为不可信；解析有大小和记录数上限；确定性规则对照独立来源。

### Prompt injection

控制：报告文本不能扩展工具权限；模型只返回受限 schema；模型端口不持有任意 Shell、文件、SQL、repository、发布、
Python 或写链工具。未知操作、额外字段、任务参数漂移以及结果金额/状态漂移在确定性边界拒绝。

### 伪造或重复事件

控制：检查 chain、token、区块、交易哈希、log index；按事件身份键去重；必要时保存 block hash。

### 数据源不完整

控制：分页完整性显式建模；超时、限流、重组或来源冲突返回 `INCONCLUSIVE`。

### 回执泄露隐私

控制：公开版和私有证据分离；公开前展示待发布内容并取得授权；使用内容哈希关联，不默认发布原始报告。

### 错误链上信誉

控制：只有证据充分的 `FAIL` 可以进入负面反馈候选；写链前显示服务、任务范围、回执哈希和网络；确认后才显示成功。

### M8–M10 承诺与公开验证

- 任务承诺只包含任务哈希、公开身份、时间和必要公共引用；受限组织标签、原始报告、模型输入和凭据不得进入签名明文或链上事件。
- EIP-712 domain 必须绑定 chain ID、验证合约或明确的应用域和版本，防止跨链、跨环境与跨用途重放。
- 服务接单和交付签名必须分别校验 task hash、report hash、attempt、service ID 与签名者授权关系。
- 当前 M8 EIP-712 domain 固定 `TrustReceipt`、版本 `1` 与 chain ID；Validation Registry 只读探针不授予写权限，且其接口
  不被当作 requester 通用锚。只有专用 adapter 完成合约审查、授权与真实读回后，anchor 才能从 `NOT_SUBMITTED` 变化。
- 匿名演示入口只能发起只读验收和准备待授权对象；不得调用服务器 Reviewer 钱包替匿名用户自动确认任务、发布或写链。
- 公开验证页只读取公开回执和公共链上数据，不得通过 task hash 枚举私有报告、SQLite 工作区或未授权返工内容。
- 公开历史包必须授权所有 attempt；公开版本链重新绑定公开快照哈希，包含首次 FAIL 也须在授权说明中明示。
  匿名验证页禁止读取本地路径和私有快照，网络读取限制到配置公共存储，禁重定向、限体积与超时。
  反馈交易必须由只读 RPC 取得 canonical Registry 事件；输入的交易哈希或文件自报关联不能作为已验证反馈。
- M10 历史投影只显示可追溯事实，不输出永久黑名单；`INCONCLUSIVE` 不计入负面信誉。
- `app/static/` 为公开静态目录，只允许经过检查的品牌资产；不得放入上传报告、回执、SQLite、凭据或指向私有目录的链接。
  工作区历史只读私有原始 attempt 回执，不向独立公开验证页暴露路径或自动发布内容。

### M16 headless / MCP

- MCP 只运行本机 stdio，不监听 HTTP；当前不声称具备公网或多租户安全边界。
- tool 输入只接受不透明 workspace handle、领域对象和内联严格 JSON；数据库/回执/上传目录由 operator 配置固定，客户端不得提供路径。
- 任务确认与报表核验的 challenge 必须由 MCP 之外的本机交互命令批准；布尔值、确认短语参数或模型重复调用不构成授权。
- challenge 的授权摘要同时绑定工作区、动作、内容哈希、task、`spec_hash` 与 attempt，15 分钟过期；消费结果持久化并幂等返回，
  不能跨工作区/任务复用或用重试生成额外 attempt。结果视图携带 `spec_hash`，比较器不得只按显示顺序或 task ID 推断同一范围。
- MCP 工具不包含发布、写链、任意 URL、Shell、Python、SQL、环境变量或密钥读取。错误边界只返回稳定分类和脱敏说明，
  不回显无效报告、RPC URL、配置路径或秘密字段。
- 默认 `LIVE_READ_ONLY` 缺配置即 `BLOCKED`；`FIXTURE_TEST_ONLY` 必须显式配置并在每个业务响应标记，不能冒充真实链上结果。

## 日志要求

结果解释与处理建议失败仅允许固定错误码 `RESULT_EXPLANATION_UNAVAILABLE` / `FOLLOW_UP_ADVICE_UNAVAILABLE`，
不得拼接异常的 message、loc、input、供应商正文或 URL。页面只精确匹配这两个码及既有固定恢复通知，转为受控中文。
旧会话/历史中的未知 `ai_errors`、带前后缀的码和非字符串统一显示固定不可用提示，不做子串匹配或原文回显，
也不改写原核对记录、Receipt、金额、结论或次数；AI 产物被拒绝不撤销已完成的确定性核对，不自动重试。

范围候选失败只对外暴露 `TaskDraftError.kind` 与固定安全消息，不显示或记录供应商异常正文。
候选等待使用本次专属异步连接、20 秒预算与 SDK retry=0；取消后关闭连接、不保留后台同步请求或迟到候选。
这不保证远端已经收到的请求停止计费。输出上限 2048 tokens；截断或 schema 失败必须拒绝，不能放宽校验补成有效候选。
手工填写也必须经过相同字段与显式范围确认门槛，不把上传报表的观察范围自动当成用户确认范围。

- 允许记录任务 ID、步骤、耗时、状态码和脱敏错误。
- 地址默认可显示缩略形式；需要完整地址时明确标记其为链上公共数据。
- 禁止记录请求头、环境变量全集、私钥、JWT 和完整模型认证信息。
- 外部响应正文仅在必要时保存，并采用大小限制和访问边界。
- `APP_REQUIRE_LIVE` 只控制生产能力开关，不包含凭据；DeepSeek、RPC 与 Blockscout 凭据仍只通过受限 `.env` 注入，禁止进入
  镜像、仓库、页面或日志。
- `PINATA_JWT` 与 `REVIEWER_PRIVATE_KEY` 只能由 `.env` 注入 publisher/reputation adapter；公共回执扫描禁止
  `private_key`、`signature`、`jwt`、`authorization`、`api_key`、`secret` 和原始 `report_text` 字段。
- HTTPS fallback 公共目录只允许应用容器写、Nginx 容器只读，文件名必须内容寻址且只创建不覆盖；公网路径仅允许 GET/HEAD、
  禁止目录列表，并不得与 `receipts/private/` 共用目录或挂载权限。
- Streamlit 需要内联启动脚本和运行时样式；生产反向代理仅在公开的 `/trust-receipt/` 路径放开
  `script-src/style-src 'unsafe-inline'`，其余站点继续使用更严格的全局 CSP，并保留 HSTS、同源 frame、MIME 嗅探防护和权限策略。

## 依赖与供应链

M8 上传在解析前按 SHA-256 私有留档，不使用上传文件名构造路径；拒绝重复 JSON key、浮点金额、错误来源和超限输入。
`services.upload` 用同目录 `mkstemp` 创建私有临时文件（POSIX 权限 0600；Windows 继承受限私有目录 ACL），
完整写入并 flush/fsync/关闭后硬链接到哈希目标；已存在目标只核对、不覆盖，真实损坏继续拒绝。
异常仅删除当前调用独占临时路径，不清理其他写入者的文件；突然终止的私有临时孤立文件不算完成原件。
`local-upload-intake` 只认证本地接收封装，不认证原报表作者。Requester 与 service 采用独立临时密钥，均不复用 Reviewer；
密钥不进入 SQLite、公开回执或日志。恢复必须重验签名与 reference manifest；默认未配置链锚读回的存储不能恢复
自称已提交或已确认的 task anchor。专用合约候选无付款、外部调用、owner 升级能力，不作为已审查/已部署服务宣传。

- 主应用使用 `requirements.txt` 声明范围，`requirements.lock.txt` 保存当前解析结果。
- Blockscout MCP 运行在 `.venv-blockscout` 隔离环境。
- `references/` 是上游参考副本，不在其中运行自动依赖修复。
- 依赖升级必须运行单元测试、契约测试和 `pip check`。
- ERC-8004 参考仓库当前上游 npm 审计报告包含漏洞；在其仅作为测试参考时不得误报为主应用运行依赖。

## 私有表格转换边界

CSV/XLSX reader 与数值适配不调用 RPC、外部链接，不执行公式或宏，不解压到磁盘。输入最多 1 MB、200 行明细、64 列、
每个单元格 4096 字符；XLSX 最多 128 个成员，单成员最多 1 MB、总展开最多 4 MB。
ZIP 只允许 stored/deflate，每次 XML 读取也限制解压输出，不只信任 ZIP 目录中的大小。重复 ZIP 成员、加密、实体声明、
NUL/XML 非支持编码、外部关系、合并单元格、多工作表及公式拒绝。未知行/单元格命名空间不静默跳过。
数值只接受 General 格式，日期格式不能作为区块或金额。
金额必须为明确单位的十进制文本；Excel 数值金额拒绝，不能恢复已被 Excel 舍弃的精度。

列映射、人工常量、原文件名及派生摘要只属于私有来源记录，不是链上参考证据。转换 ready 仅表示可解析，不表示 PASS。
ADR-032 用独立自动识别留档用例替代旧采纳界面，不用 `confirmed=True` 冒充用户确认；
旧留档函数仅保留内部历史兼容，其参数不成为授权令牌。自动读取不确认范围、不执行 attempt、不公开上传或写链。
原文件名不参与输出路径，原文件、JSON 和 provenance 均以内容哈希追加到工作区私有目录；不要放入静态目录或公开回执。

模型只接收最多 64 个、每个最多 80 字符的安全业务表头与原列索引，不发送原文件名、完整文件、数据行或原金额/地址/hash。
疑似私有备注、客户/邮箱、密钥、长标识符或提示指令的列名过滤；原表字段保留在私有原件，不因过滤而改写数值。
表头一律视为不可信数据；模型没有工具或文件/网络执行权限，仅返回受限角色 schema。
所有发送列必须唯一且完整覆盖、角色不得覆盖已知字段或静默删除声明摘要，歧义与单位不明确阻塞。
真实模型固定配置，识别请求最多 30 秒、SDK 自动重试为 0；供应商错误消息不显示、不记录原响应或凭据。
缺配置、超时、无效输出不回退 fixture。离线 mock 必须显式标注 `offline-test`，不能作为真实识别验收。
成功后仍需范围确认和主动核验；模型角色、派生摘要及 provenance 不认证原作者，原始声明可能仍然错误。

## 漏洞处理流程

发现潜在漏洞时，先保存最小复现、受影响边界和证据，不在公开问题中提交真实密钥或未脱敏数据。原型未配置正式披露邮箱，问题先由项目维护者在私有渠道处理。
