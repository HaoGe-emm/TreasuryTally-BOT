---
doc-id: m14-readiness-evidence-2026-10-07
title: M14 2026-10-07 浏览器技术验收快照
status: source
authority-for:
  - m14-2026-10-07-observed-evidence
last-reviewed: 2026-10-07
---

# M14 2026-10-07 浏览器技术验收快照

本记录只整理暂停前实际完成的运行。用户已要求停止追加自动操作并准备手动确认，完整矩阵仍未齐，不宣称全部验收完成。
没有真实用户或内部测试用户；自动化不等于用户验证。

## 输入与运行

- 工作区：`C:/Users/Gzhou/.codex/worktrees/m14-user-trial-prep/HACKTHON`
- 本地入口：`http://127.0.0.1:8534`，真实 DeepSeek + 真实 Sepolia RPC，发布和写链配置关闭。
- 应用依赖：M12 `a739551`、单位摘要修复 `9f1cd85`、资金流范围修复 `f09b57c`；本线等价修复提交为 `862a1ff`、`61d4ec3`。
- 最新完成浏览器运行使用执行器 `6cc1f7e`，记录目录 `output/playwright/m14-live-06/`。
- 自备输入：`fixtures/m11/independent/corrected-complete.json`，由第二组公开 Sepolia 事件形成，不是 R1 固定报表。
- 输入 SHA-256：`5eae6754080563af6ebef809a4c7021177018770e42474fe76827d4d1619baee`。
- 工作区 ID：`m14-restart-06`。
- 金额：`321794352786` 最小单位；实际 RPC 诊断为 `COMPLETE`。
- 任务指纹：`0xd00d62e0d0915051329adc3fbdb2e8c247fd681382c35a11a54185503907ede6`，刷新后保持一致。

## 逐项结果

| 项目 | 状态 | 已有证据及未齐条件 |
|---|---|---|
| UR-01 固定真实链修复闭环 | BLOCKED | 本运行未执行；M13 的主线材料独立交接，不在此冒计 |
| UR-02 非固定独立报表 | PASS | 自备 JSON、编辑范围、确认、真实模型/RPC、金额一致；`independent-pass.png` |
| UR-03 冷浏览器会话 | PASS | 新命名独立上下文，无历史任务，完成第二组输入；`cold.png` |
| UR-04 持久化恢复 | BLOCKED | 页面刷新后同任务指纹恢复；进程重启/新上下文恢复尚未运行 |
| UR-05 上传边界及恢复 | PASS | 空、重复 key、浮点、缺字段、错误来源、201 条、错误编码、超 1 MB 均拒绝，合法文件恢复；`upload-recovered.png` |
| UR-06 未确认拒绝 | PASS | 确认前没有执行入口，未勾选提交明确拒绝，随后可显式确认 |
| UR-07 证据不足 | BLOCKED | 浏览器故障场景未运行；其他线领域/CLI 检查不替代本层证据 |
| UR-08 来源冲突 | BLOCKED | 本地隔离故障 launcher 已提交，启动后因暂停关闭，未执行浏览器故障场景 |
| UR-09 第三次拒绝 | BLOCKED | 本运行只完成一个 PASS attempt；领域测试不冒计为本层通过 |
| UR-10 作者身份 | PASS | 上传说明明确 intake 不认证作者；`identity.png` |
| UR-11 未授权写隔离 | PASS | 查看公共回执区，未点击公开写操作，未提交状态和禁用发布控件；`write-isolation.png` |
| UR-12 响应式与放大 | BLOCKED | 首屏与结果页 1440/390/759/761px 无页面级溢出；720px 检查不能代替实际 200% 放大 |
| UR-13 键盘操作 | PASS | Tab 到候选按钮，Enter/Space 操作生成、规则、确认、冻结、核验与证据折叠区；`keyboard.png` |
| UR-14 自助说明路径 | PASS | 自备上传、候选编辑、显式确认、真实核验和来源下钻步骤与页面一致 |

合计：8 PASS、0 FAIL、6 BLOCKED；`ready=false`。BLOCKED 包含未执行或部分覆盖，不代表能力已经失败。

## 执行器和旧失败

- 执行器使用新命名会话和 loopback URL，结构化输出 `matrix.json`；未执行项默认 BLOCKED，无证据不能 PASS。
- 文件和目录只创建不覆盖；旧 `m14-initial`、`m14-recovered`、`m14-live-01` 至 `m14-live-05` 均保留。
- 初次结果读取、复选框、文件移除及工作区重设问题已在本线修复，旧失败不删除。
- `tests/m14/test_readiness_evidence.py` 实际执行 6 项通过；专属 Python Ruff 检查通过。
- `92de556` 新增恢复/故障脚本仅通过当时 Ruff 检查，浏览器路径未执行；不能声称它们通过运行验收。

## 暂停前已执行命令

```powershell
D:/HACKTHON/.venv/Scripts/python.exe scripts/m14/check_readiness.py `
  --base-url http://127.0.0.1:8534 `
  --report fixtures/m11/independent/corrected-complete.json `
  --task-spec fixtures/m11/independent/task-spec.json `
  --scope "Sepolia chain11155111,WETH0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9,资金账户0x0C88262f03B183DD183C2fC7A78578dBcE1e664C,资助对象0x3dea9a7d55beA23D193B9308a7e85E6A2a9a6364,起止区块11855664,无排除规则" `
  --expected-total 321794352786 --build 61d4ec3 `
  --workspace-id m14-restart-06 --public-test-input-confirmed `
  --evidence-dir output/playwright/m14-live-06
```

命令返回 `ready=false` 并保存完整矩阵；shell 显示的非零退出只表示矩阵未全齐，不应把已通过项目抹去或把未执行项目改成通过。
以上是历史命令，不是暂停期间的执行指令。运行文件保留在 Git 忽略目录，本快照只提交公开输入标识、脱敏事实及覆盖范围。
