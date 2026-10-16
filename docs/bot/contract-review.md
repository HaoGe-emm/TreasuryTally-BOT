# CommitmentAnchor 候选合约审阅

本轮沿用上游源码，未改变原有业务规则。此文件是工程预检记录，不是外部审计结论。

## 实际功能与权限

- `anchorTask`：调用者成为 requester。记录键为 `tasks[msg.sender][taskDigest]`，因此其他账户不能抢占请求者自己的命名空间。相同请求者与相同 digest 重复登记回滚。
- `anchorDelivery`：只允许任务登记时的 serviceSigner 调用。attempt 范围为 1–2，同 requester、taskDigest、attempt 只能登记一次。
- 合约没有管理员、付款、资金托管、外部合约调用、服务注册身份认证或报表验证功能。
- TaskAnchored 与 DeliveryAnchored 事件字段、成功/失败回执以及存储值都必须按既定预期读回。

## 必须保留的业务边界

合约只拒绝部分零值、重复和未授权操作。它不会自行重算 TaskSpec、校验 EIP-712 签名，或证明 digest 与 specHash/serviceId/reportHash 的关系。
因此前端和原 Python 代码必须校验完整模型、哈希、请求者签名和服务签名者来源。任何非零 digest 被登记，不自动成为有效 TreasuryTally 业务承诺。

上游 TaskCommitment 的 EIP-712 字段包含 serviceId，但不包含 serviceSigner。当前实现保留该规则：服务签名者由请求者审阅并在 anchorTask 交易中登记。
如需把 serviceSigner 也纳入请求者的离线签名，必须另行审阅、升级模型/签名版本及兼容读取，不在本轮悄然修改。

合约允许先登记 attempt 2，也不检查有效期、两次交付的先后顺序或服务签名是否有效。
本地对抗测试会特意复用旧 digest 验证这一边界；该测试不代表有效的第二次业务交付。
业务规则继续由原模型、签名校验及确定性核验流程执行。
相同逻辑任务使用新的 commitmentId/时间/签名可能得到新 digest；合约的重复保护不等于 taskId 或 specHash 的全局唯一性。

## 编译与 EVM 兼容性

使用精确版本 solc 0.8.30，显式 `evmVersion: paris`，optimizer runs=200，单独输出本地产物。
在 Ganache 的 Merge EVM、chain 1337 中验证部署与业务调用，避免依赖后续硬分叉指令。
BOT 官方文档确认 EVM 兼容及网络参数，但本轮未取得明确的主网硬分叉清单。因此本地产物通过不等于 BOT 主网部署已验证。
后续部署前仍需检查官方 RPC 身份、主网只读模拟/估算、预期 runtime 字节码及浏览器验证方式。

网络参数来源：https://dev-docs.botchain.ai/docs/Developers/quick-guide/ 。

## 验证入口

- `local-evm/scripts/check_anchor_local.mjs`：原 TaskSpec fixture 的哈希、规范化本地变体、完整任务/交付签名、真实本地 EVM 部署与交易、事件、字节码、存储、回滚及错误网络。
- `scripts/bot/check_vectors.py`：使用未改动的上游 Python 模型、hashing 与 eip712 代码复核 viem 生成的公开本地向量。
- `scripts/check_m8_anchor_local.py`：保留原脚本，并以隔离 loopback EVM 与本地产物执行。
- `web3-demo/scripts/check_units.cjs`：哈希与时间规范化、身份/网络拒绝及钱包协议测试；钱包 provider 为测试替身。

Ganache 为独立本地测试依赖，存在旧的间接依赖告警，不进入网页部署依赖。仅使用内存 EVM 或 loopback RPC，未使用真实密钥。
