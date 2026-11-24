"""Meta Pixel CAPI + event log for admin."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib import error, request

from app.settings_store import load_settings

# newest first, capped
EVENT_LOG: List[Dict[str, Any]] = []
_MAX_LOG = 200


def _sha256(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _push_log(entry: Dict[str, Any]) -> None:
    EVENT_LOG.insert(0, entry)
    del EVENT_LOG[_MAX_LOG:]


def send_capi_event(
    *,
    event_name: str,
    user: Optional[Dict[str, Any]] = None,
    custom_data: Optional[Dict[str, Any]] = None,
    event_source_url: Optional[str] = None,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    settings = load_settings()
    capi = settings.get("capi") or {}
    pixel = settings.get("pixel") or {}
    if not capi.get("enabled"):
        return {"skipped": True, "reason": "capi_disabled"}

    pixel_id = (capi.get("pixelId") or pixel.get("pixelId") or "").strip()
    token = (capi.get("accessToken") or "").strip()
    if not pixel_id or not token:
        return {"skipped": True, "reason": "missing_credentials"}

    # event toggles
    flag_map = {
        "Purchase": "sendPurchase",
        "Subscribe": "sendPurchase",
        "CompleteRegistration": "sendRegistration",
        "InitiateCheckout": "sendInitiateCheckout",
        "Lead": "sendLead",
        "AddPaymentInfo": "sendInitiateCheckout",
    }
    flag = flag_map.get(event_name)
    if flag and not capi.get(flag, True):
        return {"skipped": True, "reason": f"{flag}_off"}

    user_data: Dict[str, Any] = {}
    if user:
        phone = (user.get("phone") or "").strip()
        if phone:
            digits = "".join(ch for ch in phone if ch.isdigit())
            if digits:
                if not digits.startswith("91") and len(digits) == 10:
                    digits = "91" + digits
                user_data["ph"] = [_sha256(digits)]
        if user.get("email"):
            user_data["em"] = [_sha256(str(user["email"]))]
        if user.get("id"):
            user_data["external_id"] = [_sha256(str(user["id"]))]
        if user.get("name"):
            parts = str(user["name"]).strip().split()
            if parts:
                user_data["fn"] = [_sha256(parts[0])]
            if len(parts) > 1:
                user_data["ln"] = [_sha256(parts[-1])]

    eid = event_id or str(uuid.uuid4())
    event: Dict[str, Any] = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "event_id": eid,
        "action_source": "website",
        "user_data": user_data,
    }
    if event_source_url:
        event["event_source_url"] = event_source_url
    if custom_data:
        event["custom_data"] = custom_data

    payload: Dict[str, Any] = {"data": [event]}
    test_code = (capi.get("testEventCode") or "").strip()
    if test_code:
        payload["test_event_code"] = test_code

    version = (capi.get("apiVersion") or "v21.0").strip()
    url = f"https://graph.facebook.com/{version}/{pixel_id}/events?access_token={token}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

    result: Dict[str, Any] = {"event_name": event_name, "event_id": eid, "ok": False}
    try:
        with request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            result["ok"] = True
            result["status"] = resp.status
            try:
                result["response"] = json.loads(raw)
            except Exception:  # noqa: BLE001
                result["response"] = raw[:400]
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        result["status"] = exc.code
        result["error"] = raw[:600]
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)

    _push_log(
        {
            "id": eid,
            "ts": int(time.time() * 1000),
            "channel": "capi",
            "event_name": event_name,
            "ok": result.get("ok"),
            "status": result.get("status"),
            "error": result.get("error"),
            "custom_data": custom_data,
            "user_id": (user or {}).get("id"),
        }
    )
    return result


def log_pixel_client_event(event_name: str, meta: Optional[Dict[str, Any]] = None) -> None:
    _push_log(
        {
            "id": str(uuid.uuid4()),
            "ts": int(time.time() * 1000),
            "channel": "pixel",
            "event_name": event_name,
            "ok": True,
            "meta": meta or {},
        }
    )
