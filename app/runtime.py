"""Composition root for one isolated Streamlit browser session."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from eth_account import Account

from trust_receipt.agents import (
    DeepSeekStructuredOutputAdapter,
    M4AISettings,
    OfflineDemoStructuredOutputAdapter,
    OpenAIStructuredOutputAdapter,
    RestrictedAIService,
    TaskSpecCandidate,
)
from trust_receipt.chain import RpcReferenceEvidenceProvider
from trust_receipt.integrations.config import M0Settings
from trust_receipt.m9 import LocalRevisionStore
from trust_receipt.m9.publication import PublicBundleStore
from trust_receipt.orchestration import (
    M5Workflow,
    M6Workflow,
    M8CommitmentWorkflow,
    StaticEvidenceProvider,
    candidate_from_fixture,
    eligible_records,
    evidence_from_fixture,
    load_vertical_demo_fixture,
)
from trust_receipt.orchestration.m8_workspace import M8WorkspaceWorkflow
from trust_receipt.orchestration.m10 import M10Workflow
from trust_receipt.publishing import HttpsDirectoryPublisher, M6Settings, PinataPublisher
from trust_receipt.reputation import ERC8004ReceiptFeedback
from trust_receipt.services import FaultMode, TeamControlledReportService
from trust_receipt.services.report_recognition import HeaderRecognizer, build_header_recognizer
from trust_receipt.storage.m8 import M8ArtifactStore
from trust_receipt.storage.sqlite import SQLiteRepository
from trust_receipt.verification.scope import scope_violation


class ConfigurationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class AppRuntime:
    workflow: M5Workflow
    services: dict[str, TeamControlledReportService]
    mode_label: str
    editable_seed: TaskSpecCandidate
    evidence_label: str
    publication_workflow: M6Workflow
    publisher: PinataPublisher | HttpsDirectoryPublisher | None
    feedback_adapter: ERC8004ReceiptFeedback | None
    publication_status: str
    feedback_status: str
    commitment_workflow: M8CommitmentWorkflow
    commitment_anchor_status: str
    m8_workflow: M8WorkspaceWorkflow
    revision_store: LocalRevisionStore
    public_bundle_store: PublicBundleStore
    upload_directory: Path
    history_workflow: M10Workflow
    report_recognizer: HeaderRecognizer | None = None


def create_runtime(
    *,
    project_root: Path,
    session_id: str,
    provider: str,
    evidence_mode: str,
) -> AppRuntime:
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", session_id) is None:
        raise ConfigurationBlocked("工作区 ID 仅允许 1-32 位小写字母、数字和连字符")
    fixture = load_vertical_demo_fixture(project_root)
    candidate = candidate_from_fixture(fixture)
    ai_service, mode_label = _ai_service(provider, candidate, project_root)
    evidence_provider, evidence_label = _evidence_provider(
        evidence_mode,
        fixture=fixture,
        project_root=project_root,
    )
    repository = SQLiteRepository(project_root / "data" / "m5" / f"{session_id}.db")
    workflow = M5Workflow(
        repository=repository,
        evidence_provider=evidence_provider,
        ai_service=ai_service,
        receipt_directory=project_root / "receipts" / "private" / "m5" / session_id,
    )
    if evidence_mode == "真实 Sepolia RPC":
        def records_provider(task):
            return _eligible_live_records(evidence_provider, task)
    else:
        records = eligible_records(fixture)

        def records_provider(task):
            del task
            return records
    services = {
        "服务 A · 首次故意漏项": TeamControlledReportService(
            service_id="service-a",
            private_key=Account.create().key.to_0x_hex(),
            records_provider=records_provider,
            fault_by_attempt={1: FaultMode.OMIT_LAST_TRANSFER},
        ),
        "服务 B · 完整交付": TeamControlledReportService(
            service_id="service-b",
            private_key=Account.create().key.to_0x_hex(),
            records_provider=records_provider,
        ),
    }
    m6_settings = M6Settings.load(project_root / ".env")
    publisher = (
        PinataPublisher(
            m6_settings.pinata_jwt,
            api_url=m6_settings.pinata_api_url,
            gateway_url=m6_settings.pinata_gateway_url,
        )
        if m6_settings.pinata_jwt is not None
        else None
    )
    publication_status = "Pinata/IPFS 已配置" if publisher else "缺少 PINATA_JWT，公共发布暂不可用"
    if (
        publisher is None
        and m6_settings.public_receipt_directory is not None
        and m6_settings.public_receipt_base_url is not None
    ):
        publisher = HttpsDirectoryPublisher(
            m6_settings.public_receipt_directory,
            m6_settings.public_receipt_base_url,
        )
        publication_status = "HTTPS 内容寻址公共目录已配置（Pinata 未配置）"
    feedback_adapter = None
    feedback_status = "M6_ENABLE_WRITES=false，ERC-8004 写入已关闭"
    settings = M0Settings.load(project_root / ".env")
    write_requirements = {
        "ETH_RPC_URL": settings.rpc_url,
        "AGENT0_SERVICE_ID": settings.agent0_service_id,
        "AGENT0_EXPECTED_OWNER": settings.agent0_expected_owner,
        "ERC8004_IDENTITY_REGISTRY_ADDRESS": settings.identity_registry_address,
        "ERC8004_REPUTATION_REGISTRY_ADDRESS": settings.reputation_registry_address,
        "REVIEWER_PRIVATE_KEY": settings.reviewer_private_key,
    }
    missing_write = [name for name, value in write_requirements.items() if value is None]
    if m6_settings.enable_writes and not missing_write:
        feedback_adapter = ERC8004ReceiptFeedback(
            rpc_url=settings.rpc_url_value(),
            chain_id=settings.chain_id,
            service_id=settings.agent0_service_id or "",
            expected_service_owner=settings.agent0_expected_owner or "",
            identity_registry=settings.identity_registry_address or "",
            reputation_registry=settings.reputation_registry_address or "",
            reviewer_private_key=settings.reviewer_private_key,
            expected_reviewer=settings.reviewer_address,
            request_timeout_seconds=settings.rpc_timeout_seconds,
        )
        feedback_status = "ERC-8004 写入已显式启用；提交前仍需页面二次授权"
    elif m6_settings.enable_writes:
        feedback_status = "ERC-8004 配置阻塞：缺少 " + ", ".join(missing_write)
    commitments = M8CommitmentWorkflow()
    return AppRuntime(
        workflow=workflow,
        services=services,
        mode_label=mode_label,
        editable_seed=candidate,
        evidence_label=evidence_label,
        publication_workflow=M6Workflow(repository),
        publisher=publisher,
        feedback_adapter=feedback_adapter,
        publication_status=publication_status,
        feedback_status=feedback_status,
        commitment_workflow=commitments,
        commitment_anchor_status=(
            "EIP-712 本地承诺可验证；链上锚定未提交（Validation Registry 仅启用只读接口探针）"
        ),
        m8_workflow=M8WorkspaceWorkflow(
            workflow, commitments, M8ArtifactStore(project_root / "data" / "m5" / f"{session_id}.db"),
        ),
        revision_store=LocalRevisionStore(
            project_root / "receipts" / "private" / "m5" / session_id / "revisions"
        ),
        public_bundle_store=PublicBundleStore(
            project_root / "receipts" / "private" / "m5" / session_id / "public-history"
        ),
        upload_directory=project_root / "receipts" / "private" / "m5" / session_id / "uploads",
        report_recognizer=(
            None if provider == "离线 fixture 演示"
            else build_header_recognizer(provider, M4AISettings.load(project_root / ".env"))
        ),
        history_workflow=M10Workflow(
            repository,
            project_root / "receipts" / "private" / "m5" / session_id,
            LocalRevisionStore(project_root / "receipts" / "private" / "m5" / session_id / "revisions"),
        ),
    )


def _evidence_provider(evidence_mode: str, *, fixture, project_root: Path):
    if evidence_mode == "完整 fixture 证据":
        return StaticEvidenceProvider(evidence_from_fixture(fixture)), "fixture · 完整人工标注证据"
    if evidence_mode == "模拟证据不可用":
        return (
            StaticEvidenceProvider(evidence_from_fixture(fixture, sufficient=False)),
            "fixture · 模拟证据不可用",
        )
    settings = M0Settings.load(project_root / ".env")
    if settings.rpc_url is None:
        raise ConfigurationBlocked("真实 RPC 配置阻塞：缺少 ETH_RPC_URL")
    live = RpcReferenceEvidenceProvider(
        settings.rpc_url_value(),
        expected_chain_id=settings.chain_id,
        timeout_seconds=settings.rpc_timeout_seconds,
        confirmations=settings.rpc_confirmations,
        blockscout_mcp_url=settings.blockscout_mcp_url,
        enable_blockscout_cross_check=settings.blockscout_pro_api_key is not None,
    )
    blockscout = "已配置抽样交叉检查" if settings.blockscout_pro_api_key is not None else "未配置，RPC-only"
    return live, f"真实 Sepolia RPC · Blockscout {blockscout}"


def _eligible_live_records(evidence_provider, task):
    evidence = evidence_provider.fetch(task)
    if not evidence.evidence_sufficient:
        return ()
    return tuple(
        record
        for stream in evidence.streams
        for page in stream.pages
        for record in page.transfers
        if scope_violation(task, record) is None
    )


def _ai_service(provider: str, candidate, project_root: Path) -> tuple[RestrictedAIService, str]:
    settings = M4AISettings.load(project_root / ".env")
    if provider == "离线 fixture 演示":
        adapter = OfflineDemoStructuredOutputAdapter(candidate)
        return RestrictedAIService(adapter), "离线 fixture 演示（非真实模型调用）"
    if provider == "OpenAI 真实模型":
        missing = settings.missing_for_openai()
        if missing:
            raise ConfigurationBlocked(f"OpenAI 配置阻塞：缺少 {', '.join(missing)}")
        adapter = OpenAIStructuredOutputAdapter(
            api_key=settings.api_key_value(),
            model_name=settings.model_name or "",
            timeout_seconds=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )
        return RestrictedAIService(adapter), f"OpenAI 真实模型：{settings.model_name}"
    missing = settings.missing_for_deepseek()
    if missing:
        raise ConfigurationBlocked(f"DeepSeek 配置阻塞：缺少 {', '.join(missing)}")
    adapter = DeepSeekStructuredOutputAdapter(
        api_key=settings.deepseek_api_key_value(),
        model_name=settings.deepseek_model_name or "",
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    return RestrictedAIService(adapter), f"DeepSeek 真实模型：{settings.deepseek_model_name}"
