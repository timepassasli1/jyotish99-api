from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

from app import db


def current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = None
    if authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        else:
            token = authorization.strip()
    user = db.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Maintenance gate (ops settings)
    try:
        from app.settings_store import load_settings

        app_cfg = (load_settings().get("app") or {})
        if app_cfg.get("maintenanceMode"):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "MAINTENANCE",
                    "message": app_cfg.get("maintenanceMessage")
                    or "App under maintenance. Try again later.",
                },
            )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        pass

    # Ban enforcement
    try:
        from app import ops_store as ops

        ban = ops.BANNED.get(user["id"])
        if ban:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "BANNED",
                    "message": ban.get("reason") or "Account restricted",
                },
            )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        pass

    db.reset_user_runtime(user["id"])
    return user
