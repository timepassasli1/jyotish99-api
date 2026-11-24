"""Startup ops data: promos, flags, pushes, audit, support notes, bans."""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

PROMOS: List[Dict[str, Any]] = []
FEATURE_FLAGS: Dict[str, Any] = {
    # DEMO defaults — agent-set for local testing / showcase
    "paywall_enabled": False,
    "₹1_trial_enabled": True,
    "tarot_enabled": True,
    "kundli_enabled": True,
    "stories_enabled": True,
    "family_profiles_enabled": True,
    "chat_rich_blocks": True,
    "astro_coach_enabled": True,
    "force_update": False,
    "web_pwa_install_prompt": True,
    "demo_mode": True,
}
PUSH_CAMPAIGNS: List[Dict[str, Any]] = []
AUDIT_LOG: List[Dict[str, Any]] = []
SUPPORT_NOTES: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> notes
BANNED: Dict[str, Dict[str, Any]] = {}  # user_id -> {reason, at}
ANNOUNCEMENTS: List[Dict[str, Any]] = []
WEBHOOKS: List[Dict[str, Any]] = []


def audit(actor: str, action: str, detail: Optional[Dict[str, Any]] = None) -> None:
    AUDIT_LOG.insert(
        0,
        {
            "id": str(uuid.uuid4()),
            "ts": int(time.time() * 1000),
            "actor": actor,
            "action": action,
            "detail": detail or {},
        },
    )
    del AUDIT_LOG[500:]


def seed_ops_defaults() -> None:
    if not PROMOS:
        PROMOS.extend(
            [
                {
                    "id": "promo_welcome50",
                    "code": "WELCOME50",
                    "type": "percent",
                    "value": 50,
                    "maxRedemptions": 1000,
                    "redeemed": 12,
                    "active": True,
                    "appliesTo": ["plus", "pro"],
                    "expiresAt": None,
                    "note": "New user 50% off Plus/Pro",
                },
                {
                    "id": "promo_trial1",
                    "code": "ASTRO1",
                    "type": "fixed",
                    "value": 0,
                    "maxRedemptions": 5000,
                    "redeemed": 84,
                    "active": True,
                    "appliesTo": ["trial1"],
                    "expiresAt": None,
                    "note": "Marketing free trial code",
                },
            ]
        )
    if not ANNOUNCEMENTS:
        ANNOUNCEMENTS.append(
            {
                "id": "ann_1",
                "title": "Diwali special live",
                "body": "₹1 trial + extra remedies this week",
                "active": True,
                "placement": "home_banner",
                "createdAt": int(time.time() * 1000),
            }
        )
    if not WEBHOOKS:
        WEBHOOKS.append(
            {
                "id": "wh_slack",
                "url": "",
                "events": ["purchase", "signup", "refund"],
                "active": False,
                "note": "Slack / Discord ops webhook",
            }
        )


def seed_demo_users() -> None:
    """Populate realistic demo traffic so admin dashboard isn't empty after restart."""
    from app import db

    if len(db.USERS) >= 5:
        return

    demo = [
        ("9810010001", "Ananya Sharma", True, "trial1", 3, False),
        ("9810010002", "Rohan Mehta", True, "plus", 40, False),
        ("9810010003", "Priya Nair", False, None, 5, False),
        ("9810010004", "Vikram Singh", True, "pro", 120, True),
        ("9810010005", "Sneha Kapoor", False, None, 5, True),
        ("9810010006", "Amit Joshi", True, "trial1", 8, False),
        ("9810010007", "Blocked User", False, None, 0, True),
        ("9810010008", "Kavita Rao", True, "plus", 15, False),
    ]
    now = int(time.time() * 1000)
    for i, (phone, name, premium, plan, used, banned) in enumerate(demo):
        if phone in db.USERS:
            continue
        uid = f"demo-user-{i+1}"
        user = {
            "id": uid,
            "phone": phone,
            "name": name,
            "gender": "female" if i % 2 == 0 else "male",
            "dob": "1994-05-12",
            "birthTime": "10:30",
            "birthTimeUnknown": False,
            "place": "Delhi, India",
            "marriageStatus": "single",
            "occupation": "Professional",
            "photoUrl": None,
            "language": "hi" if i % 2 else "en",
            "onboardingComplete": True,
            "paymentGateSeen": True,
            "notificationPromptSeen": True,
            "createdAt": now - (i + 1) * 86400000,
        }
        db.USERS[phone] = user
        db.reset_user_runtime(uid)
        q = db.QUOTAS[uid]
        q["used"] = used
        if premium and plan == "pro":
            q["is_premium"] = True
            q["unlimited"] = True
            q["limit"] = 999999
        elif premium:
            q["is_premium"] = True
            q["unlimited"] = False
            q["limit"] = 200 if plan == "plus" else 200
        else:
            q["limit"] = db.FREE_MESSAGE_LIMIT
        if premium and plan:
            db.MEMBERSHIPS[uid] = {
                "active": True,
                "plan_id": plan,
                "order_id": f"ord_demo_{i+1}",
                "autopay": True,
                "upiId": f"{name.split()[0].lower()}@ybl",
                "autoRenew": True,
                "renewPrice": 199 if plan == "trial1" else (299 if plan == "plus" else 699),
            }
            plan_obj = next((p for p in db.PLANS if p["id"] == plan), None)
            amount = (plan_obj or {}).get("price") or 1
            oid = f"ord_demo_{i+1}"
            db.ORDERS[oid] = {
                "orderId": oid,
                "planId": plan,
                "amount": amount,
                "currency": "INR",
                "status": "paid",
                "method": "upi",
                "upiAppId": "gpay",
                "upiId": f"{name.split()[0].lower()}@ybl",
                "autopay": True,
                "userId": uid,
                "createdAt": now - (i + 1) * 86000000,
                "paidAt": now - (i + 1) * 85900000,
                "gateway": "mock_cashfree_autopay",
            }
        # sample chat
        db.CHATS[uid] = {
            "1": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "text": "Namaste, aapka sawaal poochiye.",
                    "timestamp": now - 50000,
                },
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "text": "Career ke baare mein batao",
                    "timestamp": now - 40000,
                },
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "text": "Agle 21 din career ke liye favourable hain. Peela kapda pehne.",
                    "timestamp": now - 30000,
                    "blocks": [{"type": "text", "text": "Agle 21 din career ke liye favourable hain."}],
                },
            ]
        }
        SUPPORT_NOTES.setdefault(uid, []).append(
            {
                "id": str(uuid.uuid4()),
                "ts": now - 10000,
                "author": "support",
                "text": "VIP — prefers Hindi replies" if premium else "Free user — nudge trial",
            }
        )
        if banned or phone.endswith("0007"):
            BANNED[uid] = {"reason": "Abuse reports", "at": now - 20000}

    if not PUSH_CAMPAIGNS:
        PUSH_CAMPAIGNS.append(
            {
                "id": "push_1",
                "title": "Pandit ji waiting",
                "body": "Aapka free message limit reset — aaj sawaal poocho",
                "segment": "free_users",
                "status": "sent",
                "sentAt": now - 3600000,
                "delivered": 420,
                "opened": 118,
            }
        )
