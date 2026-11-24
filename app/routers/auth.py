from __future__ import annotations

import os
import secrets
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.deps import current_user
from app.persist import touch as persist_touch

router = APIRouter(prefix="/auth", tags=["auth"])

# phone -> (count, window_start)
_OTP_RATE: Dict[str, Tuple[int, float]] = {}
_OTP_WINDOW_SEC = 600
_OTP_MAX = 5


class SendOtpBody(BaseModel):
    phone: str = Field(min_length=10, max_length=15)


class VerifyOtpBody(BaseModel):
    phone: str
    otp: str


class ProfileBody(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    birthTime: Optional[str] = None
    birthTimeUnknown: Optional[bool] = None
    place: Optional[str] = None
    marriageStatus: Optional[str] = None
    occupation: Optional[str] = None
    photoUrl: Optional[str] = None
    language: Optional[str] = None
    onboardingComplete: Optional[bool] = None
    paymentGateSeen: Optional[bool] = None
    notificationPromptSeen: Optional[bool] = None


def _blank_profile(phone: str) -> Dict[str, Any]:
    skip_paywall = os.environ.get("SKIP_PAYWALL", "0") == "1"
    return {
        "id": str(uuid.uuid4()),
        "phone": phone,
        "name": "",
        "gender": None,
        "dob": None,
        "birthTime": None,
        "birthTimeUnknown": False,
        "place": None,
        "marriageStatus": None,
        "occupation": None,
        "photoUrl": None,
        "language": "en",
        "onboardingComplete": False,
        "paymentGateSeen": True if skip_paywall else False,
        "notificationPromptSeen": False,
    }


def _check_otp_rate(phone: str) -> None:
    now = time.time()
    count, start = _OTP_RATE.get(phone, (0, now))
    if now - start > _OTP_WINDOW_SEC:
        count, start = 0, now
    count += 1
    _OTP_RATE[phone] = (count, start)
    if count > _OTP_MAX:
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again later.")


def _issue_session(phone: str, *, signup_tag: str = "phone_login") -> Dict[str, Any]:
    """Create/resume user session for a phone. Shared by login + OTP verify."""
    user = db.USERS.get(phone)
    is_new = False
    if not user:
        user = _blank_profile(phone)
        db.USERS[phone] = user
        is_new = True
    else:
        # Backfill flags for older in-memory users
        user.setdefault("onboardingComplete", bool(user.get("name") and user.get("dob") and user.get("place")))
        if os.environ.get("SKIP_PAYWALL", "0") == "1":
            user["paymentGateSeen"] = True
        else:
            user.setdefault("paymentGateSeen", False)
        user.setdefault("notificationPromptSeen", False)
        user.setdefault("gender", None)
        user.setdefault("dob", None)
        user.setdefault("birthTime", None)
        user.setdefault("birthTimeUnknown", False)
        user.setdefault("place", None)
        user.setdefault("marriageStatus", None)
    token = secrets.token_hex(16)
    db.SESSIONS[token] = user
    db.reset_user_runtime(user["id"])
    if is_new:
        try:
            from app.tracking import send_capi_event

            send_capi_event(
                event_name="CompleteRegistration",
                user=user,
                custom_data={"status": True, "content_name": signup_tag},
            )
        except Exception:  # noqa: BLE001
            pass
    persist_touch()
    return {"success": True, "token": token, "user": user}


@router.post("/send-otp")
def send_otp(body: SendOtpBody) -> Dict[str, Any]:
    # TODO(otp): wire real SMS provider (MSG91/Twilio) — kept for later.
    phone = body.phone.strip()
    _check_otp_rate(phone)
    # Demo OTP until SMS provider is wired; never echo unless DEV_OTP_ECHO=1
    db.OTPS[phone] = "1234"
    persist_touch()
    out: Dict[str, Any] = {"success": True, "message": "OTP sent"}
    if os.environ.get("DEV_OTP_ECHO", "1") == "1":
        out["devOtp"] = "1234"
    return out


@router.post("/login")
def login_phone(body: SendOtpBody) -> Dict[str, Any]:
    """Phone-only login (no OTP). Flip REQUIRE_OTP / app flag later to re-enable OTP."""
    phone = body.phone.strip()
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone")
    return _issue_session(phone, signup_tag="phone_login")


@router.post("/verify-otp")
def verify_otp(body: VerifyOtpBody) -> Dict[str, Any]:
    # TODO(otp): re-enable from app when SMS OTP ships; endpoint stays valid.
    phone = body.phone.strip()
    expected = db.OTPS.get(phone, "1234")
    if body.otp.strip() != expected:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    return _issue_session(phone, signup_tag="otp_signup")


@router.get("/me")
def me(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _bearer(authorization)
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"success": True, "user": user, "quota": db.snapshot_quota(user["id"])}


@router.patch("/profile")
def update_profile(body: ProfileBody, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        user[key] = value
    # Keep phone-keyed USERS in sync
    phone = user.get("phone")
    if phone and phone in db.USERS:
        db.USERS[phone].update(user)
    # Seed self family profile when onboarding finishes
    if data.get("onboardingComplete") and user.get("name"):
        profiles = db.FAMILY.setdefault(user["id"], [])
        if not any(p.get("relation") == "Self" for p in profiles):
            for p in profiles:
                p["active"] = False
            profiles.insert(
                0,
                {
                    "id": str(uuid.uuid4()),
                    "name": user.get("name") or "Self",
                    "relation": "Self",
                    "dob": user.get("dob"),
                    "tob": None if user.get("birthTimeUnknown") else user.get("birthTime"),
                    "place": user.get("place"),
                    "gender": user.get("gender"),
                    "marriageStatus": user.get("marriageStatus"),
                    "active": True,
                },
            )
    return {"success": True, "user": user}


@router.get("/places")
def places(q: str = "") -> Dict[str, Any]:
    from app.places_data import search_places

    items = search_places(q, limit=12)
    return {"success": True, "items": items, "source": "local_catalog"}


@router.get("/avatars")
def avatars() -> Dict[str, Any]:
    import os

    host = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    base = f"{host}/static/avatars"
    return {
        "success": True,
        "items": [f"{base}/a{i}.webp" for i in range(1, 7)],
        "occupations": [
            "Student",
            "Working professional",
            "Business / Self-employed",
            "Homemaker",
            "Looking for job",
            "Other",
        ],
    }


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return authorization.strip()
