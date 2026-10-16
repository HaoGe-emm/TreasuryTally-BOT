"""Independent public history explorer and explicit sharing controls."""

from __future__ import annotations

from app.m9_components import render_public_verification
from trust_receipt.hashing import canonical_json_bytes
from trust_receipt.integrations.config import M0Settings
from trust_receipt.m9 import (
    PublicBundleResolver,
    PublicReceiptReference,
    PublicReferenceKind,
    ResolvedPublicReceipt,
    build_public_bundle,
    verify_public_reference,
)
from trust_receipt.m9.bundles import read_public_json
from trust_receipt.m9.feedback import ERC8004PublicResolver
from trust_receipt.m9.public_reader import PublicArtifactReader
from trust_receipt.publishing import M6Settings


class _SingleReceiptResolver:
    def __init__(self, payload: bytes, attempt: int) -> None:
        self._payload = payload
        self._attempt = attempt

    def resolve(self, reference):
        return ResolvedPublicReceipt(payload=self._payload, attempt=self._attempt)


def render_public_explorer(ui, project_root) -> None:
    """Available before any task, AI configuration, or private workspace is opened."""
    with ui.expander("验证他人分享的回执", expanded=True):
        ui.caption("上传公开回执或完整验证包；只读取本次提供的公开文件。")
        uploaded = ui.file_uploader("公开验证 JSON", type=("json",), max_upload_size=4, key="m9-public-input")
        uri = ui.text_input("公开验证包或回执链接（HTTPS / IPFS）", key="m9-public-uri")
        kind = ui.selectbox(
            "公开引用类型", ("URI", "RECEIPT_HASH", "TASK_HASH", "FEEDBACK_TRANSACTION"), key="m9-reference-kind",
        )
        value = ui.text_input("回执或任务哈希（按 URI 验证时留空）", key="m9-reference-value")
        attempt = ui.radio("单回执 attempt（完整包自动定位）", (1, 2), horizontal=True, key="m9-public-attempt")
        ready = bool(kind == "FEEDBACK_TRANSACTION" or uri.strip() or uploaded is not None)
        ready = ready and bool(kind == "URI" or value.strip())
        if ui.button("验证公开内容", disabled=not ready, key="m9-verify-upload"):
            location = uri.strip() or "uploaded-public-file"
            settings = M6Settings.load(project_root / ".env")
            reader = PublicArtifactReader(
                https_base_urls=tuple(dict.fromkeys(filter(None, (
                    settings.public_receipt_base_url, "https://creatoros.top/trust-receipt/public",
                )))),
                ipfs_gateway=settings.pinata_gateway_url,
            )
            if kind == "FEEDBACK_TRANSACTION":
                chain = M0Settings.load(project_root / ".env")
                if chain.rpc_url is None or chain.reputation_registry_address is None:
                    ui.warning("反馈交易核验需要配置 Sepolia RPC 和 Reputation Registry 地址。")
                    return
                resolver = ERC8004PublicResolver(
                    rpc_url=chain.rpc_url_value(), reputation_registry=chain.reputation_registry_address,
                    chain_id=chain.chain_id, reader=reader, attempt=attempt,
                    bundle_payload=uploaded.getvalue() if uploaded is not None else None,
                )
                result = verify_public_reference(
                    PublicReceiptReference(PublicReferenceKind.FEEDBACK_TRANSACTION, value.strip()), resolver,
                )
                render_public_verification(ui, result)
                return
            if uploaded is not None:
                payload = uploaded.getvalue()
            else:
                try:
                    payload = reader.fetch(location)
                except (OSError, ValueError) as error:
                    ui.warning(f"公开内容无法读取：{type(error).__name__}")
                    return
            try:
                raw = read_public_json(payload)
                is_bundle = isinstance(raw, dict) and "bundle_version" in raw
            except (ValueError, UnicodeError):
                is_bundle = False
            reference = PublicReceiptReference(
                PublicReferenceKind(kind), location if kind == "URI" else value.strip(),
            )
            resolver = (
                PublicBundleResolver(payload, location=location)
                if is_bundle else _SingleReceiptResolver(payload, attempt)
            )
            result = verify_public_reference(reference, resolver)
            render_public_verification(ui, result)
            ui.caption("核验范围：公开内容完整性、对象关系和所记录规则结论；参考链上数据未重新抓取。")


def render_public_history(ui, runtime, receipts) -> None:
    with ui.expander("分享完整验收历史", expanded=False):
        ui.caption("包含首次结果、补交结果及公开版本关系，可在新会话独立验证。")
        authorized = ui.checkbox(
            "我授权导出并分享所有 attempt 的脱敏回执，包括首次失败及任务范围",
            key=f"m9-history-authorized-{receipts[0].task_spec.task_id}",
        )
        if not authorized:
            return
        bundle = build_public_bundle(receipts, authorized=True)
        payload = canonical_json_bytes(bundle) + b"\n"
        ui.download_button(
            "下载完整公开验证包", payload, file_name="public-history.json", mime="application/json",
            key="m9-download-history",
        )
        with ui.expander("预览将分享的内容"):
            ui.json(bundle.model_dump(mode="json"))
        artifact = runtime.public_bundle_store.get(bundle)
        if artifact is None:
            publish_authorized = ui.checkbox("我授权将该完整历史上传到公共存储", key="m9-publish-history-authorized")
            if ui.button(
                "发布完整验收历史", key="m9-publish-history",
                disabled=runtime.publisher is None or not publish_authorized,
            ):
                try:
                    artifact = runtime.public_bundle_store.publish(
                        bundle, runtime.publisher, authorized=publish_authorized,
                    )
                except (ValueError, RuntimeError, OSError) as error:
                    ui.error(f"公开历史发布未完成：{type(error).__name__}")
        if artifact is not None:
            ui.write("公开验证包链接")
            ui.code(artifact.uri, language=None)
            ui.caption(f"公开字节 SHA-256：{artifact.content_hash}")
            if ui.button("重新下载并验证完整历史", key="m9-verify-history"):
                try:
                    downloaded = runtime.publisher.fetch(artifact.uri) if runtime.publisher is not None else b""
                    reference = PublicReceiptReference(PublicReferenceKind.URI, artifact.uri)
                    result = verify_public_reference(reference, PublicBundleResolver(
                        downloaded, location=artifact.uri, expected_content_hash=artifact.content_hash,
                    ))
                    render_public_verification(ui, result)
                except (ValueError, RuntimeError, OSError) as error:
                    ui.warning(f"无法下载公开历史：{type(error).__name__}")
