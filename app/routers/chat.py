from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import db
from app.deps import current_user
from app.llm import enrich_blocks, generate_reply, provider_status
from app.persist import touch as persist_touch

router = APIRouter(prefix="/chat", tags=["chat"])


class InitBody(BaseModel):
    characterId: str
    firstMessage: Optional[str] = None


class SendBody(BaseModel):
    characterId: str
    text: str


def _chat_key(character_id: str) -> str:
    return str(character_id)


@router.post("/init")
def init_chat(body: InitBody, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    uid = user["id"]
    key = _chat_key(body.characterId)
    chats = db.CHATS[uid]
    if key not in chats:
        pandit = next((p for p in db.PANDITS if str(p["characterId"]) == key or p["id"] == key), None)
        intro = (pandit or {}).get("intro", {})
        chats[key] = [
            {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "text": intro.get("subtitle") or "Namaste! How can I help you today?",
                "timestamp": int(time.time() * 1000),
            }
        ]
        if body.firstMessage:
            chats[key].append(
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "text": body.firstMessage,
                    "timestamp": int(time.time() * 1000),
                }
            )
    return {"success": True, "chatId": key, "messages": chats[key]}


@router.get("/history")
def history(characterId: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    uid = user["id"]
    key = _chat_key(characterId)
    messages = db.CHATS.get(uid, {}).get(key, [])
    return {"success": True, "messages": messages, "quota": db.snapshot_quota(uid)}


@router.get("/provider")
def chat_provider(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Debug: which live model path is active (original app = Livo + GEMINI)."""
    return {"success": True, "provider": provider_status()}


@router.post("/send")
def send_message(body: SendBody, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    uid = user["id"]
    quota = db.snapshot_quota(uid)
    # SKIP_PAYWALL=1 → never block chat for recharge testing
    if (
        not quota.get("unlimited")
        and (quota.get("remaining") or 0) <= 0
        and __import__("os").environ.get("SKIP_PAYWALL", "0") != "1"
    ):
        raise HTTPException(
            status_code=402,
            detail={
                "code": "MESSAGE_LIMIT",
                "message": "Message limit reached",
                "quota": quota,
            },
        )

    key = _chat_key(body.characterId)
    chats = db.CHATS[uid]
    if key not in chats:
        chats[key] = []

    user_msg = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "text": body.text.strip(),
        "timestamp": int(time.time() * 1000),
    }
    chats[key].append(user_msg)

    pandit = next((p for p in db.PANDITS if str(p["characterId"]) == key or p["id"] == key), None) or {
        "name": "Pandit Ji",
        "gender": "male",
        "persona": "Vedic Astrologer",
        "prompt": "You are a warm Indian vedic pandit. Use masculine Hindi.",
    }
    # Active family profile overrides self fields when present
    profiles = db.FAMILY.get(uid, []) or []
    active = next((p for p in profiles if p.get("active")), None)
    effective_user = dict(user)
    if active:
        effective_user["name"] = active.get("name") or effective_user.get("name")
        effective_user["dob"] = active.get("dob") or effective_user.get("dob")
        effective_user["place"] = active.get("place") or effective_user.get("place")
        effective_user["gender"] = active.get("gender") or effective_user.get("gender")
        if active.get("tob"):
            effective_user["birthTime"] = active.get("tob")
            effective_user["birthTimeUnknown"] = False

    t0 = time.time()
    reply_text, provider = generate_reply(
        pandit=pandit,
        history=chats[key],
        user_text=body.text,
        user=effective_user,
    )
    # Fast providers (template/pollinations) feel instant — pad to ~1.8–3.2s think time
    elapsed = time.time() - t0
    min_think = 1.8 + (min(len(reply_text), 280) / 280.0) * 1.4
    if elapsed < min_think:
        time.sleep(min_think - elapsed)
    blocks = enrich_blocks(pandit=pandit, user_text=body.text, reply_text=reply_text)
    assistant_msg = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "text": reply_text,
        "blocks": blocks,
        "timestamp": int(time.time() * 1000) + 1,
        "provider": provider,
    }
    chats[key].append(assistant_msg)

    db.QUOTAS[uid]["used"] += 1
    persist_touch()
    return {
        "success": True,
        "message": assistant_msg,
        "messages": chats[key],
        "quota": db.snapshot_quota(uid),
        "provider": provider,
    }


@router.get("/suggested-questions")
def suggested(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {"success": True, "items": db.SUGGESTED_QUESTIONS}


@router.get("/suggested-replies")
def suggested_replies(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {
        "success": True,
        "items": ["Tell me more", "What remedy helps?", "Is timing good?", "Thank you"],
    }
