"""POST /enroll - Stages 1-4: ingest a scan, extract its embedding, store the
enrolled user and initialize their wallet at balance 0."""
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import database
from ..models import embedding as embedding_model
from ..services import pipeline
from ..utils import resolve_side, save_upload_to_tmp

router = APIRouter()


@router.post("/enroll")
async def enroll(
    user_id: str = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
    side: Optional[str] = Form(None),
):
    resolved_side = resolve_side(file.filename, side)
    tmp_path = await save_upload_to_tmp(file)
    try:
        scan_result = pipeline.process_scan_to_depth_map(str(tmp_path), resolved_side)
        emb = embedding_model.extract_embedding(scan_result.depth_map)
    except ValueError as e:
        raise HTTPException(422, f"Could not process scan: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    database.create_user(user_id=user_id, name=name, embedding=emb.tolist(), side=resolved_side)
    database.log_event(
        user_id=user_id,
        event_type="enroll",
        reasoning=(
            f"Enrolled '{name}' with {resolved_side}-ear scan "
            f"(ear detection: {scan_result.ear_detection_path}). Wallet initialized at balance 0."
        ),
    )
    return {
        "user_id": user_id,
        "name": name,
        "enrolled_side": resolved_side,
        "ear_detection_path": scan_result.ear_detection_path,
        "wallet_balance": database.get_balance(user_id),
    }
