"""M16 facade composed exclusively from existing domain and orchestration ports."""

from __future__ import annotations

from datetime import UTC, datetime

from trust_receipt.agents import (
    DeepSeekStructuredOutputAdapter,
    M4AISettings,
    OfflineDemoStructuredOutputAdapter,
    OpenAIStructuredOutputAdapter,
    RestrictedAIService,
    TaskSpecCandidate,
)
from trust_receipt.chain import RpcReferenceEvidenceProvider
from trust_receipt.hashing import stable_hash
from trust_receipt.headless.authorization import AuthorizationStore
from trust_receipt.headless.config import WorkspaceConfig, WorkspaceRegistry
from trust_receipt.headless.contracts import (
    AttemptFindingView,
    AttemptResultView,
    AuthorizationAction,
    AuthorizationChallenge,
    AuthorizationState,
    ConfirmedTaskView,
    HeadlessProfile,
    ReceiptReplayView,
    ReceiptView,
    TaskCandidateView,
)
from trust_receipt.headless.errors import HeadlessError, blocked, rejected
from trust_receipt.integrations.config import M0Settings
from trust_receipt.orchestration.m5 import (
    M5Workflow,
    StaticEvidenceProvider,
    candidate_from_fixture,
    evidence_from_fixture,
    load_vertical_demo_fixture,
)
from trust_receipt.receipts import load_receipt, replay_receipt
from trust_receipt.services.upload import UploadedReportService, parse_report
from trust_receipt.storage.sqlite import RepositoryStateError, SQLiteRepository


