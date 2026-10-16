---
doc-id: operations-runbook
title: 本地开发与运行手册
status: active
authority-for:
  - local-setup
  - run-commands
  - troubleshooting
last-reviewed: 2026-10-07
---

# 本地开发与运行手册

## 当前安全修复镜像的精确回滚

此运行手册仅适用于已切换的 `trust-receipt:safe-ai-c474a08`，不要用旧scope回滚命令替代。
前一版本e2cf/d897保留为 `trust-receipt:safe-ai-rollback-c474a08`，备份目录root700、文件600，
不含.env、SQLite或用户回执。故障恢复前只读核实该tag实际image为
`sha256:e2cf19fe284eef425f37e0691f2fdaa0b0bb4eea1f5e58384e4939ed36eb4d10`。

```bash
docker compose --project-directory /opt/trust-receipt/deploy -p deploy \
  -f /opt/trust-receipt-backups/safe-ai-before-c474a08/compose-before.yml \
  -f /opt/trust-receipt-backups/safe-ai-before-c474a08/rollback-image.yml \
  up -d --no-deps --no-build app
docker exec campus-creator-nginx nginx -t
docker exec campus-creator-nginx nginx -s reload
```

随后核实app healthy/OOMKilled=false、原3绝对RW挂载、env哈希、保护服务ID/StartedAt与HTTPS健康端点。
回滚只换应用，不清理数据、不重建代理或Blockscout、不重新执行模型/验收/公开发布或写链；本次没有执行此回滚。

## 业务报告与本地导出运行边界

报告调用 `build_business_report(receipt, submission, fund_flow=..., previous=..., revisions=...)`，页面的原 JSON 回执下载不变。
`export_html`、`export_docx`、`export_pdf` 与 `graph_png` 返回 bytes，不执行上传、写链或任意路径写入。
报告仅使用已记录证据，不为导出重取 RPC 或调用 AI。冷恢复使用默认 recorded 模式，实时核验只有确认实际来源后才标 live_rpc。

DOCX 使用 python-docx 1.2.0，PDF 使用 reportlab 4.4.9，PNG 使用 Node 22.23.3 / sharp 0.34.5 的 ECharts SVG 栅格结果；
Pillow 12.3.0 只校验 PNG。独立 package.json/package-lock.json 位于 `src/trust_receipt/reporting/assets/renderer/`，用 npm ci 安装。
组合层复用 `EChartsRenderer(node_path=..., modules_path=...)`，所有导出显式传 `renderer=renderer`。
底层 node_path 省略时从受信 PATH 查找 node；部署页面必须显式使用进程配置，不走 PATH 回退。
`REPORT_RENDERER_NODE` 固定 `/opt/trust-receipt-renderer/renderer-node`，
`REPORT_RENDERER_MODULES` 固定 `/opt/trust-receipt-renderer/node_modules`；仅运维受信环境可配置，不接受用户路径或 JS。
Docker 使用 pinned Node 22.23.3 / Python 3.12 镜像与 renderer lock 的 `npm ci --ignore-scripts`，保留 optional native 包及许可证。
Fontconfig 注册包内字体；renderer-node 只允许固定参数和包内脚本，Linux seccomp 拒绝 socket 创建/连接等操作，
不影响父应用的模型/RPC socket 能力。未知 ABI、seccomp 不可用或资源不足拒绝导出。
生产 compose 设置总内存及 memswap 均为 640 MiB（无额外 swap）、128 pids、1 CPU、drop ALL capabilities 和 no-new-privileges；
这约束应用与 renderer 的 native 总资源，不把 JS 堆 128 MB 称为独立 native 内存上限。
单应用必须复用一个 renderer 实例；`export_slot()` 非阻塞完整导出预算为 1，Node 并发独立为 1，20 秒 timeout。
DOCX 字体嵌入、PDF 排版、HTML 构建和 ZIP 打包结束前不释放完整预算，同线程嵌套可重入，竞争线程立即明确繁忙。
原 JSON 下载独立于该预算；串行通过不代表低内存主机已适配，切换前仍需 SDK 预热、多会话与最坏规模实测。
启动器另设 20 秒 CPU、64 fd、8 MB file-size 和禁 core dump。
页面使用总 16 MiB / 单文件 8 MiB 的全应用私有衍生缓存，最多当前视图五格式；
换视图或工作区清自己的衍生缓存和准确媒体引用，不清原 JSON 与历史。
去重媒体使用 canonical bytes，其他控件尚未释放的引用仍占预算；超限或不兼容明确导出不可用。
该候选缓存预算须与最终 source/wheel/image 的真实 SDK 预热、多会话及最坏规模测试共同验收，不是 native 硬限。
低内存部署预检须在旧 app 仍可用时独立运行；实时可用内存至少为测试硬限加 256 MiB 保护余量。
只使用无网络、无生产 env/用户数据、只读且有超时/kill 边界的测试容器；先验证再仅切换 app。
`check_report_runtime.py` 默认严格核对 640 MiB、swap=0、128 pids；诊断其他资源配置必须显式传期望参数，不能读取实际值冒充校验。
压力门还要求 memory.events 的 max/oom/oom_kill 为 0，并记录 peak/current 与 anon/file/kernel，触限回收不冒充有余量。
全量镜像以主环境生成的 requirements.lock.txt 为 constraints；app-only release 必须基于已验证的新 renderer runtime，
旧不含 Node/字体/报告依赖的基底会拒绝构建，不会假称 app-only wheel 更新已补齐运行环境。
部署方加无网络、native 总内存/pids 限额；缺失依赖、失败或繁忙明确 EXPORT_UNAVAILABLE。Python 正式安装以规范生成的主环境锁为准，
不能因为本地 adapter 能调用就声称生产依赖已经就绪。生产 Linux 不依赖 Word/LibreOffice；中文字体随 wheel 打包并保留 OFL 许可证，
PDF 嵌入子集，DOCX 内嵌字体。资源缺失必须显示导出不可用，不生成假后缀；原 JSON 下载不受渲染器影响。
带图 HTML 也需要 ECharts worker，不能声称 Node 缺失仍可导出完整 HTML。
Linux 还需 Fontconfig：将打包的 ReportSans-Regular.ttf 安装到镜像字体目录并执行 fc-cache；
worker 用固定 fc-match 探针核对 TreasuryTally Report Sans，字体缺失拒绝导出。原生 npm 包保留 README/package.json
许可声明与 sharp LICENSE；@img/sharp-libvips-linux-x64 1.2.4 声明 LGPL-3.0-or-later，不能只保留 sharp 的 Apache 许可证。
图超过 200 条保存记录明确不可用，不能把局部图称为完整图；文档边界检查的 400 条只用于拒绝资源超限，非绘图能力承诺。

