"""Pure, provider-independent verification of ERC-20 report submissions."""

from trust_receipt.verification.engine import verify_submission
from trust_receipt.verification.evidence import ReferenceEvidence, ReferencePage, ReferenceStream

__all__ = ["ReferenceEvidence", "ReferencePage", "ReferenceStream", "verify_submission"]
