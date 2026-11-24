"""Admin panel API — dashboard, users, orders, plans, Pixel/CAPI settings."""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from app import db
from app import ops_store as ops
from app.admin_auth import create_session, revoke_session, validate_session
from app.llm import provider_status
from app.persist import touch as persist_touch
from app.settings_store import admin_password, load_settings, public_tracking_config, save_settings
from app.tracking import EVENT_LOG, send_capi_event

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")) -> str:
    # Accept session token (preferred). Legacy: password only if it matches AND no sessions exist — disabled.
    if not x_admin_key or not validate_session(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session")
    return x_admin_key


def _mask_secret(value: Optional[str]) -> Dict[str, Any]:
    v = (value or "").strip()
    if not v:
        return {"set": False, "masked": ""}
    if len(v) <= 8:
        return {"set": True, "masked": "••••••••"}
    return {"set": True, "masked": v[:4] + "…" + v[-4:]}


def _public_settings_view() -> Dict[str, Any]:
    s = load_settings()
    capi = dict(s.get("capi") or {})
    tok_meta = _mask_secret(capi.get("accessToken"))
    capi.pop("accessToken", None)
    capi["accessTokenSet"] = tok_meta["set"]
    capi["accessTokenMasked"] = tok_meta["masked"]

    clevertap = dict(s.get("clevertap") or {})
    ct = _mask_secret(clevertap.get("token"))
    clevertap.pop("token", None)
    clevertap["tokenSet"] = ct["set"]
    clevertap["tokenMasked"] = ct["masked"]

    cashfree = dict(s.get("cashfree") or {})
    sk = _mask_secret(cashfree.get("secretKey"))
    cashfree.pop("secretKey", None)
    cashfree["secretKeySet"] = sk["set"]
    cashfree["secretKeyMasked"] = sk["masked"]

    firebase = dict(s.get("firebase") or {})
    fk = _mask_secret(firebase.get("apiKey"))
    firebase.pop("apiKey", None)
    firebase["apiKeySet"] = fk["set"]
    firebase["apiKeyMasked"] = fk["masked"]

    return {
        **s,
        "capi": capi,
        "clevertap": clevertap,
        "cashfree": cashfree,
        "firebase": firebase,
    }


class LoginBody(BaseModel):
    password: str


class SettingsBody(BaseModel):
    pixel: Optional[Dict[str, Any]] = None
    capi: Optional[Dict[str, Any]] = None
    clevertap: Optional[Dict[str, Any]] = None
    firebase: Optional[Dict[str, Any]] = None
    cashfree: Optional[Dict[str, Any]] = None
    app: Optional[Dict[str, Any]] = None


class QuotaBody(BaseModel):
    used: Optional[int] = None
    limit: Optional[int] = None
    is_premium: Optional[bool] = None
    unlimited: Optional[bool] = None


class PlanBody(BaseModel):
    id: Optional[str] = None
    name: str
    price: float
    currency: str = "INR"
    messages: Optional[int] = None
    durationDays: Optional[int] = 30
    durationMinutes: Optional[int] = None
    durationLabel: Optional[str] = None
    unlimited: bool = False
    highlight: bool = False
    autopay: bool = True
    renewPrice: Optional[float] = None
    autoRenewText: Optional[str] = None
    benefits: Optional[List[str]] = None


class TestCapiBody(BaseModel):
    eventName: str = "Purchase"
    value: float = 1
    currency: str = "INR"


class ClientEventBody(BaseModel):
    eventName: str
    meta: Optional[Dict[str, Any]] = None


class PromoBody(BaseModel):
    id: Optional[str] = None
    code: str
    type: str = "percent"
    value: float = 0
    maxRedemptions: int = 1000
    active: bool = True
    appliesTo: Optional[List[str]] = None
    note: Optional[str] = None


class NoteBody(BaseModel):
    text: str


class BanBody(BaseModel):
    banned: bool = True
    reason: str = ""


class PushBody(BaseModel):
    title: str
    body: str
    segment: str = "all"


class FlagsBody(BaseModel):
    flags: Dict[str, Any]


class AnnouncementBody(BaseModel):
    id: Optional[str] = None
    title: str
    body: str
    active: bool = True
    placement: str = "home_banner"


class SuggestedBody(BaseModel):
    items: List[str]


@router.post("/login")
def login(body: LoginBody) -> Dict[str, Any]:
    if body.password != admin_password():
        raise HTTPException(status_code=401, detail="Wrong password")
    token, exp = create_session()
    ops.audit("admin", "login")
    persist_touch()
    return {
        "success": True,
        "token": token,
        "expiresAt": int(exp * 1000),
        "message": "OK",
    }


@router.post("/logout")
def logout(token: str = Depends(require_admin)) -> Dict[str, Any]:
    revoke_session(token)
    ops.audit("admin", "logout")
    return {"success": True}


@router.get("/dashboard")
def dashboard(_: None = Depends(require_admin)) -> Dict[str, Any]:
    users = list(db.USERS.values())
    orders = list(db.ORDERS.values())
    paid = [o for o in orders if o.get("status") in {"paid", "success", "confirmed"}]
    revenue = sum(float(o.get("amount") or 0) for o in paid)
    active_members = sum(1 for m in db.MEMBERSHIPS.values() if m.get("active"))
    msg_used = sum(int(q.get("used") or 0) for q in db.QUOTAS.values())
    chat_threads = sum(len(v) for v in db.CHATS.values())
    onboarded = sum(1 for u in users if u.get("onboardingComplete"))
    paywall_seen = sum(1 for u in users if u.get("paymentGateSeen"))
    free_users = sum(1 for u in users if not (db.MEMBERSHIPS.get(u["id"]) or {}).get("active"))
    banned = len(ops.BANNED)
    arpu = round(revenue / max(1, len(paid)), 2)
    conversion = round((len(paid) / max(1, len(users))) * 100, 1)
    # simple 7-day series from order timestamps
    now = int(time.time() * 1000)
    day_ms = 86400000
    series = []
    for d in range(6, -1, -1):
        start = now - (d + 1) * day_ms
        end = now - d * day_ms
        day_orders = [o for o in paid if start <= (o.get("paidAt") or o.get("createdAt") or 0) < end]
        day_users = [u for u in users if start <= (u.get("createdAt") or 0) < end]
        series.append(
            {
                "day": time.strftime("%a", time.localtime((end - 1000) / 1000)),
                "revenue": sum(float(o.get("amount") or 0) for o in day_orders),
                "signups": len(day_users),
                "paid": len(day_orders),
            }
        )
    funnel = {
        "signups": len(users),
        "onboarded": onboarded,
        "paywallSeen": paywall_seen,
        "paid": len(paid),
        "activeMembers": active_members,
    }
    return {
        "success": True,
        "stats": {
            "users": len(users),
            "orders": len(orders),
            "paidOrders": len(paid),
            "revenue": revenue,
            "arpu": arpu,
            "conversionPct": conversion,
            "activeMembers": active_members,
            "freeUsers": free_users,
            "messagesUsed": msg_used,
            "chatThreads": chat_threads,
            "pandits": len(db.PANDITS),
            "plans": len(db.PLANS),
            "banned": banned,
            "promos": len(ops.PROMOS),
            "pushes": len(ops.PUSH_CAMPAIGNS),
        },
        "funnel": funnel,
        "series": series,
        "kpis": {
            "trialToPaid": conversion,
            "msgPerUser": round(msg_used / max(1, len(users)), 1),
            "autopayRate": round(
                100
                * sum(1 for o in paid if o.get("autopay"))
                / max(1, len(paid)),
                1,
            ),
        },
        "chatProvider": provider_status(),
        "settings": {
            "pixelEnabled": bool(load_settings()["pixel"].get("enabled")),
            "capiEnabled": bool(load_settings()["capi"].get("enabled")),
            "freeMessageLimit": load_settings()["app"].get("freeMessageLimit"),
        },
        "recentOrders": sorted(orders, key=lambda o: o.get("createdAt") or 0, reverse=True)[:10],
        "recentUsers": sorted(users, key=lambda u: u.get("createdAt") or 0, reverse=True)[:10],
        "flags": ops.FEATURE_FLAGS,
    }


@router.get("/users")
def list_users(_: None = Depends(require_admin)) -> Dict[str, Any]:
    rows = []
    for u in db.USERS.values():
        uid = u["id"]
        q = db.snapshot_quota(uid)
        m = db.MEMBERSHIPS.get(uid) or {}
        threads = db.CHATS.get(uid) or {}
        rows.append(
            {
                **u,
                "quota": q,
                "membership": m,
                "chatCount": sum(len(msgs) for msgs in threads.values()),
                "threadCount": len(threads),
                "banned": uid in ops.BANNED,
                "notesCount": len(ops.SUPPORT_NOTES.get(uid) or []),
            }
        )
    rows.sort(key=lambda r: r.get("phone") or "")
    return {"success": True, "items": rows}


def _find_user(user_id: str) -> Optional[Dict[str, Any]]:
    for u in db.USERS.values():
        if str(u.get("id")) == str(user_id) or str(u.get("phone")) == str(user_id):
            return u
    return None


@router.get("/users/{user_id}")
def user_detail(user_id: str, _: None = Depends(require_admin)) -> Dict[str, Any]:
    user = _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    uid = user["id"]
    threads = db.CHATS.get(uid) or {}
    orders = [o for o in db.ORDERS.values() if o.get("userId") == uid]
    return {
        "success": True,
        "user": user,
        "quota": db.snapshot_quota(uid),
        "membership": db.MEMBERSHIPS.get(uid),
        "family": db.FAMILY.get(uid) or [],
        "orders": orders,
        "chats": {k: v for k, v in threads.items()},
        "notes": ops.SUPPORT_NOTES.get(uid) or [],
        "banned": ops.BANNED.get(uid),
    }


@router.patch("/users/{user_id}/quota")
def patch_quota(user_id: str, body: QuotaBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    user = _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    uid = user["id"]
    db.reset_user_runtime(uid)
    q = db.QUOTAS[uid]
    if body.used is not None:
        q["used"] = max(0, int(body.used))
    if body.limit is not None:
        q["limit"] = max(0, int(body.limit))
    if body.is_premium is not None:
        q["is_premium"] = bool(body.is_premium)
    if body.unlimited is not None:
        q["unlimited"] = bool(body.unlimited)
        if body.unlimited:
            q["limit"] = 999999
    return {"success": True, "quota": db.snapshot_quota(uid)}


@router.get("/orders")
def list_orders(_: None = Depends(require_admin)) -> Dict[str, Any]:
    items = sorted(db.ORDERS.values(), key=lambda o: o.get("createdAt") or 0, reverse=True)
    return {"success": True, "items": items}


@router.get("/plans")
def list_plans(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": db.PLANS}


@router.put("/plans")
def replace_plans(body: List[PlanBody], _: None = Depends(require_admin)) -> Dict[str, Any]:
    db.PLANS = [p.model_dump() for p in body]
    return {"success": True, "items": db.PLANS}


@router.post("/plans")
def upsert_plan(body: PlanBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    data = body.model_dump()
    if not data.get("id"):
        data["id"] = f"plan_{int(time.time())}"
    found = False
    for i, p in enumerate(db.PLANS):
        if p.get("id") == data["id"]:
            db.PLANS[i] = {**p, **data}
            found = True
            break
    if not found:
        db.PLANS.append(data)
    return {"success": True, "items": db.PLANS}


@router.get("/pandits")
def list_pandits(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": db.PANDITS}


@router.get("/settings")
def get_settings(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "settings": _public_settings_view()}


@router.put("/settings")
def put_settings(body: SettingsBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    current = load_settings()
    # keep existing secrets if blank submitted
    if "capi" in patch and patch["capi"] is not None:
        incoming = patch["capi"]
        if not (incoming.get("accessToken") or "").strip():
            incoming["accessToken"] = current.get("capi", {}).get("accessToken") or ""
    if "clevertap" in patch and patch["clevertap"] is not None:
        incoming = patch["clevertap"]
        if not (incoming.get("token") or "").strip():
            incoming["token"] = current.get("clevertap", {}).get("token") or ""
    if "cashfree" in patch and patch["cashfree"] is not None:
        incoming = patch["cashfree"]
        if not (incoming.get("secretKey") or "").strip():
            incoming["secretKey"] = current.get("cashfree", {}).get("secretKey") or ""
    if "firebase" in patch and patch["firebase"] is not None:
        incoming = patch["firebase"]
        if not (incoming.get("apiKey") or "").strip():
            incoming["apiKey"] = current.get("firebase", {}).get("apiKey") or ""
    save_settings(patch)
    persist_touch()
    return {"success": True, "settings": _public_settings_view()}


@router.get("/tracking/events")
def tracking_events(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": EVENT_LOG[:100]}


@router.post("/tracking/test-capi")
def test_capi(body: TestCapiBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    result = send_capi_event(
        event_name=body.eventName,
        user={"phone": "9999999999", "id": "admin-test", "name": "Admin Test"},
        custom_data={"currency": body.currency, "value": body.value, "content_name": "Astro99 Test"},
        event_source_url=os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000") + "/admin/",
    )
    return {"success": True, "result": result}


@router.get("/chat-provider")
def chat_provider(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "provider": provider_status()}


@router.post("/users/{user_id}/notes")
def add_note(user_id: str, body: NoteBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    user = _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    note = {
        "id": str(__import__("uuid").uuid4()),
        "ts": int(time.time() * 1000),
        "author": "admin",
        "text": body.text.strip(),
    }
    ops.SUPPORT_NOTES.setdefault(user["id"], []).insert(0, note)
    ops.audit("admin", "note_add", {"userId": user["id"]})
    return {"success": True, "notes": ops.SUPPORT_NOTES[user["id"]]}


@router.post("/users/{user_id}/ban")
def ban_user(user_id: str, body: BanBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    user = _find_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    uid = user["id"]
    if body.banned:
        ops.BANNED[uid] = {"reason": body.reason or "Banned by admin", "at": int(time.time() * 1000)}
    else:
        ops.BANNED.pop(uid, None)
    ops.audit("admin", "ban" if body.banned else "unban", {"userId": uid, "reason": body.reason})
    persist_touch()
    return {"success": True, "banned": ops.BANNED.get(uid)}


@router.get("/promos")
def list_promos(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": ops.PROMOS}


@router.post("/promos")
def upsert_promo(body: PromoBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    data = body.model_dump()
    if not data.get("id"):
        data["id"] = f"promo_{int(time.time())}"
        data["redeemed"] = 0
    found = False
    for i, p in enumerate(ops.PROMOS):
        if p.get("id") == data["id"] or p.get("code") == data["code"]:
            ops.PROMOS[i] = {**p, **data}
            found = True
            break
    if not found:
        ops.PROMOS.append(data)
    ops.audit("admin", "promo_upsert", {"code": data["code"]})
    return {"success": True, "items": ops.PROMOS}


@router.get("/flags")
def get_flags(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "flags": ops.FEATURE_FLAGS}


@router.put("/flags")
def put_flags(body: FlagsBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    ops.FEATURE_FLAGS.update(body.flags or {})
    ops.audit("admin", "flags_update", body.flags)
    return {"success": True, "flags": ops.FEATURE_FLAGS}


@router.get("/pushes")
def list_pushes(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": ops.PUSH_CAMPAIGNS}


@router.post("/pushes")
def create_push(body: PushBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    # mock send — counts by segment
    users = list(db.USERS.values())
    if body.segment == "free_users":
        audience = [u for u in users if not (db.MEMBERSHIPS.get(u["id"]) or {}).get("active")]
    elif body.segment == "premium":
        audience = [u for u in users if (db.MEMBERSHIPS.get(u["id"]) or {}).get("active")]
    else:
        audience = users
    delivered = max(1, len(audience)) * 53  # demo multiplier
    row = {
        "id": f"push_{int(time.time())}",
        "title": body.title,
        "body": body.body,
        "segment": body.segment,
        "status": "sent",
        "sentAt": int(time.time() * 1000),
        "delivered": delivered,
        "opened": int(delivered * 0.28),
    }
    ops.PUSH_CAMPAIGNS.insert(0, row)
    ops.audit("admin", "push_send", {"segment": body.segment, "title": body.title})
    return {"success": True, "item": row, "items": ops.PUSH_CAMPAIGNS}


@router.get("/announcements")
def list_announcements(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": ops.ANNOUNCEMENTS}


@router.post("/announcements")
def upsert_announcement(body: AnnouncementBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    data = body.model_dump()
    if not data.get("id"):
        data["id"] = f"ann_{int(time.time())}"
        data["createdAt"] = int(time.time() * 1000)
    found = False
    for i, a in enumerate(ops.ANNOUNCEMENTS):
        if a.get("id") == data["id"]:
            ops.ANNOUNCEMENTS[i] = {**a, **data}
            found = True
            break
    if not found:
        ops.ANNOUNCEMENTS.insert(0, data)
    return {"success": True, "items": ops.ANNOUNCEMENTS}


@router.get("/content/suggested")
def get_suggested(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": db.SUGGESTED_QUESTIONS}


@router.put("/content/suggested")
def put_suggested(body: SuggestedBody, _: None = Depends(require_admin)) -> Dict[str, Any]:
    db.SUGGESTED_QUESTIONS = [x.strip() for x in body.items if x.strip()]
    ops.audit("admin", "suggested_update", {"count": len(db.SUGGESTED_QUESTIONS)})
    return {"success": True, "items": db.SUGGESTED_QUESTIONS}


@router.get("/audit")
def audit_log(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": ops.AUDIT_LOG[:200]}


@router.get("/webhooks")
def list_webhooks(_: None = Depends(require_admin)) -> Dict[str, Any]:
    return {"success": True, "items": ops.WEBHOOKS}


@router.get("/export/users.csv")
def export_users(_: None = Depends(require_admin)) -> PlainTextResponse:
    lines = ["id,phone,name,premium,plan,used,limit,banned"]
    for u in db.USERS.values():
        uid = u["id"]
        q = db.snapshot_quota(uid)
        m = db.MEMBERSHIPS.get(uid) or {}
        lines.append(
            ",".join(
                [
                    uid,
                    u.get("phone") or "",
                    (u.get("name") or "").replace(",", " "),
                    str(bool(q.get("is_premium"))),
                    str(m.get("plan_id") or ""),
                    str(q.get("used") or 0),
                    str(q.get("limit") or ""),
                    str(uid in ops.BANNED),
                ]
            )
        )
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


@router.get("/export/orders.csv")
def export_orders(_: None = Depends(require_admin)) -> PlainTextResponse:
    lines = ["orderId,userId,planId,amount,status,autopay,upiId,createdAt"]
    for o in db.ORDERS.values():
        lines.append(
            ",".join(
                [
                    str(o.get("orderId")),
                    str(o.get("userId")),
                    str(o.get("planId")),
                    str(o.get("amount")),
                    str(o.get("status")),
                    str(o.get("autopay")),
                    str(o.get("upiId") or ""),
                    str(o.get("createdAt") or ""),
                ]
            )
        )
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


# ——— public (no admin auth) ———

public_router = APIRouter(tags=["tracking-public"])


@public_router.get("/tracking/config")
def tracking_config() -> Dict[str, Any]:
    return {"success": True, **public_tracking_config(), "flags": ops.FEATURE_FLAGS}


@public_router.get("/public/announcements")
def public_announcements() -> Dict[str, Any]:
    return {
        "success": True,
        "items": [a for a in ops.ANNOUNCEMENTS if a.get("active")],
    }


@public_router.post("/tracking/client-event")
def client_event(body: ClientEventBody) -> Dict[str, Any]:
    from app.tracking import log_pixel_client_event

    log_pixel_client_event(body.eventName, body.meta)
    return {"success": True}


@router.get("/")
def admin_index() -> FileResponse:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "static", "admin", "index.html")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Admin UI missing")
    return FileResponse(path, media_type="text/html")