作者与 QA artifact 使用 loader-selected bundled Python；Windows bundle 不含 LibreOffice，不能调用会回退桌面 soffice 的渲染路径。
专属 QA Dockerfile 位于 `tests/reporting/qa/Dockerfile`，只用于离线测试报告。构建可拉取字体/工具依赖，实际渲染必须 `--network none`，
不挂 .env、密钥、data 或私有回执；使用单独可写输出目录、CPU/内存/pids 上限与 timeout，逐页检查生成 PNG。
可复用经过核实的本地 Debian 工具基础镜像，但必须记录来源与独立 QA 工具版本，不当作 loader bundled renderer。

## 已准备环境

- 主 Python 3.12 虚拟环境：`D:\HACKTHON\.venv`
- Blockscout MCP 隔离环境：`D:\HACKTHON\.venv-blockscout`
- Node.js/npm：供 ERC-8004 参考合约测试使用
- 上游参考仓库：`D:\HACKTHON\references`

Docker Desktop 当前不可用，但不阻塞开发，因为 Blockscout MCP 已安装到隔离 Python 环境。

## 首次配置

```powershell
cd D:\HACKTHON
Copy-Item .env.example .env
notepad .env
```

需要按开发阶段填写：

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=
AI_TIMEOUT_SECONDS=30
AI_MAX_RETRIES=2
BLOCKSCOUT_PRO_API_KEY=
BLOCKSCOUT_MCP_URL=http://127.0.0.1:8000
ETH_RPC_URL=
CHAIN_ID=11155111
RPC_TIMEOUT_SECONDS=30
RPC_CONFIRMATIONS=2
TEST_TOKEN_ADDRESS=
TEST_TRANSFER_TX_HASH=
TEST_FROM_BLOCK=
TEST_TO_BLOCK=
ERC8004_IDENTITY_REGISTRY_ADDRESS=
ERC8004_REPUTATION_REGISTRY_ADDRESS=
ERC8004_VALIDATION_REGISTRY_ADDRESS=
AGENT0_SERVICE_ID=
AGENT0_EXPECTED_OWNER=
ERC8004_FEEDBACK_TX_HASH=
ERC8004_REVIEWER_ADDRESS=
ERC8004_FEEDBACK_INDEX=
M0_ENABLE_WRITES=false
SERVICE_A_PRIVATE_KEY=
SERVICE_B_PRIVATE_KEY=
REVIEWER_PRIVATE_KEY=
PINATA_JWT=
PINATA_API_URL=https://uploads.pinata.cloud/v3/files
PINATA_GATEWAY_URL=https://gateway.pinata.cloud/ipfs
PUBLIC_RECEIPT_DIRECTORY=
PUBLIC_RECEIPT_BASE_URL=
M6_ENABLE_WRITES=false
DATABASE_URL=sqlite:///data/trust_receipt.db
```

“整理核对范围”的候选请求使用独立 20 秒等待预算、单次调用（SDK retry=0）和 2048 输出 token 上限，
不受 `AI_MAX_RETRIES` 的两次重试延长；`AI_TIMEOUT_SECONDS` 更短时仍采用更短的底层请求超时。
该预算包含候选调用/校验，不是供应商可靠性保证或操作系统硬实时保证；SDK 初始化、线程调度及连接收尾存在开销。
超时取消本地异步等待并关闭本次连接，不启动后台同步请求、不接纳迟到输出；已被供应商接收的请求是否终止/计费未知。
超时、连接失败、限流、供应商失败和结构校验失败分别分类，不能把网络错误称为模型输出被拒绝。
用户可显式重试或手动填写范围，仍须严格校验和确认；失败不创建任务、不消耗 attempt、不触发链上操作。
其他 AI 步骤与表头识别预算不变；不新增凭据或环境变量。

候选超时修复使用独立部署目录 `/opt/trust-receipt-releases/scope-49c5092/source`，
镜像 `trust-receipt:scope-49c5092` 的实际 revision 为 `49c5092cd4e31b838e5c5c80f65a937d0f40052c`。
不能以仓库最新 main 直接覆盖此发布范围。回滚到修复前已部署镜像时，仅执行 app：

```bash
docker compose --project-directory /opt/trust-receipt/deploy -p deploy \
  -f /opt/trust-receipt-backups/scope-before-49c5092/compose-before.yml \
  -f /opt/trust-receipt-backups/scope-before-49c5092/rollback-image.yml \
  up -d --no-deps --no-build app
