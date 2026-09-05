"""GET /audit-log - every enroll/verify/payment/recharge decision, most recent first."""
from fastapi import APIRouter, Query

from .. import database

router = APIRouter()


@router.get("/audit-log")
async def audit_log(limit: int = Query(100, ge=1, le=1000)):
    return {"entries": database.get_audit_log(limit=limit)}
