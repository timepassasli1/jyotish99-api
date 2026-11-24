from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import db
from app.deps import current_user
from app.persist import touch as persist_touch

router = APIRouter(prefix="/family", tags=["family"])


class ProfileBody(BaseModel):
    name: str
    relation: str = "Self"
    dob: Optional[str] = None
    tob: Optional[str] = None
    place: Optional[str] = None
    gender: Optional[str] = None


@router.get("/profiles")
def list_profiles(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {"success": True, "items": db.FAMILY.get(user["id"], [])}


@router.post("/profiles")
def create_profile(body: ProfileBody, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    profiles: List[Dict[str, Any]] = db.FAMILY.setdefault(user["id"], [])
    profile = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "relation": body.relation,
        "dob": body.dob,
        "tob": body.tob,
        "place": body.place,
        "gender": body.gender,
        "active": len(profiles) == 0,
    }
    if profile["active"]:
        for p in profiles:
            p["active"] = False
    profiles.append(profile)
    persist_touch()
    return {"success": True, "data": profile}


@router.post("/profiles/{profile_id}/switch")
def switch_profile(profile_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    profiles = db.FAMILY.get(user["id"], [])
    found = None
    for p in profiles:
        p["active"] = p["id"] == profile_id
        if p["active"]:
            found = p
    if not found:
        raise HTTPException(status_code=404, detail="Profile not found")
    persist_touch()
    return {"success": True, "data": found}