docker exec campus-creator-nginx nginx -t
docker exec campus-creator-nginx nginx -s reload
```

回滚后确认健康、HTTPS 页面/Logo/WebSocket、原 env/挂载/开发源码和受保护服务一致；不调用模型或链上业务。
`trust-receipt:scope-rollback-49c5092` 固定旧镜像；源码备份不含 env、用户数据或回执，不用它覆盖运行数据。

范围模板与历史证据原因发布采用独立 `/opt/trust-receipt-releases/preset-history-d897b5c/source`。
其 revision 为 `d897b5c8ab67336f7f1aba2db7e1fcff56be748c`，不使用含 M16 的 latest main 替代。
该发布的 app-only 回滚目标是保留的 `trust-receipt:preset-rollback-d897b5c`（旧 scope-49 镜像），
与上面 scope-49 本身的回滚目标不同。回滚前核对保护备份及精确镜像，执行：

```bash
docker compose --project-directory /opt/trust-receipt/deploy -p deploy \
  -f /opt/trust-receipt-backups/preset-before-d897b5c/compose-before.yml \
  -f /opt/trust-receipt-backups/preset-before-d897b5c/rollback-image.yml \
  up -d --no-deps --no-build app
docker exec campus-creator-nginx nginx -t
docker exec campus-creator-nginx nginx -s reload
```

此备份的 `source-before.tar.gz` 不含 env、用户数据或回执。不得用回滚源码覆盖持久化目录；
不重建 Blockscout/代理，不以握手或首页 200 代替真实报表流程验收。部署、预检与真实案例的实际状态仅在 STATUS 记录。

所有私钥必须是测试网专用密钥。

`AGENT0_SERVICE_ID` 必须指向团队控制的演示身份，`AGENT0_EXPECTED_OWNER` 用于在探针中强制核对所有者。
已有确认反馈可通过 `ERC8004_FEEDBACK_TX_HASH`、`ERC8004_REVIEWER_ADDRESS` 和
`ERC8004_FEEDBACK_INDEX` 做只读重放，无需再次广播。
ERC-8004 写探针默认关闭；只有完成地址、身份、余额和测试钱包核对后，才临时设置
`M0_ENABLE_WRITES=true`。该探针只提交值为 0、带有 `trust-receipt-m0` 标签的中性测试反馈。

公开合约地址和测试代币地址需与 [INTEGRATIONS.md](INTEGRATIONS.md) 的已核实记录一致；不要从未知来源复制地址。
OpenAI 或 DeepSeek 真实 M4 探针分别要求对应 API key 与固定模型名；只跑离线测试时可以留空。`PINATA_JWT` 留空时
Pinata/IPFS adapter 不可用，但配置完整的 HTTPS 内容寻址 fallback 仍可执行真实公共发布。

M6 缺少 `PINATA_JWT` 且未配置 HTTPS fallback 时，页面明确阻塞公共上传；本地测试仍使用隔离目录 adapter 完整验证脱敏、
上传后哈希核验与新进程重放。
只有核对 Sepolia chain ID、受控 service owner、Reviewer 地址、余额和 pending nonce 后，才可临时设置
`M6_ENABLE_WRITES=true`；页面仍要求二次显式授权。`SUBMITTED` 或广播结果未知时只执行链上读回，不重新点击提交。

生产缺少 Pinata 时可配置内容寻址 HTTPS fallback：应用将 `PUBLIC_RECEIPT_DIRECTORY=/app/receipts/public` 与
`PUBLIC_RECEIPT_BASE_URL=https://creatoros.top/trust-receipt/public` 配对使用。Compose 把宿主机 `receipts/public/` 以可写方式
挂入应用；反向代理必须把同一宿主机目录只读挂到 `/srv/trust-receipt-public`，并使用 `deploy/nginx-location.conf` 的静态规则。
该路径只允许 GET/HEAD、关闭目录列表并固定 JSON 安全头。创建目录时沿用 `receipts/private/` 的容器用户属主，不得使用
world-writable 权限。

