"""
Stage 9 - Dummy/mocked Razorpay integration.

No real Razorpay API calls are made anywhere in this MVP (see Non-Goals).
This module's function signatures are deliberately shaped to mirror the real
`razorpay` Python SDK's Orders API:

    import razorpay
    client = razorpay.Client(auth=(key_id, key_secret))
    order = client.order.create({"amount": amount, "currency": "INR", ...})
    payment = client.payment.capture(payment_id, amount)

so that swapping this module for `razorpay.Client(...)` calls later is a
localized change (new client + real credentials) rather than a rewrite of
every call site. That swap is NOT done here - this is intentionally mock-only.
"""
import uuid


def create_order(amount: float, currency: str = "INR") -> dict:
    """Mirrors `client.order.create(...)` - fabricates an order, no network call."""
    return {
        "id": f"mock_order_{uuid.uuid4().hex[:12]}",
        "amount": amount,
        "currency": currency,
        "status": "created",
    }


def capture_payment(order_id: str) -> dict:
    """Mirrors `client.payment.capture(...)` - always "succeeds" for this MVP;
    there is no failure-injection path since there's no real gateway behind it."""
    return {
        "order_id": order_id,
        "status": "captured",
    }
