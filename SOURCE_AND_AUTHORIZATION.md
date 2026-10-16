# TreasuryTally BOT Chain Edition — 来源与授权记录

记录日期：2026-10-16（Asia/Shanghai）。本目录是独立开发副本。

| 项目 | 保留的来源 | 固定版本 |
|---|---|---|
| 业务项目 / 原作者 | https://github.com/CH-ZHOU-0512/TreasuryTally / CH-ZHOU-0512 | `f5efc9cf9b1a5860bc824d176d3a92407e96b495` |
| 原 Codex Skill / 原作者 | https://github.com/CH-ZHOU-0512/TreasuryTallySkill / CH-ZHOU-0512 | `c128dab79e39f0df87e6013ed25b15f4e8765a45` |
| 原公开网站（仅作为来源） | https://creatoros.top/trust-receipt/ | 未登录、未修改其服务器 |

## 获取方式与可追溯性

本机标准 Git clone 受代理和连接重置阻断，因此通过 GitHub codeload 获取固定 SHA 的完整源码归档，而非声称已取得上游 Git 历史。
业务归档的全部 443 个文件已对照该 SHA 的 Git tree 逐一计算 Git Blob SHA-1，全部一致，包括图片、字体和第三方资产。
本地 Git `upstream-snapshot` 分支保存这份源码快照；`bot-chain-phase1` 用于独立开发。该本地快照提交不是上游提交 SHA。
`upstream` remote 保留原地址，push URL 设为禁用占位值；未执行 push。

业务源码归档 SHA-256：`0cb76cb683ba5d63306799e7ac875ad80ce1c39037bd2c337facb73c878db3d5`。
Skill 归档 SHA-256：`9db11c53d10cc52cdf9abd50e76a1c2b35632402806cafb72794eca887820c2f`。
原 Skill 的本机参考副本在 `references/TreasuryTallySkill/`，由现有 `.gitignore` 排除，未安装为全局 Skill。其 README 中历史仓库名保留原样。

## 版权与许可证

业务仓库固定版本未发现仓库根 LICENSE，GitHub 也未识别仓库级许可证。不得将某个文件的声明解释为整个业务项目的统一许可。
`contracts/CommitmentAnchor.sol` 自带 `SPDX-License-Identifier: MIT`；该候选源文件本轮未修改。
原 Skill 是 MIT License，版权署名 `Copyright (c) 2026 CH-ZHOU-0512`；保留其 LICENSE。
原项目内字体 OFL、ECharts LICENSE/NOTICE 等第三方声明保留原样。

## 项目专门授权（独立于许可证）

本轮用户提供的授权事实：

> 原负责人已经明确授权我复制、修改及独立公开部署项目，但我没有原 GitHub 仓库的写入权限，也没有原网站服务器的 SSH 权限。

此记录保留用户提供的授权范围和来源，不伪造原负责人签署的许可证或书面文件。
本轮执行范围仅为本地文件、依赖、代码和本地测试。主网部署、主网交易、真实钱包主网交易签名、GitHub push、Vercel 发布均留待后续分别批准。

## 数据边界

仅从公开 GitHub 固定版本获取源码及公开 fixture。没有复制真实 `.env`、数据库、私有回执、生产钱包密钥、助记词或服务器凭据。
`.env.example` 为上游公开配置模板，继续保留。隔离 EVM 仅使用临时开发账户和本地测试余额。
未读取或修改 `D:\HKS`，未登录或修改原生产服务器。