## 激活主环境

```powershell
cd D:\HACKTHON
.\.venv\Scripts\Activate.ps1
python -m pip check
```

如 PowerShell 执行策略阻止激活，可直接使用：

```powershell
D:\HACKTHON\.venv\Scripts\python.exe -m pytest
```

## 启动 Blockscout MCP

```powershell
$env:BLOCKSCOUT_PRO_API_KEY="填入密钥"
New-Item -ItemType Directory -Force .tmp | Out-Null
Push-Location .tmp
D:\HACKTHON\.venv-blockscout\Scripts\python.exe `
  -m blockscout_mcp_server `
  --http `
  --http-host 127.0.0.1 `
  --http-port 8000
```

服务停止后执行 `Pop-Location`。必须从 `.tmp/` 启动，避免 Blockscout 自身的设置模型误读项目根目录 `.env`
中的其他配置。该环境与主应用环境必须保持分离。CLI 启动时可能出现来自 `pydantic_settings`
的非致命 warning；只有服务无法监听或工具调用失败才视为启动失败。

## 启动应用

```powershell
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py
```

默认本地数据写入 `data/`，私有回执写入 `receipts/private/`，两者均不提交版本库。

## 启动 M16 本机 MCP

M16 不启动公网 HTTP。先复制 `docs/m16/mcp-workspaces.example.json` 为 Git 忽略的本机配置，替换随机 workspace handle 与
私有目录，再按 `docs/m16/codex-mcp.example.json` 配置客户端。启动命令、外置批准流程和工具清单见
`docs/m16/README.md`。默认 live profile 从项目 `.env` 读取固定模型和 `ETH_RPC_URL`；缺配置返回 `BLOCKED`，不会改用 fixture。

MCP 客户端准备确认或核验后，必须由用户在独立终端运行 `python -m trust_receipt.headless.cli ... approve` 并输入完整动态短语。
不得把 approval CLI 注册成 MCP tool，也不得为自动化方便增加 `--yes`。服务重启后可安全重试已消费 challenge；第三次 attempt
仍由 repository 拒绝。当前不部署、不反代、不开放端口。

### Linux 容器部署

首屏品牌与 CSS 通过 `st.html` 渲染，Logo eager 请求原生媒体管道生成的 288px PNG 预览，两个位置共用内容寻址资源；不重绘或替换原始品牌 PNG。媒体 URL 保留反向代理的 baseUrlPath 前缀，原始静态 URL 作为无媒体运行时的回退。
部署检查须分别核实标题、CSS、Logo 的实际可见性和加载过程，不把灰色占位或最终截图当作首屏速度证据。

