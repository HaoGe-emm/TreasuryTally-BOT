"""Fixed business wording from saved evidence codes, never provider free text."""
# ruff: noqa: RUF001

from trust_receipt.models import VerificationResult

_RPC_REASONS = {
    "HISTORICAL_DATA_UNAVAILABLE": (
        "当前节点无法提供所选区块的历史转账证据，需使用支持该历史范围的节点后重新核对。"
    ),
    "TIMEOUT": "链上数据读取超时，本次未取得完整参考证据。",
    "UNAVAILABLE": "链上数据源暂不可用，本次未取得完整参考证据。请查看诊断并检查数据源配置。",
    "WRONG_NETWORK": "链上数据源返回的网络与已确认任务不一致。请检查数据源网络配置。",
    "UNCONFIRMED_RANGE": "所选区块尚未达到要求的确认数。需等待区块确认。",
    "INVALID_RESPONSE": "链上数据源返回的事件格式无法验证。请查看数据源诊断。",
    "INVALID_OR_UNAVAILABLE": "链上证据读取失败或返回内容无法使用。请查看诊断。",
}
_UNKNOWN_REASON = "证据来源未完成，需查看诊断。"


def inconclusive_explanation(result: VerificationResult) -> str | None:
    """One stable primary note; other precision/graph notes remain separate.

    A supplemental diagnostic or zero events never changes the verdict. Only
    saved incomplete RPC descriptors can select a known technical cause.
    Unknown/missing/non-string codes fail closed, including recovered receipts
    without diagnostic snapshots. No parsing of exception strings or URLs.
    """
    if result.outcome.value != "INCONCLUSIVE":
        return None
    reasons = []
    for source in result.reference_sources:
        if source.source.value != "rpc" or source.complete:
            continue
        code = source.details.get("error_code")
        reason = _RPC_REASONS.get(code, _UNKNOWN_REASON) if type(code) is str else _UNKNOWN_REASON
        if reason not in reasons:
            reasons.append(reason)
    return "".join(reasons or [_UNKNOWN_REASON]) + "本次暂不能判断通过或服务失败。"
