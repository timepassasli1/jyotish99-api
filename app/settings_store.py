"""Persistent admin settings (Pixel / CAPI / limits / integrations)."""
from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = BASE_DIR / "data" / "admin_settings.json"
_LOCK = threading.Lock()

DEFAULTS: Dict[str, Any] = {
    "pixel": {
        "enabled": False,
        "pixelId": "",
        "events": {
            "PageView": True,
            "ViewContent": True,
            "CompleteRegistration": True,
            "Lead": True,
            "InitiateCheckout": True,
            "AddPaymentInfo": True,
            "Purchase": True,
            "Subscribe": True,
            "Contact": True,
        },
    },
    "capi": {
        "enabled": False,
        "pixelId": "",
        "accessToken": "",
        "testEventCode": "",
        "apiVersion": "v21.0",
        "sendPurchase": True,
        "sendRegistration": True,
        "sendInitiateCheckout": True,
        "sendLead": True,
    },
    "clevertap": {
        "enabled": False,
        "accountId": "",
        "token": "",
        "region": "in1",
    },
    "firebase": {
        "enabled": False,
        "measurementId": "",
        "apiKey": "",
    },
    "cashfree": {
        "enabled": False,
        "appId": "",
        "secretKey": "",
        "env": "sandbox",
    },
    "app": {
        "freeMessageLimit": 5,
        "maintenanceMode": False,
        "maintenanceMessage": "App update ho rahi hai — thodi der baad try karein.",
        "supportWhatsapp": "",
        "supportEmail": "support@astro99.app",
    },
}


def _ensure() -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> Dict[str, Any]:
    with _LOCK:
        _ensure()
        try:
            raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            raw = {}
        return _deep_merge(DEFAULTS, raw)


def save_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        current = load_settings()
        merged = _deep_merge(current, patch)
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        # sync free limit into runtime db module
        try:
            from app import db

            limit = int(merged.get("app", {}).get("freeMessageLimit") or 5)
            db.FREE_MESSAGE_LIMIT = limit
        except Exception:  # noqa: BLE001
            pass
        return merged


def public_tracking_config() -> Dict[str, Any]:
    """Safe subset for the client app (no CAPI token / secrets)."""
    s = load_settings()
    return {
        "pixel": {
            "enabled": bool(s["pixel"].get("enabled") and s["pixel"].get("pixelId")),
            "pixelId": s["pixel"].get("pixelId") or "",
            "events": s["pixel"].get("events") or {},
        },
        "firebase": {
            "enabled": bool(s["firebase"].get("enabled") and s["firebase"].get("measurementId")),
            "measurementId": s["firebase"].get("measurementId") or "",
        },
        "clevertap": {
            "enabled": bool(s["clevertap"].get("enabled") and s["clevertap"].get("accountId")),
            "accountId": s["clevertap"].get("accountId") or "",
            "region": s["clevertap"].get("region") or "in1",
            # token not exposed — server/SDK only
        },
        "app": {
            "maintenanceMode": bool(s["app"].get("maintenanceMode")),
            "maintenanceMessage": s["app"].get("maintenanceMessage") or "",
            "supportWhatsapp": s["app"].get("supportWhatsapp") or "",
            "supportEmail": s["app"].get("supportEmail") or "",
            "freeMessageLimit": int(s["app"].get("freeMessageLimit") or 5),
        },
        "capiActive": bool(s["capi"].get("enabled") and s["capi"].get("accessToken") and (s["capi"].get("pixelId") or s["pixel"].get("pixelId"))),
    }


def admin_password() -> str:
    return os.environ.get("ADMIN_PASSWORD", "astro99admin")