部署不要求真实用户参与；仍须记录版本、质量门与未完成的技术验收。部署授权不自动授权公开回执上传、写链或恢复已暂停的浏览器排练。

若依赖声明与锁定快照完全未变，可复用已验证运行镜像作为基底，以本地构建的纯 Python wheel 执行
`pip install --no-index --no-deps --force-reinstall`，再复制同一提交的 `src/`、`app/`、`fixtures/` 与 `.streamlit/`。
永久配置使用 `deploy/Dockerfile.release`，构建上下文包含源码归档和同源 wheel。页面入口优先导入 `/app/src`，
只更新 wheel 会被旧基镜像源码遮蔽；禁止省略源码同步，也不能通过 PYTHONPATH 绕过验收。
使用 `git archive` 打包已提交源码，传输后校验源码和 wheel 的 SHA-256；镜像必须写入完整
`org.opencontainers.image.revision`，并执行镜像内 `pip check` 和无网络演示。依赖发生变化时不得沿用此快捷路径。
两种 Dockerfile 均在构建期执行 `scripts/deploy/check_image.py`：比较 `/app/src/trust_receipt` 与已安装 wheel 的全部
Python 文件（仅归一化 Git 换行），并用真实 `/app/app/streamlit_app.py` 执行 AppTest，要求零 exception、实际产品标题
及正确源码导入路径。隔离检查不挂生产目录、不注入 `.env`、不提供真实密钥，构建时使用 `--network=none`。
缺外部配置可显示明确阻塞，不可有导入异常。健康端点、HTTP 200、WebSocket 和 `/release` 下演示不能替代真实入口检查。
检查通过 `python -c` 的 runpy 调用从 `/app` 启动，保留生产 `python -m streamlit` 的工作目录导入语义；
不要直接运行位于 `/opt` 的脚本导致脚本目录取代应用根目录，也不另外设置 PYTHONPATH。
切换后只用新独立浏览器会话检查首页渲染及无异常；这不补记业务矩阵或真实用户验收。
切换前保留旧镜像及源码备份，保留 `.env`、data 与私有/公开回执挂载；仅使用
`docker compose ... up -d --no-deps --no-build app` 切换已构建应用镜像，不重建其他容器。

若需保持 `/opt/trust-receipt` 开发源码不变，将已验源码/wheel/Compose 放入独立、root-only 发布目录，
以原 `--project-directory /opt/trust-receipt/deploy` 和实际项目名 `-p deploy` 启动。
发布前内部解析配置并核对 image、资源、三个绝对挂载、live/writes 开关；不可打印解析出的凭据。
相对 `.env`、data、receipts 路径仍指向原项目，不复制密钥或用新空目录冒充持久化数据。

```bash
report_release=/opt/trust-receipt-releases/report-REVISION
report_image_tag=report-REVISION
TRUST_RECEIPT_IMAGE_TAG="$report_image_tag" docker compose \
  --project-directory /opt/trust-receipt/deploy -p deploy \
  -f "$report_release/source/deploy/docker-compose.prod.yml" \
  up -d --no-deps --no-build app
docker exec campus-creator-nginx nginx -t && docker exec campus-creator-nginx nginx -s reload
```

`REVISION` 必须替换为已核验发布目录/镜像标签。应用重建可能改变 Docker IP；静态 `proxy_pass` 上游名称
可能仍缓存旧 IP，所以内部 healthy 后须 `nginx -t` 并定向 reload，保持代理容器及配置不变。
随后实际检查公网根页、健康、静态资源和 WebSocket，不以内部健康代替公网成功。
失败必须回滚旧镜像/旧配置，并再次刷新代理上游；切换不意味着无需短暂重启。

```bash
report_backup=/opt/trust-receipt-backups/report-before-REVISION
docker compose --project-directory /opt/trust-receipt/deploy -p deploy \
  -f "$report_backup/compose-before.yml" -f "$report_backup/rollback-image.yml" \
  up -d --no-deps --no-build app
docker exec campus-creator-nginx nginx -t && docker exec campus-creator-nginx nginx -s reload
```

旧 Compose、source 归档与回滚 image tag 在切换前保护；备份不含 `.env`、私钥、data 或原始私有回执。
回滚后同样核对原 `.env` 哈希、三个挂载、公网状态及 Blockscout/代理身份，没有默认模型/RPC业务复测或写链授权。

