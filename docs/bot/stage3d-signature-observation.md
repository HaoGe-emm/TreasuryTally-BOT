# TreasuryTally BOT 677 · 阶段 3D 签名后只读预检

检查时间：2026-10-16 15:46:34 UTC，BOT Chain 区块 26,908,231。工作分支 `bot-chain-phase3`，本地提交 `b3cda1cd07c7d811707340afe373db70cc73e8be`。

## 浏览器中已验证的签名结果

现有页面显示 MetaMask 账户和签名者均为 `0x89F415bb42e356E8b892C10B05522e0a8Ef151F3`，钱包 Chain ID 与 RPC Chain ID 均为 677，页面提示 TypeScript 与原 Python 模型交叉校验成功。固定 EIP-712 消息摘要是 `0x193954b4c310b54ac5b93bf9cb546d31f831f40b76378a100c53010d93fb7f2a`。签名导出的任务摘要为：

`0xc3702a7758dc0eb150ed0a51c13c8c30dd7b6b850f41c0abdcb446778361b25d`

原始签名没有保存到此报告或仓库。上述验证成功状态来自当前网页的实际显示；本次只读 RPC 检查使用已经显示的公开摘要与参数。

## 拟调用参数

`anchorTask(bytes32 taskDigest, bytes32 specHash, bytes32 serviceIdHash, address serviceSigner)`

| 字段 | 值 |
| --- | --- |
| From / Requester | `0x89F415bb42e356E8b892C10B05522e0a8Ef151F3` |
| To / 合约 | `0xAf845BA2D1aF0e842FD2185fa081720D6D3D7148` |
| `taskDigest` | `0xc3702a7758dc0eb150ed0a51c13c8c30dd7b6b850f41c0abdcb446778361b25d` |
| `specHash` | `0x9e0073e83868993f4da3bc013fe8aca7e90af7a99fb80bcda8d593963528d093` |
| `serviceIdHash` | `0x540bafe01cfa9731e46b8116f8dc63fa62e3a2853b0cb28beeabdaaa0ddbd7cd` |
| `serviceSigner` | `0xb6bF6a936F529650992B71e2DeB79E80Fd3da71B` |

## BOT Chain 主网只读结果

- `eth_chainId` = 677。
- 合约运行时代码 1,297 字节；SHA-256 = `0xe19c6b11680cbd60c5fb6061d52052c65596e48b9c10cbc59415538e03a75eaf`，与审阅值一致。
- `tasks(requester, taskDigest)` 读回两个零地址，未发现重复登记。
- 以上述 Requester 为 `from`、部署合约为 `to`、四个参数编码为 `data` 的 `eth_call` 返回 `0x`，模拟成功。
- `eth_estimateGas` = 71,634；按页面的 120% 规则计算 Gas 上限 = 85,960。
- `eth_gasPrice` = 20,000,000,000 wei；对应的最高预算 = 0.0017192 BOT。
- Requester 余额 = 0.48357372 BOT；账户 nonce `latest/pending` = `5/5`。

这是当时的只读报价。任何后续发送之前，须重新读取网络、合约代码、重复登记、nonce、Gas 与余额，并取得单独的主网交易授权。签名与 `eth_call` 均未生成主网业务交易。

## 界面阻断与状态保存

当前标签页显示签名校验成功及任务摘要，但“运行只读 anchorTask 模拟与费用预览”按钮没有产生动作。浏览器 DOM 检查显示该按钮当时没有 React 点击处理器；本报告的只读预检因此直接使用项目 ABI 编码的公开参数调用 RPC。不能凭当前页面按钮完成后续交易。原因尚未定位；开发服务器与构建产物同时运行可能相关，但尚未证实。

本报告仅保存公开任务摘要、参数及只读结果。当前页面的内存状态和原始签名不能保证在电脑关机后恢复。后续阶段应先修复页面交互与安全恢复流程，再准备任何主网发送。若恢复流程确实需要新签名，必须另行取得授权。

内部 Demo 任务的固定区块查询此前返回零条匹配 ERC-20 Transfer；本次签名或未来任务登记均不证明发生过资金转账，也不证明财务核验通过。`service_id` 不是已注册 ERC-8004 身份。
