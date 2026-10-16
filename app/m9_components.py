"""Independent Streamlit renderers for M9 artifacts.

Integration: import these functions from the page layer and pass the active
``streamlit`` module. They only consume immutable M9 models and never access
SQLite, provider SDKs, private keys, or verification internals.
"""

from __future__ import annotations

from trust_receipt.m9 import PublicVerificationResult, RepairComparison, ReworkPackage


def render_rework_package(ui, package: ReworkPackage) -> None:
    ui.subheader("返工要求")
    ui.caption(
        f"任务 {package.task_id} · 来源回执 {package.source_receipt_hash} · "
        f"确认问题 {len(package.items)} 项"
    )
    for item in package.items:
        with ui.container(border=True):
            ui.markdown(f"**{item.finding_type.value}** · `{item.finding_id}`")
            ui.write(item.violated_rule)
            ui.caption(f"要求动作：{item.required_action.value}")
            with ui.expander("查看预期、实际与证据引用"):
                ui.json(
                    {
                        "expected": item.expected,
                        "actual": item.actual,
                        "evidence_refs": item.evidence_refs,
                    }
                )


def render_repair_comparison(ui, comparison: RepairComparison) -> None:
    ui.subheader("修复前后对比")
    ui.caption(f"同一任务 {comparison.task_id} · 结果 {comparison.resolution.value}")
    before_column, after_column = ui.columns(2)
    for column, label, snapshot in (
        (before_column, "首次交付", comparison.before),
        (after_column, "修复后", comparison.after),
    ):
        with column, ui.container(border=True):
            ui.markdown(f"**{label} · Attempt {snapshot.attempt}**")
            ui.metric("验收结论", snapshot.outcome.value)
            ui.write(f"服务：{snapshot.service_id}")
            ui.write(f"声称金额（最小单位）：{snapshot.claimed_total_base_units}")
            calculated = snapshot.calculated_total_base_units or "无法确定"
            ui.write(f"链上有效金额（最小单位）：{calculated}")
            ui.caption(f"回执：{snapshot.receipt_hash}")
            ui.caption(f"承诺核验：{snapshot.commitment_status.value}")
    ui.write(f"已解决 Finding：{len(comparison.resolved_finding_ids)}")
    ui.write(f"仍存在 Finding：{len(comparison.remaining_finding_ids)}")
    with ui.expander("查看版本关系与证据引用"):
        ui.json(comparison.model_dump(mode="json"))


def render_public_verification(ui, result: PublicVerificationResult) -> None:
    ui.subheader("独立公开验证")
    message = f"{result.status.value}: {result.reason}" if result.reason else result.status.value
    if result.status.value == "VERIFIED":
        ui.success(message)
    elif result.status.value == "INVALID":
        ui.error(message)
    else:
        ui.warning(message)
    ui.caption(f"入口：{result.reference_kind.value} · {result.reference_value}")
    if result.receipt_hash is not None:
        ui.write(
            {
                "task_id": result.task_id,
                "service_id": result.service_id,
                "attempt": result.attempt,
                "receipt_hash": result.receipt_hash,
                "outcome": result.outcome.value if result.outcome else None,
                "resolution": result.resolution.value if result.resolution else None,
                "commitment_status": result.commitment_status.value,
            }
        )
    with ui.expander("查看核验项与证据"):
        for check in result.checks:
            ui.write(f"{check.state.value} · {check.check_id} · {check.detail}")
        ui.json({"evidence_refs": result.evidence_refs})