页面 Logo 保持用户原始 PNG，存放于 `app/static/logo.png`；`.streamlit/config.toml` 启用
`server.enableStaticServing` 保留原始静态访问；品牌展示使用兼容 `server.baseUrlPath` 的同源 288px 媒体预览 URL，使浏览器复用资源，避免每次重跑
重复发送大段 base64。OpenAI/Agent0 SDK 仅在对应 adapter 实际使用时加载。生产接入这些改动须经授权重建镜像，
随后检查 `/trust-receipt/app/static/logo.png`、页面实际 `/trust-receipt/media/` 资源、Logo 透明底和 DPR 清晰度及 WebSocket；本地优化不代表生产已经更新。

生产服务器使用 `deploy/docker-compose.prod.yml` 构建两个相互隔离的容器：Streamlit 主应用与
Blockscout MCP。两者只加入既有反向代理网络，不直接向公网发布容器端口；`data/` 和
`receipts/private/` 通过宿主机目录持久化。Compose 固定设置 `APP_REQUIRE_LIVE=true`，因此生产页面只能使用真实
DeepSeek 与真实 Sepolia RPC；缺少任一必要配置时直接阻塞，不会回退 fixture。

```bash
cd /opt/trust-receipt
chmod 600 .env
docker compose -f deploy/docker-compose.prod.yml up -d --build
docker compose -f deploy/docker-compose.prod.yml ps
```

反向代理使用 `deploy/nginx-location.conf` 中的路径规则，入口为 `/trust-receipt/`。规则包含 WebSocket 和长连接，
公开入口不要求 HTTP Basic Auth；明文 HTTP 入口仍必须重定向到 HTTPS。如果 Nginx 配置使用单文件 bind mount，宿主机
原子替换配置后应重建代理容器，使新 inode 被重新挂载。部署后分别检查容器内健康端点、匿名公网入口以及
一次页面 WebSocket 会话。Streamlit 的内联启动脚本和运行时样式需要路径级 CSP 例外；必须使用
`deploy/nginx-location.conf` 中仅限该路径的安全头，不能放宽整个域名。`.env` 和 PEM 私钥不得进入镜像。

若部署地域无法连接 `api.blockscout.com`，清空部署环境的 `BLOCKSCOUT_PRO_API_KEY` 并重建主应用容器，页面会
明确显示 `RPC-only`。此时必须单独验证 `ETH_RPC_URL` 的真实 Sepolia 读取；不得保留已配置提示并让每次操作等待
Blockscout 超时，也不得把 RPC 结果伪装成 Blockscout 抽样成功。

若要恢复受阻地域的 Blockscout 补充抽样，可将 `deploy/blockscout-relay/` 部署到 Vercel，绑定并验证自定义域名后再设置
`BLOCKSCOUT_PRO_API_BASE_URL`。部署完成必须从目标服务器运行真实 MCP 探针；只有返回 `SAMPLED` 后才能重新启用
`BLOCKSCOUT_PRO_API_KEY`。未认领的临时 URL 不得作为生产依赖。

当前生产值为 `BLOCKSCOUT_PRO_API_BASE_URL=https://blockscout-relay.creatoros.top`；DNSPod 的 `blockscout-relay` CNAME
指向 Vercel 提供的项目专用记录。更换域名或部署后应先执行 Vercel 域名验证，再从广州服务器验证配置端点、真实交易端点、
MCP 工具与产品级 `SAMPLED` 诊断，整个过程不得输出 Bearer key。

本地首次启动默认进入明确标注的离线 fixture 演示，不调用模型网络。切换到 OpenAI 或 DeepSeek 时，必须同时配置对应 API key
和固定模型名；选择“真实 Sepolia RPC”还必须配置 `ETH_RPC_URL`，可用 `RPC_CONFIRMATIONS` 调整确认数。缺少配置会在页面
显示阻塞。工作区 ID 对应独立本地数据库、私有回执目录和运行时生成的无资产签名账户；进程重启后输入同一 ID 可恢复最新任务
及两个 attempt，历史 AI 文本不会重新生成。M6 公共发布和 ERC-8004 写入分别要求页面内显式授权；缺少 publisher 或写链配置
时按钮保持禁用，已发布但尚未写链的回执保持 `NOT_SUBMITTED`。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv-blockscout\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\export_schemas.py --check
.\.venv\Scripts\python.exe scripts\check_file_sizes.py
.\.venv\Scripts\python.exe scripts\run_mvp_demo.py
```

最后一条是无需凭据的 M7 演示：执行服务 A `FAIL`、切换服务 B `PASS`、两个 attempt 持久化、两份回执独立重放和进程恢复。
输出 `"valid": true` 才算成功；其 `publication_mode=not-executed` 明确表示该命令不代替真实 M6 公共发布与写链验收。

M4 离线门槛与真实模型探针分别运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\m4
.\.venv\Scripts\python.exe -m pytest tests\external\test_openai_ai_probe.py -m external -v
.\.venv\Scripts\python.exe -m pytest tests\external\test_deepseek_ai_probe.py -m external -v
.\.venv\Scripts\python.exe -m pytest tests\external\test_m5_live_product_probe.py -m external -v
```

