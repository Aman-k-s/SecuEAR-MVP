"""POST /verify - Stages 2-4+6: compare a fresh scan against an enrolled
embedding and return the tiered decision. Does NOT touch the wallet - that's
/pay's job. Every call (all three tiers) is logged to the audit table."""
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import database
from ..utils import resolve_side, save_upload_to_tmp
from ..verification import verify_scan

router = APIRouter()


@router.post("/verify")
async def verify(
    user_id: str = Form(...),
    txn_ref: str = Form(...),
    file: UploadFile = File(...),
    side: Optional[str] = Form(None),
):
    if database.get_user(user_id) is None:
        raise HTTPException(404, f"user '{user_id}' is not enrolled")

    resolved_side = resolve_side(file.filename, side)
    tmp_path = await save_upload_to_tmp(file)
    try:
        result = verify_scan(user_id, str(tmp_path), resolved_side)
    except ValueError as e:
        raise HTTPException(422, f"Could not process scan: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    database.log_event(
        user_id=user_id,
        event_type="verify",
        txn_ref=txn_ref,
        match_score=result.score,
        high_threshold=result.decision.high_threshold,
        med_threshold=result.decision.med_threshold,
        decision_tier=result.decision.tier.value,
        comparison_mode=result.comparison_mode,
        reasoning=f"{result.decision.reasoning} (ear detection: {result.ear_detection_path})",
    )

    return {
        "user_id": user_id,
        "txn_ref": txn_ref,
        "match_score": result.score,
        "decision_tier": result.decision.tier.value,
        "comparison_mode": result.comparison_mode,
        "high_threshold": result.decision.high_threshold,
        "med_threshold": result.decision.med_threshold,
        "reasoning": result.decision.reasoning,
        "ear_detection_path": result.ear_detection_path,
    }