class HeadlessTrustReceiptFacade:
    """Workspace-isolated facade; callers never control a filesystem location."""

    def __init__(self, registry: WorkspaceRegistry) -> None:
        self._registry = registry

    def draft_task(self, workspace_handle: str, user_request: str) -> TaskCandidateView:
        if not user_request.strip() or len(user_request) > 4_000:
            raise rejected("INVALID_USER_REQUEST", "Task request must contain 1 to 4,000 characters.")
        config = self._workspace(workspace_handle)
        candidate = self._ai_service(config).draft_task(user_request)
        return TaskCandidateView(
            workspace_handle=workspace_handle,
            profile=config.profile,
            fixture_test_only=config.profile is HeadlessProfile.FIXTURE_TEST_ONLY,
            candidate_digest=stable_hash(candidate),
            candidate=candidate,
        )

    def prepare_task_confirmation(
        self, workspace_handle: str, candidate: TaskSpecCandidate
    ) -> AuthorizationChallenge:
        config = self._workspace(workspace_handle)
        if not candidate.ready_for_confirmation:
            raise rejected("CANDIDATE_NOT_READY", "Task candidate still has missing fields or ambiguities.")
        content_digest = stable_hash(candidate)
        digest = self._authorization_digest(
            workspace_handle=workspace_handle,
            action=AuthorizationAction.CONFIRM_TASK,
            content_digest=content_digest,
        )
        return self._authorization(config, workspace_handle).create(
            action=AuthorizationAction.CONFIRM_TASK,
            payload_digest=digest,
            payload={"candidate": candidate.model_dump(mode="json"), "content_digest": content_digest},
            summary=f"Confirm immutable task candidate {content_digest}.",
        )

    def confirm_task(self, workspace_handle: str, challenge_id: str) -> ConfirmedTaskView:
        config = self._workspace(workspace_handle)
        store = self._authorization(config, workspace_handle)
        stored = store.require_approved(challenge_id, AuthorizationAction.CONFIRM_TASK)
        if stored.challenge.authorization_state is AuthorizationState.CONSUMED:
            return ConfirmedTaskView.model_validate({**stored.result, "idempotent_replay": True})
        candidate = TaskSpecCandidate.model_validate(stored.payload["candidate"])
        content_digest = stable_hash(candidate)
        expected_digest = self._authorization_digest(
            workspace_handle=workspace_handle,
            action=AuthorizationAction.CONFIRM_TASK,
            content_digest=content_digest,
        )
        if content_digest != stored.payload.get("content_digest") or expected_digest != stored.challenge.payload_digest:
            raise rejected("CHALLENGE_PAYLOAD_MISMATCH", "Task candidate no longer matches its authorization.")
        repository = self._repository(config)
        confirmed_at = stored.approved_at or datetime.now(UTC)
        deterministic_id = challenge_id.removeprefix("ch_")
        ai_service = self._ai_service(config)
        task = ai_service.confirm_task(
            candidate, task_id=f"task-{deterministic_id}", confirmed_at=confirmed_at
        )
        try:
            repository.add_task(task)
        except RepositoryStateError:
            if repository.get_task(task.task_id).task != task:
                raise rejected("TASK_ID_CONFLICT", "Authorized task conflicts with stored workspace state.") from None
        view = ConfirmedTaskView(
            workspace_handle=workspace_handle,
            profile=config.profile,
            fixture_test_only=config.profile is HeadlessProfile.FIXTURE_TEST_ONLY,
            task_id=task.task_id,
            spec_hash=task.spec_hash,
            idempotent_replay=False,
        )
        store.consume(challenge_id, view.model_dump(mode="json"))
        return view

    def prepare_report_verification(
        self, workspace_handle: str, task_id: str, report_json: str
    ) -> AuthorizationChallenge:
        config = self._workspace(workspace_handle)
        payload = report_json.encode("utf-8")
        parse_report(payload)
        repository = self._repository(config)
        try:
            stored_task = repository.get_task(task_id)
        except KeyError:
            raise rejected("UNKNOWN_TASK", "Task is not present in this workspace.") from None
        status = self._attempt_status(config, repository, task_id)
        if status.next_attempt is None:
            reason = status.blocking_reason.value if status.blocking_reason is not None else "STATE_CONFLICT"
            raise rejected("ATTEMPT_NOT_ALLOWED", f"Attempt is blocked by persisted state: {reason}.")
        attempt = status.next_attempt
        from trust_receipt.hashing import content_hash

        content_digest = content_hash(payload)
        digest = self._authorization_digest(
            workspace_handle=workspace_handle,
            action=AuthorizationAction.VERIFY_REPORT,
            content_digest=content_digest,
            task_id=task_id,
            task_spec_hash=stored_task.task.spec_hash,
            attempt=attempt,
        )
        return self._authorization(config, workspace_handle).create(
            action=AuthorizationAction.VERIFY_REPORT,
            payload_digest=digest,
            payload={
                "task_id": task_id,
                "task_spec_hash": stored_task.task.spec_hash,
                "report_json": report_json,
                "content_digest": content_digest,
            },
            summary=f"Verify report {content_digest} as attempt {attempt} for task {task_id}.",
            task_id=task_id,
            task_spec_hash=stored_task.task.spec_hash,
            attempt=attempt,
        )

    def verify_report(self, workspace_handle: str, challenge_id: str) -> AttemptResultView:
        config = self._workspace(workspace_handle)
        store = self._authorization(config, workspace_handle)
        stored = store.require_approved(challenge_id, AuthorizationAction.VERIFY_REPORT)
        if stored.challenge.authorization_state is AuthorizationState.CONSUMED:
            if "spec_hash" not in stored.result:
                return self.get_result(
                    workspace_handle,
                    stored.result["task_id"],
                    stored.result["attempt"],
                )
            return AttemptResultView.model_validate({**stored.result, "idempotent_replay": True})
        payload = stored.payload["report_json"].encode("utf-8")
        from trust_receipt.hashing import content_hash

        content_digest = content_hash(payload)
        expected_digest = self._authorization_digest(
            workspace_handle=workspace_handle,
            action=AuthorizationAction.VERIFY_REPORT,
            content_digest=content_digest,
            task_id=stored.payload["task_id"],
            task_spec_hash=stored.payload["task_spec_hash"],
            attempt=stored.challenge.attempt,
        )
        if content_digest != stored.payload.get("content_digest") or expected_digest != stored.challenge.payload_digest:
            raise rejected("CHALLENGE_PAYLOAD_MISMATCH", "Report no longer matches its authorization.")
        task_id = stored.payload["task_id"]
        repository = self._repository(config)
        current_task = repository.get_task(task_id).task
        if (
            current_task.spec_hash != stored.payload["task_spec_hash"]
            or current_task.spec_hash != stored.challenge.task_spec_hash
        ):
            raise rejected("TASK_SCOPE_CHANGED", "Confirmed task scope no longer matches its authorization.")
        status = self._attempt_status(config, repository, task_id)
        if status.next_attempt != stored.challenge.attempt:
            raise rejected("ATTEMPT_STATE_CHANGED", "Workspace attempt state changed after authorization.")
        workflow = self._workflow(
            config,
            repository,
            id_factory=lambda: challenge_id.removeprefix("ch_"),
            clock=lambda: stored.approved_at or datetime.now(UTC),
        )
        service = UploadedReportService(payload, private_directory=config.directory / "uploads")

        def require_authorized_attempt(reserved_attempt: int) -> None:
            if reserved_attempt != stored.challenge.attempt:
                raise RepositoryStateError("reserved attempt does not match the authorization challenge")

        try:
            execution = workflow.run_attempt(task_id, service, pre_submit=require_authorized_attempt)
        except RepositoryStateError:
            raise rejected(
                "ATTEMPT_STATE_CHANGED", "Another request reserved or changed this workspace attempt."
            ) from None
        view = self._execution_view(workspace_handle, config, execution, idempotent=False)
        store.consume(challenge_id, view.model_dump(mode="json"))
        return view

    def get_result(self, workspace_handle: str, task_id: str, attempt: int) -> AttemptResultView:
        config = self._workspace(workspace_handle)
        record = self._attempt(config, task_id, attempt)
        receipt = self._load_receipt(config, task_id, attempt)
        result = record.verification_result
        if result is None or result != receipt.verification_result:
            raise rejected("INCOMPLETE_ATTEMPT", "Attempt has no consistent verification result.")
        return self._result_view(workspace_handle, config, record.submission.attempt, receipt, idempotent=True)

    def get_receipt(self, workspace_handle: str, task_id: str, attempt: int) -> ReceiptView:
        config = self._workspace(workspace_handle)
        self._attempt(config, task_id, attempt)
        receipt = self._load_receipt(config, task_id, attempt)
        return ReceiptView(
            workspace_handle=workspace_handle,
            profile=config.profile,
            fixture_test_only=config.profile is HeadlessProfile.FIXTURE_TEST_ONLY,
            task_id=task_id,
            attempt=attempt,
            receipt=receipt,
        )

    def replay_receipt(self, workspace_handle: str, task_id: str, attempt: int) -> ReceiptReplayView:
        config = self._workspace(workspace_handle)
        self._attempt(config, task_id, attempt)
        receipt = self._load_receipt(config, task_id, attempt)
        replay = replay_receipt(receipt)
        return ReceiptReplayView(
            workspace_handle=workspace_handle,
            profile=config.profile,
            fixture_test_only=config.profile is HeadlessProfile.FIXTURE_TEST_ONLY,
            task_id=task_id,
            attempt=attempt,
            receipt_hash=receipt.receipt_hash,
            spec_hash=receipt.task_spec.spec_hash,
            recorded_outcome=replay.recorded_outcome,
            recomputed_outcome=replay.recomputed_outcome,
            links_valid=replay.links_valid,
            valid=replay.valid,
        )

    def _workspace(self, handle: str) -> WorkspaceConfig:
        try:
            return self._registry.get(handle)
        except KeyError:
            raise rejected("UNKNOWN_WORKSPACE", "Unknown workspace handle.") from None

    @staticmethod
    def _repository(config: WorkspaceConfig) -> SQLiteRepository:
        return SQLiteRepository(config.directory / "workspace.db")

    @staticmethod
    def _authorization(config: WorkspaceConfig, handle: str) -> AuthorizationStore:
        return AuthorizationStore(config.directory / "authorization.db", handle)

    def _workflow(self, config: WorkspaceConfig, repository, *, id_factory, clock) -> M5Workflow:
        return M5Workflow(
            repository=repository,
            evidence_provider=self._evidence_provider(config),
            ai_service=self._ai_service(config),
            receipt_directory=config.directory / "receipts",
            id_factory=id_factory,
            clock=clock,
        )

    @staticmethod
    def _attempt_status(config: WorkspaceConfig, repository, task_id: str):
        read_only = M5Workflow(
            repository=repository,
            evidence_provider=None,
            ai_service=None,
            receipt_directory=config.directory / "receipts",
        )
        return read_only.get_attempt_status(task_id)

    @staticmethod
    def _authorization_digest(
        *,
        workspace_handle: str,
        action: AuthorizationAction,
        content_digest: str,
        task_id: str | None = None,
        task_spec_hash: str | None = None,
        attempt: int | None = None,
    ) -> str:
        return stable_hash(
            {
                "interface_version": "1.0",
                "workspace_handle": workspace_handle,
                "action": action.value,
                "content_digest": content_digest,
                "task_id": task_id,
                "task_spec_hash": task_spec_hash,
                "attempt": attempt,
            }
        )

    @staticmethod
    def _fixture(config: WorkspaceConfig):
        return load_vertical_demo_fixture(config.project_root)

    def _ai_service(self, config: WorkspaceConfig) -> RestrictedAIService:
        if config.ai_provider == "fixture":
            return RestrictedAIService(
                OfflineDemoStructuredOutputAdapter(candidate_from_fixture(self._fixture(config)))
            )
        settings = M4AISettings.load(config.project_root / ".env")
        if config.ai_provider == "openai":
            missing = settings.missing_for_openai()
            if missing:
                raise blocked("MODEL_CONFIGURATION_MISSING", "Live model configuration is incomplete.")
            adapter = OpenAIStructuredOutputAdapter(
                api_key=settings.api_key_value(),
                model_name=settings.model_name or "",
                timeout_seconds=settings.timeout_seconds,
                max_retries=settings.max_retries,
            )
        else:
            missing = settings.missing_for_deepseek()
            if missing:
                raise blocked("MODEL_CONFIGURATION_MISSING", "Live model configuration is incomplete.")
            adapter = DeepSeekStructuredOutputAdapter(
                api_key=settings.deepseek_api_key_value(),
                model_name=settings.deepseek_model_name or "",
                timeout_seconds=settings.timeout_seconds,
                max_retries=settings.max_retries,
            )
        return RestrictedAIService(adapter)

    def _evidence_provider(self, config: WorkspaceConfig):
        if config.evidence_provider == "fixture":
            return StaticEvidenceProvider(evidence_from_fixture(self._fixture(config)))
        settings = M0Settings.load(config.project_root / ".env")
        if settings.rpc_url is None:
            raise blocked("RPC_CONFIGURATION_MISSING", "Live read-only RPC configuration is missing.")
        return RpcReferenceEvidenceProvider(
            settings.rpc_url_value(),
            expected_chain_id=settings.chain_id,
            timeout_seconds=settings.rpc_timeout_seconds,
            confirmations=settings.rpc_confirmations,
            blockscout_mcp_url=settings.blockscout_mcp_url,
            enable_blockscout_cross_check=settings.blockscout_pro_api_key is not None,
        )

    @staticmethod
    def _attempt(config: WorkspaceConfig, task_id: str, attempt: int):
        if isinstance(attempt, bool) or attempt not in (1, 2):
            raise rejected("INVALID_ATTEMPT", "Attempt must be 1 or 2.")
        try:
            return SQLiteRepository(config.directory / "workspace.db").get_attempt(task_id, attempt)
        except KeyError:
            raise rejected("UNKNOWN_ATTEMPT", "Attempt is not present in this workspace.") from None

    @staticmethod
    def _load_receipt(config: WorkspaceConfig, task_id: str, attempt: int):
        target = (config.directory / "receipts" / task_id / f"attempt-{attempt}.json").resolve()
        receipt_root = (config.directory / "receipts").resolve()
        if not target.is_relative_to(receipt_root) or not target.is_file():
            raise rejected("RECEIPT_NOT_FOUND", "Receipt is not present in this workspace.")
        return load_receipt(target)

    def _execution_view(self, handle, config, execution, *, idempotent):
        return self._result_view(
            handle,
            config,
            execution.submission.attempt,
            execution.receipt,
            idempotent=idempotent,
            diagnostics=execution.evidence_diagnostics,
        )

    @staticmethod
    def _result_view(handle, config, attempt, receipt, *, idempotent, diagnostics=()):
        result = receipt.verification_result
        safe_diagnostics = tuple(
            {
                "source_id": item.source_id,
                "source": item.source.value,
                "role": item.role,
                "status": item.status,
                "page_count": item.page_count,
                "record_count": item.record_count,
                "detail": (
                    "Independent reference read was incomplete."
                    if item.status in {"INCOMPLETE", "DEGRADED"}
                    else item.detail
                ),
            }
            for item in diagnostics
        )
        return AttemptResultView(
            workspace_handle=handle,
            profile=config.profile,
            fixture_test_only=config.profile is HeadlessProfile.FIXTURE_TEST_ONLY,
            task_id=result.task_id,
            spec_hash=receipt.task_spec.spec_hash,
            submission_id=result.submission_id,
            attempt=attempt,
            outcome=result.outcome,
            reference_complete=result.reference_complete,
            evidence_sufficient=result.evidence_sufficient,
            calculated_total_base_units=result.calculated_total_base_units,
            calculated_count=result.calculated_count,
            inconclusive_reason=result.inconclusive_reason,
            findings=tuple(
                AttemptFindingView(
                    finding_id=item.finding_id,
                    finding_type=item.finding_type.value,
                    severity=item.severity.value,
                    violated_rule=item.violated_rule,
                    evidence_refs=item.evidence_refs,
                )
                for item in result.findings
            ),
            evidence_diagnostics=safe_diagnostics,
            receipt_hash=receipt.receipt_hash,
            idempotent_replay=idempotent,
        )


def safe_error_payload(error: Exception) -> dict:
    if isinstance(error, HeadlessError):
        return {"ok": False, "status": error.status, "code": error.code, "reason": error.safe_message}
    if isinstance(error, (TypeError, ValueError)):
        return {
            "ok": False,
            "status": "REJECTED",
            "code": "INVALID_INPUT",
            "reason": "Input does not satisfy the strict headless contract.",
        }
    return {
        "ok": False,
        "status": "INCONCLUSIVE",
        "code": "HEADLESS_OPERATION_FAILED",
        "reason": "The operation failed without exposing private configuration or report content.",
    }
