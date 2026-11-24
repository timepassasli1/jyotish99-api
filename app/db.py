"""In-memory store for Astro99 demo API."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

# phone -> otp
OTPS: Dict[str, str] = {}

# token -> user dict
SESSIONS: Dict[str, Dict[str, Any]] = {}

USERS: Dict[str, Dict[str, Any]] = {}

# user_id -> list of family profiles
FAMILY: Dict[str, List[Dict[str, Any]]] = {}

# user_id -> chat_id -> messages
CHATS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

# user_id -> message quota
QUOTAS: Dict[str, Dict[str, Any]] = {}

# user_id -> membership
MEMBERSHIPS: Dict[str, Dict[str, Any]] = {}

# order_id -> order
ORDERS: Dict[str, Dict[str, Any]] = {}

PANDITS: List[Dict[str, Any]] = []
HOME_FEED: List[Dict[str, Any]] = []
PLANS: List[Dict[str, Any]] = []
HOROSCOPE: Dict[str, Any] = {}
ASTROLOGY: Dict[str, Any] = {}
STORIES: List[Dict[str, Any]] = []
TAROT_CARDS: List[Dict[str, Any]] = []
TAROT_SESSIONS: Dict[str, Dict[str, Any]] = {}
SUGGESTED_QUESTIONS: List[str] = []


# Free tier matches original MessageLimitData (server-driven); clone default = 5/day.
FREE_MESSAGE_LIMIT = 5


def _skip_paywall() -> bool:
    import os

    return os.environ.get("SKIP_PAYWALL", "0") == "1"


def reset_user_runtime(user_id: str) -> None:
    if user_id not in QUOTAS:
        QUOTAS[user_id] = {
            "used": 0,
            "limit": FREE_MESSAGE_LIMIT,
            "is_premium": False,
            "unlimited": False,
        }
    else:
        # Drop TEMP demo bump (50) back to original free tier when not premium
        if not QUOTAS[user_id].get("is_premium") and QUOTAS[user_id].get("limit", 0) > FREE_MESSAGE_LIMIT:
            if QUOTAS[user_id].get("limit") in {50}:
                QUOTAS[user_id]["limit"] = FREE_MESSAGE_LIMIT
    # Testing: recharge / message-limit off
    if _skip_paywall():
        QUOTAS[user_id]["unlimited"] = True
        QUOTAS[user_id]["is_premium"] = True
    if user_id not in CHATS:
        CHATS[user_id] = {}
    if user_id not in FAMILY:
        FAMILY[user_id] = []
    if user_id not in MEMBERSHIPS:
        MEMBERSHIPS[user_id] = {"active": False, "plan_id": None}
    if _skip_paywall():
        MEMBERSHIPS[user_id] = {
            **MEMBERSHIPS[user_id],
            "active": True,
            "plan_id": MEMBERSHIPS[user_id].get("plan_id") or "pro_unlimited",
        }


def get_user_by_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    return SESSIONS.get(token)


def snapshot_quota(user_id: str) -> Dict[str, Any]:
    reset_user_runtime(user_id)
    q = QUOTAS[user_id]
    used = q["used"]
    unlimited = bool(q.get("unlimited")) or _skip_paywall()
    limit = int(q.get("limit") or FREE_MESSAGE_LIMIT)
    remaining = 999999 if unlimited else max(0, limit - used)
    percent = 0 if unlimited else (100 if limit == 0 else min(100, int((used / limit) * 100)))
    return {
        "used": used,
        "limit": limit if not unlimited else None,
        "remaining": remaining if not unlimited else None,
        "unlimited": unlimited,
        "is_premium": q["is_premium"],
        "bottom_sheet": {
            "headerTitle": "Message limit",
            "headerBackgroundColor": "#F6F2E9",
            "progressBackgroundColor": "#E3D3BE",
            "progressColor": "#E0A92C",
            "progressPercent": percent,
            "remainingCountText": "∞" if unlimited else str(remaining),
            "remainingLabel": "unlimited messages" if unlimited else "messages left today",
            "usedText": "Unlimited" if unlimited else f"{used} used of {limit}",
            "dismissCta": {"label": "Maybe later", "action": "dismiss"},
            "transactionsCta": {"label": "Recharge", "action": "open_plans"},
        },
    }
