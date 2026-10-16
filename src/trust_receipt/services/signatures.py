"""EVM-compatible signatures over immutable service report hashes."""

from eth_account import Account
from eth_account.messages import encode_defunct

from trust_receipt.models.submissions import ServiceSubmission


def _message(report_hash: str):
    return encode_defunct(hexstr=report_hash)


def sign_report_hash(report_hash: str, private_key: str) -> str:
    return Account.sign_message(_message(report_hash), private_key=private_key).signature.to_0x_hex()


def recover_submission_signer(submission: ServiceSubmission) -> str | None:
    if submission.signature is None:
        return None
    try:
        return Account.recover_message(_message(submission.report_hash), signature=submission.signature)
    except (ValueError, TypeError):
        return None


def verify_submission_signature(submission: ServiceSubmission, expected_signer: str) -> bool:
    recovered = recover_submission_signer(submission)
    return recovered is not None and recovered.lower() == expected_signer.lower()
