from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app import db
from app.deps import current_user

router = APIRouter(tags=["home"])


@router.get("/home/feed")
def home_feed(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    sections = list(db.HOME_FEED)
    quota = db.snapshot_quota(user["id"])
    # Don't nag recharge when already unlimited / premium (SKIP_PAYWALL demo too)
    if quota.get("unlimited") or quota.get("is_premium"):
        sections = [s for s in sections if s.get("type") != "ACTION_BANNER"]
    return {"success": True, "sections": sections, "quota": quota}


@router.get("/characters")
def characters(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {"success": True, "items": db.PANDITS}


@router.get("/characters/{character_id}")
def character_by_id(character_id: str, _user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    for p in db.PANDITS:
        if str(p["characterId"]) == str(character_id) or p["id"] == str(character_id):
            return {"success": True, "data": p}
    return {"success": False, "data": None}
