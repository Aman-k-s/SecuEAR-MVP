"""
Core verification logic (Stage 4 comparison + Stage 6 decision) shared by the
`/verify` and `/pay` routers, so both run the exact same match/decision path.
"""
from dataclasses import dataclass

from . import database
from .models import decision as decision_model
from .models import embedding as embedding_model
from .services import pipeline


@dataclass
class VerificationResult:
    score: float
    decision: decision_model.Decision
    comparison_mode: str
    ear_detection_path: str


def verify_scan(user_id: str, ply_path: str, side: str) -> VerificationResult:
    """Runs Stages 2-4 on `ply_path` and compares it to `user_id`'s enrolled
    embedding, applying the Stage 4 cross-side mirroring rule as needed, then
    the Stage 6 tiered decision."""
    stored = database.get_user_embedding(user_id)
    if stored is None:
        raise LookupError(f"user '{user_id}' is not enrolled")
    enrolled_embedding, enrolled_side = stored

    scan_result = pipeline.process_scan_to_depth_map(ply_path, side)
    embedding, comparison_mode = embedding_model.extract_embedding_for_verification(
        scan_result.depth_map, scan_side=side, enrolled_side=enrolled_side
    )

    score = embedding_model.cosine_similarity(embedding, enrolled_embedding)
    decision = decision_model.decide(score)

    return VerificationResult(
        score=score,
        decision=decision,
        comparison_mode=comparison_mode.value,
        ear_detection_path=scan_result.ear_detection_path,
    )
