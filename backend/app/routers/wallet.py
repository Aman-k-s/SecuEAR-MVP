"""Stage 9 - wallet recharge (via the mocked Razorpay flow) and balance lookup."""
from fastapi import APIRouter, Form, HTTPException

from .. import database
from ..services import razorpay_mock_service

router = APIRouter()


@router.post("/wallet/recharge")
async def recharge(user_id: str = Form(...), amount: float = Form(...)):
    if database.get_user(user_id) is None:
        raise HTTPException(404, f"user '{user_id}' is not enrolled")
    if amount <= 0:
        raise HTTPException(400, "amount must be positive")

    order = razorpay_mock_service.create_order(amount)
    capture = razorpay_mock_service.capture_payment(order["id"])

    if capture["status"] != "captured":
        raise HTTPException(502, "mock payment capture failed")  # unreachable in this MVP - see service docstring

    new_balance = database.credit_wallet(user_id, amount)
    database.record_payment(
        txn_ref=f"recharge_{order['id']}", mock_order_id=order["id"], amount=amount, status="captured"
    )
    database.log_event(
        user_id=user_id,
        event_type="recharge",
        reasoning=f"Wallet recharged by {amount:.2f} via mock Razorpay order {order['id']}; new balance {new_balance:.2f}.",
    )
    return {"user_id": user_id, "amount": amount, "mock_order_id": order["id"], "wallet_balance": new_balance}


@router.get("/wallet/{user_id}")
async def get_wallet(user_id: str):
    balance = database.get_balance(user_id)
    if balance is None:
        raise HTTPException(404, f"user '{user_id}' is not enrolled")
    return {"user_id": user_id, "wallet_balance": balance}
