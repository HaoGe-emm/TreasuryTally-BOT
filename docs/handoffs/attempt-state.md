---
doc-id: attempt-state-recovery-interface
title: 持久化 Attempt 状态与只读恢复接口
status: source
authority-for: []
last-reviewed: 2026-10-07
---

# 根因与接口

业务流程先持久化 REQUESTED，交付后 SUBMITTED/VERIFYING，保存结果后才创建回执文件。
异常或中断会留下请求/交付或只有结果但缺回执的任务。`restore_latest` 原来只恢复有结果且有回执的 attempt；
因此空 executions 不能证明数据库尚未开始。页面用 executions 长度决定首轮按钮，会与正确的安全锁冲突。
这是可通过单次调用后的异常复现的路径，不需要重复点击。线上实际数据库状态未经本分支读取。

`M5Workflow.get_attempt_status(task_id)` 和 `M8WorkspaceWorkflow.get_attempt_status(task_id)` 返回
冻结 `storage.models.AttemptStatus`：

| 字段 | 类型 | 语义 |
|---|---|---|
| task_id | str | 当前明确任务 |
| state | TaskState | 数据库持久化状态 |
| persisted_attempts | int | 已保存交付数，不含未交付 REQUESTED |
| completed_attempts | int | 已保存确定性结果数，不等于已有回执数 |
| in_flight_attempt | int 或 None | 正在请求/验收的编号；不声明进程仍活着 |
| next_attempt | int 或 None | 新请求候选编号；仍须通过核心事务校验 |
| blocking_reason | AttemptBlockReason 或 None | 明确阻塞代码 |

状态规则：CONFIRMED 且0交付 -> next1；1交付且完整终态 FAIL/INCONCLUSIVE -> next2；
REQUESTED/SUBMITTED/VERIFYING -> IN_FLIGHT、nextNone；PASS -> PASSED；
2轮非PASS终态 -> ATTEMPTS_EXHAUSTED；不一致 -> STATE_CONFLICT。
已保存结果缺原始回执 -> MISSING_RECEIPT；回执损坏/与DB对象冲突 -> RECEIPT_CONFLICT。
REQUESTED0交付是 in_flight1，REQUESTED1交付且首轮完成是 in_flight2。
旧 RETRY_REQUESTED 或无法解释的组合保守阻塞，不把未知映射为成功。

状态查询是只读投影，不是预约令牌。多个浏览器的状态快照可过时；实际 `request_attempt` 在 IMMEDIATE 事务内
读取/校验/设置 REQUESTED，只有一个请求获准。不能通过客户端重试绕过并发拒绝。
M5 配置 receipt_directory 时检查原始回执完整性与 task/submission/result/service 绑定；
未配置目录的纯业务流程不依赖文件，但也不提供可分享历史恢复承诺。

## 页面消费（M12 唯一 app 写者）

不能使用 `len(session.executions)` 计算 next 或把空列表解释为首次未开始。
每次重跑和捕获执行异常后读取当前 task_id 的状态；nextNone 时不渲染可执行首轮/补交按钮。
请求/验收中或中断的任务只查看留档，允许显式开启新工作区/新任务，但不要取消旧请求或自动再执行。
此修复不恢复线上悬挂请求，不修改用户数据、不生成未知结果。

`M5Workflow.restore_task(task_id)` -> `(task, executions)`；
`M8WorkspaceWorkflow.restore_task(task_id)` -> `(task, executions, snapshots)`。
仅读指定 task，不调用 AI、证据提供器或服务；`restore_latest` 委托相同恢复逻辑，保持旧接口。
state completed count大于 session结果数量时可只读刷新当前任务，不能切换为其他会话创建的最新任务。
缺原始回执的 attempt仍不伪造execution；有效但缺旧M8附加快照则 snapshot/evidence为None、不伪造资金图。
M8快照冲突会按现有恢复边界抛ValueError，UI须阻塞并说明，不应吞异常后提供新的执行按钮。

## 最小回归

`tests/m5/test_attempt_status.py`覆盖新会话REQUESTED/SUBMITTED/VERIFYING、交付后provider异常、
结果提交后磁盘失败、缺/冲突receipt、两轮非PASS后耗尽、当前任务恢复及两连接原子请求。
所有输入为隔离fixture与临时无资产账户；不执行公开上传或写链。
本分支不改app；消费者以已提交SHA合流代码和测试，状态摘要以根STATUS为准。
