"""
Stage 6 - Confidence-gated decision logic.

A flat yes/no biometric match was flagged early on as unsafe to fully trust
with a financial decision on its own (see Technical Documentation section 7).
This module implements the three-tier gate instead:

  score >= HIGH_THRESHOLD           -> auto_approve  (debit immediately)
  MED_THRESHOLD <= score < HIGH     -> pin_required   (simulated PIN gate)
  score < MED_THRESHOLD             -> deny           (no debit)

This is pure decision logic with no I/O - it takes a score and thresholds and
returns a structured, human-readable decision. Callers (routers) are
responsible for writing the result to the audit log.
"""
from dataclasses import dataclass
from enum import Enum

from .. import config


class DecisionTier(str, Enum):
    AUTO_APPROVE = "auto_approve"
    PIN_REQUIRED = "pin_required"
    DENY = "deny"


@dataclass
class Decision:
    tier: DecisionTier
    score: float
    high_threshold: float
    med_threshold: float
    reasoning: str


def decide(score: float, high_threshold: float = None, med_threshold: float = None) -> Decision:
    high = config.HIGH_THRESHOLD if high_threshold is None else high_threshold
    med = config.MED_THRESHOLD if med_threshold is None else med_threshold

    if score >= high:
        tier = DecisionTier.AUTO_APPROVE
        reasoning = (
            f"Match score {score:.4f} >= high threshold {high:.2f} -> "
            "auto-approved, wallet debited immediately."
        )
    elif score >= med:
        tier = DecisionTier.PIN_REQUIRED
        reasoning = (
            f"Match score {score:.4f} in [{med:.2f}, {high:.2f}) -> "
            "moderate confidence, simulated PIN confirmation required before debit."
        )
    else:
        tier = DecisionTier.DENY
        reasoning = (
            f"Match score {score:.4f} < med threshold {med:.2f} -> "
            "denied, no debit."
        )

    return Decision(tier=tier, score=score, high_threshold=high, med_threshold=med, reasoning=reasoning)
