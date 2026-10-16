---
doc-id: m14-user-readiness-evidence-template
title: M14 用户就绪验收证据模板
status: active
authority-for:
  - m14-readiness-evidence
last-reviewed: 2026-10-07
---

# M14 用户就绪验收证据模板

复制本模板为一次实际运行记录。不得预填通过结果，不得创建参与者 ID、访谈引语、人工观察或满意度字段。

## 运行身份

- 记录 ID：
- 开始/结束时间与时区：
- 执行者：自动化名称与版本，或工程验证者代号
- 应用构建/commit：
- 自动化 commit：
- 入口与环境标签：
- 浏览器及版本：
- 视口/缩放：
- 工作区匿名 ID：
- 全新上下文：是 / 否；若否，说明恢复场景

## 输入来源

- 输入类别：R1 固定基线 / R2 独立输入 / N1 非法输入 / E1 环境异常
- 报表文件代号与 SHA-256：
- 报表是否包含真实敏感信息：必须为否
- schema 版本：
- 范围摘要：chain、token、账户数量、区块范围、排除规则
- 预期结果的独立来源：RPC 预检记录/案例 manifest；不得写“来自页面结果”
- 是否为固定样例：是 / 否
- 若为 R2，区别于 R1 的字段与组装方法：

## 外部能力实测

| 能力 | 配置是否存在 | 实际调用 | 证据 | 结果 |
|---|---|---|---|---|
| DeepSeek 结构化模型 |  | 是 / 否 | 脱敏请求 ID/诊断 | PASS / FAIL / BLOCKED |
| Sepolia RPC |  | 是 / 否 | chain ID、区块、页数、记录数 | PASS / FAIL / BLOCKED |
| Blockscout 补充来源 |  | 是 / 否 / 非必需 | 采样状态 | PASS / FAIL / N/A |
| 公共发布 |  | 必须为否，除非有另行授权 | 状态 | NOT_SUBMITTED / 其他 |
| 链上写入 |  | 必须为否，除非有另行授权 | 状态 | NOT_SUBMITTED / 其他 |

## 矩阵结果

| 验收 ID | 输入/步骤摘要 | 预期 | 实际 | 结构化证据 | 截图/trace | 结果 |
|---|---|---|---|---|---|---|
| `UR-__` |  |  |  |  |  | PASS / FAIL / BLOCKED |

## 关键一致性证据

- 上传内容哈希：
- 任务指纹：
- Attempt 1 ID / submission hash / receipt hash / outcome：
- Attempt 2 ID / submission hash / receipt hash / outcome：
- 参考来源完整性与诊断：
- 代表性完整事件键 `chain_id + transaction_hash + log_index`：
- 声称金额 / 链上有效金额 / 差额（最小单位整数）：
- Finding ID、类型和证据引用：
- 恢复前后哈希一致性：
- 页面级 `scrollWidth / innerWidth`：

## 异常与复测

| 问题 ID | 首次构建 | 最小复现 | 预期/实际 | 归属 | 修复 commit | 复测结果与证据 |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

## 结论

- 矩阵通过数 / 失败数 / 阻塞数：
- 固定基线真实链闭环：PASS / FAIL / BLOCKED
- 独立输入真实链闭环：PASS / FAIL / BLOCKED
- 全新浏览器会话：PASS / FAIL / BLOCKED
- 异常恢复：PASS / FAIL / BLOCKED
- 可声明结论：未验证 / 部分验证 / 支持范围内技术自助路径已验证
- 限定语：未进行真实用户测试；自动化不等于真实用户验证。
- 未完成项：

## 脱敏检查

记录中不得包含密钥、JWT、认证头、完整环境变量、真实客户报告、生产钱包、私有组织标签或未批准录屏。公开 Sepolia 地址和
交易仅在案例允许时保留；其余使用别名。失败证据必须保留事实，后续成功不得覆盖首次失败。
