from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import db
from app.deps import current_user
from app.persist import touch as persist_touch

router = APIRouter(prefix="/payments", tags=["payments"])

UPI_APPS: List[Dict[str, Any]] = [
    {"id": "gpay", "name": "Google Pay", "package": "com.google.android.apps.nbu.paisa.user"},
    {"id": "phonepe", "name": "PhonePe", "package": "com.phonepe.app"},
    {"id": "paytm", "name": "Paytm", "package": "net.one97.paytm"},
    {"id": "bhim", "name": "BHIM UPI", "package": "in.org.npci.upiapp"},
]


class CreateOrderBody(BaseModel):
    planId: str
    method: str = "upi"
    upiAppId: Optional[str] = None
    upiId: Optional[str] = None
    autopay: bool = True
    promoCode: Optional[str] = None


@router.get("/plans")
def plans(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    enriched = []
    for p in db.PLANS:
        row = dict(p)
        row.setdefault("autopay", True)
        row.setdefault(
            "autoRenewText",
            f"After plan ends, auto-renews · Cancel anytime. UPI Autopay enabled.",
        )
        enriched.append(row)
    return {
        "success": True,
        "plans": enriched,
        "upiApps": UPI_APPS,
        "upiHints": ["@oksbi", "@okaxis", "@ybl", "@paytm", "@ibl"],
        "autopayDefault": True,
        "policy": "Cancel anytime. Subscription auto-renews via UPI Autopay.",
    }

@router.get("/message-limit")
def message_limit(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {"success": True, "quota": db.snapshot_quota(user["id"])}


@router.post("/create-order")
def create_order(body: CreateOrderBody, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    plan = next((p for p in db.PLANS if p["id"] == body.planId), None)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    order_id = f"ord_{uuid.uuid4().hex[:12]}"
    upi_id = (body.upiId or "").strip().lower()
    if body.autopay and upi_id and "@" not in upi_id:
        raise HTTPException(status_code=400, detail="Enter a valid UPI ID (e.g. name@ybl)")
    amount = int(plan["price"])
    promo_applied = None
    code = (body.promoCode or "").strip().upper()
    if code:
        try:
            from app import ops_store as ops

            promo = next(
                (p for p in ops.PROMOS if str(p.get("code", "")).upper() == code and p.get("active", True)),
                None,
            )
            if not promo:
                raise HTTPException(status_code=400, detail="Invalid promo code")
            ptype = str(promo.get("type") or "percent").lower()
            val = int(promo.get("value") or 0)
            if ptype in {"percent", "pct"}:
                amount = max(0, int(amount * (100 - val) / 100))
            elif ptype in {"fixed", "flat"}:
                amount = max(0, amount - val)
            promo["redeemed"] = int(promo.get("redeemed") or 0) + 1
            promo_applied = {"code": code, "type": ptype, "value": val}
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Promo could not be applied")
    order = {
        "orderId": order_id,
        "planId": plan["id"],
        "amount": amount,
        "originalAmount": plan["price"],
        "currency": plan["currency"],
        "status": "created",
        "method": body.method,
        "upiAppId": body.upiAppId,
        "upiId": upi_id or None,
        "autopay": bool(body.autopay),
        "promo": promo_applied,
        "userId": user["id"],
        "createdAt": int(time.time() * 1000),
        "gateway": "mock_cashfree_autopay",
    }
    db.ORDERS[order_id] = order
    persist_touch()
    try:
        from app.tracking import send_capi_event

        send_capi_event(
            event_name="InitiateCheckout",
            user=user,
            custom_data={
                "currency": plan.get("currency") or "INR",
                "value": float(plan.get("price") or 0),
                "content_name": plan.get("name") or plan["id"],
                "content_ids": [plan["id"]],
            },
        )
    except Exception:  # noqa: BLE001
        pass
    return {
        "success": True,
        "order": order,
        "checkout": {
            "mode": "mock_autopay",
            "upiIntent": f"upi://pay?pa=astro99@upi&pn=Astro99&am={plan['price']}&cu=INR&tn={order_id}",
            "message": "UPI Autopay mandate mock — confirming creates subscription",
            "autopay": bool(body.autopay),
        },
    }


@router.post("/confirm/{order_id}")
def confirm_order(order_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    order = db.ORDERS.get(order_id)
    if not order or order["userId"] != user["id"]:
        raise HTTPException(status_code=404, detail="Order not found")
    plan = next((p for p in db.PLANS if p["id"] == order["planId"]), None)
    order["status"] = "paid"
    order["paidAt"] = int(time.time() * 1000)
    order["autopayStatus"] = "ACTIVE" if order.get("autopay") else "OFF"
    db.QUOTAS[user["id"]]["is_premium"] = True
    db.QUOTAS[user["id"]]["used"] = 0
    if plan and plan.get("unlimited"):
        db.QUOTAS[user["id"]]["limit"] = 999999
        db.QUOTAS[user["id"]]["unlimited"] = True
    else:
        db.QUOTAS[user["id"]]["limit"] = (plan.get("messages") if plan else None) or 200
        db.QUOTAS[user["id"]]["unlimited"] = False
    db.MEMBERSHIPS[user["id"]] = {
        "active": True,
        "plan_id": order["planId"],
        "order_id": order_id,
        "autopay": bool(order.get("autopay")),
        "upiId": order.get("upiId"),
        "autoRenew": bool(order.get("autopay")),
        "renewPrice": (
            plan.get("renewPrice")
            if plan and plan.get("renewPrice") is not None
            else (199 if plan and plan["id"] in {"trial", "trial1"} else plan["price"] if plan else 199)
        ),
    }
    try:
        from app.tracking import send_capi_event

        send_capi_event(
            event_name="Purchase",
            user=user,
            custom_data={
                "currency": order.get("currency") or "INR",
                "value": float(order.get("amount") or 0),
                "content_name": (plan or {}).get("name") or order.get("planId"),
                "content_ids": [order.get("planId")],
                "order_id": order_id,
            },
            event_id=f"purchase_{order_id}",
        )
        if order.get("autopay"):
            send_capi_event(
                event_name="Subscribe",
                user=user,
                custom_data={
                    "currency": order.get("currency") or "INR",
                    "value": float(order.get("amount") or 0),
                    "predicted_ltv": float(
                        db.MEMBERSHIPS[user["id"]].get("renewPrice") or order.get("amount") or 0
                    ),
                },
                event_id=f"subscribe_{order_id}",
            )
    except Exception:  # noqa: BLE001
        pass
    persist_touch()
    return {
        "success": True,
        "order": order,
        "membership": db.MEMBERSHIPS[user["id"]],
        "quota": db.snapshot_quota(user["id"]),
        "autopayDialog": {
            "title": "UPI AUTOPAY ENABLED",
            "subtitle": (
                f"Next renewal ₹{db.MEMBERSHIPS[user['id']]['renewPrice']} will be "
                f"auto-debited from {order.get('upiId') or 'your UPI'}. Cancel anytime."
                if order.get("autopay")
                else "One-time payment completed. Autopay was skipped."
            ),
        },
    }


@router.get("/status/{order_id}")
def payment_status(order_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    order = db.ORDERS.get(order_id)
    if not order or order["userId"] != user["id"]:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"success": True, "order": order, "membership": db.MEMBERSHIPS.get(user["id"])}
