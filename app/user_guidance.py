"""Plain-language view helpers; never compute outcomes or change workflow state."""

from trust_receipt.models import PublicationChainStatus, VerificationOutcome


def chain_state_copy(status: PublicationChainStatus) -> str:
    return {
        PublicationChainStatus.NOT_SUBMITTED: "未提交",
        PublicationChainStatus.SUBMITTED: "已提交，待读回确认",
        PublicationChainStatus.CONFIRMED: "已确认并读回一致",
        PublicationChainStatus.FAILED: "失败，请查看原因",
    }[status]


def outcome_copy(outcome: VerificationOutcome) -> str:
    return {
        VerificationOutcome.PASS: "核对通过",
        VerificationOutcome.FAIL: "发现差异",
        VerificationOutcome.INCONCLUSIVE: "暂时无法下结论",
    }[outcome]


def next_step(outcome: VerificationOutcome, attempt_count: int) -> str:
    if outcome is VerificationOutcome.PASS:
        return "下一步：保存回执。需要对外分享时，先预览脱敏内容，再另行授权发布。"
    if attempt_count >= 2:
        return "两次核对已用完。请保存当前回执与差异；本任务不能再次补交，原记录不会被覆盖。"
    if outcome is VerificationOutcome.INCONCLUSIVE:
        return "下一步：先检查证据来源或连接问题。确认资料齐备后再核对一次；本任务只剩一次机会。"
    return "下一步：按下方差异修正报表，然后上传修正版再核对一次。本任务只剩一次补交机会。"


def short_explanation(summary: str, limit: int = 180) -> str:
    """The original explanation remains available; shortening is presentation only."""
    compact = " ".join(summary.split())
    return compact if len(compact) <= limit else compact[:limit].rstrip() + "…"


def explanation_preview(summary: str) -> str:
    if not any("\u4e00" <= char <= "\u9fff" for char in summary):
        return "说明原文不是中文，已保留在详情中。请先看下方中文差异与处理建议；这里不会改变核对结果。"
    return short_explanation(summary)
