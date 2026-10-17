# TreasuryTally BOT 677 · 阶段 3D 主网任务登记

记录日期：2026-10-17（Asia/Shanghai）。本地分支 `bot-chain-phase3`，登记前 HEAD `b7e632544c8d1c7840661be9ee6d15fa27668539`。

## 范围与来源

这是一份内部 Demo TaskSpec：`web3-demo/public/bot677-demo/task-spec.json`，任务 ID 为 `bot677-demo-usdt-26879920-two-accounts`。它约定检查 BOT Chain 677 区块 26,879,920 的指定 USDT 合约、请求者和收款方；先前只读查询没有发现匹配的 ERC-20 Transfer。`service_id` 是内部演示标识，不是已注册的 ERC-8004 身份。登记仅证明请求者钱包在链上记录了任务承诺，不证明发生资金转账、报表金额正确或财务核验通过。

任务摘要来自 2026-10-16 页面显示的 MetaMask EIP-712 签名结果，当时 TypeScript 与原 Python 模型交叉校验通过。原始签名未保存；本次没有重新签名，因此不能将历史摘要载入视为本次重新验签。签名域不含 `verifyingContract`，消息字段不直接包含 `serviceSigner`，`expiresAt` 为空。详见 `stage3d-signature-observation.md`。

## 固定交易

| 项目 | 值 |
| --- | --- |
| 网络 | BOT Chain Mainnet，Chain ID 677 |
| From / Requester | `0x89F415bb42e356E8b892C10B05522e0a8Ef151F3` |
| To / CommitmentAnchor | `0xAf845BA2D1aF0e842FD2185fa081720D6D3D7148` |
| 函数 | `anchorTask(bytes32,bytes32,bytes32,address)` |
| `taskDigest` | `0xc3702a7758dc0eb150ed0a51c13c8c30dd7b6b850f41c0abdcb446778361b25d` |
| `specHash` | `0x9e0073e83868993f4da3bc013fe8aca7e90af7a99fb80bcda8d593963528d093` |
| `serviceIdHash` | `0x540bafe01cfa9731e46b8116f8dc63fa62e3a2853b0cb28beeabdaaa0ddbd7cd` |
| `serviceSigner` | `0xb6bF6a936F529650992B71e2DeB79E80Fd3da71B` |
| 交易 Hash | `0x3727bca4c744308638da4dfcc79a5c2d86f1f0a81d0eaff8df2fa9e994435c4d` |
| 区块 | 26,967,683 |
| 实际 Gas 费用 | 0.0014154 BOT |

[BOTScan 交易](https://scan.botchain.ai/tx/0x3727bca4c744308638da4dfcc79a5c2d86f1f0a81d0eaff8df2fa9e994435c4d) · [BOTScan 合约](https://scan.botchain.ai/address/0xAf845BA2D1aF0e842FD2185fa081720D6D3D7148)

## 发送前检查与链上读回

发送前，本地页面对固定参数执行了钱包账户/Chain ID、RPC Chain ID、合约运行时代码 SHA-256、`tasks` 重复登记、`eth_call` 模拟、Gas、余额与 `latest/pending` nonce 检查。页面显示模拟成功、Gas 估算 71,634、上限 85,960、Gas 报价 20,000,000,000 wei、最高预算 0.0017192 BOT、余额 0.48357372 BOT、nonce 5；参数与用户单独批准的交易一致。MetaMask 弹窗由用户本人确认，网页随后显示上述交易 Hash。

网页的 `readAnchorReceipt` 实现会从 BOT RPC 读取交易与回执，并要求：Receipt `status=success`、Chain ID 677、合约运行时代码哈希一致、交易 `from/to/input` 与固定四参一致、回执中恰有一个匹配的 `TaskAnchored` 事件、`tasks(requester, taskDigest)` 与事件一致。用户报告该页面显示“回执事件和合约存储一致”，随后主动点击“只读重查交易回执、事件与存储”，页面再次显示“BOT 677 成功回执、TaskAnchored 事件和 tasks 存储已交叉核验”，并显示上述区块、摘要和实际费用。

此报告的链上成功结论基于该本地页面的实时 RPC 读回及用户转述的页面结果。记录时，当前执行环境直连 `https://rpc.botchain.ai` 报 `fetch failed`，直连 BOTScan API 超时，独立的命令行核验没有完成。因此不能声称本报告另有第二条独立网络通道完成复核；后续在网络恢复时应以交易 Hash 再运行独立只读核验。

登记后，`.env.local` 的 `NEXT_PUBLIC_ENABLE_MAINNET_WRITES` 已恢复为 `false`，`NEXT_PUBLIC_ENABLE_TASK_SIGNATURES` 与 `NEXT_PUBLIC_ENABLE_MAINNET_DEPLOY` 也为 `false`；本地状态接口返回 `enabled:false,status:"disabled"`。只读链上查询继续可用。没有执行 `anchorDelivery`、其他主网写入、重新部署、GitHub push 或 Vercel 发布。

## 比赛交付进度

| 要求 | 当前状态 |
| --- | --- |
| 公开可访问的网站 | 未完成；目前是本地开发页面 |
| GitHub 代码仓库 | BOT Edition 尚未推送；原项目上游仓库已记录 |
| Connect Wallet 与 MetaMask / OKX Wallet | 入口已实现；本次真实主网操作使用 MetaMask，OKX Wallet 尚未完成同等真实验收 |
| 切换 BOT Chain 677 | 已实现；本次页面与钱包显示 677 |
| BOT 主网业务合约 | 已部署 `CommitmentAnchor`，有部署交易和合约地址 |
| 用户钱包签名且成功执行的主网业务交易 | 本次 `anchorTask` 已由用户在 MetaMask 确认；页面的回执、事件和存储读回成功，独立命令行复核待网络恢复 |
| 清楚展示 BOT Chain 的产品作用 | 本地 Demo 显示 TaskSpec、历史签名摘要、主网任务登记及链上读回；公开演示站尚未发布 |
