"""
POST /pay - Stage 6 decision -> wallet debit, backed by the mocked Razorpay
flow (Stage 9). Every call re-runs verification against a freshly uploaded
scan (a kiosk always re-scans, including the PIN-confirmation follow-up call).

Tier behavior:
  auto_approve             -> mock order created + captured, wallet debited immediately.
  pin_required, no confirm -> mock order created (status 'pending_pin'), NOT debited;
                               response tells the client to re-call with pin_confirmed=true.
  pin_required, confirmed  -> mock order created + captured, wallet debited.
  deny                     -> no order captured, no debit.

A simple insufficient-balance guard is included (a wallet debit should never
push a balance negative) - this is a minimal correctness check, not the
production-grade error handling explicitly out of scope for this MVP.
"""
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import database
from ..models.decision import DecisionTier
from ..services import razorpay_mock_service
from ..utils import resolve_side, save_upload_to_tmp
from ..verification import verify_scan

router = APIRouter()


@router.post("/pay")
async def pay(
    user_id: str = Form(...),
    txn_ref: str = Form(...),
    amount: float = Form(...),
    file: UploadFile = File(...),
    pin_confirmed: bool = Form(False),
    side: Optional[str] = Form(None),
):
    if database.get_user(user_id) is None:
        raise HTTPException(404, f"user '{user_id}' is not enrolled")
    if amount <= 0:
        raise HTTPException(400, "amount must be positive")

    resolved_side = resolve_side(file.filename, side)
    tmp_path = await save_upload_to_tmp(file)
    try:
        result = verify_scan(user_id, str(tmp_path), resolved_side)
    except ValueError as e:
        raise HTTPException(422, f"Could not process scan: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    tier = result.decision.tier
    should_attempt_debit = tier == DecisionTier.AUTO_APPROVE or (
        tier == DecisionTier.PIN_REQUIRED and pin_confirmed
    )

    order = razorpay_mock_service.create_order(amount)
    reasoning = f"{result.decision.reasoning} (ear detection: {result.ear_detection_path})"
    payment_status = "denied"
    new_balance = database.get_balance(user_id)
    response_status = tier.value

    if should_attempt_debit:
        if new_balance < amount:
            payment_status = "failed"
            response_status = "insufficient_funds"
            reasoning += f" Debit skipped: balance {new_balance:.2f} < amount {amount:.2f}."
        else:
            razorpay_mock_service.capture_payment(order["id"])
            new_balance = database.debit_wallet(user_id, amount)
            payment_status = "captured"
            reasoning += f" Wallet debited {amount:.2f}; new balance {new_balance:.2f}."
    elif tier == DecisionTier.PIN_REQUIRED:
        payment_status = "pending_pin"
        reasoning += " Awaiting simulated PIN confirmation before debit."
    else:
        reasoning += " No debit performed."

    database.record_payment(
        txn_ref=txn_ref, mock_order_id=order["id"], amount=amount, status=payment_status
    )
    database.log_event(
        user_id=user_id,
        event_type="payment",
        txn_ref=txn_ref,
        match_score=result.score,
        high_threshold=result.decision.high_threshold,
        med_threshold=result.decision.med_threshold,
        decision_tier=tier.value,
        comparison_mode=result.comparison_mode,
        reasoning=reasoning,
    )

    return {
        "user_id": user_id,
        "txn_ref": txn_ref,
        "match_score": result.score,
        "decision_tier": tier.value,
        "status": response_status,
        "payment_status": payment_status,
        "mock_order_id": order["id"],
        "comparison_mode": result.comparison_mode,
        "wallet_balance": new_balance,
        "reasoning": reasoning,
    }
