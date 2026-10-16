---
doc-id: project-status
title: 当前项目状态
status: active
authority-for:
  - current-status
  - active-work
  - known-blockers
last-reviewed: 2026-10-08
---

# 当前项目状态

## 可选 AI 错误安全联合集成（2026-10-08，已合并并上线）

- 主控在 main `70d0716` 上合流核心 `3e08c6b`、页面 `4fc7f7f` 与实际案例记录 `8836ef4`，
  只解决原异常正文传播及旧缓存显示，保留原失败记录与确定性业务结果；不带入新功能或变更金额、回执、次数。
- 联合代码静止的非 external 全量实际 770 passed / 16 deselected / 1 既有 warning，175.35 秒；
  Ruff、pip check、21 Schema、1000 行和 diff 门通过。更早一次因 STATUS 合流冲突未解便启动测试，已中断，不能计作通过。
- [PR #31](https://github.com/CH-ZHOU-0512/TreasuryTally/pull/31) 最新 head `aa6849b` 的两项 CI 37730734926/37730740650 成功后，
  主控显式合并为 `c36af48ac3bc4cf41ccf693bec48905209293b95`，合并后 CI 37731018181 实际成功。
  生产以独立 c474/8ad 上线，不从包含 M16 的 main 直接部署；主控独立验证公网 health=200/ok、home=200。
- CSV/XLSX 各最多 6 次必要真实模型调用的追加验收在安全修复上线后已由主控确认启动；
  启动时实际累计调用仍为 10 次，最终结果待回报。历史 RPC、原文件首次候选失败与真实 AI 工件校验失败仍是未闭环项目。

## AI 安全修复独立发布（2026-10-08，已上线，真实模型稳定性待验）

- 主控另行明确授权后仅promote上述8ad/c474 app，不部署主线M16；新容器
  `e24cdf002cb52ab1d50e283ac33f1f8f5c56fd01afb6ee742da1fa4d917f7e1b`，
  StartedAt 2026-10-08T05:18:11.059711991Z（北京时间13:18:11），running/healthy/OOMKilled=false。
  实际live117源码/wheel逐byte、app27/9sourceproof、候选20秒/2048tokens、live必须/writesfalse断言通过。
- 原project-directory /opt/trust-receipt/deploy、-p deploy、no-deps/no-build app-only切换；640MiB/swap0/CPU1/pids128/dropALL/nnp。
  原env/dev哈希、3绝对RW挂载、代理配置哈希及SSL只读挂载、Blockscout/Nginx完整ID和StartedAt不变。
  Nginx-t/reload成功（仅既有http2 listen弃用warning），公网根页/health/原Logo200，TLSverifiedWS101/SecAccept通过。
  WebSocket仅握手，不发送业务消息，不声称浏览器首屏速度或真实用户已测。
- 回滚保留确切旧e2cf tag `trust-receipt:safe-ai-rollback-c474a08` 和root700目录
  `/opt/trust-receipt-backups/safe-ai-before-c474a08`，compose-before/rollback-image/source-before文件600且不含env/用户数据；
  本次未执行回滚。后置只读promotion-summary root600保留；临时SSH副本精确删除、原用户key保留。
  本次新增真实模型/RPC/公开上传/写链0，原真实调用10及失败仍保留；CSV/XLSX追加12矩阵已获上线后主控授权，待执行。
  上线仅修复安全错误提示，不表示供应商输出稳定、原文件流程通过或历史RPC完整证据恢复。

### 以下为切换前同源候选与正式预检事实

- 候选源 `c474a082392cc969edba26a2af0f803bceb9eeaa` 精确基于线上d897加core3e08/app4fc，
  只解决可选AI异常正文和旧会话错误显示；与d897差异仅两个业务模块、两个专属测试、SECURITY与STATUS。
  不包含M16、依赖变化或其他新功能。core117/app27；8项既有proof只更新report_evidence为891a3d…，
  第9项core.m5为f234f117…且固定两安全码，旧558/188 helper与原失败日志完整保留。
- 此独立源静止非external实际746 passed / 16 deselected / 1既有warning，184.91秒；
  Ruff、pip check、21 Schema、1000物理行、diff与无凭据MVP双回执重放/恢复通过。
  此数量不混合主控含M16联合源码770项或两独立补丁754/757项。
- 主控确认PR31最新head aa6849b两项CI success并显式批准后，才在新root700私有目录
  `/opt/trust-receipt-releases/safe-ai-c474a08` 单次离线build，无生产.env/数据/密钥。
  fresh1176884KiB高于917504KiB门，disk23484428288字节，30分钟内核26记录/0OOM；
  network=none/no-index/640MiB/swap=0/CPU1，104.62秒完成，20秒间隔实际阶段输出。
- 镜像 `sha256:8adfeff603dd3ffdf0e2c31ca585023f3db4678ef2626545ad473d7c23e3b605`，revision为c474。
  tar SHA f28e061dafad0cd6c7321c41da05ebd5e7f5f699665e65c296cd65cf1eb3f8c2；
  wheel SHA 2f164bd7c0544acd5bd1095dfff2644c73d68f8ee542f5eb4b33b10407692a2f。
  117源码与wheel逐字节相同，archive不含.env/PEM/DB/pycache/M16。
- 正式combined独立容器fresh1243916KiB、640MiB/swap=0/pids128/CPU1/dropALL/nnp/networknone：
  actual入口零exception；7合成案例PNG/nativeWordPDF、4会话14视图8接受6预算拒绝、
  5实际AppTest格式/6下载、原JSON与历史/视图不变、共享renderer/cache清理均通过。
  12SDK故障单次/连接关闭/stall取消、7范围错误/手填零模型/显式确认/3非法范围，以及实际M5M8历史拒绝
  一次getLogs→INCONCLUSIVE/null→保存→新runtime恢复/nativeWordPDF全部通过。
- 新安全专项实际Pydantic合成输入拒绝，解释/建议只输出固定码；两attempt FAIL→PASS、回执replay/restore/不可变通过。
  6类旧错误/码变体/非字符串与固定恢复提示经真实AI说明AppTest安全显示，无合成input泄露。
  此9次是离线adapter调用，不是真实模型；final cgroup peak405344256字节（约386.57MiB），
  max/oom/oom_kill/pagecache_max/pagecache_oom全部0。build与preflight原日志root600保留。
- 预检时生产仍e2cf/d897，容器74a653cc完整ID/StartedAt、3绝对RW挂载、env/dev/代理配置哈希、
  Blockscout与Nginx完整ID/StartedAt均实核不变，health200，未自动promote。
  受限本次临时SSH副本精确删除，原用户key保留；新增真实模型/RPC/公开上传/写链为0。
  先前真实模型累计10次与失败继续保留，CSV/XLSX追加12矩阵须安全镜像切换后主控确认才执行。
  未完成真实模型稳定性、原文件完整验收与历史节点完整证据，不把离线预检写为财务PASS。

## 可选 AI 错误安全码（2026-10-08，核心本地验证，未部署）

- 在精确 main `70d07165a990e949882d2f03d8b814b3a54f06a7` 新独立分支，M5 解释/后续建议异常
  只生成固定 `RESULT_EXPLANATION_UNAVAILABLE` / `FOLLOW_UP_ADVICE_UNAVAILABLE`。
  不读取异常 str/repr/message/input，也不改变 ai_errors 的 tuple 结构、AI validator、调用/重试策略或 Receipt Schema。
  页面 exact allowlist 和旧缓存固定兜底由 M12 独立交付；本核心提交不包含页面或服务器变更。
- 修复前真实 Pydantic ValidationError（仅合成私有输入标记）复现1项失败：原异常 input 进入 ai_errors。
  修复后13项新增回归加最近3项工作流共16 passed：两可选阶段、Pydantic/vendor/不可stringify异常、
  FAIL/INCONCLUSIVE、成功的另一项保留、单次调用、两项同时失败仍能第二次PASS、回执保存/replay/恢复与原字节不变。
  业务 view 不包含合成输入/vendor正文；此项不是本轮 Word/PDF 或浏览器验证。
- 静止完整非 external 实跑754 passed / 16 deselected / 1既有第三方弃用warning，196.27秒。
  全目录Ruff、pip check、21 Schema、1000物理行与diff检查通过；无凭据MVP FAIL→PASS/两回执replay/恢复通过。
  技能要求的独立只读前置调查与后置绕过/回归复核均未发现此核心边界的具体残留问题。
- 新增真实模型/RPC/公开上传/写链均0；没有重新调用失败的live阶段，没有切换当前d897生产镜像或生产端点。
  本修复仅关闭可选AI异常正文传播；模型稳定性、原文件完整验收与完整历史证据阻塞仍保留，不宣称财务PASS。

## M12 AI 错误详情安全投影（2026-10-08，独立本地补丁，未集成部署）

- 在最新主线 `70d0716` 上单独修复 AI 说明中的 `ai_errors` 显示边界：只精确接受
  `RESULT_EXPLANATION_UNAVAILABLE` / `FOLLOW_UP_ADVICE_UNAVAILABLE` 和既有固定恢复通知，显示固定中文。
  旧会话/历史未知串、前后缀或空白变体与非字符串使用固定不可用提示，绝不回显异常输入或供应商正文。
  不修改原错误记录、合法 AI 说明/建议、金额、结论、Receipt、Schema、次数或公开授权。
- 修复前真实 AppTest 用明确合成 Pydantic ValidationError 复现 input_value 出现在 warning，安全回归实际 1 failed；
  修复后原触发器、供应商 URL、码变体、非字符串、历史切换及合法产物等与既有 UI 专项实际 52 passed、1 既有 warning。
  技能要求的独立只读调查及一次补丁绕过复核完成；复核未发现授权边界内的具体绕过或回归，另实际 17 项通过。
- 代码静止的非 external 全量实际 757 passed、16 deselected、1 既有第三方 warning，129.42 秒。
  Ruff、pip check、21 Schema、1000 行、diff 和文档治理门实际通过；未新增依赖。
  core 异常生成处由 M14 独立修复，本分支不包含其补丁，主控负责联合集成。
- 未执行真实模型/RPC、服务器、浏览器、公开发布或写链；未重新生成或检查原生 Word/PDF。
  业务报告视图不消费 `ai_errors`，本次不改变既有报告/导出路径，不能将先前服务器导出门计作本轮新验证。

## 当前验收范围与上线摘要（2026-10-08）

- 当前生产已上线安全修复 `c474a08` / `8adfeff`；d897/e2cf 为其上一版本。具体保护、预检及回滚记录见发布节，旧段落是历史快照。
- 用户明确原 `corrected-complete.json` 不是唯一验收范围：主页 `error-missing-transfer.json` 与 `corrected-complete.json`
  必须实际下载并重传，在同一固定任务保留错误版首次与修正版补交两次核对；还须覆盖 CSV/XLSX 正常上传路径。
- 主控授权的原文件/主页双文件实测已执行累计 10 次模型调用，失败未重试；原候选失败、主页第二 AI 建议被拒绝。
  主页两次核对已保存回执，并完成独立恢复和 JSON/Word/PDF 导出；CSV/XLSX 追加真实矩阵尚未执行。
  AI 异常信息安全修复已合并并部署，CSV/XLSX 真实追加验收已启动、结果待回报。
  浏览器自动化仍暂停，不将 native 上传适配或媒体测试记作浏览器 HTTP 上传/下载。
- 当前历史 RPC 无法提供区块 11855664 完整转账证据。安全返回 INCONCLUSIVE 只能证明证据不足流程正确，
  不能关闭修正版 PASS / 错误版 FAIL→修正版 PASS 的业务验收，也不能宣称全部正常路径完成；不公开回执、不写链。

## 历史证据提示联合集成（2026-10-08，初次构建前快照）

- [PR #27](https://github.com/CH-ZHOU-0512/TreasuryTally/pull/27) 两项 CI 37723407162 / 37723414539 实际成功后，
  主控显式合并为 `7708322a7b5022122fe2ef5721917de19095693a`；合并后主线 CI 37723670377 实际成功。
  主线集成源非 external 实跑
  715 passed / 16 deselected / 1 既有 warning（355.93 秒）；Ruff、pip check、21 Schema、1000 行与 diff 门通过。
- 生产候选从 `49c5092` 单独合流为 `95da1903060e770abae49a21e3566e080fbb32b5`，不包含主线 M16。
  该源非 external 实跑 691 passed / 16 deselected / 1 既有 warning（401.50 秒），与主线 715 项归属不同。
  六个业务文件包含 RPC 分类、安全原因投影及页面精简；117 个 Python 源文件与 wheel 字节一致。
- 广州服务器构建前可用内存不足 640 MiB 预检加 256 MiB 宿主余量的 896 MiB 门，已拒绝启动构建。
  授权追加三次只读快照依次为 921010176 / 921735168 / 931880960 字节，均低于 939524096 字节门；
  仅第三次有明确服务器时间 2026-10-08 11:41:24（Asia/Shanghai），不补造前两次时间。
  不降低门、不停止现用服务、不清用户缓存；当前生产仍为原 `65343fee…` 健康镜像。
  只上传私有发布包，未创建镜像或执行新镜像预检；本轮受限临时 SSH 副本已删除，用户原密钥不变。
- 原 JSON 与原提示词仍待实际上线镜像的完整流程验证；允许得到真实 INCONCLUSIVE，并验证保存、恢复与 JSON/Word/PDF 导出，
  不把流程运行通过写成财务一致。尚无完整参考历史证据、模型业务实测或新镜像部署；不发布、不写链。
- 用户新增第一步预设专业核验要求的需求已交 M12 独立后续工作；不混入本轮已冻结发布源。

## 历史拒绝与范围模板发布（2026-10-08，已上线、真实案例部分通过）

### 原文件与主页案例实际验证

- 在精确线上 e2cf19/d897 image 和同生产网络，用两个新独立私有工作区执行授权原文件/主页案例；
  不读取旧用户工作区，不公开上传或写链。真实模型累计 10 次，私有诊断 SDK retry=0；不改变生产其他 AI 阶段重试配置。
  两个临时 case.env 已删除；失败阶段均未重新调用，CSV/XLSX 真实调用仍为 0。
- 原文件工作区 original-case-d897-a：原702字节与原提示词上传保留通过；第一次候选调用8.462秒失败，
  诊断 wrapper 丢失原异常类别，只能标记 UNKNOWN，不能据耗时猜测 timeout。tasks/attempts/results/publication/m8 全为0。
  资源峰值176312320字节，memory.events max/oom/oom_kill/pagecache_max/pagecache_oom 全0。
- 主页工作区 homepage-case-d897-a：真实原生主页媒体下载和 UploadedFile 再上传通过，候选3.489秒合法且人工确认。
  首次错误报表完成核对、回执及原生 JSON/Word/PDF 导出；修正版在同任务完成第二核对与回执。
  SQLite 实际 tasks=1、attempts=2、verification_results=2、m8_artifacts=4、publication_events=0。
  两次均 INCONCLUSIVE、reference_complete/evidence_sufficient=false，计算金额与数量均 null；不是金融 FAIL→PASS 验收。
- 主页案例9次真实模型调用：候选及首轮4项全部 schema 合法；第二轮主张、计划、解释合法，
  最后一项 FollowUpAdvice 在 adapter.generate 内抛出 Pydantic ValidationError，2.751秒。
  具体字段 loc/type 未保存，不能追回或猜测。严要求全部 AI 工件合法的测试门失败，但产品安全捕获后已保存第二回执；
  不把这个测试 assert 当作第二核对失败。峰值320294912字节，上述五个内存事件全0。
- 随后授权独立只读恢复：源新工作区全文件只读挂载，复制到临时目录，network=none、dummy非真实凭据、
  socket/AI/RPC/attempt/发布/写链入口全部拒绝。新实际 AppTest 会话恢复两个独立回执并 replay valid；
  第二回执原生 JSON/Word/PDF 导出通过，格式切换原 JSON 不变，源全文件前后 SHA-256 一致，新增模型/RPC调用0。
  Word6408878字节、SHA d5d426014c3b3ea99679daf7d212466c901b6aef29b6c2b5f0db41662046f808；
  PDF131286字节、SHA 0d9ee3ea300e8cc4af6693ad7f713808f81f882fafee844ffa4ef4811a424a5d。
  首次只读脚本缺少/app import路径失败，随后仅修正诊断入口一次；首次日志独立保留，不重跑live阶段。
- 恢复后的 AI 说明是固定“未重新生成”提示；默认行动来自确定性报告投影，第二次用尽后要求人工复核。
  但实时错误路径 m5._safe_ai_result_artifacts 拼接 str(error)，AI说明tab原样 warning；可能含 ValidationError input，
  已交主控/M12处理，不宣称现场 AI 错误已完全脱敏。旧 FollowUp失败记录继续保留。
- 官方 README 列出的新增候选 https://www.sepoliarpc.space 只在精确线上 image/网络单次只读检查：
  eth_chainId 首次 ConnectionError 后停止；历史header、decimals、精确from/to getLogs均未调用。
  未切换生产端点、未读取receipt子集或扫描、未追加模型调用。服务器日志 root600 保留。
- 当前未完成：原文件完整流程、全部真实 AI 工件稳定门、可用完整历史 RPC、CSV/XLSX真实完整路径。
  本轮使用原生 AppTest，不是浏览器/真实用户测试；线上存活或离线717门不能代替这些缺口。

### 实际上线与保护

- 经主控另行授权，只以最终 e2cf19 image / d897 revision app-only 切换，生产容器
  `74a653cc890fbd9da9d1d33d327e9ba188f67c9e048af2e575ecf8807e212def`，StartedAt 2026-10-08T04:27:15.164597472Z。
  running/Health.Status=healthy/OOMKilled=false；实时 core117/wheel 严格 byte、app27、8 源 proof、候选20秒/2048与live/writes=false实核通过。
- 原 project-directory /opt/trust-receipt/deploy、-p deploy、no-deps/no-build，640 MiB/swap=0/pids128/CPU1/drop ALL/nnp；
  原 /opt/trust-receipt/data、receipts/private、receipts/public 三个绝对 RW 挂载保留，没有清理用户历史。
  原 env 哈希 ce0a52c9de223764e09ce9b3650d1283280af3245639d80ec4dce34766960a06，开发入口哈希
  f7aa2e3b48c2437323c08982692fdb318fb2d23ab59e2f6b4554348b87bf689a 保持不变。
- Blockscout f4af6faa 与 Nginx 7e786e09 的完整 ID/StartedAt/网络保持不变，未重建；Nginx-t/reload成功，
  仅原 http2 listen 弃用警告，配置哈希 a2741d5c9f7d6e9ee039d5049bef6426d85a4ae58890dd42578784160df7bdd5 与 SSL 只读挂载不变。
  公网根页/health/原 Logo HTTP 200；验证 TLS 的 WebSocket 101/Sec-Accept，仅握手不发送业务消息，不声称首屏感知速度已测。
- 切换前保留旧653 tag trust-receipt:preset-rollback-d897b5c 与 root700备份 /opt/trust-receipt-backups/preset-before-d897b5c，
  旧 compose/source 备份不含 env/data/回执、文件600；本次未执行回滚。受限临时 SSH 副本精确删除，原用户 key 保留。
  上线切换阶段模型/RPC业务调用0；随后真实案例与累计模型10次见前节，未浏览器测试、公开上传或写链。
- 线上公共 committed fixture 只读盘点：主页错误版106字节/hash307f840ef45c3085e33a8d06344075967b9e35c4924621799c85979fe7a8d4c2，声明0/数量0；
  修正版702字节/hashc7dbc77b832a6bfa0ed50eb16c15b48285b464802a297d393c74031082b71d6e，声明180674489737/数量1，与用户原corrected字节相同。
  另有空白JSON模板105字节/hash503d0261e39934c8ed9366945e8776cc50768268bc29a3f19e63847806850f70；没有CSV/XLSX下载对，仅支持上传。
  随后实际主页媒体下载/intake/真实两attempt/恢复/原JSONWordPDF已执行，部分门通过与真实AI失败见前节，
  不以字节相同或合成门代替完整金融验收。

### 同源质量门与发布过程

- 独立源 `d897b5c8ab67336f7f1aba2db7e1fcff56be748c` 为精确 `95da190` 加 M12 原 `136b294`；
  仅 STATUS 合流冲突保留双方事实。与已合并 main `85592f4` 的 app/非 M16 业务一致，明确不包含 headless/MCP/
  新上传服务/对应 pyproject 与 M16 tests 变更，不伪装为主线 image revision。
- 本 checkout 静止完整非 external 实际 717 passed / 16 deselected / 1 既有 warning，167.09 秒；
  Ruff、pip check、21 Schema、1000 行、diff 与无凭据 MVP FAIL→PASS/双回执 replay/恢复均通过。
  source tar SHA-256 `7bbd445e3761a96f179b6ac5d6aaa7d9754e27a923028bd6e277258c8c94213b`，
  wheel SHA-256 `67fa0133a7fa19e21cde095a5edeb121408dd8ce6dfa155f96ac46693283fad6`。
  实际 core 117 Python 文件逐字节相同；新增 scope_request 属于 app，app 模块数 26→27，不误报 core 118。
- 新独立私有目录 `/opt/trust-receipt-releases/preset-history-d897b5c`，不覆盖 95/旧失败记录。
  一次 fresh 954700 KiB、空闲磁盘 23542812672 字节、daemon 正常、生产 Health.Status=healthy/OOMKilled=false 后，
  原 network=none/no-index/640 MiB/swap=0/CPU=1 的 offline build 在 600 秒总预算内 260.61 秒成功，每 20 秒打印实际阶段。
  同源 tar 全文件与 context 实核，image `sha256:e2cf19fe284eef425f37e0691f2fdaa0b0bb4eea1f5e58384e4939ed36eb4d10`，revision 为上述 d897。
- 此精确最终 image 独立正式 combined 门实际通过：fresh 1076924 KiB，640 MiB/swap=0/pids=128/CPU=1/drop ALL/
  no-new-privileges/network=none，无真实密钥/.env/生产用户数据。core117/wheel 严格 byte、app27、8 项模板及报告源码 proof、真实入口零异常通过。
  7 案例 PNG/native Word/PDF、4 会话 14 视图、5 种实际 AppTest 格式与原 JSON、固定字体/assets/socket 隔离全部通过，
  导出预算接受 8/拒绝 6，原回执/历史/视图不改，共享 renderer/cache 清理通过。
- 12 个 SDK transport 故障注入各一次请求并关闭连接，stall 正确取消；真实新 UI 未填 GUIDED 模板禁用整理、无候选/任务，
  切 RAW 保留原文后原 7 类错误/手填零模型/显式确认及 3 类非法范围拒绝全部通过。
  仅另稿调整旧脚本 fixture 显式选择 RAW，不取消产品模板门、不 mock candidate、不覆旧脚本。
  历史拒绝专项通过实际 M5/M8 保存与新 runtime 恢复，INCONCLUSIVE、计算金额/数量 null、安全历史原因及 native Word/PDF 正常。
  这些均为合成数据与无网络注入；原用户报表/原提示词真实模型案例未执行，付费模型/RPC 调用仍为 0，不声称金融 PASS。
- 最终 combined cgroup peak 473489408 字节（约 451.55 MiB），max/oom/oom_kill/pagecache_max/pagecache_oom 均 0。
  新日志 root600 保留，生产仍旧 `65343fee`，三个保护服务/env/dev checkout 不变、health HTTP 200。
  本次构建受限 SSH 副本精确删除、原用户 key 保留。上述为切换前独立候选门，不代表真实案例通过；上线事实见前节。

## 历史 RPC 拒绝分类（2026-10-08，分类修复与探针历史；现已上线）

- 新增受限 `HISTORICAL_DATA_UNAVAILABLE`：只识别 eth_getLogs 的结构化整数 4444 加 history/pruned/unavailable 三个独立词，
  确定拒绝不重试；未知同码/其他方法不误分类，普通 timeout/连接重试不变。新诊断固定安全正文，不保留供应商异常链。
- 首版 M5 与 M0 专项实际 49 passed / 1 既有 warning；文档治理 2 passed。Ruff、pip check、21 份 Schema、1000 行和 diff 门通过。
  这些是离线测试，不代表真实模型速度、历史节点恢复或用户完整案例已通过。
- 广州实际生产镜像/同生产网络下，原节点链 ID、最新区块、decimals 可读，但区块 11855664 的 getLogs 返回 4444；
  区块哈希匹配上传报表，已知交易 receipt 和整区块 receipts 均为 null，不能作为完整参考证据。
  两个官方客户端 README 候选仅隔离验证：rpc.sepolia.org 首个 chain ID 响应无法解析 JSON，
  rpc-sepolia.rockx.com 首个 chain ID 连接失败；两者都未取得完整证据。没有切换生产端点或付费模型调用。
  用户原文件与原提示词的完整流程尚未执行；财务一致性判定仍需可用历史 RPC，但 INCONCLUSIVE 流程可继续验收，
  不以空集合、receipt 子集或抽样宣布报表一致。
- 首版源码 overlay 分类实测未匹配：3.070 秒、三次 getLogs、仍 UNAVAILABLE，未部署。随后授权的单次安全特征探针
  确认 history/pruned/unavailable 同时出现，historical state/not available 不出现；据此收窄到三个独立词组合。
  另两授权候选 rpc.sepolia.online 连接失败、rpc.bordel.wtf/sepolia 响应不能解析 JSON；均在首个 chain ID 停止。
- 修正版在广州同生产镜像的明确测试源码 overlay 实测：1.872 秒、一次 getLogs，固定码 HISTORICAL_DATA_UNAVAILABLE，
  complete=false/evidence_sufficient=false、总额 unknown/null，未创建模型候选或执行 attempt；生产镜像/端点/服务/env 均未改。
  这是新分类和停止无效重试的服务器验证，不是部署或取得完整历史证据；首次失败 overlay 与随后修正记录分别保留。

## M12 范围模板与预设核验要求（2026-10-08，本地实施历史；现已上线）

- 在 `f807167` 基线上实现首次空输入的范围模板及直接写说明；精度为可选报表声明，不猜填或新增领域字段。
  必要范围未填、重复字段或仍有占位时不请求模型、不锁定模型候选；严格上传、人工确认与主动核对保持不变。
- 原文、空格、换行和填写方式在重跑/方式切换时保留；案例说明与自备范围分层，切换报表路径不覆盖原文。
  受信候选提示词仅预设核验要求，用户原说明仍作为不可信 payload 原样传递；无最终金额、PASS、执行或公开授权权力。
  范围入口删除重复执行解释与额外帮助文字，仅在未补齐模板时显示一条行动提示。
- 定向范围/AI/上传回归实际 78 passed；模板/案例/旧 M5/历史与 attempt 兼容复核 59 passed。
  修复前完整运行有模板挡住案例的失败，且过程中修改导致 import 签名不一致，不能计作通过；
  修复后代码静止的 `pytest -m "not external" -q` 实际 695 passed、16 deselected、1 既有 warning，98.46 秒。
  Ruff、pip check、21 Schema、1000 行、diff 和无凭据 MVP FAIL→PASS/双回执重放实际通过；未新增依赖。
- 此提交不进入已冻结发布源，不修改报告缓存或原回执，也不证明广州服务器真实用户案例完成。
  未执行真实模型/RPC、浏览器、服务器操作、公开上传、写链、推送或部署；生产集成由主控另行决定。

## M12 证据不足主区说明与小字精简（2026-10-08，本地验证，未部署）

- 在 `07fe48b` 页面基线上消费已冻结业务视图接口：INCONCLUSIVE 首条 uncertainty 为安全主要原因，
  默认显示“为什么暂不能判断”及下一步；其余精度/投影限制移到已有验证依据，不复制原异常或猜故障。
  原样消费 M13 新安全原因 mapper `2b4ffd9` 为本地 `a43cbbd`；不能把本次 UI 回归称服务器用户案例已通过。
- 按用户新增反馈，核对网络、短代币地址和区块合成一行；保留来源模式、金额单位和实际问题。
  完整账户、排除规则、适用声明与精度说明集中于现有“核验范围与来源”，不新增折叠层级。
  确认、公开授权、剩余核对次数、金额、Schema、回执和原 attempt 不变。
- 新增主原因/安全 fallback/精简身份可见性/技术说明仍可达/有效合成回执原 JSON 媒体保留回归。
  实际 AppTest 生成阅读副本、切换完整视图并释放衍生缓存后，原 JSON 下载地址仍可读回完全相同字节及原回执哈希；
  未发现缓存故障依据，因此不改缓存。此项非浏览器 HTTP 下载或真实 Word/PDF 生成。
- 最终本地 `pytest -m "not external" -q`：643 passed / 16 deselected / 1 既有 warning，133.54 秒。
  较早完整运行 640 passed / 1 failed：旧 M5 测试硬编码旧中性文案，随后改为核验真实 INCONCLUSIVE、醒目原因和中性语义。
  Ruff、pip check、21 Schema、1000 行及 diff 门通过。所有本机验证仅为开发回归，不替代广州服务器真实同报表/提示词全流程。
- 上述 643 项属于消费 mapper 前页面冻结源的完整验证；消费后最终原因投影/M5 页面/业务报告/原技术入口/下载 UI
  专项实际 57 passed / 1 既有 warning，17.87 秒，另 27 项 mapper 页面定向通过。
  新增已存 UNAVAILABLE、HISTORICAL_DATA_UNAVAILABLE、未知码且缺图快照的真实读模型到 AppTest 主原因回归，
  只用显式合成回执，不假称实际 RPC 成功；中性文案断言兼容同一语义的“不能认定”及“暂不能判断”。
  本轮后续未再执行消费 mapper 后完整测试，最终合流/服务器门由主控记录；静态/pip/21 Schema/1000 行门再次通过。
- 真实服务器模型/RPC、完整回执、最终同源镜像和发布验收由 M14/主控完成；本会话未重复 live 调用，
  未恢复浏览器、操作线上用户任务、公开上传、写链、推送或部署。

## 候选请求超时修复（2026-10-08）

- 仅范围候选采用独立 20 秒异步操作预算、SDK retry=0 与输出 2048 tokens 上限；请求取消后关闭本次连接，
  不接纳迟到候选。失败分为 timeout/connection/rate_limit/provider/invalid_output/unavailable，公开消息不含供应商正文。
  其他 AI 步骤、表头识别及字段/金额/任务确认校验不变。本地取消不保证远端停止生成或计费。
- 已执行 M4、M5 与文档治理专项：58 项通过；Ruff、pip check、1000 行门和 diff check 通过。
  OpenAI/DeepSeek 真实 SDK 加无网络 mock transport 检查单次失败、取消和连接关闭，不能称真实模型延迟已改善。
- 非 external 全量为 621 项通过、16 项外部门排除；独立 Linux SDK mock transport 12 类案例通过，
  0.15 秒测试预算下挂起请求均在约 0.152 秒取消并关闭连接。该诊断不代表最终发布镜像或线上供应商实测。
- 页面安全提示/手动范围入口由 M12 集成通过；本次最小超时修复已部署，发布记录如下。

### 超时修复发布（2026-10-08，已部署）

- [PR #25](https://github.com/CH-ZHOU-0512/TreasuryTally/pull/25) 已合并为
  `75a1a7961a6ff2f386425ddc049c25c4306af539`；分支、PR 与合并后主线 CI 37720082435 实际成功。
  生产只采用独立发布源 `49c5092cd4e31b838e5c5c80f65a937d0f40052c`：dc899 基线加候选核心与 M12 UI，
  不包含主线另行合入的 M16 上传服务变更；镜像 revision 不伪装为最新 main SHA。
- M12 同业务源码全量离线门为 638 passed / 16 external deselected / 1 既有 warning；
  M14 核对 app/src/tests/scripts/deploy/依赖声明与该 tested 源完全相同，追加本 checkout 专项 36 passed。
  source tar SHA-256 `8d26706c025db20d2b5b683ca9e9a10de200ac0dd21e2ea2eb16ff1951032ecd`，
  wheel SHA-256 `204a733a8d8c9011bb604a0cfd24656f4848469b441704731ea3057953fe4744`，服务器已实核。
- 最终服务器镜像 `sha256:65343fee4bbe87af570f572f8dae9a6dac17cda9ccb41b05d031c46431992ce5`，
  116 源文件与 wheel 一致，真实入口 AppTest 零 exception。640 MiB/swap=0/pids=128/CPU=1 下同过程
  七例导出、SDK 预热、四会话十四 view 与五格式/原 JSON、隔离/字体/资产门通过。
  两 API 的 SDK mock transport 十二例单次请求、错误分型/取消/关闭连接/无异常正文保留通过；
  实际镜像入口七类安全错误、显式重试、手工零模型调用、确认门及三类非法范围拒绝通过，attempt 执行为 0。
  综合 native peak `406515712` 字节（约 388 MiB），memory.events max/oom/oom_kill/pagecache_max/pagecache_oom 全为 0。
- 仅切换 app 后容器 `0c4b16e0283cb93cfac16a9a2c91c602c8d7c6aa99d8ba109d253bdc81df5df6`
  healthy、OOMKilled=false；Memory=MemorySwap=671088640，pids=128，CPU=1，drop ALL、no-new-privileges。
  页面/健康/原 Logo HTTP 200，独立 TLS WebSocket 握手 101；只测试握手，未发送 Streamlit 业务消息。
  APP_REQUIRE_LIVE=true、M6_ENABLE_WRITES=false、候选预算 20 秒/2048 tokens 实核通过。
- 原 env 哈希、三个数据/回执挂载、开发目录源码、Blockscout/Nginx ID 与启动时间不变。
  Nginx 配置哈希仍为 `a2741d5c9f7d6e9ee039d5049bef6426d85a4ae58890dd42578784160df7bdd5`，
  只执行配置测试与 reload；未重建代理。回滚镜像与无 env/data 的旧部署源码/Compose 位于
  `/opt/trust-receipt-backups/scope-before-49c5092`；本次切换一次成功，未触发自动回滚。
- 未做真人/浏览器或真实模型延迟验收，未新增付费模型、RPC、公共上传或写链；不承诺供应商不再超时，
  也不承诺本地取消后远端停止生成或计费。

### M12 范围整理安全恢复（本地验证记录）

- 从精确发布基线 `867ca61` 消费 M14 `a83c826` 和最终安全修补 `26fc747`，本地分别映射 `9587a56` / `c18a05d`；
  未混入 M16 上传服务、主线其他改动或共享脏工作区。页面只存固定错误 kind，不显示或保留供应商异常正文。
- 六类安全提示、显式重试和直接手工范围入口保留已读取报表及说明，不因 rerun 自动请求、不回退演示范围。
  手工候选无报表推断值，复用同一严格表单、人工确认与任务校验；确认成功后仍须主动开始核对。
  更换文件/模型或修改模型候选对应说明清旧候选；文件不合规时两入口均阻塞。
- 新增 17 项离线恢复测试实际通过，覆盖保留输入、未知异常/无效输出不泄漏、显式重试、手工零模型调用、
  未确认/缺字段/错误链/倒置区块/重复账户拒绝及文件变更。最终 core+UI 完整非 external 实跑：
  `pytest -m "not external" -q` 为 638 passed / 16 deselected / 1 既有 warning，169.79 秒。
  Ruff、pip check、21 份 Schema、1000 行和 diff 门通过；离线 MVP FAIL→PASS、双回执重放与恢复 valid=true。
- 未恢复浏览器、真实模型/RPC、公开上传或写链；未 push/merge/部署。供应商实际延迟、最终镜像和生产切换仍待 M14/主控验收，
  不以本地等待预算或离线通过承诺远端取消、停止计费或线上可靠性改善。

更新时间：2026-10-08

## 当前阶段

### 自动报表与业务报告最终发布（2026-10-08，已部署）

- 主控推送/合并 [PR #20](https://github.com/CH-ZHOU-0512/TreasuryTally/pull/20)，
  功能 CI 与主线 CI 实际成功；最小资源修订 [PR #22](https://github.com/CH-ZHOU-0512/TreasuryTally/pull/22)
  显式等检查成功后合并为 `867ca617c02b493cd9b919133f1187669934d8e0`，合并后 CI 37715820124 成功。
  主控独立 diff 确认该 main 源码树与 M14 已验 `dc8990583c4b1ccf19f21f3abba6c5d727682630` 完全一致。
  本次镜像实际 revision 使用 dc899，而非把同树 main SHA 伪装成构建来源。
- 私有 SSH 传输的运行基底归档 SHA-256 为 `337dd08db0a2fad3daf4f0e51ec720870612a7f56f76622295a5506e383cf150`。
  最终源码归档为 `14494716a9d9d715e430a8673e466eb0d38ea593e3ebfd0137ab5acb83181b0d`；
  同源 wheel 为 `380ea09607004674948519b0702d5e7f9e3cb5ed2583a28c1185ab1a3aeb271a`，服务器实核相同。
  最终 offline/no-index/no-deps release 镜像为
  `sha256:76836da51f9cb4f820daf501e1c964e7ad2f73c68d1c69ff046983493ad9cd88`。
- 服务器只读/无网络/无 env、key、用户数据的有界预检通过：入口 115 源文件与 wheel 匹配、AppTest exception=0、
  七例真实 PNG/DOCX/PDF、字体/资产/许可证/seccomp、真实 SDK 离线构造保持、4 会话 14 view、五格式及原 JSON 六下载。
  640 MiB/swap=0/pids=128/CPU=1 下峰值 422989824 字节（约 403 MiB），current=351440896，
  anon=289652736/file=48914432/kernel=12632064，max/oom/oom_kill=0；缓存拒绝与 JSON/结论/历史不变已验证。
  首轮合成 fixtures 被 SCP 保留 root-only 权限导致严格七例门拒绝；只修合成测试目录可读后原样重跑，未改真实数据权限或跳门。
- 首次应用切换内部健康及配置通过，但公网根检查因 Nginx 上游旧 IP 缓存超时，按失败门自动回滚旧镜像。
  定向 `nginx -t`/reload 恢复旧公网 200 后重试；第二次健康后刷新代理上游，最终页面/健康/原始 Logo HTTP 200，
  独立 TLS WebSocket 握手 101。Nginx 配置哈希与已审查退役路由配置精确相同，未重建代理。
  该次切换后容器 `86f3985d4c0d2058ab53c88d9ef6593f485fc60325de02cff9bb3942bd2fa931` healthy、OOMKilled=false，
  实核 Memory=MemorySwap=671088640、PidsLimit=128、NanoCpus=1000000000、drop ALL、no-new-privileges。
- 原 `.env` SHA-256 保持 `ce0a52c9de223764e09ce9b3650d1283280af3245639d80ec4dce34766960a06`，
  live=true、M6 writes=false，三个 data/private/public 绝对挂载不变；Blockscout/Nginx ID 与 StartedAt 不变。
  部署使用独立 `/opt/trust-receipt-releases/report-dc89905/source/deploy` Compose、原 project-directory 与 `-p deploy`；
  原 `/opt/trust-receipt` 开发源码未覆盖，入口文件哈希实核不变。
  回滚镜像 `trust-receipt:report-rollback-dc89905` 对应原 5357c9f；旧 source/Compose/明确镜像 override
  保护在 `/opt/trust-receipt-backups/report-before-dc89905/`，回滚后也须刷新代理上游。
- 用户明确弃用旧业务后，合计删除十二个旧归档、十九个旧业务源码/备份目录、八个旧容器、旧校园 app-data 卷，
  精确删除三个旧业务 repository 的 52 个 image tag（不 force、不全局 prune，保留全部信据/容器引用及共享层），
  两个旧 workflow stop/disable 后删除对应源码和 unit 文件；Nginx/SSL/续期目录/网络/log卷及本项目全部数据与回滚保护。
  旧文件/数据无已核外部备份，不能保证恢复；目录/image 虚拟大小不能当作实际回收空间。
  清理后实测可用内存约 1039 MiB；此为动态快照，不是永久保证。
- 发布不依赖真人测试。没有恢复已暂停的浏览器自动化、真实模型/RPC业务复测、线上历史恢复、公共回执上传或写链。
  HTTP/WS/合成 AppTest 不等于全状态/手机/200% 放大视觉矩阵或 Logo 首屏加载速度验收。
  页面首步已上线 CSV/XLSX/JSON 自动识别与规范数据转写，缺条件局部询问，人工范围确认和主动核验仍必需。
  最后复查容器 healthy/OOMKilled=false、公网健康 200、配置哈希与三个运行服务正常；
  本地受限临时 SSH 私钥副本已精确删除并核不存在，用户原始 key 文件仍在且未修改。

### 最严组合资源修订（2026-10-08，切换前历史）

512 MiB 提案被后续实测替代：807af6e 新进程同一次先七例 native 导出/seccomp/资产门，
再保留真实 SDK、4 会话 14 view、全五格式，虽业务通过/OOM=0，但峰值 536870912 恰触硬限，max=1329。
因此不得发布或把早前分开测试的零 max/热轮峰值作为最终余量。
唯一追加 640 MiB/swap=0/pids=128/CPU=1 同组合实测全部通过，峰值 464470016（约 443 MiB），max/oom/oom_kill=0。
新进程不保证宿主文件缓存冷态；保留此前 512 触限证据，不用较低热轮抹去风险。
配置与运行检查默认同步为 640；压力脚本新增严格零 max 门和 current/anon/file/kernel 诊断，未改业务源/金额/记录/缓存预算。
新资源代码对应 source/wheel/image 及服务器预检仍待完成；生产当前 app 继续旧 healthy。

### 低内存集成与旧业务清理（2026-10-08，切换前历史）

- M14 原样集成 M13 完整导出预算及 M12 有界缓存，源码分别映射 `1cd6a05`、`1387d12`。
  本分支完整非 external 实跑 605 passed / 16 deselected / 1 既有 warning，280.07 秒；
  91 项导出/缓存/UI专项、Ruff、pip check、21 Schema 与 1000 行/diff 门通过。
- 同源 `ce519c7cf0b64bbfbfbe72866f701f25bd2a7145` 完整/离线 release 镜像真实初始入口 115 源文件与 wheel 一致、exception=0。
  512 MiB/swap=0/pids=128/CPU=1/network=none/只读下七例 PNG/DOCX/PDF、资产/字体/许可证/seccomp 门与实际五格式加 JSON 六下载通过。
  离线构造并保留真实 OpenAI/DeepSeek/Web3 SDK，4 会话 14 view 实际生成 Word，再生成五格式通过。
  六次拒绝实测均为 `download budget exceeded`，不是其他导出错误；JSON/结论/历史未改，OOM/max 事件均为 0。
  初轮峰值 471818240 字节（约 450 MiB）；后续热轮 318902272 / release 326934528，仍按较高初轮评估。
  512 配置及最终新源/镜像/服务器门仍须完成，不能用热轮较低峰值声称生产已上线。
- 用户明确“除了这次 /opt/trust-receipt 及其要用到的东西，之前的都用不上”，按该扩展授权停止六个旧校园/作品集容器，
  随后删除这六个及两个已停旧作品集容器、旧 `campus-creator_app-data` 卷、十二个 `campus-creator.previous-*` 精确目录及旧作品集源码。
  先前批准的十二个旧归档亦已删除，逻辑大小共 157326141 字节；旧数据/源码无已核外部备份，不能保证恢复。
  两个旧 workflow 服务已精确 stop/disable，尚未删除其源码/单位文件；没有全盘 prune 或系统目录清除。
  Nginx 四个旧业务 proxy 路由改为 410，candidate/真实 nginx -t 和 reload 成功，信据代理/CSP/SSL/公开路径保留。
  旧配置备份在 `/opt/trust-receipt-backups/retired-sites-20261008/nginx-before.conf`。
  信据/Blockscout/Nginx 容器 ID 保持、信据 healthy、公网健康 200；可用内存恢复约 901 MiB。
  本项目目录、数据、回执、回滚镜像/备份、Nginx/SSL/网络/log卷和运行依赖保护；没有模型/RPC请求、浏览器、公开上传或写链。

### M12 低内存导出页面适配（2026-10-08，本地验证，未部署）

- 最小消费 M13 `4e8bfbea6e5a0556abae57655002c24bb954be16` 为本地 `42d27dd`，未摘其 STATUS。
  `application_renderer()` 仍是受信单应用实例；app 外层复用其 `export_slot()` 包住整个 builder、缓存提交与下载媒体注册，
  同线程嵌套重入，跨线程立即拒绝、无排队。未自行改 reporting、Node、Docker、锁或共享环境。
- `app.report_download_cache` 全应用私有衍生字节预算，M14 给定压力候选总 16 MiB / 单文件 8 MiB，
  每会话仅当前 full view 的五格式。session_state 只留 lease/view 元数据，不留导出 bytes；超过预算明确不可用。
  切换 view、工作区、下一任务或绑定失败释放衍生缓存及自身准确 session/coordinate/fileID 媒体引用。
  框架去重采用 canonical bytes；别的会话或同会话其他控件仍持有相同文件时不误删，继续计预算至引用释放。
  旧实现的衍生 bytes 迁移清理，原 JSON、Receipt、task、executions、数据库和其他业务媒体不清理。
  session lease 收尾也释放自己的缓存；兼容适配集中于 app，缺所需框架能力在注册前拒绝。
- 实际固定 Streamlit 1.65.0 的 MediaFileManager/MemoryMediaFileStorage 回归覆盖 4 会话 × 30 视图、
  8 线程全局预算竞争、同文件去重/引用保护、其他控件准确引用、异常 enqueue 后释放、lease GC、单文件与总容量拒绝。
  真实 AppTest 连续 30 view 验证旧衍生文件不累积、session_state 无衍生 bytes、原 JSON/历史保留；
  跨线程繁忙分别拒绝生成和已有下载注册，释放预算后恢复；超限保持原结论。
  最新缓存/下载/业务报告组合 **39 通过、1 条既有 warning**；较早全 M12/reporting 专项 170 通过。
- 复用已由 bundled 作者生成的合成 PASS 五格式真实 payload，实际 AppTest 五文件 + 独立 JSON 六下载通过，
  总缓存字节与真实五文件长度之和一致（包含约 6.43 MB Word），不是 native 生成/cgroup/浏览器或新文档视觉验收。
  首轮完整非 external 604 通过 / 16 排除 / 1 warning；随后加强同会话其他控件精确 coordinate 保护，
  M12 最终源码 bec69d33 的完整非 external 实跑 605 通过 / 16 排除 / 1 warning，221.53 秒。
  此为 M12 独立证据，不是 M14 的运行集成或生产内存门。完整 Ruff、pip check、21 schema、1000 行与 diff 门通过；
  离线 MVP 再次 FAIL→PASS、双回执重放与恢复 valid=true。
- 经主控确认同步上传文案及全部一致比较为“上传自己的报表”，必填字段只标明 JSON 适用；
  既有 CSV/XLSX/JSON 自动读取、必要局部补充、人工范围确认与主动核验不变，没有新增转换/采用步骤。
- 16/8 是 M14 指定待最终压力 gate 的候选代码预算，真实 SDK warmup、多会话峰值、memory.peak/OOM、
  最终 source/wheel/image 门及服务器内存边界仍由 M14 实测，不能拿其此前单轮 512 MiB 检查作上线承诺。
  浏览器仍暂停；未 push、merge、部署、服务器清理、公开上传、写链或使用真实模型/RPC。

### 发布前服务器资源检查（2026-10-08，暂缓发布）

用户继续授权提交/推送/合并/部署后，M14 实际安全 fetch 并独立 ls-remote 核实 main 仍为
`e2cfbe24d0e95999057870433956e97310694928`，也是验收分支 merge-base；未混入 M15/M16 或其他支线。
服务器只读审计为 Linux x86_64、cgroup v2、2 CPU、物理内存 1931 MiB（Docker MemTotal 2025336832），
可用约 801 MiB，1 GiB swap 已使用 654 MiB，同时运行 app 与其他服务。
已验收配置的 app 与 renderer 合计 native 2 GiB、swap=0 边界大于整机物理内存；不能将本地隔离成功当作该主机足够余量证明。
按主控资源不足先停止的发布要求，在新资源决策/明确适配授权前暂缓，不自行降低资源边界、停止其他服务或改线上配置。
旧 app healthy，三个 data/private/public 挂载和 Blockscout 保持原状；仅核 `.env` 哈希，不读取或输出内容。
没有推送、PR、合并、部署、线上任务操作、模型/RPC请求、公开上传、写链或浏览器操作；受限临时 SSH 私钥副本用后清理，原文件不变。

### M14 箭头修复后最终本地运行复验（2026-10-08，通过，未发布）

在前项本地集成之上原样消费 M13 最小 `cf4f6122cde83420d8cb9f7922487b0c064340cf`，
映射为最终运行代码 `6a102da8df6a07accad21e6898b63024d719aa33`。未修改事实、金额、事件身份、
Node/sharp 锁、受信 launcher 或主环境生成的 Python 锁；新增 card-edge-geometry.js 按已有规则进入新 wheel。
下述 07cdf4a 验收只属修复前历史，不能覆盖本次新资源。

- 新代码独立完整非 external：572 passed / 16 deselected / 1 条既有 websockets warning，108.08 秒；
  Ruff、pip check、21 Schema、1000 行、diff 门与无凭据 MVP 双回执重放/冷恢复 valid=true 通过。
- 新完整镜像 `trust-receipt:report-runtime-6a102da`，实际 image ID
  `sha256:072bb9703f938ec10d158cde9a1ae4f72639d2220eff8173c270c3c00ca49dc2`；
  新离线 release 镜像 `trust-receipt:report-release-6a102da`，实际 image ID
  `sha256:c11df3873a12981083e0cf615bad3948957db48f0b11f480cb55ced3dd69b027`；
  两者 inspect revision 均精确为上述 6a102da 完整 SHA，不使用旧镜像换标。
- 新提交归档 SHA-256 `75f1383caea4be85625c25d72b37c37902e158ae8caa3d508471302028e3ae15`；
  由此构建的 wheel SHA-256 `3251c26daefa9484c3f964c28fc58ccaffe3be273c9ad77777f053324843a651`。
  release 在 network=none 完成无索引/无依赖 wheel 安装与 pip check、source/wheel/实际入口门。
- 两个新镜像分别独立实跑七例真实 SSR→PNG→DOCX/PDF、全部报告资产/字体 source/wheel parity、
  view/hash 绑定与许可证、cgroup memory/swap/pids、seccomp/父 socket/匿名管道、缺依赖与任意参数拒绝全部通过。
  不挂 source/app/launcher 覆盖，不挂真实 env、key、用户数据；渲染 network=none、只读、资源界限与前项一致。
- 两个新镜像分别实跑 Linux Node 20 组直线/曲线/反向/resize/zoom/pan 几何测试通过，测试只读挂载固定检查脚本。
  实际 AppTest 由页面单应用 renderer 主动生成五格式加独立 JSON 六下载，正确格式、完整 view 缓存及原回执/结论不变。
  新完整镜像独立 `/app` 初始入口 115 源文件匹配 wheel、exception=0、品牌区存在；release 同项在离线构建时实际通过。
- M13 独立视觉证据已核读 card-contact-review.md：新 86 页重渲染，14 个变更图表页逐个原始分辨率复查，
  72 页哈希与其先前逐页审查页一致。归属 M13，不写成 M14 重看了 86 页；纵向箭头待修复项已由此新版本替代。
- 未进行浏览器/HTTP 下载、真人测试、真实模型/RPC复测或线上任务恢复；未推送、主线合并、部署、
  公开上传、写链或修改生产数据/配置。本地运行与格式验收通过不等于生产已切换或全状态浏览器视觉矩阵已完成。

### M14 报告运行集成本地验收（2026-10-08，修复前历史，未发布）

M14 独立 `codex/report-runtime-integration` 从 M12 `5f59055` 整合 M13 export `0a0883a`（映射 `d408f1c`）、
运行接线 `2a9c90e` 与 M12 最终下载 UI `ecaa992`（映射 `2c198a5`），不修改主 checkout、共享环境或线上配置。
主控在项目主 `D:/HACKTHON/.venv` 实际安装 python-docx 1.2.0 / reportlab 4.4.9，Pillow 12.3.0 不变，
主控实跑 pip check 与 M13 reporting 49 项测试通过；仅新增传递依赖 lxml 6.1.3，无旧包删除或升级。
M14 原样机械复制主环境 `pip freeze --exclude-editable` 生成产物为 requirements.lock.txt，
源/目标 SHA-256 同为 `d82759bcdf6af75c548b41ded2dc0146aa4750b0571a7025fd6d299a30200800`。
独立 Compare-Object 确认仅新增上述 3 条锁项，其余 Git 差异只是 freeze 排序；未手改锁条目。
requirements.txt 同步三精确导出依赖，与 pyproject 主声明一致，避免开发安装与正式包声明分叉。
运行接线包括 pinned Node/sharp、字体、许可证、子进程 seccomp、容器 native 总内存/pids 与缓存并发界限。
最终运行代码 `07cdf4a9b17e94ede57d6a12f8bfeea9df019808`：组合非 external 独立实跑 571 passed /
16 deselected / 1 条既有 warning；Ruff、pip check、21 Schema、1000 行门、diff check 通过。
离线 MVP FAIL→PASS、双回执重放与冷恢复 valid=true。没有模型/RPC/公开发布或写链动作。

- 同源完整 Linux 镜像 `trust-receipt:report-runtime-07cdf4a`，实际 revision 为上述完整 SHA，
  image ID `sha256:b14f4a38cc60ac9c81733e7251a499821f0ebdffef471565ce5be642f945ac72`。
  新锁 constraints 构建与镜像 pip check 通过；实读 Python 3.12.14、Node 22.23.3、python-docx 1.2.0、
  reportlab 4.4.9、Pillow 12.3.0、lxml 6.1.3；worker 实查 sharp 0.34.5。
- 两镜像运行均 network=none、read-only、2 GiB memory/swap=0、256 pids、2 CPU、drop ALL capabilities、
  no-new-privileges；只读挂 7 个合成 view，无源/app/launcher 覆盖挂载，无真实 env/key/data/私有回执。
  实际 cgroup 限制断言通过，父 socket 可创建；隔离子进程网络 socket 和 AF_INET socketpair 返回 EPERM，
  匿名 AF_UNIX stdio socketpair 可用；任意 Node -e 参数拒绝、缺 renderer 明确不可用。
- 7 例（PASS/FAIL/INCONCLUSIVE/修复/uint256 大额/精度 255/200 条事件）的真实 ECharts SSR→sharp PNG→
  DOCX/PDF 完成，PNG/view 哈希绑定、字体内嵌、完整报告资产 source/wheel 与安装字体一致；
  保留 Node/LICENSE、sharp/LICENSE、native README/package.json LGPL 声明。
- 使用实际 app 单实例 renderer 的 AppTest 主动生成 Word/PDF/HTML/PNG/SVG，六个下载（含独立原 JSON）注册，
  格式 magic、完整 view 缓存、原 JSON 和业务结论不变；不是预生成 bytes 或 mock exporter。
  实际 `/app` 初始入口独立通过：115 源文件匹配 wheel、package_origin=/app/src/trust_receipt、exception=0、品牌区存在。
  Streamlit 输出已有 bare-context/components-v1 弃用提示，不隐瞒或将其写为业务错误修复。
- 同提交归档 SHA-256 `b9c0c0582455eade9d516005bbefbe83448978b01dfa2ab6b361d0ffb0997e4f`；
  其 wheel SHA-256 `ea6b1c8c5d8e512a5bb762673cda4fee6c712264ec95f1f6465a20cb90a76804`。
  `Dockerfile.release --network none` 以已验证新 runtime 为基底完成离线 wheel 安装、pip check、source/wheel 与入口门；
  `trust-receipt:report-release-07cdf4a` image ID
  `sha256:fb7e412152f205625a7e17187162099c8238bd565c88d082a403d375b6e15797`，revision 同上，
  另独立原样重跑 7 例真实导出与 AppTest 五格式门全部通过。release 显式要求 RUNTIME_IMAGE，不默认使用旧基底。
- 首次运行隔离规则误拦匿名 stdio socketpair，收窄为仅允许 AF_UNIX 后原样重跑通过；
  一次重构下载 PyArrow 遇构建网络超时，依赖缓存/分层重构后重试成功，未删测试断言或降级渲染格式。
  早期 smoke 的 .gitignore 资产对比和 HTML PNG-data-url 假设分别按真实 wheel 内容及内联 SVG 契约修正。
- 纵向内部互转箭头的 M13 视觉修复仍待消费；本门不等于逐页视觉总体通过、浏览器/HTTP 下载、真人测试或线上能力。
  未推送、主线合并、部署、操作用户 workspace、公开上传或写链；当前生产未改变。

### M12 业务报告导出页面本地接线（2026-10-08）

- 独立 `codex/report-intake-ui` 消费 M13 导出提交 `0a0883a4a963124348823977121d8522164f6f67`
  为本地 `329b174`。主业务面按需提供真实 Word/PDF 与独立原 JSON；唯一技术入口中的“其他格式下载”
  提供 HTML/PNG/SVG。页面不公开、写链、调用模型/RPC 或增加 attempt；缓存绑定完整业务 view 与格式。
- 按 M14 约定以无参数 `st.cache_resource` 共享单应用 renderer，显式传给全部格式；仅读取受信进程环境
  `REPORT_RENDERER_NODE` / `REPORT_RENDERER_MODULES`，缺失或空配置用固定 `/opt/trust-receipt-renderer/` 路径，
  不发现 PATH 裸 Node、不硬编码个人 bundle 路径、不接用户配置输入。缺依赖/繁忙/失败提示导出不可用且原 JSON 保留。
  M14 隔离启动器、Docker 与运维配置仍在独立集成，本页面接线不等于生产运行边界已通过。
- M12 本次实际执行 `python -m pytest -m 'not external' -q`：**571 通过、16 排除、1 条既有第三方弃用 warning**。
  新增导出页面测试 8 通过；完整 Ruff、pip check、21 份 schema 可重复检查、1000 物理行限制与 diff 检查通过。
  离线 MVP 再次 FAIL→PASS，两份独立回执重放与冷恢复有效；未执行外部服务或密钥检查。
- 根工作区主环境未被本任务安装/修改；只读核验其中 python-docx 1.2.0、reportlab 4.4.9、Pillow 12.3.0。
  用 loader-selected bundled Python/Node 与 M13 独立 sharp 0.34.5 的只读依赖目录生成一份合成 PASS 的真实
  DOCX/PDF/HTML/PNG/SVG，AppTest 注册五种真实文件 payload 加独立 JSON 六个下载入口、完整 view 缓存字节一致。
  此 smoke 使用预先由 bundled 作者生成的真实文件；不是页面实际生产 renderer 执行、HTTP 下载或浏览器验收。
- M12 实际以原始分辨率查看该 PASS 资金流 PNG 与 PDF 全部 3 页：中文、金额、明细完整，但发现纵向内部互转
  箭头提前终止、未接下方账户卡片，已交 M13 引擎负责人复查；本轮不能记为视觉完全通过。
  M12 未重新渲染 DOCX（Windows bundle 缺 canonical LibreOffice），没有交付 QA 文件；M13 的 86 页记录仍只算其独立证据。
  浏览器自动化继续暂停，未 push、merge、部署、公开上传或写链，未改 Docker/Node 包与锁/共享主环境。

### 自动上传与单一业务报告页面（2026-10-07，本地联调中，未发布）

M12 从 `9fd663c` 消费 M14 自动识别三组核心/记录和有界外部测试提交，取代未发布的手工映射/采用 JSON 入口。
正常 CSV/.xlsx/JSON 上传后自动读取；仅必要链/资产/精度/金额单位局部询问，首步和修正版共用组件。
文件/模型/局部条件变化清旧结果与服务；失败不回退旧报表，范围确认和主动核验仍必需。
`6068b83` 视觉集成版本完整非 external 实跑 554 passed / 16 deselected / 1 既有 warning，Ruff、pip check、21 Schema、1000 行门通过。
新 UI/缓存 13 项、原值/私有留档入口 8 项及全页自动修正版 3 项均通过；XLSX 合法金额和公式替换阻塞使用显式模型 double。
本地浏览器实际选 CSV 验证未配真实识别模型的阻塞；严格 JSON 无采纳步骤直接摘要，明确确认范围、主动首轮 FAIL，
自动读取 JSON 修正版但不自动核验，主动第二轮 PASS 保留原失败、无第三次入口；390px 无页面横向溢出、exception 0。

结果报告按 ADR-033 由 M13 reporting 视图驱动：消费 `4b91d0b`、`8b46ec9`、`e6097c0`，不另造报告/金额模型。
默认三项正常单位金额、中文结论/范围、同类差异概览及两次业务对比；AI 原文/签名/诊断/JSON 集中一个技术入口。
错误或混合资产/精度不猜换算，冷恢复不借当前模式冒充原核验；报告公开授权按回执身份隔离。
消费 M13 ECharts `6a7c79d`（本地 `25d6049`），默认本地隔离 iframe 图、12 条显式分页、前后切换、文字图例已接入；
完整事件正常单位表放在单一技术入口。4 项新增 AppTest 证明全部 200 条逐页可达、原失败保留、缺图不补造，
消费 M13 `005b1a9`（本地 `fc66134`），正常可比金额差异说明使用精确代币单位，未知/冲突不猜换算，下一步移除内部工作流术语。
消费 M13 `677e5b0`（本地 `c28cffd`），事件仅在任务资产、唯一参考精度与事件精度一致时换算，
否则保留整数最小单位并标「精度未确认」。reporting/报告/图控件组合 60 项通过；既有无凭据演示双回执重放/恢复 valid=true。
用户暂停浏览器自动操作，本次接图后未调用浏览器或声称视觉验收；手机可读性与真实交互留待人工检查。
Word/PDF 逐页验收及接线尚未完成；不能称整版报告或导出完成。
用户随后取消 Canva、明确继续 ECharts；仅消费 M13 `5b939ed` 的三个实现/测试文件和 `3602720` 横向箭头修复，
不取其状态或 dirty 导出。动态图显示角色卡片、20px 金额/12px 状态，长标签省略但完整事实保留，720px 图内滚动。
随后消费标签小修 `ef481e1`（本地 `0a2551e`），长单位指向完整明细，未知精度始终明确标「最小单位（精度未确认）」，
内部互转标签进一步避开卡片；新增实际错误资产 fixture 的可见标签/原整数/完整来源测试。
最新报告/图控件组合 62 项、Ruff/21 Schema/1000 行/diff 通过，本次小修未重跑全量，不把前次 554 计作新增测试后的全量。
继续消费 `e68cd25`（本地 `aa40d9f`）的两行避让/单位文案修复，61 项回归、Ruff/1000 行/diff 再次通过。
该提交不包含「最多前 4」或「并行线仅 1 标签」的逻辑；未将这些尚未交接规则记作网页已实现，仍保持 12 条显式分页。
M13 确认这些限制仅属于待交静态打印层；随后消费 `9a10773`（本地 `2baed9c`）单条事件高度修复，
仅调整布局高度和回归测试，62 项报告/图控件通过，不影响完整事件、金额、来源或网页分页。
紧接消费 `8230a5f`（本地 `77031b2`），按 ECharts 退化跨度将最小布局高度修正为 2，避免单条标签压扁；
两项修复一并保留，62 项回归、Ruff/1000 行/diff 再次通过，不把第一项单独称为最终视觉效果。
实际查看更新的离线合成 PNG，确认横向箭头不再被卡片覆盖；不是浏览器/触摸/生产验收，未把 PNG 或此前 imagegen 草案嵌入任务。
固定 Node/ECharts SSR + pinned sharp 的导出方案已批准并写入 ADR-033，renderer/依赖/运行环境等待各负责人已验提交，
不把方案批准当实现或逐页检查成功；Word/PDF 仍待接线和验收，不回退 Python 仿制图。
旧 ADR-031 各项验收为历史事实，不发布旧交互。
未自行追加真实模型/RPC 调用、真人测试、线上工作区恢复、公共上传/写链、推送、合并或部署；M14 外部识别实跑归属见下项。

### 统一上传与受限模型识别（2026-10-07，本地核心，未发布）

用户最新需求替代旧转换/采纳界面：正常路径统一 CSV / `.xlsx` / JSON 上传，模型只识别表头，
用户不手动转换或采纳 JSON。旧 `9fd663c` 手动界面不发布；下面 ADR-031 各项作为历史本地证据保留。
M14 从 `9fd663c` 切 `codex/automatic-report-recognition`，单写受限核心与技术文档；
M12 从同一基线独立单写 app/PRODUCT/FRONTEND/ADR-032；核心提交已交接，最终页面接线仍由 M12 完成。
核心 `header_recognition` / `report_recognition` 已实现安全表头、真实列绑定、严格 JSON bypass、
单位/整表条件局部问题、原声明不修正、失败脱敏/无 fixture fallback、自动私有留档与缓存原件/模型绑定。
没有模型行值、文件名、私有备注外发，没有新增依赖或修改公共 Schema/签名/金额/attempt 规则。
核心提交为 `f275825902ad3058f644b6139dab3e9234fc7a6c` 与增量
`ac2015f5c0f96bd227698f2b7f1f55c39a3a755e`，新增 35 项离线 mock 识别测试通过；
最终完整非 external 门实际完成 490 passed / 14 deselected / 1 条既有 websockets warning。
全仓 Ruff、主环境 pip check、21 Schema 重生成检查、1000 物理行限制与 diff check 通过。
随后有界真实验收使用既有被忽略配置的固定 `DeepSeek:deepseek-flash`，实际 factory/provider/
recognize_report 路径的 2 项 external 测试通过（1 条既有 warning）；请求超时上限 30 秒、自动重试 0。
只发送合成业务表头及索引，不发送文件名、行值、金额、地址、哈希、备注或用户文件，没有切换供应商。
正常 CSV 用时 3.469 秒，API/Schema/真实列绑定通过、ready=true；缺金额单位 CSV 用时 2.375 秒，
API/Schema/绑定通过，ready=false 且仅提示 `amount_unit`，本地补充 base 后缓存复用 ready=true、无第三次请求。
脱敏列绑定：0 chain_id、1 token_address、2 transaction_hash、3 log_index、4 block_number、
5 from_address、6 to_address、7 amount_base_units（缺单位案例为 amount）、8 token_decimals、
9 claimed_total_base_units、10 claimed_count；schema_version=1.0、所有 ambiguous=false、无 issues/missing_fields。
只证明这两个合成 CSV 场景的模型识别，不代表完整业务、RPC、真实 XLSX/API 失败场景或生产页面已验收。
未推送、主线合并、部署或操作用户任务。

### 表格转换独立集成验收（2026-10-07，本地通过，未发布）

M14 新建 `m14-report-conversion-integration/HACKTHON`、`codex/report-conversion-integration`，
实际重试 fetch 核实 `origin/main=e2cfbe24d0e95999057870433956e97310694928`；整条分支 fast-forward 至
M12 `2c645ba067c47b28679a3d4754f7111965a830b0`，没有重复摘取转换核心。仅补充 M14 的 STATUS-only
`095040e` 证据（本地映射 `ef3df38`）、恢复/私有来源集成测试及 TEST_PLAN/本状态记录，不改 app。
M12 浏览器证据属于下项负责人实测；不写成 M14 重做了完整浏览器矩阵。

- M14 独立全量非 external：455 passed / 14 deselected / 1 条既有第三方 warning（包括新增 1 项转换恢复测试）。
  全仓 Ruff、主环境 pip check、21 Schema 可复现、1000 物理行和 diff check 通过。
  无凭据 MVP 演示 FAIL→PASS、两份回执重放与新会话恢复 valid=true。
- 同源归档/wheel 的隔离 Linux 镜像构建门及独立 `--network none` 运行门通过：101 个源码文件匹配安装 wheel，
  实际入口导入 `/app/src/trust_receipt`、页面 exception 0、TreasuryTally 产品区存在。没有生产环境、真实密钥或用户数据挂载。
  该门只证明真实初始页面可运行，不代表外部核验或生产部署。
- 额外 Linux 测试使用只读测试源码挂载：21 项转换 UI 加 1 项恢复/私有来源测试全部通过。
  首次挂载包含 Windows 字节码缓存，导致 11 项 inspect 源路径失败；容器独立缓存并原样重跑后 22 passed。
  不跳过失败断言，不将缓存问题改成应用修复。
- 新增测试证明采纳不创建任务/attempt，原声明和 local-upload-intake 身份保留；新 workflow 从持久化证据与签名恢复，
  不重新取证。原 CSV 私有备注、文件名及转换 provenance 不进入本地构造的授权公开包；未授权导出拒绝。
  只测试序列化，不调用 publisher 或写链。
- 审查未发现阻断本地合流的新增问题。私有输入使用内容哈希文件名，位于工作区 `receipts/private/.../uploads`，
  不在 `app/static` 或公共回执目录；签名、Receipt/Schema、发布器、确定性规则和品牌资产与基线无差异。
  confirmed 参数不是授权令牌，provenance 不是原作者签名；跨文件留档非事务，失败可能留下私有孤立文件。
  原型不提供多租户访问控制，不适合真实敏感报表；这些限制没有因转换入口而解除。
- 未进行真实模型/RPC/外部服务核验、真人测试、线上任务恢复、760px 两侧/原生 200% 全状态视觉矩阵，
  未推送、合并 main、部署、公开上传或写链；生产仍保留既有品牌版本。

### 原始报表转换 UI（2026-10-07，本地完成，未部署）

M12 在独立 `m12-report-intake/HACKTHON` 工作树、`codex/report-intake-ui` 分支从已发布主线
`e2cfbe24d0e95999057870433956e97310694928` 开发；不修改有未提交改动的旧主 checkout。
M14 拥有 CSV/XLSX 纯转换核心，M12 唯一写入首次/修正版页面与 PRODUCT/FRONTEND_SPEC/ADR-031。
转换与明确采纳边界已写入设计文档；UI 确认状态按原字节哈希、文件名、映射、共用条件及工作区/入口隔离，
改变输入撤销旧采纳，恢复旧设置也不会自动恢复。已消费 M14 `611523d`、`de776dc`、`dc52a71`，
首步与修正版共用映射、缺失条件、预览和明确采用组件；非法或未采用修正版阻塞执行，不回退旧报表。
本轮实跑非 external 全量 454 passed / 14 deselected / 1 条既有 warning，含 21 项 UI 采纳/修正新增测试；
Ruff、pip check、21 Schema、1000 物理行和 diff 检查通过；离线 MVP 双回执重放通过。
独立本地 8538 浏览器实际上传 CSV/XLSX：CSV 预览、映射失效、原表手机横向容器检查及采用/范围确认后 PASS；XLSX 首次 FAIL、
公式修正版阻塞、合法修正版明确采用后第二次 PASS，保留首次记录且无第三次入口。
缺日志身份、Excel 数字金额和公式实际阻塞；共用链编号由用户明确填写，格式转换不认证作者、不代表 PASS。
1440/390px 输入和结果页无页面横向溢出；完整刷新重开引导，普通 rerun 不重开。
未执行外部服务、真实链上核验、真人可用性测试、用户线上工作区操作、公开上传、写链、推送、main 合并或部署。

### 首步表格转 JSON（2026-10-07，本地实现，未发布）

M14 核心 `611523d`、结构拒绝增量 `de776dc`、有界解压增量 `dc52a718de7e6802cc48c307608b9f65a2205e94`
基于 `e2cfbe2`，支持受限 CSV/单工作表 XLSX 到既有
UploadedReport 的确定性转换候选与确认后私有留档。原始声明、重复行及来源边界不变，不调用 AI/RPC，不创建参考证据。
最终核心实际验证：转换专项 66 passed；全量非 external 433 passed / 14 deselected / 1 条既有 warning；
全仓 ruff、pip check、21 Schema 可复现与 diff check 通过。新增代码与测试的物理行数均低于 1000 行。
核心阶段由 M12 独立接入 UI 并单写 PRODUCT/FRONTEND_SPEC/ADR031；现已完成，界面证据见前项。
未进行真实用户测试、外部网络核验、推送、合并或部署；生产仍是下述品牌版本，不将本地候选称为上线能力。

### TreasuryTally 品牌统一（2026-10-07，已合并并部署）

用户确认产品与品牌名称统一为 `TreasuryTally`。网页标题、品牌文字、Logo 替代文本、README、产品与前端规范、
自助说明、立项材料、包描述及回执 CLI 帮助已修改；受维护主线文本扫描无旧品牌或 AGNET 拼写残留。
兼容性技术标识与历史签名/回执保持不变，边界见 ADR-030；不重命名仓库、生产路径或协议标识。
主控实跑非 external pytest 为 367 passed / 14 deselected / 1 条既有 warning；pip check、21 Schema 与文件规模门通过。
Skill 品牌增量 `1b6e525` 与 MCP 品牌增量 `808ff86` 已由各负责人在独立分支验证；不将其新增实现混入网页发布。
Skill 独立公开仓库品牌同步提交 `be53ac0`，URL 保持不变。

- 品牌提交 `3c6ad8815b0b75fdd3f7c81123f5a43bf471f2bc` 经
  [PR #17](https://github.com/CH-ZHOU-0512/xinjv/pull/17) 合并为 `5fb7f753fb7c72ecd65e68e45e2024c35832c8a0`，
  并完成首次品牌镜像切换。随后主控补充 app 包 docstring，完整品牌提交为
  `935dc82e60d48b2612f04f1c2af00b51efb78059`，经
  [PR #18](https://github.com/CH-ZHOU-0512/xinjv/pull/18) 合并为 `5872c8922a0760035a340c0f46c39dff5d8faad8`，
  两者源码树相同；两次 PR/分支及合并主线 CI 均通过。不是把首次镜像改标为补漏后的源码。
- 当前生产镜像 `trust-receipt:brand-935dc82e60d48b2612f04f1c2af00b51efb78059`，revision 为完整品牌提交，
  image ID `sha256:5357c9fb6562072cf761d8f3306f1883437bd46724edb610e32a7a72bb4c1a01`。
  同源归档/wheel 上传 SHA-256 校验通过；构建、独立无网络运行和切换前真实 `/app` 入口均为
  98 源文件匹配 wheel、exception 0、TreasuryTally 品牌区存在；镜像 pip check 通过。
- 只替换 app，两次切换均核验 `.env` 哈希、三个数据/回执挂载、Blockscout ID/启动时间不变；当前 healthy、公网 health 200/ok，
  `APP_REQUIRE_LIVE=true`、`M6_ENABLE_WRITES=false`。未动 Nginx、用户任务或历史回执，无公开上传/写链。
- 最新回滚 `trust-receipt:brand-rollback-935dc82e60d48b2612f04f1c2af00b51efb78059` 指向前一健康品牌镜像 `brand-3c6ad88…`，
  原业务版本回滚 `trust-receipt:brand-rollback-3c6ad8815b0b75fdd3f7c81123f5a43bf471f2bc` 指向 `ui-002b8e1…`；
  均按旧镜像自身入口门验证，不用新品牌要求否决旧版本。两次源码备份分别在
  `/opt/trust-receipt-backups/brand-935dc82e60d48b2612f04f1c2af00b51efb78059/` 与
  `/opt/trust-receipt-backups/brand-3c6ad8815b0b75fdd3f7c81123f5a43bf471f2bc/`。
- 发布者独立 `m14-brand-release` 在最终镜像切换后刷新并实测 1440×1000 / 390×844 首页：标题与可见品牌为 TreasuryTally，
  Logo alt 为 TreasuryTally Logo，可见页面无旧中文品牌，exception 0、无页面水平溢出，黑金 CSS 就绪；
  名称完整显示。两处 Logo 实际复用 `.../media/fcec295ccbc208d821452279307d79e9.png`，自然宽 288px，
  桌面显示 52/144px、手机 44px/大图按规范隐藏；不能仅由 image_id 更名推断 URL 必变。
  原 PNG SHA-256 仍为 `875de454…0610c`。截图位于发布者工作树忽略目录
  `output/playwright/treasurytally-final-1440.png` 和 `treasurytally-final-390.png`。
- 发布者复跑品牌/文档 4 项通过，补漏 docstring Ruff/diff check 通过；完整 367 项质量门由主控实际执行并由各轮 CI 复验。
  发布浏览器记录包含容器切换期间 WebSocket close 与短暂 502，最终页面与健康恢复；不声称全会话 console 0。
  未做本轮真实核验、上传、用户故障任务恢复或性能改善验证，未纳 M15/M16 实现；原有多状态视觉与冷加载待验收项仍保留。

### 网页集成修复发布（2026-10-07，已合并并部署）

- 用户授权继续发布仅 M9 持久化 attempt 修复与 M12 引导/普通交互整合；不纳入 M15/M16。
  完整分支提交 `002b8e117f24033238cd686c230083a140b33bab` 已经
  [PR #15](https://github.com/CH-ZHOU-0512/xinjv/pull/15) 合并至
  `1153e51cb40831f29f9207eeb25671f3803cb782`，两者源码树完全一致；分支、PR 和合并主线 CI 均通过。
- 广州当前应用镜像为 `trust-receipt:ui-002b8e117f24033238cd686c230083a140b33bab`，revision 与完整源码提交一致，
  image ID 为 `sha256:c630c94f5450d4d474e5da96cf2b8f20b1b3cc1983105e8b69495de286666140`。
  source archive 和纯 Python wheel 上传后 SHA-256 校验通过；构建期、独立无网络运行、切换前均通过真实 `/app` 入口门：
  98 个源码文件与安装 wheel 一致、导入 `/app/src`、首页 exception 0、品牌区存在；依赖未变，镜像 pip check 通过。
- 只重建 app。`.env` 字节哈希、Blockscout 容器 ID/启动时间、三处数据/私有与公开回执挂载前后一致；应用 healthy，
  公网 health 返回 200/ok，`APP_REQUIRE_LIVE=true`、`M6_ENABLE_WRITES=false`。未改 Nginx、Blockscout 或业务开关。
  未删除、解锁或重跑用户 task/attempt/receipt，未新增公开上传、链上交易或合约部署。
- 回滚镜像 `trust-receipt:ui-rollback-002b8e117f24033238cd686c230083a140b33bab` 指向切换前健康的 `recovery-ea8f772…`，
  旧镜像也实际通过隔离入口门；源码备份与旧镜像记录在
  `/opt/trust-receipt-backups/ui-002b8e117f24033238cd686c230083a140b33bab/`。原图 SHA-256 仍为 `875de454…0610c`。
- 发布者独立公网浏览器 `m14-public-ui` 实测新标题、引导第 1/5 步、下一步到第 2 步、Escape 关闭；
  输入全新隔离工作区 `m14-release-probe-002b8e1` 并 Enter 后实际后端重跑完成，新工作区文件存在且引导保持关闭；
  完整刷新后从第 1/5 步重开。没有上传报表或执行核验。主控独立 `root-ui-release` 另复核新版引导、刷新重开及手机首页。
- 公网当前首页 1440×1000 与 390×844：异常 0、页面无横向溢出、主题 CSS 就绪；可见文字字号只在
  `12/14/16/20/24px` 集合，流程卡片 gap 为 16px，手机页顶为 12px。两处 Logo 复用同一自然宽 288px PNG：
  桌面显示 52/144px，手机 44px/大图按规范隐藏。未上传文件时“整理核对范围”禁用，没有首次/补交执行入口。
  截图为发布工作树忽略目录 `output/playwright/public-ui-1440.png`、`public-ui-390.png`；不能据首页推断完整结果/全部状态规范通过。
- 公网资源加载仍慢：独立首次导航的多个基础 chunk 耗时约 20–83s；一次带浏览器缓存的 reload 中 Logo 请求约 14.7s，
  浏览器报 slow-network 信息。无修复前同条件基线、无双视口全新冷上下文完整时序，不声称首屏速度达标或改善幅度；
  容器健康和页面最终渲染不替代速度验收。发布者检查时无 console error；主控会话有旧导航错误，不据此声称所有会话 console 0。
- 未完成：线上用户故障工作区具体原因或恢复验证、本轮真实 RPC/模型验收、公开上传/写链、完整冷加载性能对比、
  760px 边界两侧及 200% 全状态视觉矩阵。真人测试由用户取消；下面本地/旧发布条目为历史阶段证据，不代表当前未部署。

### 发布前本地网页集成验证（2026-10-07，历史阶段）

- 新独立工作树 `m14-local-ui-integration/HACKTHON`、分支 `codex/m14-local-ui-integration` 从已安全 fetch 核实的
  `origin/main=675728a` 创建；原 M14 工作树干净且保留。按顺序合入 M9 `795dddd` 和 M12
  `6f41026 / 5660f99 / ea4b82f / 8642b5c / a9c6523`，代码集成提交 `287770b`；没有合入 `8f8a311` 或 M15/M16。
  文档冲突保留 ADR-025 取消真人要求、ADR-026/029 UI 决定及已部署 Logo 记录，027/028 仍留给后续扩展。
- 合流后完整非 external pytest 再跑为 367 passed / 14 deselected（1 条既有第三方弃用 warning）；Ruff、主环境
  pip check、21 份 Schema、1000 行限制、diff check 通过。无凭据 FAIL→PASS→重放→恢复演示 valid=true。
- 本轮本地 Docker Desktop 可用。隔离 Linux 验证镜像 `trust-receipt:local-ui-287770b` 从同源归档/wheel、锁定依赖构建，
  没有 `.env`、真实密钥或生产挂载；构建期和独立 `docker run --rm --network none` 均通过真实 `/app` 入口门：
  98 个源码文件与 wheel 一致、实际导入 `/app/src`、首页异常 0、品牌区存在。该镜像只是本地验证，不是生产发布镜像。
- 本地浏览器 1440×1000 与 390×844、DPR 2：完整刷新从引导第 1 步开始；关闭后切换报表输入触发实际后端重跑，
  引导不重开；只读状态刷新同样不重开。Escape、Tab/Shift+Tab 焦点环实测通过。纯 JS 生命周期测试另覆盖打开时步骤保持。
  浏览器弹窗打开时按 `r` 未观察到后端重跑，不能将此时仍在第 2 步计为“打开弹窗下重跑”的浏览器实测。
- 新建本地 fixture 中断工作区恢复为 REQUESTED，仅显示中文阻塞与只读刷新，没有首次或补交按钮。
  两视口刷新后 task ID 不变、仍 REQUESTED / 0 交付 / 0 结果 / in-flight=1 / next_attempt=None；没有解锁、重跑或删除。
  截图 `output/playwright/integrated-pending-1440.png`、`integrated-pending-390.png`，只属于本地测试工作区。
- 两视口实际走通离线合成报表首次 FAIL → 缺修正版禁用最后一次 → 上传修正版 → PASS；首次记录保留，
  不再提供首次/补交按钮，不出现第三次请求，引导不重开，页面无横向溢出或 exception。
  截图分别为 `output/playwright/integrated-fail-{1440,390}.png`、`integrated-pass-{1440,390}.png`。
- 原 `branding.py/styles.py` 与主线首屏修复无差异；本地待处理页可见字号全部属于五级集合、导航 gap=16px、CSS 就绪、异常 0，
  两处 Logo 复用自然宽 288px 媒体资源；桌面 52/144px、手机 44px/大图隐藏。原 PNG 未修改。
- 未完成：真实 RPC/模型、线上用户任务原因确认或中断请求恢复、公开上传、写链、线上首屏冷时序、760px 两侧及 200% 完整视觉矩阵。
  该本地验证阶段未推送、未合并 main、未部署；后续经授权的发布结果见上方。测试脚本/本地 fixture 留在忽略的 `.tmp/`，截图不提交。

M12 新手引导独立补丁（2026-10-07，本地未部署）：工作台五步原生弹窗已接入，完整刷新从第一步显示；
Streamlit rerun 保留步骤与关闭状态，公开验证入口不弹上传引导。纯 JS 生命周期与 Python 接入测试 4 项通过，
非外部全量测试 311 passed / 13 deselected，Ruff 与 pip check 通过。本地浏览器实测下一步、Escape、
关闭后切换输入模式不重开、完整刷新重开；390×844 弹窗宽 352px、无页面横向溢出、按钮高 44px。
未执行本轮外部服务检查、公开上传、写链或部署。

### Attempt 持久化状态错位修复（本地业务与页面已接入，待主控集成部署）

- 用户截图的“仍显示 Attempt 1，却被安全锁拒绝”已在隔离测试复现同类路径：交付后异常保留 VERIFYING，
  或结果已保存但回执写入失败；恢复过滤未完成/缺回执 attempt，页面空 session 错当未开始。不归因于重复点击。
  未读取或修改用户线上工作区，因此不宣称已确认其具体数据库状态。
- 新增只读 `get_attempt_status(task_id)`，由持久化 state、交付与结果计数决定 in-flight/next attempt；
  缺失或冲突原始回执阻塞页面执行。M5/M8 `restore_task(task_id)` 仅读当前任务，不误选其他会话最新任务。
  REQUESTED/SUBMITTED/VERIFYING 不自动解锁、回滚或重跑；最多两次和第二次仅 FAIL/INCONCLUSIVE 规则不变。
- `request_attempt` 读/检查/请求在 SQLite IMMEDIATE 事务内串行化，两连接不能同时预约同一 attempt。
  本轮11项新增状态/故障/并发回归通过；页面接线由 M12 唯一写入，尚未部署或在线恢复用户任务。
- 修复基线为已知 `origin/main=675728a`；本轮 fetch 因 GitHub 443 连接失败未成功，不称已取实时最新远端。
- M9 分支报告本地完整 pytest 为 340 通过、14 项外部配置缺失跳过；Ruff、pip check、21 份 Schema、1000 行限制和 diff 检查通过。
  该数字是来源分支记录，M16 消费后以本分支实际重跑为准。没有读取真实线上故障状态，不宣称线上同一原因已修。

### Logo 首屏与间距修复（已部署，公网冷加载时序待复核）

用户确认两个 Logo 曾一起缺席、随后出现，并授权修复。原图仍为 1,395,476 字节；标题和全局样式原经
Markdown 异步组件，当前 Streamlit 1.65.0 的 Markdown 独立 chunk 为 226,308 字节，HTML 独立 chunk 为 1,788 字节
（不含各自共享依赖，不把此大小比当作加载速度提升倍数）。修复首屏 CSS/品牌区改用直接 HTML，Logo 明确 eager，
两个位置复用原生媒体管道生成的 288px PNG 预览；保持原始图字节及业务行为不变。实际渲染资源已调整，不能沿用原始静态 URL 不变的旧结论；尚未声称生产加载速度已改善。

同次规范核查发现移动同组字段/卡片 gap 为 8px、页顶 padding 为 11.2px，结果结论卡片 margin 为 24px；分别修正为
16px、12px、16px。桌面输入面板 24px / 移动 16px 内边距属于 FRONTEND_SPEC 材质面板明确例外，保持不变。
本地输入页 1440px 与 390px 可见字号均属于五级集合，未发现页面横向溢出；不据此声称完整结果页/所有状态已通过规范验收。
修正后浏览器复测：移动页顶 12px、同组字段 16px、三步卡片间距 16px；桌面同组字段/三步卡片均为 16px。
显示预览为 288×288 RGBA（alpha 范围 0–254），82,098 bytes；原图 SHA-256 为
`875de454cce5210d4d8ca3049f68126b6196be1e465d558f8aa840146a00610c`，未修改。
本地非外部 pytest 329 passed / 14 deselected，ruff、pip check、diff check 通过；DPR 2 桌面小图 52px / 大图 144px
复用自然宽 288px 资源，手机小图 44px / 大图按规范隐藏，均已加载。
修复提交 `ea8f772a9bd8a512e01de0319e028bb24df99344` 经 [PR #13](https://github.com/CH-ZHOU-0512/xinjv/pull/13)
合并至 `2cc27e23ae8e2c71756b0c5206c5ee8e02f0b633`，两者源码树相同，分支/PR/main CI 均通过。
生产镜像 `trust-receipt:recovery-ea8f772a9bd8a512e01de0319e028bb24df99344` 已切换，仅重建 app；构建、独立运行和
切换前真实入口检查均 PASS（98 个源码文件与 wheel 一致、首页异常 0、品牌区存在）。容器 healthy，公网健康端点 200，
生产原图 hash 一致；APP_REQUIRE_LIVE=true、M6_ENABLE_WRITES=false，三处数据/回执挂载保持原路径，Blockscout 启动时间未变。
回滚镜像 `trust-receipt:recovery-rollback-ea8f772a9bd8a512e01de0319e028bb24df99344` 指向本次切换前已恢复的版本，
源码备份位于 `/opt/trust-receipt-backups/recovery-ea8f772a9bd8a512e01de0319e028bb24df99344/source.tar.gz`。
本轮新独立公网浏览器导航 60s 超时，未取得可用的线上冷加载时序；不能以容器/健康端点正常替代实际浏览器加载速度，
也不能由本地时序或资源字节比推断线上加速。线上加载复核与完整多状态视觉验收仍未完成；本轮没有真实用户测试、公开上传或写链。

本轮用户明确取消真实用户测试要求，并授权更新文档、提交、推送、合并与部署。发布采用 M14 已合流的 M9–M12 功能、
M13 已提交专属材料及 M14 技术验收交付；不纳入 M13 未提交浏览器驱动，不恢复暂停的浏览器排练。
真人参与不是发布条件，但 M14 仍为 8 PASS / 6 BLOCKED，M13 重新确认排练第三轮中断；不得称全部技术验收完成。
本授权不包含新增公开回执上传、合约部署或写链。当前发布执行结果将在本文件记录。

### M9–M14 发布与部署（2026-10-07）

#### 页面启动事故已恢复

- 修复提交 `b5f2bcf` 与调用方式修正 `bdc705cff5ed073451ddf21cacb0d5df0ef1b51b` 已分别通过
  [PR #10](https://github.com/CH-ZHOU-0512/xinjv/pull/10)、[PR #11](https://github.com/CH-ZHOU-0512/xinjv/pull/11)
  合并；修复主线为 `050a8527068e2b3e516ebdc0baf93c1ebf891ceb`，分支、PR、合并主线 CI 均通过。
- 当前线上镜像为 `trust-receipt:recovery-bdc705cff5ed073451ddf21cacb0d5df0ef1b51b`，revision label 对应同名完整源码提交，
  其应用/部署树与 PR #11 合并主线一致。98 个 Python 文件与已安装 wheel 一致（只归一化换行）。
- 旧故障镜像运行新增一致性门明确失败；恢复镜像在构建、隔离运行和切换前均通过真实 `/app/app/streamlit_app.py`
  AppTest：零 exception、产品标题渲染、实际导入 `/app/src/trust_receipt/__init__.py`。无网络、无生产挂载、无密钥，未用 PYTHONPATH。
  检查器初版直接从 `/opt` 启动的路径差异也被门拦截；修正为匹配生产模块启动的 `/app` 工作目录调用后才放行。
- 主控独立 `root-release-recovery` 浏览器在切换后实际显示工作台、产品标题、Logo、自定义黑金样式、运行配置、服务历史、
  示例/严格 JSON 模板与任务候选入口。最终 DOM 为 header=true、logoLoaded=true、moduleError=false、stException=0，console error=0。
  完整首页截图为主控工作区 `.playwright-cli/page-2026-10-07T09-00-19-212Z.png`（UTC 工具文件名，仅首页呈现证据）。
  初始灰色占位为尚未完成的异步加载，后续自行完成；未测速，不推导稳定加载耗时。本发布会话两个超时/空快照不冒计通过。
- 应用 running/healthy，公网 health 为 200/ok，镜像 pip check 通过。只替换应用容器，原配置及三个数据/回执挂载保持不变，
  Blockscout 仍为 `trust-receipt-blockscout:d0cf46a`，`M6_ENABLE_WRITES=false`，未触发业务上传、公开发布或写链。
- 已准备可用的 M8 回滚镜像 `trust-receipt:recovery-rollback-bdc705cff5ed073451ddf21cacb0d5df0ef1b51b`，
  同时保留原 M8 源码备份；故障现场源码保存在
  `/opt/trust-receipt-backups/recovery-bdc705cff5ed073451ddf21cacb0d5df0ef1b51b/source.tar.gz`，不把故障镜像当作健康回滚。
- 本地修复全量门为 326 passed、14 external deselected，新增 7 项发布回归通过；后续调用小修正的 9 项专属/治理检查通过，
  CI 重新运行完整门。Ruff、pip check、21 份 Schema、文件规模检查均通过。真人测试不要求；M14 六项待验收及 M13 中断边界不变。

**发布事故纠正：** 下列 healthy/200/WebSocket 仅证明服务连接，不代表业务页面成功渲染。用户截图与真实镜像隔离 AppTest
已复现 `streamlit_app.py:23 → m9_components.py:10 → ModuleNotFoundError: trust_receipt.m9`。
新 wheel 含 M9/history，但快捷发布漏复制 src，页面优先导入继承的 M8 `/app/src`。此前 `/release` 目录演示掩盖了旧源码覆盖，
“网页正常”结论撤回。当前按用户继续发布授权修复：永久 Dockerfile 同源复制 src，并新增真实入口及源码/wheel 一致性门。
修复部署结果见上方恢复记录；健康检查不补记 M13/M14 缺失验收。

- 发布分支已提交并推送，[PR #8](https://github.com/CH-ZHOU-0512/xinjv/pull/8) 已合并；
  主线部署提交为 `cd01f8dad329ebe6b7874c56a9a9ee0c005cc2e7`，分支、PR 与合并主线 CI 均通过。
- 广州应用镜像为 `trust-receipt:m14-cd01f8dad329ebe6b7874c56a9a9ee0c005cc2e7`，revision label 与部署提交完全一致。
  源码归档与纯 Python wheel 哈希校验通过；依赖未变，镜像内 pip check 通过，无网络 FAIL→PASS、回执重放及恢复 valid=true。
- 应用 running/healthy；匿名公网入口、健康端点、Logo 均为 200，WebSocket 连接为 Open。
  原 `.env`、data、private/public 回执挂载保留；Blockscout 仍为 `trust-receipt-blockscout:d0cf46a`，未重建其他应用，
  `M6_ENABLE_WRITES=false`。
- 回滚镜像为 `trust-receipt:m14-rollback-cd01f8dad329ebe6b7874c56a9a9ee0c005cc2e7`；源码备份为
  `/opt/trust-receipt-backups/m14-cd01f8dad329ebe6b7874c56a9a9ee0c005cc2e7/source.tar.gz`，同目录记录旧镜像。
- 本次不做真实用户测试，不恢复暂停的页面交互验证；M14 的 6 项待验收及 M13 第三轮中断保留。
  未新增公开回执上传、合约部署或链上交易。后续文档收尾提交不改变已部署的应用代码版本。

### 本轮发布质量门

- 发布合流版本实际执行非 external pytest：319 passed、14 deselected，1 条既有第三方弃用 warning。
- 全仓 Ruff、主环境 pip check、21 份可重复 Schema、1000 物理行限制和 git diff --check 通过。
- 无凭据演示得到 FAIL→PASS、两份回执重放及恢复，valid=true；未执行公开发布。
- 本轮没有重跑外部探针或暂停的浏览器排练；这些本地检查不补记 M13/M14 缺失的技术验收。

M12 页面接入补充（2026-10-07）：已消费 M9 `795dddd` 的 M8 状态与当前 task 恢复端口，
首次/补交按钮仅依赖持久化 next_attempt；未完成请求、缺回执、记录或快照冲突均阻塞，不以空 session 判首次。
操作失败保留实际错误并 rerun 只读重投影，点击前再次检查状态；不自动重试、撤销请求、删历史或新增第三次。
当前任务缓存落后时仅读恢复该 task_id，不误选另一会话最新任务；恢复冲突提供中文阻塞和实际错误详情。
27 项状态专项回归（核心 11 + 页面 6 + 视图/同步 10）通过；最终非外部全量 348 passed / 13 deselected。
Ruff、pip check、21 份 Schema 重新生成无差异、1000 行限制与 diff 检查通过。
本地浏览器恢复独立 fixture 中断工作区，1440×1000 与 390×844 均无横向溢出；无首次按钮，
只有只读刷新，刷新后 DB 仍 REQUESTED、零交付，引导未重开。截图留在 `.tmp/`，不提交。
新会话恢复、请求后异常、结果写后回执异常、FAIL/INCONCLUSIVE 补交、PASS/两次结束及并发预约由离线测试验证。
线上具体 DB 状态未读取，真实 RPC/模型、公开上传、写链、部署与用户线上悬挂请求恢复均未执行。


M12 普通人交互独立补丁（2026-10-07，本地未部署）：业务按钮与必要报表选择、完整范围确认、
高级配置折叠、原输入折叠、金额/差额/原因/下一步优先及证据详情折叠已实现。缺文件/范围不能继续，
整理失败不替代演示范围，首次 FAIL 上传任务缺修正版禁用唯一补交；模拟说明与真实 AI 调用区分。
非外部全量 318 passed / 13 deselected（最后文案收敛前），新增交互测试覆盖输入门禁、确认、AI 失败、
三态与写链状态、修正版门禁和唯一主操作。本地 390px 浏览器实测显式练习→整理→人工确认→主动核对→
FAIL 差异与修正版门禁，页面无横向溢出；引导全程未重开。修正版 PASS 与 INCONCLUSIVE 由 AppTest 验证，
AppTest 不支持文件上传，修正版 adapter 使用测试注入，不冒充真实浏览器上传。本轮真实模型/RPC、
公开上传、写链和部署未执行。M14 `ea8f772` 的品牌/CSS 与相关测试块已局部移植至本地共测，
未移植部署脚本/根文档；最终共测 321 passed / 13 deselected，Ruff、pip check 与行数检查通过。
浏览器冷启动确认 288px 原生媒体 Logo 与引导共存、390px 无横向溢出；上一页/五步/完成可用，
首尾 Tab 与 Shift+Tab 的显式循环焦点约束已补强并实测，Python/JS 引导测试 4 passed。
本地热更新曾遇旧 branding 模块缓存，重启本人启动的本地进程后冷启动正常，不视为生产部署验证。

M1 已完成：领域契约、Pydantic 模型、8 份 JSON Schema、契约测试和 12 份人工标注 fixtures
均已集成到 `codex/m1-integration`。M2 PR #1 已合并，远端合并提交为
`d9ac1108e9a21fe0073587d4f458848ed1ac8ecd`。M3 无 UI 纵向闭环及本地回执重放已在本地实现并验证。
M4 受限 AI 编排、供应商 adapter、离线对抗测试及真实 DeepSeek 结构化调用已完成。M5 Streamlit 产品页面、
fixture 路径与真实 DeepSeek + Sepolia RPC + Blockscout 产品闭环均已完成；桌面、移动端和进程重启恢复均已做真实浏览器检查。
M5 已部署至广州 Linux 服务器的隔离容器，并通过现有 HTTPS 反向代理公开访问。M6 公共回执发布与 ERC-8004 关联均已
完成真实 Sepolia 产品闭环：公共内容哈希、链上反馈、事件读回和 SQLite 终态一致。M7 验收封装与本地收尾已完成；
`codex/m1-integration` 已同步远端 M2 合并历史并进入 `main`，最终主线 CI 已通过。M8 资金流投影、EIP-712 承诺、前端主流程
重构与 Validation Registry 只读探针已合并并部署到广州应用；M9–M14 本轮已集成发布，剩余技术验收见前述记录。
专用锚仍只是未部署候选。

合流依赖分支补充记录（待主控统一治理）：

重构与 Validation Registry 只读探针已通过 PR #6 合并到 `main`（`821bbc2`）。M9 确定性返工、外置版本链、修复对比与公开验证
已在独立交付分支实现并完成本地验收，包括 M8 承诺快照、恢复、返工主流程、可移交公开历史包和独立验证页面；
已只读核验既有公开回执与 Sepolia feedback，尚未合并主线、部署或上传新的公开历史包。
M10 已在独立交付分支接入 M8+M9 工作区与页面并完成本地验收；尚未合并主线或部署。

## 已完成

- Python 3.12 主环境 `.venv` 已创建，`pip check` 通过。
- Agent0 SDK、LangChain、Streamlit、Web3.py、Pydantic、SQLAlchemy、Pytest、Ruff 已安装。
- Blockscout MCP 已在 `.venv-blockscout` 独立安装，CLI 和 `pip check` 通过。
- Streamlit 基础启动健康检查已通过。
- `agent0-py`、`erc-8004-contracts`、Blockscout `mcp-server` 已下载到 `references/`。
- ERC-8004 参考合约编译成功，79 项上游测试通过。
- 根目录、环境变量模板、依赖清单和锁定快照已建立。
- 开发前产品、架构、数据、测试、安全、运维和协作文档已建立。
- M0 外部集成规格、分阶段依赖门槛和代码文件规模约束已建立。
- Git 仓库已连接到 `https://github.com/CH-ZHOU-0512/xinjv`，默认分支为 `main`。
- 已创建 `pyproject.toml`、`src/trust_receipt/` 包和 `tests/external/`，包含 RPC、Blockscout MCP、
  Agent0 与 ERC-8004 的最小探针。
- 外部调用统一设置超时；只读操作最多重试两次；ERC-8004 写探针默认关闭且不自动重发未知交易。
- RPC 已在 Sepolia 读取固定历史区块和真实 WETH Transfer，保留整数金额及完整事件键。
- Blockscout MCP 已完成 initialize、16 项工具发现及同一笔 Sepolia 交易查询；客户端与服务端统一使用 MCP 1.26.0。
- 已创建团队控制的 Agent0 身份 `11155111:10691`，Agent0 SDK 1.7.1 可重复读取名称、owner 和 active 状态。
- 三个 ERC-8004 Registry 的链上 bytecode 与相互关联已核验；中性反馈交易已确认并从链上读回一致内容。
- 已建立 `codex/m1-integration` 与 `codex/m1-core-models` 分支，并从远端 `main` 合并提交
  `b44945b48bef8b77b9fe4633fd714de75a66d636` 开始 M1。
- 已冻结 `trust_receipt.models` 公共边界，覆盖任务、转账、服务交付、白名单计划、三态验证结果、回执及
  M1 fixture/manifest 模型。
- 核心金额在领域边界使用无符号十进制整数字符串；事件键保留 `chain_id + transaction_hash + log_index`；
  参考不完整或证据不足强制为 `INCONCLUSIVE`。
- fixture 布局固定为 `fixtures/m1/manifest.json` 与 `fixtures/m1/cases/`；8 个顶层 Schema 文件固定输出到
  `schemas/v1/`，导出脚本路径固定为 `scripts/export_schemas.py`。
- A 的 12 份 fixtures 与 B 的 8 份 Schema、导出脚本和契约测试已通过 PR 集成；3 处参考记录与来源描述符
  不一致已修正，来源标签现在可交叉核验。

## M2/M3 验证进展

- 已实现任务范围过滤、完整事件键去重、整数汇总、分页连续性校验和可定位 Finding。
- 首条纵向切片得到 `110000`、`FAIL` 和两项 Finding。
- 对抗性测试复现并修复了完整来源事件集合不一致、同一区块哈希冲突两类误判 PASS；两者现在返回 INCONCLUSIVE。
- 严格联调入口 `python -m pytest tests/verification/test_m1_fixtures.py --m1-fixtures fixtures/m1`
  已实际运行，12 份 fixtures 的金额、数量、三态结果、Finding、规则和事件键全部匹配。
- 全量测试 97 项通过、5 项因外部配置缺失而跳过；fixture Schema 校验、Ruff 与 pip check 均通过。
- 已实现拒绝 `float` 的 canonical JSON、SHA-256 稳定哈希及 TaskSpec、ServiceSubmission、Receipt 校验函数。
- 已实现团队控制服务 A/B 端口、EVM 签名恢复校验和独立故障注入元数据，模拟故障不混入参考来源。
- 已实现 SQLite task/attempt/verification 分表留档与状态机；attempt 只追加，最多一次补交，签名失败不消耗 attempt。
- 无 UI 编排已跑通首次遗漏导致 `FAIL`、同服务补交或切换服务后 `PASS`，两个 attempt 均可分别读取。
- 已实现 ReceiptBuilder、本地只创建不覆盖的 JSON 存储和独立进程重放；FAIL/PASS attempt 分别生成不同哈希，
  重放会校验回执哈希、任务哈希、对象链接并重新推导三态结果。
- 已增加最小 GitHub Actions 配置：普通 CI 执行非 external pytest、Ruff、pip check；外部探针不伪装成功。
- 当前全量本地测试为 107 项通过、5 项因外部配置缺失而明确跳过；Ruff 与 pip check 通过。

## M4 AI 编排进展

- 已实现 `TaskSpecCandidate`、`ClaimExtraction`、`FollowUpAdvice` 和 `ResultExplanation` 严格 Pydantic 契约，
  并新增 4 份可重复生成的 JSON Schema；缺失字段、歧义、重复主张类型和非规范金额在候选边界拒绝。
- 已实现无工具 `StructuredOutputPort`、`RestrictedAIService`、LangChain OpenAI adapter 与 DeepSeek
  OpenAI-compatible Responses adapter；核心 models、verification、storage 和 receipts 不依赖供应商 SDK。
- 任务 ID、确认时间和 `spec_hash` 只由确定性代码生成；VerificationPlan 必须完整命中白名单并逐项绑定已确认任务。
- 补查建议仅允许封闭动作枚举；结果解释必须保持确定性 outcome、金额、数量、Finding ID 和证据引用。
- 离线测试覆盖 prompt injection、未知操作、参数漂移、缺失检查、歧义任务、冲突主张以及金额/结论篡改。
- `deepseek-flash` 真实 external 探针已返回并通过 schema 校验；凭据仅保存在被 Git 忽略的本机 `.env`。
- OpenAI external 探针因缺少 `OPENAI_API_KEY` 和固定 `OPENAI_MODEL` 明确阻塞，没有用 mock 冒充实测。
- 删除临时凭据后的全量质量门为 128 项通过、7 项 external 因当前配置缺失而明确跳过；DeepSeek 探针另有此前
  单独执行的 1 项真实通过记录。Ruff、pip check、12 份 Schema 重生成检查和 1000 行限制均通过。

## M5 Streamlit 页面进展

- 已实现自然语言任务入口、候选缺失/歧义展示、可修改字段、显式确认与不可变 `spec_hash`；任务未确认前页面不提供执行入口。
- 页面只调用 `M5Workflow` 与稳定端口，不直接依赖供应商 SDK、SQLite 表或验证内部实现；AI 主张/计划校验失败会撤销请求且
  不消耗 attempt。
- 已串联团队控制服务 A/B、确定性三态验证、金额、Finding、受限解释/补查、本地回执预览，以及一次补交或换源；attempt 1/2
  分别展示和留档，后一次不会覆盖前一次。
- 缺少模型密钥时默认使用明确标注的离线 fixture 演示，不冒充真实模型调用；OpenAI/DeepSeek 选项会显示缺少 key/固定模型名
  的配置阻塞。
- 页面明确区分服务交付 `SUBMITTED` 与公共发布 `NOT_SUBMITTED`；M5 不执行公开上传、ERC-8004 写入或 M6 发布动作。
- 桌面 1440×1000 浏览器检查确认任务编辑采用双列；移动 390×844 检查确认关键水平容器折叠为单列、页面
  `scrollWidth=innerWidth=390`，长地址、Finding、attempt、回执与按钮均可读可操作。
- M5 AppTest 实际走通未确认拒绝、attempt 1 `FAIL`、attempt 2 `PASS`，两个结果同时保留；M5 收尾复核的
  非 external 质量门为 140 项通过、8 项 external 明确排除，Ruff、pip check 和 1000 行限制均通过。
- 已实现真实 `RpcReferenceEvidenceProvider`：校验 chain ID 与确认数、连续分页读取完整区块范围、保留整数与完整事件键；
  RPC 失败、缺页或未确认范围返回 `INCONCLUSIVE`。Blockscout 仅作可选补充抽样，未配置时明确显示 RPC-only。
- 真实组合 external 探针已使用 DeepSeek、Sepolia RPC 与 Blockscout 跑通候选生成、服务 A 漏项 `FAIL`、切换服务 B
  `PASS`、合法受限 AI 产物和两个独立回执；目标区块读取 1 页、6 条 RPC 原始事件，Blockscout 对真实交易完成补充抽样。
- 真实浏览器复跑得到同样的 `FAIL → PASS`，两个 attempt 均展示 RPC `COMPLETE` 与 Blockscout `SAMPLED`；重启 Streamlit
  后输入相同工作区 ID，可从 SQLite 与私有回执恢复已确认任务及两个 attempt，历史 AI 文本不会重新生成。
- 已新增不包含 `.env`、PEM、私有回执和本地数据的容器构建文件；生产容器以非 root 用户运行，SQLite 与私有回执挂载到
  宿主机持久化目录，应用端口不直接发布到公网。
- 广州服务器入口为 `https://creatoros.top/trust-receipt/`，使用 HTTPS；IP 明文入口只执行 HTTPS 重定向。
  Basic Auth 已从仓库和服务器反向代理配置移除；匿名页面与健康检查返回 `200`，WebSocket 握手成功，既有 IP 重定向不受影响。
- 部署服务器已真实调用 DeepSeek 并得到 schema 合法候选，真实 Sepolia RPC 读回固定交易与整数金额。该地域无法直连
  `api.blockscout.com`，现已通过团队 Vercel 中继与自定义域名恢复 Blockscout 补充抽样。
- 生产 Compose 已固定 `APP_REQUIRE_LIVE=true`，线上页面只提供 DeepSeek 真实模型和真实 Sepolia RPC；容器内复验得到
  `deepseek_schema_ok=True`、`rpc_real_ok=True`，且浏览器真实点击已返回由 DeepSeek 生成的缺失字段与澄清问题。
- M5 页面已重构为可用的验收工作台，包含运行信号、结构化步骤、任务摘要、attempt 结果卡和移动端布局；生产反向代理的
  Streamlit 路径级 CSP 已修复。桌面与 390×844 生产浏览器检查通过，移动端 `scrollWidth=innerWidth=390`。
- 固定上游、只转发 GET/POST 且要求 Blockscout Pro Bearer key 的中继已部署至 Vercel，并绑定
  `https://blockscout-relay.creatoros.top`。广州容器实测配置端点 `200`、真实交易端点 `200`、MCP 工具和分页完整性通过；
  产品证据诊断为 RPC `COMPLETE`、Blockscout `SAMPLED`，抽样 1 条记录。
- M5 最终交接复核确认生产应用容器为 `healthy`，Blockscout 容器持续运行，容器内健康端点返回 `ok`。公开入口的
  Basic Auth 已按产品要求移除并完成匿名访问验证。本地同名远端分支尚未同步。

## M6 公共回执与 ERC-8004 进展

- 已实现 `ContentPublisher` 端口、Pinata/IPFS adapter 与隔离目录离线 adapter。公开快照在上传前拒绝私钥、签名、JWT、
  Authorization、API key、secret 和原始报告正文等字段；上传后必须从 gateway 下载精确字节并核对 SHA-256。
- Pinata adapter 已按官方 v3 multipart 协议固定 `network=public`，JWT 只进入 Bearer header。缺少 JWT 时生产使用同一端口下的
  内容寻址 HTTPS fallback：应用只创建公共文件，Nginx 只读公开，并执行相同的公网下载哈希核验；不冒充 IPFS 固定。
- SQLite 新增只追加 `publication_events`，保存 `NOT_SUBMITTED / SUBMITTED / CONFIRMED / FAILED` 全部快照；进程重启按
  receipt ID 恢复最新状态，旧状态不覆盖。
- ERC-8004 产品 adapter 在写入前核对 Sepolia chain ID、受控 service owner、Reviewer、余额和 pending nonce；直接绑定公共
  URI 与内容 SHA-256。广播只执行一次，超时仍以已签名交易哈希和 nonce 保持 `SUBMITTED`，随后只允许读回，不自动重发。
- 链上确认必须从 `NewFeedback` 事件读回 service、Reviewer、URI、哈希和结果标签一致后才进入 `CONFIRMED`；确定性失败可在
  用户再次授权后从 `FAILED` 恢复为 `NOT_SUBMITTED`，`TRANSACTION_UNKNOWN` 禁止走该恢复路径。
- Streamlit 已接入两次独立授权：先授权公开脱敏 JSON，再授权 Sepolia 写入；页面分别展示公共 URI、内容哈希、nonce、交易哈希、
  feedback index、区块和脱敏错误。新会话可只读公共 JSON，在独立进程校验哈希并重放确定性三态检查。
- M6 HTTPS publisher 已部署到广州服务器；生产应用容器为 `healthy`，匿名页面与健康端点返回 `200`，WebSocket 握手成功，
  应用端口仍仅在 Docker 网络暴露。公共路径只允许 GET/HEAD，POST 实测返回 `403`。
- 已用真实 DeepSeek + Sepolia RPC + Blockscout 生成一份 `PASS` 回执并公开至
  `https://creatoros.top/trust-receipt/public/3b922f5825fe7127c0fa5da6c3664a2e93e7381db49579cc992d85b4292fa26e-receipt-e593dcc8-dc29-4db9-829c-31802a7de630.json`；
  公网下载返回 `200 application/json`，精确字节 SHA-256 为 `0x3b922f…a26e`，独立进程复核 receipt/task/link 与三态重放均有效。
  SQLite 已保存授权发布事件。
- Reviewer 专用测试钱包、0.1 Sepolia ETH、service `11155111:10691` owner 与两份 Registry 合约均已完成真实预检。首次交易
  `0xd8e556abeecdd5cee7b77865cdca5d145770a8dc135cbaee47dd8a03405d5f2d` 仅广播一次并确定性回执失败；诊断确认固定
  350,000 Gas 上限不足（实际消耗 345,000，同调用只读回放成功）。状态已落库为 `FAILED`，未自动重发。
- ERC-8004 adapter 已改为链上估算 Gas 后增加 20%（至少 50,000）缓冲并部署。用户再次明确授权后，系统从 `FAILED`
  恢复并仅广播 nonce 1：交易 `0xbf09156a706ca8a49b18606083cacd2f2d844684a0af60e65602c6167374dad9`
  已在区块 11860021 确认，feedback index 为 1，Gas 732,373 / 895,600。
- 独立进程已复核交易成功、数据库 `CONFIRMED`、Service ID、Reviewer、PASS 值、双标签、公共 URI、内容哈希、nonce、区块和
  feedback index 全部一致；公网重新下载哈希亦一致。生产应用健康，持久化 `M6_ENABLE_WRITES=false` 已恢复。

## M7 验收封装进展

- 新增无凭据演示入口 `scripts/run_mvp_demo.py`：真实执行离线 fixture 的服务 A `FAIL`、切换服务 B `PASS`、两个 attempt
  追加留档、两份回执独立重放及进程恢复；输出显式标记 `publication_mode=not-executed`，不冒充 M6 外部验收。
- README 与运维手册已补齐一条命令演示和完整质量门；CI 新增 Schema 漂移、1000 物理行限制及演示执行。
- 新增治理测试，机械校验根目录 Markdown metadata、`doc-id` 唯一性和本地链接；修正旧文档中已过期的 CI、Blockscout、
  Pinata fallback 与 M6 页面说明。
- 完整 `pytest` 在临时注入公开 Agent0/ERC 读参数并启动隔离 Blockscout MCP 后为 158 项通过、1 项跳过；唯一跳过项是
  非 MVP 必需且未配置的 OpenAI 探针。非 external 门为 151 项通过；Ruff、主/Blockscout 环境 `pip check`、12 份 Schema
  漂移检查、1000 行限制和无凭据演示均通过。
- 生产匿名页面与健康端点返回 `200`，无 Basic Auth header；公共回执返回 `200` 且 SHA-256 仍为 `0x3b922f…a26e`。
  应用容器 `healthy`，持久化 `M6_ENABLE_WRITES=false`。

## 待外部配置验证

- Pinata/IPFS 是优先 adapter，但当前缺少 `PINATA_JWT`；MVP 已按计划使用真实 HTTPS 公共文件 fallback 完成发布验收。

## 后续阶段外部配置待办

- 可选配置 `OPENAI_API_KEY` 与固定 `OPENAI_MODEL`；MVP 生产路径使用已实测 DeepSeek，不受此项阻塞。
- 可选配置 `PINATA_JWT` 以验证 IPFS pinning adapter；MVP 已使用真实 HTTPS 内容寻址公共发布完成验收。

## 已知问题

- Docker Desktop 4.79.0 当前无法启动，自动升级在管理员阶段失败。Blockscout MCP 本地 Python 运行方案已绕过该问题，Docker 不阻塞 MVP。
- ERC-8004 上游参考仓库存在 npm peer dependency 冲突，安装需 `--legacy-peer-deps`。
- 上游 npm 审计报告 35 个依赖漏洞；该仓库当前仅作参考和合约测试，没有执行自动修复。
- GitHub Actions 仅覆盖无需密钥的本地质量门；真实 external 探针仍需显式配置后单独执行。
- Pytest 当前有一条来自第三方 `websockets.legacy` 的弃用 warning；不影响测试结果，后续依赖升级时处理。
- 广州机房仍无法直接连接 Blockscout Pro API；加密 DNS 能得到正确地址，但目标 SNI/TLS 被重置。生产已通过受认证的
  Vercel 中继解决，RPC 仍是完整性权威源，Blockscout 继续只承担补充抽样。

## 下一步

按新授权补齐保留的技术验收；不依赖用户招募，也不自动恢复暂停的浏览器操作。专用最小锚只交付未部署候选；
真实部署、生产接入、公共上传验证与写链仍需额外审查、配置和明确授权。

## M8 开发分支进展

- 页面已重构为黑金 12px 卡片主题和“上传报表 → 确认范围 → 链上核验”主流程，结果优先展示服务声称、链上有效金额、
  精确差异、资金流与 Finding；RPC、签名、Registry 和原始 JSON 默认折叠。
- `FundFlowProjection` 从已有 submission、reference evidence 与 Finding 投影匹配、漏报、链上未找到、内部互转、重复和
  证据不足；每条边保留完整事件键、双方来源引用与 Finding ID，不反向计算 outcome。
- `TaskCommitment` 与 `DeliveryCommitment` 使用 EIP-712；服务接单和交付分别签名，篡改 task/service/attempt/report hash
  或错误签名者会被拒绝。三个 M8 Schema 已加入稳定导出。
- Sepolia 只读探针已真实读取 Validation Registry 的 bytecode、Identity Registry 关联与 service `11155111:10691` 请求列表。
  当前接口不适合作为 requester 通用任务锚，因此未广播交易，页面明确显示 `NOT_SUBMITTED`。
- 非 external 全量门为 158 项通过、9 项排除；M8 Sepolia 只读 external 探针单独 1 项通过。Ruff、pip check、15 份 Schema
  漂移、1000 行限制与无凭据 MVP 演示均通过。真实浏览器走通首次 FAIL 资金流，390×844 下无页面水平溢出。

## M8–M10 计划范围

### M8 补齐与视觉收敛

- 严格 UTF-8 JSON 上传现在是实际核验对象，不再仅作为提示词。原始字节内容寻址私有留档，原金额/count/事件声明不改写；
  本地 intake 签名明确不认证原作者。固定错误报表 FAIL、补交完整报表 PASS、第三次提交拒绝的路径已通过测试。
- 接单在交付生成前签名，绑定完整 task commitment digest、spec hash 和微秒时间戳。M8 SQLite artifacts 只追加保存承诺与
  reference evidence，重启恢复须验证签名、receipt manifest 并重放同一确定性结果；篡改证据拒绝恢复，缺少旧快照不伪造图。
- SVG 有向账户图与事件明细保留双方原始记录；字段不一致、范围错误不再误标成“链上未找到”。12 个冻结 fixture 的投影矩阵通过。
- `.streamlit/config.toml` 与页面 CSS 统一深色，移除说明文字原生 60% 透明度和大面积白底。正文/辅助/说明文字与三个背景
  对比度均超过 7:1；普通卡片/指标/折叠区不描边，状态装饰统一中性灰，强调靠结论层级、行动含义和独立金额分组。
- `CommitmentAnchor.sol` 候选与只读 `DedicatedAnchorReader` 已提供；Solidity 0.8.30 编译和 loopback 开发链 1337 模拟执行通过，
  覆盖 requester 命名空间防占位、服务授权、只追加两次交付与事件读回。没有真实部署、没有 Sepolia 写链，也未接入生产页面。
- 实际上传文件的浏览器路径已走通 FAIL → 补交 → PASS；进程重启后通过原 workspace ID 恢复两份签名、证据与图。
  真实 Sepolia Validation Registry 只读探针单独 1 项通过（进程内补充公开 Registry 地址与 agent ID，未修改 `.env`）。
- 专用锚候选不等于独立安全审查通过；真实委托方/外部服务作者认证、专用锚部署和外部写入验收仍未完成，不能称全量链上闭环。
- 根据用户后续视觉要求：添加本地静态区块/节点/链式连接背景、炭黑层次与轻微材质光影；金色集中在主操作，强调用字号、
  字重与独立分组。运行参数只保留折叠区，不再重复为三张气泡；流程序号只保留顶部一套。原 TR 占位与 favicon 已换为
  用户最新提供的透明 PNG Logo，原图无修改。390px 输入页实测无水平溢出、无大块白底；说明文字 opacity=1。
- 字号按用户要求收敛到 `12/14/16/20/24px` 五级角色 token，自定义 HTML 与原生组件共用；页面标题、结论和关键金额不再使用
  32px/约 29px。SVG 固定 720px 画布，窄屏局部滚动，避免容器缩放改变 12px 节点文字。
  `FRONTEND_SPEC.md` 清理字体、描边、状态配色、材质和旧 TR 占位的矛盾表述；纳入用户五张 H5 参考图的组件取舍。
  `TEST_PLAN.md` 增加实际计算字号与视觉回归规则，设计规范不复制瞬时进展。
- 本次浏览器输入页实测 `1440×1000` 与 `390×844`：可见文字计算字号均在五级集合内，无页面级水平溢出。
  本次未完成结果页、760px 两侧及 200% 放大的完整视觉复验，不把自动测试视作全部前端验收。
- 参考图已落实到 M8 页面：深灰双层输入/确认/执行面板、短金色标题底衬与结论光泽、桌面原 logo 材质展示、
  香槟金细斜纹、12 条金色曲线与暖金区块链几何；移动端隐藏纯装饰 logo。正文与状态不普遍染金，不增加卡片外框。
  1440px 桌面与 390px 手机输入页截图已检查；手机计算字号无越界，页面无水平溢出。
  Dockerfile 已补齐原生主题配置复制，避免生产镜像缺少深色控件主题。本次提交、推送、合并与部署仅针对 M8，不包含 M9/M10 分支。
- 最新非 external 门 207 项通过、9 项排除；Ruff、pip check、16 份 Schema、1000 行限制和无凭据演示通过。
  实际链上只有前述只读 Registry 探针；本地模拟合约交易不计作 Sepolia 外部写入验收。

- M8：资金流对账图、任务/接单/交付承诺和可下钻链上证据；技术详情默认折叠，每个状态只有一个主操作。
- M9：确认 Finding 生成返工包、修复前后并排对比、只追加回执版本链和独立公开验证入口。
- M10：按任务类型聚合可追溯的服务历史事实，并用于下一次人工选择服务；不生成永久综合评分。
- 黑客松阶段明确不建设多租户、复杂账号/RBAC、计费、开放市场、自动付款或主网资金控制。

## M8 发布与部署

- 2026-10-07：M8 代码提交 `484f941` 已推送；[PR #6](https://github.com/CH-ZHOU-0512/xinjv/pull/6)
  合并为 `821bbc228e68beccbd1c761e15cfc631b6225d37`，分支与主线 CI 均通过。未合并或修改 M9/M10 独立分支。
- 广州 `/opt/trust-receipt` 应用已切换为 `trust-receipt:m8-821bbc2`，镜像 revision label 与合并提交一致。
  仅重建应用容器；Blockscout、Nginx 与其他应用不重建。原 `.env`、数据与私有/公共回执挂载保持不变。
- 全量构建下载过慢且会重新选择依赖，已停止该构建容器。最终镜像使用已备份运行层、本次 M8 纯 Python wheel 和静态页面源码，
  离线强制安装 M8 包，并把 langchain-core/openai/types-requests 对齐到已测试锁定版本；未修改依赖锁文件。
  发布源码 tar 与 M8 wheel 的 SHA-256 已校验；镜像 `pip check`、M8 主题/模型 smoke、无网络 FAIL→PASS 与回执重放通过。
- 公网 [应用入口](https://creatoros.top/trust-receipt/) 与健康端点均为 200；WebSocket 握手通过。
  生产配置隔离启动通过，页面只提供真实 DeepSeek 与 Sepolia RPC。线上桌面与 390px 手机输入页截图已检查，
  手机可见文字计算字号均在五级集合内，无页面水平溢出。结果页、760px 两侧与 200% 放大仍未完成完整视觉复验。
- 回滚保留 `trust-receipt:m8-rollback-484f941` 镜像及
  `/opt/trust-receipt-backups/m8-before-484f941/source.tar.gz`；备份目录仅 root 可访问。
  本次没有真实链锚部署、写链或公开回执上传；网页部署不等于全量链上闭环完成。
## M10 服务历史实现进展

- 已新增独立 `trust_receipt.history` 读模型：按服务、显式任务类型与任务聚合首次 PASS、修复后 PASS、FAIL、
  INCONCLUSIVE、可验证回执数和最近交付；所有计数可由任务事实与来源回执重新计算。
- 只有通过现有独立回执重放的回执进入统计；篡改或未核验回执被排除。`INCONCLUSIVE` 单独展示，不增加失败数；修复成功任务
  不继续计为负面任务，但下钻保留修复前后的完整回执链。
- 已提供只读 `ReceiptRevisionPort` 适配 M9 父级/替代关系，并提供两服务同任务类型对比与显式人工选择 API；不生成排名、
  综合分或自动选择。
- 已集成 M8/M9 页面入口与运行时装配：当前工作区历史按需扫描，两服务无历史时明确显示暂无；可下钻原始回执与真实父版本，
  显式确认服务后带入下一次报表验收。版本链核验缺父、身份冲突或篡改时排除任务并提示 INCONCLUSIVE。
- 仅原始不可变 attempt 参与统计；M6 发布快照不重复计数，本地与公开哈希不混用。跨服务 A FAIL → B FIXED 成功只属于 B，
  A 的失败保留。测试覆盖空历史、缺父链、伪造关系、重复发布、换服务修复与中性证据不足。
- AppTest 走通 A FAIL → B PASS/FIXED → 来源下钻 → 选择 B → 下一任务继续选择 B；真实浏览器走通同样的两个 attempt、
  历史对比与人工确认。1440×1000 桌面和 390×844 手机截图已检查，手机页面无横向溢出；未完成 760px 两侧/200% 全矩阵。
- 加载优化：原图 Logo 改用可缓存同源静态 URL，避免每次重跑重复内嵌约 3.72MB base64；OpenAI/Agent0 SDK 按需加载。
  本地 runtime 导入由约 3.81 秒降至 2.12–2.49 秒；本地热刷新从单次约 1.80 秒到三次 1.39–1.43 秒。
  样本有限，不当作生产测速；冷启动与网络条件不同，生产优化尚未部署。
- 本轮全量 pytest 266 项通过、9 项 external 缺配置跳过，另有第三方弃用 warning；Ruff、pip check、21 份 Schema 漂移和
  1000 行检查通过。没有新增公开上传、真实密钥使用、写链、推送、主线合并或部署。

## M7 工作区收尾

- 已按用户明确授权删除 M7/M6 临时诊断文件、浏览器与测试缓存、代码图缓存以及本地 SSH PEM；`.env`、SQLite 数据、
  私有回执和已核验公共回执继续保留，未进入 Git。
- 已移除两个已合并或补丁等价的辅助 worktree，并删除对应本地功能分支；只保留 `main` 与当前交付分支。
- 收尾后重新执行非 external 测试：151 项通过、8 项排除；Ruff、两个 Python 环境 `pip check`、Schema 漂移检查、
  1000 行限制和无凭据演示均通过。
- 主线首次 CI 暴露未使用的 `langchain[mcp]` extra 与固定 `mcp==1.26.0` 的解析冲突；依赖声明已收窄为普通
  LangChain，并使用现有锁定快照约束 CI 解析，避免无界回溯。
- 修复提交对应的 GitHub Actions 主线 CI 已通过，依赖安装、非 external 测试、Ruff、`pip check`、Schema、
  文件规模检查和无凭据演示均为绿色。

## M9 修复与回执验证进展

- 新增确定性 `ReworkPackage`：仅把 `FAIL` 回执中 `confirmed + error` Finding 映射为闭合返工动作，
  不把 hypothesis 或证据不足改写为确定指令；返工包使用 canonical SHA-256 自哈希。
- 新增外置 `ReceiptRevision` 和只创建不覆盖的 `LocalRevisionStore`；两次 attempt 以 parent/supersedes 形成自哈希链，
  不修改 `Receipt 1.0` 或旧回执哈希。`RepairComparison` 保留 task/service/attempt/receipt hash/outcome/resolution、
  整数金额与证据引用，并复用既有 v1 交付哈希和 EVM 签名校验。
- 新增只读 `PublicReceiptResolver` / `ReceiptCommitmentVerifier` 稳定端口及独立 CLI，支持 URI、receipt hash、
  task hash 和 feedback transaction 入口；必要公开证据缺失返回 `INCONCLUSIVE`，冲突返回 `INVALID`。
  M8 承诺端口缺失时显式记为 `UNVERIFIED`，不伪造承诺已核验。
- 新增 M8→M9 适配层，直接复验持久化 Task/Delivery EIP-712 承诺、完整对象链接和期望 signer；有效快照标记为
  `VERIFIED`，缺失保持 `UNVERIFIED`，篡改或冲突标记为 `INVALID`。`NOT_SUBMITTED` 锚状态继续明确展示，不冒充链上确认。
- `app/streamlit_app.py` 已接入首次失败返工单、每次 attempt 的外置版本记录、第二次修复前后对比和公共 URI 独立重放入口；
  版本存储基于原始不可变 attempt 回执，避免后续 M6 publication 状态改变回执哈希时覆盖历史。
  公共 attempt 2 缺少公开 parent revision 时按契约返回 `INCONCLUSIVE`，不会借用私有 SQLite 补证。
- 新增显式授权的 `PublicVerificationBundle`，同时携带公开父/子回执与对应外置版本链；公开哈希与本地不可变
  attempt 哈希分开重建，不混用两套历史。导出可在另一进程和空私有会话中独立验证；重复发布从追加元数据恢复，
  上传后必须下载原始字节核对哈希。未授权不能导出或上传，首轮 FAIL 不会被修复成功掩盖。
- 独立 `?verify=1` 页面不初始化 AI 或私有工作区；支持公开文件、配置范围内 HTTPS/IPFS、回执/任务哈希和真实
  feedback 交易。真实 feedback 只读校验链、Registry、确认数、canonical 区块、交易 sender、事件字段和公开内容哈希；
  调用者自报交易字符串不能作为链上证据，缺少公开父回执仍为 `INCONCLUSIVE`。
- 浏览器实际走通 fixture 服务 A 首轮 FAIL → 服务 B 第二轮 PASS → FIXED 对比 → 授权导出 → 新独立页面验证
  PASS/FIXED；两个 attempt 和不同服务身份保留。主流程与独立结果页在 390×844 均无页面横向溢出，抽查可见字号
  在 `12/14/16/20/24px` 集合内。本轮未完成 760px 两侧及 200% 放大的完整视觉矩阵。
- 已匿名下载并重放既有公开 M6 回执；已真实只读核验既有 Sepolia feedback 交易
  `0xbf09156a706ca8a49b18606083cacd2f2d844684a0af60e65602c6167374dad9`。事件、公开授权、字节哈希和回执重放通过；
  旧 attempt 2 缺少公开父链，所以总体为 `INCONCLUSIVE`，M8 承诺仍为 `UNVERIFIED`。没有新增公开上传或写链。
- 五份 M9 追加契约纳入稳定导出，总计 21 份 Schema。全量本地测试为 251 项通过、9 项 external 因当前环境配置
  缺失而明确跳过；公开历史和反馈冲突、缺父链、非规范 JSON、独立进程等边界均覆盖。M9 下一步为交给现有 M10
  分支集成服务历史与人工选择，不把 M10 能力标为已经完成。
- 收尾 Ruff、`pip check`、21 份 Schema 漂移、1000 物理行限制与无凭据 FAIL→PASS→恢复演示均通过。

## M11–M14 并行启动

- 用户已授权各工作包独立开发，并进一步授权 M9–M14 自动跨会话沟通，由当前会话主控。最终交付仍须集成验收，不能以分支完成替代。
- 共同计划基线使用 `codex/m11-m14-planning`；A `codex/m11-real-case`，B `codex/m12-user-experience`，
  C `codex/m13-demo-verification`，D `codex/m14-user-trial-prep`。各线使用隔离工作区，不修改他人分支；M12 可本地合入已提交 M10/M9/M11。
- A 拥有案例与预检脚本，B 拥有页面与前端测试，C 拥有路演检查与端到端测试，D 拥有用户就绪验收材料。
  根目录权威文档与公共 wiring 由当前集成会话统一维护，各线提交专属交接材料供同步。
- 初始开发授权不包含公开发布、写链或部署；最终交付没有真实用户及真实测试用户，取消招募依赖。
  四个会话均已发送纠正任务，D 改为自助说明、验收矩阵与证据模板；历史分支/目录名保留，不代表真实试用。
  六个会话已接收恢复协调并回复主控；该历史快照中的 Skill/MCP 当时仍为 M15/M16 候选，后续已获准分别启动。
- 四个会话与隔离工作区已创建并下发实施任务；各线从计划基线 `f66b5ad` 开始，尚不代表实现完成。

| 工作包 | 会话 ID | 隔离工作区（C:/Users/Gzhou/.codex/worktrees/ 下） | 交接材料 |
|---|---|---|---|
| A / M11 | `01a1152f-1458-7be0-8b8e-118d6d65a267` | `m11-real-case/HACKTHON` | `docs/handoffs/m11.md` |
| B / M12 | `01a1152f-1b59-7463-b967-58a294bafb1c` | `m12-user-experience/HACKTHON` | `docs/handoffs/m12.md` |
| C / M13 | `01a1152f-2336-7f21-b642-f4268353aebe` | `m13-demo-verification/HACKTHON` | `docs/handoffs/m13.md` |
| D / M14 | `01a1152f-2e06-7a02-8058-c27324c81425` | `m14-user-trial-prep/HACKTHON` | `docs/handoffs/m14.md` |

### M9–M14 恢复协调快照（2026-10-07）

- M9 `30c13c3` 与 M10 `654b2e0` 已本地交付；专属接口交接分别提交 `8f07a13` 与 `e747493`，主控已核实为仅新增 handoff。
  M10 已含 M9，未合并 main 或部署；分支报告的专项验证不代表本轮主控重跑。
- M11 第二组永久独立输入已提交 `4e19c36`，范围/账户/金额不同于固定案例；实时只读结果及交接已发送给消费者。
- M12 已提交干净本地合流基线 `a739551`，包含 M9/M10、M11 两组输入及页面接线；主控已将精确 SHA 发给 M13/M14。
  分支报告非 external 294 通过、13 排除及 M11 RPC 外部 4 通过；不是主控重跑记录，图投影已知问题仍待修复。
- M13 已提交 `377a243`，恢复新的隔离本地自动化，等待 M12 精确合流提交以执行三轮排练；不触碰用户手动标签页。
- M14 `9473928` 已交付验收材料，恢复可执行矩阵实现；正式 14 项就绪验收尚未通过。
- 主控保留 M9 公开历史包的 ADR-023，将计划与无用户验收决定分别重编号 ADR-024/025，避免本地合流重复编号。
- 六条线仍不能宣称整体完成；最终缺口为真实页面联调、三轮排练、完整就绪矩阵及修复复测。
- M12 实时页面联调发现投影范围缺陷：同区块六条 RPC 原始事件中仅一条符合任务，但图把另外五条范围外事件误标为漏报。
  金额与确定性结论未见受影响。M10 最小修复已提交 `f09b57c`（仅核心投影与专属范围测试），分支复现边数 6→1、金额及 outcome 不变。
  分支报告新增测试与既有 fixture 矩阵共 26 通过；主控核实提交范围并交 M12/M13/M14 消费，最终浏览器图语义仍须重验。
  主控另在 M10 隔离工作区实际执行 `pytest tests/m10/test_projection_scope.py tests/m8/test_fund_flow.py -q`，26 通过、1 条第三方弃用 warning。
- M13 合入整条 M10 遇权威文档冲突，已报告将退出该试合并；改等 M12 干净合流提交，后续只消费最小修复，避免循环合并。
- M12 页面增量 `9f1cd85` 修正不同币种/精度无法比较时的差额展示；分支报告真实模型/RPC 浏览器 FAIL→PASS 与双结果响应式检查通过。
- M14 已消费 `a739551` 等依赖，在隔离 8534 执行可执行矩阵；runner 初次输出解析错误已修复，旧失败保留，完整 14 项仍待实测结论。
- M13/M14 已确认消费 `9f1cd85` 与 `f09b57c`；隔离进程分别在 8533/8534 继续浏览器验证，已重启排除热加载旧 import 缓存。
  M14 报告未确认拒绝、作者未认证说明及首屏五视口证据；三轮排练与完整矩阵仍不能记为通过。
- 主控实际读取 `m14-live-04/matrix.json`：UR02/03/05/06/10/11 共六项 PASS，UR04 FAIL，其余七项 BLOCKED，`ready=false`。
  UR02 为第二组自备报表真实 RPC 金额 `321794352786`；UR05 覆盖八类非法上传后合法恢复。UR04 执行器工作区重设修复等待重跑，
  不把定位到脚本原因当作恢复验收通过；结果页、完整键盘、重启及冲突证据仍须补齐。
- M13 转达并在其会话记录确认用户最新要求停止自动操作并收尾；主控已通知 M12/M13/M14 不再追加浏览器/故障注入验证，
  仅保存现有工作和整理交接。M13 报告最新全量测试 313 通过，准确命令及排除项待最终 handoff 核实，不计作主控实跑。
  三轮连续浏览器排练和完整 M14 矩阵尚未确认通过；开发验证可收口，不宣称 M9–M14 全体验收完成，也不要求真实测试用户。
- M13 最终 HEAD `338ff37`，唯一未提交文件为 `scripts/m13/rehearse_browser.py`，主控只读核实并保留；专属交接文档仍含旧阶段说明，
  不能替代本次最终轮次证据。分支报告非 external 313 通过、14 排除、1 条第三方 warning，但原始完整命令未保留，主控不补造。
- M13 先前排练记录为 86.031 秒 PASS / 54.813 秒 FAILED / 84.578 秒 PASS，未形成连续三轮；新排练前两轮报告为
  75.438 秒与 74.906 秒 PASS，第三轮因用户停止而中断，未生成完整 results，不能记为三轮完成。原始文件留在该隔离工作区 `.tmp/`。
  独立页面读取的是此前公开回执，不是当轮新任务回执；当轮未公开发布，测试 bundle 的模拟授权不等于真实公开上传。
- M14 最终交接提交 `8669ed9`，主控只读核实工作树干净；最新 `m14-live-06/matrix.json` 为八项 PASS
  （UR02/03/05/06/10/11/13/14）、六项 BLOCKED（UR01/04/07/08/09/12），`ready=false`。
  已有独立真实报表、冷上下文、八类非法上传恢复、确认拒绝、身份、写隔离、键盘和说明路径证据；未验收的重启、
  浏览器故障/来源冲突、第三 attempt 拒绝及原生 200% 缩放等仍保留。新摘要在该分支 `docs/user-trials/readiness-evidence-2026-10-07.md`。
  故障进程已由 M14 关闭，正常 8534 保留只供手动查看；不再自动操作。未做真实用户测试，完整 M14 技术验收未齐。

## M15–M16 并行启动（2026-10-07）

- 2026-10-08 原件并发落盘修复（本地完成，待主控集成）：PR24 CI 暴露 M16 两个已批准 challenge 同原件留档时，
  `xb` 先创建哈希目标、后写入，另一写入者读取半成品而误报损坏。暂停半写的最小测试已先稳定失败。
  `services.upload.retain_original` 改为同目录私有临时文件完整写入/flush/fsync/close 后硬链接原子创建目标；
  已有目标仍逐字节核对，不覆盖损坏，不支持硬链接明确失败，仅清理本次 owned temp。
  新原件专项 9 项，M16/attempt/治理组合 37 passed；原 MCP 并发测试 20 个独立 pytest 轮次全部通过。
  包含最新报告与 M16 的非 external 全量 629 passed / 16 deselected / 1 条既有 warning（117.60 秒）；
  Ruff、pip check、21 Schema、文件规模与 diff 门通过。Windows NTFS 实测线程与 spawn 进程并发；
  Linux 既有本地镜像无 pytest，改用 stdlib 无网络只读挂载探针，暂停半写独立进程、20×8 线程、0600、
  损坏拒绝及不支持硬链接清理通过，不将该挂载探针计为镜像源码/wheel一致性或生产验收。
  本轮未推送/合并/部署，未触碰线上数据、真实模型/RPC、公开上传、写链或浏览器；生产仍不包含该修复。

- 2026-10-08：用户授权推送并合并 M16。已合流 GitHub API 核实的主线 `867ca617c02b493cd9b919133f1187669934d8e0`，
  保留现有报表导出与部署记录；服务显示名为 TreasuryTally，8 项工具名称和技术包标识保持兼容。
  合流后 M16、attempt 状态与文档治理专项 28 passed；Ruff、pip check、21 Schema、文件规模与 diff 门通过。
  合流版本完整非 external 实跑 620 passed / 16 deselected / 1 条既有 warning（94.89 秒）。
  Git HTTPS fetch/push 连接重置，发布改用 GitHub API；PR 合并结果以实际完成记录为准。

- 用户已授权 M15 Skill 与 M16 MCP 在独立会话、分支和工作区实施；两者不改变 M13/M14 尚未齐备的技术验收，也不要求真人测试。
- M16 已在 `codex/m16-mcp` 从修复基线 `e2a0a9e` 启动，冻结供 M15 消费的 `HeadlessTrustReceiptPort 1.0`：候选、外置授权后确认、
  报表核验、结果/回执读取与重放。MCP 只使用本机 stdio，不提供发布、写链、任意路径、代码或 SQL。
- M16 冻结提交为 `cee234d`。headless facade、operator workspace registry、15 分钟一次性外置批准、持久幂等消费、CLI、
  MCP stdio adapter、客户端配置示例和运行文档已实现；入口只复用现有候选、M5 workflow、UploadedReport、SQLite attempt 与回执重放。
- M16 已本地消费 attempt 状态修复 `795dddd`（本分支 `7554e9a`），不改 `app/`。准备/消费 challenge 都读取持久化状态，
  in-flight、缺失/冲突回执明确阻塞，并发 challenge 只有一个可取得原子 attempt 预留；不自动解锁或重跑。
- M16 15 项与来源修复 11 项合计 26 项专项测试通过，包括真实 stdio initialize/tools/list/tools/call、服务重启、重复调用、
  并发 request、两次 attempt 上限、跨工作区、路径/SQL/秘密注入、缺模型/RPC 和缺回执阻塞。全仓非 external 为
  352 passed / 14 deselected；Ruff、主环境 pip check、21 份 Schema、1000 行限制与 diff check 通过；无凭据演示 valid=true。
  使用的是明确 fixture 测试 profile；未读取真实线上故障状态，也未执行真实模型/RPC、公开上传、写链、推送、合并或部署，
  不宣称线上同一原因已修，不补记 M13/M14 未齐验收。

## 业务报告资金流图补充

- 在独立 reporting 工作树加入本地固定 Apache ECharts 6.0.0 组件、数据配置接口与自包含图组件；
  账户节点和转账箭头保留已保存的精确金额、来源及事件引用，不重新计算结论。默认 12 条分页预览明确标注，完整 200 条可逐页访问。
- reporting 与图接口测试 37 项通过，限定文件 Ruff 通过；五种离线视图各在 390/1440px 完成 SVG SSR 生成检查。
  此项不是人工视觉验收；独立组件交接时尚未接入页面，本地接线现况见首项，也没有生产部署。
- 用户已要求暂停浏览器自动操作，由其手动验证。实际手机可读性、交互与页面接线仍待验；
  浏览器手动验收和页面导出接线仍待联合集成，本分支不能标记全量上线。

- 本地固定 ECharts SSR → sharp 图已进入真实 DOCX/PDF/HTML 导出；未使用 Canva 或 Python 绘图兜底。
  7 类离线样例覆盖 FAIL、PASS、INCONCLUSIVE、补交历史、极大整数、255 位精度与 200 条微小金额；
  Word 40 页、PDF 46 页共 86 页按原始 PNG 逐页检查完成。修正单笔节点拉伸和末页账户索引断组；
  最终重渲染只改变 2 页，其余页面 SHA-256 与已检查页面一致。完整事件引用、金额、原回执和补交历史的格式一致性检查通过。
- loader bundled Python/Node 与独立 Linux Python 3.12.14 / Node 22.23.3 / sharp 0.34.5 均实际完成 7 类四格式生成与校验；
  Linux runtime 使用 network none/read-only root、单独输出目录及 CPU/内存/pids 上限，pip check 通过。
  reporting 专项 49 通过、schema 三组 38 通过；未执行外部 RPC/真实密钥/写链/公开上传，未恢复浏览器自动操作。
  独立 reporting 工作树实际执行 pytest -m 'not external' -q：416 通过、14 排除、1 条第三方弃用 warning；
  全目录 Ruff、1000 物理行与 diff 检查通过，wheel 含字体/许可证/固定 worker/npm lock/ECharts，未打入 node_modules 或测试产物。
  依赖与 renderer 只在独立工作树；主环境锁和生产镜像接线仍由主控/M14 规范生成并联合验证，未部署。

- 2026-10-08 修正 M12 指出的竖向箭头悬空：固定 ECharts 6.0.0 presentation adapter 按实际卡片边界裁剪连线，
  SSR 与网页组件共用；缩放、平移及 resize 后重新贴边。未修改上游 bundle、金额、事件身份或核验结论。
  下排跨列金额标签移到线下，避免长金额遮挡内部互转状态/单位。
  bundled Node 与独立 Linux Node 22.23.3 各实际通过 20 组直线/曲线/反向/resize/zoom/pan 几何检查；
  两套 runtime 的 7 类四格式生成与格式一致性重验通过。
  新版 Word/PDF 重新渲染共 86 页，14 个改变的图表页已分别按原始分辨率重查；其余 72 页 SHA-256 与此前已逐页检查的页面相同。
  此处不是把旧 86 页检查计作本轮新增检查。极大金额与 255 位精度的标签不重叠，完整金额仍保留在明细。
  本分支非 external 全量 pytest 实跑 417 通过、14 排除、1 条既有第三方 warning；全目录 Ruff、文件规模与 diff 检查通过。
  最新修正待 M12/M14 消费和联合集成验收；未部署、未恢复浏览器自动操作，旧 wheel 检查不等同本轮新 wheel 检查。

## 状态更新规则

- 这里只记录当前事实、下一步和实际阻塞。
- 完成某阶段时更新本文件，不在多个设计文档重复维护进度。
- 每项“已完成”必须能对应文件、命令输出、测试记录或外部交易。
