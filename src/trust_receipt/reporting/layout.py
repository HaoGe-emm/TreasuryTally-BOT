"""Shared content sequence for HTML, DOCX and PDF export parity."""
# ruff: noqa: RUF001

from collections import Counter
from dataclasses import dataclass

from trust_receipt.reporting.models import AmountView, BusinessReportView


@dataclass(frozen=True)
class ReportSection:
    title: str
    paragraphs: tuple[str, ...] = ()
    headers: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()


def money(amount: AmountView | None) -> str:
    return f"{amount.display} {amount.unit}" if amount else "不可确定"


def report_sections(view: BusinessReportView) -> tuple[ReportSection, ...]:
    current, scope = view.current, view.scope
    sections = [
        ReportSection("核验结论", (view.conclusion, *view.limitations)),
        ReportSection(
            "核验范围",
            (
                scope.summary,
                f"代币合同 {scope.token.full}",
                *(f"资金账户 {a.full}" for a in scope.treasuries),
                *(f"接收对象 {a.full}" for a in scope.recipients),
                *(scope.exclusions or ("未配置排除规则。",)),
            ),
        ),
        ReportSection(
            "来源与证据时点",
            (
                view.source_mode_label,
                current.identity_label,
                *(
                    f"{s.label} {'完整' if s.complete else '不完整'} 取得于 {s.retrieved_at.isoformat()}"
                    for s in current.sources
                ),
                "导出仅使用原证据快照，不表示重新核验当前链上状态。",
            ),
        ),
        ReportSection(
            "金额与记录数",
            (),
            ("项目", "报表声明", "核验值"),
            (
                ("金额", money(current.claimed), money(current.calculated)),
                (
                    "记录数",
                    str(current.claimed_count),
                    str(current.calculated_count) if current.calculated_count is not None else "不可确定",
                ),
            ),
        ),
        ReportSection(
            "金额差额",
            (
                f"报表声明减核验值 {money(current.difference)}"
                if current.difference
                else (current.difference_reason or "不可比较"),
            ),
        ),
    ]
    errors = tuple(f for f in current.findings if f.confirmed and f.severity == "error")
    grouped = Counter(f.finding_type for f in errors)
    sections.append(
        ReportSection(
            "已确认关键差异",
            tuple(
                f"{next(f.title for f in errors if f.finding_type == kind)} 共 {count} 项。"
                f"{next(f.recommendation for f in errors if f.finding_type == kind)}"
                for kind, count in grouped.items()
            )
            or ("未记录已确认错误。",),
        )
    )
    notes = tuple(f for f in current.findings if f.confirmed and f.severity != "error")
    if notes:
        sections.append(ReportSection("范围规则与说明", tuple(f"{f.title}。{f.description}" for f in notes)))
    if current.uncertainties:
        sections.append(ReportSection("明确不可确定项", current.uncertainties))
    sections.append(
        ReportSection(
            "资金流图例",
            (*tuple(
                f"{item.label}  {item.meaning}"
                for item in view.legend
                if item.status in {r.status for r in current.flow_rows}
            ), "图中最多预览前 4 条保存事件；并行连线拥挤时仅展示首条，完整记录见明细。"
               "线宽不表示金额。长金额和单位说明详见完整明细。"),
        )
    )
    if view.previous:
        before = view.previous
        sections.append(
            ReportSection(
                "两次交付对比",
                (view.repair_label or "关系未核实",),
                ("交付", "原验收结果", "报表金额", "核验金额"),
                (
                    (
                        "第 1 次",
                        f"{before.outcome_label} ({before.outcome.value})",
                        money(before.claimed),
                        money(before.calculated),
                    ),
                    (
                        "第 2 次",
                        f"{current.outcome_label} ({current.outcome.value})",
                        money(current.claimed),
                        money(current.calculated),
                    ),
                ),
            )
        )
    sections.append(ReportSection("下一步", (view.next_step,)))
    sections.append(
        ReportSection(
            "复核引用",
            (
                f"任务指纹 {view.spec_hash}",
                f"当前回执 {current.receipt_hash}",
                *((f"原始回执 {view.previous.receipt_hash}",) if view.previous else ()),
                view.notice,
            ),
        )
    )
    if current.flow_rows:
        sections.append(
            ReportSection(
                "完整资金流明细",
                (f"共 {len(current.flow_rows)} 条投影记录；图仅为局部预览，以下完整保留事件引用。",),
                ("资金方向与精确金额", "状态与来源", "链 ID 交易哈希 日志索引"),
                tuple(
                    (
                        f"{row.sender.short} → {row.recipient.short}\n{money(row.amount)}",
                        f"{row.status_label}\n{row.source_label}",
                        row.event_ref,
                    )
                    for row in current.flow_rows
                ),
            )
        )
        addresses = sorted({a.full for row in current.flow_rows for a in (row.sender, row.recipient)})
        sections.append(ReportSection("完整账户索引", tuple(addresses)))
    if current.findings:
        sections.append(
            ReportSection(
                "完整差异依据",
                tuple(
                    f"{index + 1} {finding.title} {'已确认' if finding.confirmed else '待核实'}。"
                    f"{finding.description} 建议：{finding.recommendation} "
                    f"引用：{'; '.join(finding.evidence_refs) or '见原 JSON 回执对应 Finding'}"
                    for index, finding in enumerate(current.findings)
                ),
            )
        )
    if view.previous:
        before = view.previous
        sections.append(
            ReportSection(
                "首次交付原始差异",
                (
                    f"原结果 {before.outcome_label} ({before.outcome.value})，不因补交而覆盖。",
                    *before.uncertainties,
                    *(
                        f"{finding.title} {'已确认' if finding.confirmed else '待核实'}。{finding.description} "
                        f"引用：{'; '.join(finding.evidence_refs) or '见原 JSON 回执对应 Finding'}"
                        for finding in before.findings
                    ),
                ),
            )
        )
    return tuple(sections)


def validate_export_view(view: BusinessReportView) -> None:
    # Bound local CPU/memory and page production. The application domain is <=200
    # events per side; projection may retain separate duplicate/invalid records.
    if any(len(report.flow_rows) > 400 or len(report.findings) > 1000
           for report in (view.current, view.previous) if report is not None):
        raise ValueError("report exceeds export record limits")
    if len(view.model_dump_json()) > 2_000_000:
        raise ValueError("report exceeds export size limit")

    def visit(value):
        if isinstance(value, str) and len(value) > 4096:
            raise ValueError("report text exceeds export length limit")
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    visit(view.model_dump(mode="json"))
    rendered_chars = sum(
        len(text)
        for section in report_sections(view)
        for text in (*section.paragraphs, *(value for row in section.rows for value in row))
    )
    if rendered_chars > 60_000:
        raise ValueError("report exceeds export document content budget")