外部探针缺少 key、固定模型名或 RPC 配置时会明确 skip。不要把 mock 通过解释为真实模型已连通。项目所有者明确授权继续使用
对话中提供的测试供应商密钥时，只能放入被 Git 忽略的本机 `.env`；不得写入日志、提交、fixture、回执或模型 prompt。

本地回执可在独立进程中校验和重放：

```powershell
.\.venv\Scripts\python.exe -m trust_receipt.receipts.cli path\to\receipt.json
```

命令以 JSON 输出回执哈希、任务哈希、对象链接和三态结果复算状态；任一检查失败时退出码非零。

M9 公开回执验证不读取 SQLite 或私有工作区。可对本地下载的公开 JSON 或 HTTP(S) URI 执行：

```powershell
.\.venv\Scripts\python.exe -m trust_receipt.m9.cli `
  path\to\public-receipt.json `
  --kind RECEIPT_HASH `
  --value 0x<receipt-hash> `
  --attempt 1 `
  --expected-content-hash 0x<published-byte-sha256>
```

`--kind` 还支持 `URI`、`TASK_HASH` 和 `FEEDBACK_TRANSACTION`。单 Receipt attempt 2 必须使用 `--revision`、
`--parent-revision` 和 `--parent-receipt` 提供公开父回执与关系。完整历史包可直接验证最新 attempt：

```powershell
.\.venv\Scripts\python.exe -m trust_receipt.m9.cli public-history.json --bundle --kind URI
```

哈希定位加 `--kind RECEIPT_HASH --value 0x<public-receipt-hash>` 或 `--kind TASK_HASH --value 0x<spec-hash>`。
反馈入口从配置 `ETH_RPC_URL` 和 `ERC8004_REPUTATION_REGISTRY_ADDRESS` 只读真实交易：

```powershell
.\.venv\Scripts\python.exe -m trust_receipt.m9.cli --kind FEEDBACK_TRANSACTION --value 0x<tx-hash> --attempt 2 --public-history public-history.json
```

未提供可验证公开父回执时返回 INCONCLUSIVE；未提供公开承诺时 `commitment_status=UNVERIFIED`。
页面的 `?verify=1` 为独立入口，支持文件、配置公共目录 HTTPS/IPFS 和反馈交易，不需要原工作区或模型密钥。
“分享完整验收历史”分别授权历史导出与公共上传，元数据保存在私有 `public-history/`，恢复后复用已有发布引用。

M0 真实探针使用：

```powershell
.\.venv\Scripts\python.exe -m pytest -m external -v
```

缺少配置时会逐项显示 `blocked by missing configuration` 并跳过。跳过只代表阻塞已被明确报告，不能作为
M0 已连通的证据。

## 参考合约验证

仅在需要复核 ERC-8004 上游合约时运行：

```powershell
cd D:\HACKTHON\references\erc-8004-contracts
$env:SEPOLIA_RPC_URL="http://127.0.0.1:8545"
$env:MAINNET_RPC_URL="http://127.0.0.1:8545"
npx hardhat compile
npm test
```

上游锁文件存在 Hardhat peer dependency 冲突，首次安装使用 `npm ci --legacy-peer-deps`。不要运行 `npm audit fix` 改写参考仓库。

## 常见故障

### Blockscout 工具认证失败

检查当前进程是否实际继承 `BLOCKSCOUT_PRO_API_KEY`；不要通过打印环境变量值来诊断。

### RPC 没有返回事件

依次确认链 ID、代币地址、区块范围、RPC 是否为归档/完整节点，以及查询是否因范围过大被限制。空数组和查询失败必须区分。

### Streamlit 端口占用

```powershell
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py --server.port 8502
```

### Docker Desktop

当前 4.79.0 在本机因旧运行时链接启动失败，自动升级需要管理员步骤。开发默认走本地 Blockscout MCP，不把修复 Docker 作为 MVP 前置条件。

## 清理与恢复

### M8 上传与工作区恢复

上传只接受 `schemas/v1/uploaded_report.schema.json` 对应的 UTF-8 JSON，最多 1 MB、200 条 service 来源记录。
原始文件保存在 `receipts/private/m5/<workspace-id>/uploads/`；不得公开该目录。SQLite 同工作区新增只追加 M8 artifact
表，不存私钥。重启后输入原 workspace ID，系统校验承诺、证据 manifest 并重放结果；上传任务恢复后补交需重新上传文件，
不会静默换成演示服务。缺少旧快照只保留原回执；损坏快照拒绝恢复，不自动覆盖或重拉参考证据。

专用锚候选当前没有部署地址或生产配置；本地编译可用 `npx --yes --package solc@0.8.30 solcjs --bin --abi
contracts/CommitmentAnchor.sol -o .tmp/m8-solc`。不将本地模拟交易当作 Sepolia 已提交或已确认。

可在隔离开发端口启动 `npx --yes --package ganache@7.9.2 ganache --server.host 127.0.0.1 --server.port 18549 --logging.quiet --wallet.deterministic`，
然后运行 `python scripts/check_m8_anchor_local.py`。脚本只允许 loopback HTTP 与开发 chain 1337，使用本地测试币和新生成的
测试身份，校验授权、requester 命名空间、只追加 attempt 和 task/delivery 事件读回；不读取 `.env` 或真实密钥。
Ganache 启动输出中的默认开发密钥不是生产凭据，但日志仍应留在忽略的 `.tmp/`。

页面主题由 `.streamlit/config.toml` 的原生深色主题与 `app/styles.py` 共同控制；不要只修改背景却保留原生浅色主题。
生产 Dockerfile 必须复制 `.streamlit/` 到镜像工作目录；发布需重建应用镜像，不能只刷新浏览器或更新 CSS。
更新导入的样式后重启开发 Streamlit，浏览器刷新并用原 workspace ID 恢复，避免缓存旧样式。

- 不删除 `fixtures/`、`schemas/` 或已发布回执。
- 本地数据库损坏时先复制 `data/` 作为证据，再重建开发数据库。
- 私有回执不得为了“清理”而移动到公开目录。
- 参考仓库如被意外修改，先查看 `git status`，不得使用破坏性重置覆盖未知改动。

## 首步报表转换

入口保留严格 JSON，同时支持 UTF-8（含 BOM）或 GB18030 CSV、仅一个可见工作表的无宏 XLSX。
CSV 支持逗号、分号、制表符；编码与原始字节哈希显示在转换记录中。PDF、截图、旧 XLS、UTF-16 CSV 不支持。
不是任意 Excel 导入器：公式、外部链接、日期及非 General 数值格式、合并单元格、多工作表、超限内容拒绝，不静默抽样。
XLSX 使用有界标准库 ZIP/XML reader，无新增 Excel 依赖；文本支持 inline string、共享字符串及富文本 run。

ADR-032 统一上传后，JSON 直接严格解析；CSV/XLSX 由已配置的 OpenAI/DeepSeek 固定模型识别安全表头，
数值仍确定性读取。正常路径不要求手动映射、转换或采用 JSON。仅缺链 ID、代币地址、精度时局部补充整表条件；
普通金额单位不明确时询问最小单位或代币单位。缺事件身份/地址/金额、竞争字段或声明单位不明时修正原表，不猜值。
XLSX 金额及声明总额必须为文本；原声明即使错误也不改写，缺失摘要注明由明细计算，并在范围确认时说明来源。
模型只收到受限安全表头，没有文件名或行值；沿用 M4 凭据名称和供应商端点，识别超时最多 30 秒，无 SDK 自动重试。
缺配置、超时或无效输出保持阻塞，显式重试不消耗 attempt，不静默回退离线识别。缓存按文件/模型绑定；局部条件调整
可以重用已绑定的识别角色，无需重新外发。成功后自动私有留档，再接既有 intake，仍须范围确认与主动核对。

新自动入口原件、规范 JSON、来源记录保存在私有目录 `recognition-originals/`、`recognition-json/`、
`recognition-provenance/`，含内容哈希、原文件名、模型模式/固定标识、实际角色、映射、用户补充和派生字段。
旧 `conversion-*` 文件不删除；来源记录不包含密钥，也不是原作者签名。
保留与正式提交没有跨文件事务；失败可能留下内容寻址的私有孤立文件，但不会自动签名、上传公开文件或覆盖历史交付。
