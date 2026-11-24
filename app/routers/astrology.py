from __future__ import annotations

import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.deps import current_user
from app.llm import generate_reply
from app.persist import touch as persist_touch
from app.tarot_deck import DECK_META, deck_cards

router = APIRouter(tags=["astrology"])


def _base() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@router.get("/horoscope/daily")
def daily_horoscope(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    from app.astro_coach import daily_horoscope_for_user

    return daily_horoscope_for_user(user, db.HOROSCOPE)


@router.get("/astrology/details")
def astrology_details(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {"success": True, "data": db.ASTROLOGY}


@router.get("/stories")
def stories(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return {
        "success": True,
        "items": [{"id": s["id"], "title": s["title"], "coverUrl": s["coverUrl"]} for s in db.STORIES],
    }


@router.get("/stories/{story_id}")
def story_pages(story_id: str, _user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    for s in db.STORIES:
        if s["id"] == story_id:
            return {"success": True, "data": s}
    raise HTTPException(status_code=404, detail="Story not found")


@router.get("/tarot/readers")
def tarot_readers(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    items = [p for p in db.PANDITS if not p["isVedicAstrologer"]]
    return {"success": True, "items": items}


@router.get("/tarot/daily")
def tarot_daily(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    # Keep legacy daily list for home widgets; prefer full deck cards
    cards = deck_cards(_base())
    return {
        "success": True,
        "cards": cards,
        "backImageUrl": cards[0]["backImageUrl"] if cards else None,
    }


@router.get("/tarot/decks")
def tarot_decks(_user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    back = f"{_base()}/static/tarot_card_back.webp"
    return {
        "success": True,
        "items": [
            {
                **DECK_META,
                "cardBackUrl": back,
            }
        ],
    }


class SessionBody(BaseModel):
    deckId: str = "classic_major_v1"
    readerId: Optional[str] = None
    spread: str = Field(default="single", description="single | three")


class DrawBody(BaseModel):
    count: Optional[int] = None


class ReadBody(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    language: str = "hinglish"


def _default_reader() -> Dict[str, Any]:
    readers = [p for p in db.PANDITS if not p.get("isVedicAstrologer")]
    return readers[0] if readers else {
        "id": "tarot",
        "name": "Kavya Tarot",
        "gender": "female",
        "persona": "Tarot Reader",
        "prompt": (
            "You are Kavya Tarot, a woman tarot reader. "
            "Use feminine Hindi (karti/dekh rahi/kehti hoon). Speak Hinglish, practical, never fear-monger."
        ),
    }


def _resolve_reader(reader_id: Optional[str]) -> Dict[str, Any]:
    if not reader_id:
        return _default_reader()
    for p in db.PANDITS:
        if str(p.get("id")) == str(reader_id) or str(p.get("characterId")) == str(reader_id):
            return p
    return _default_reader()


def _spread_count(spread: str) -> int:
    if spread == "three":
        return 3
    return 1


def _public_session(sess: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": sess["id"],
        "deckId": sess["deckId"],
        "readerId": sess.get("readerId"),
        "readerName": sess.get("readerName"),
        "spread": sess["spread"],
        "drawn": sess.get("drawn") or [],
        "createdAt": sess.get("createdAt"),
    }


@router.post("/tarot/sessions")
def create_session(body: SessionBody, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    if body.deckId != DECK_META["id"]:
        raise HTTPException(status_code=400, detail="Unknown deckId")
    if body.spread not in {"single", "three"}:
        raise HTTPException(status_code=400, detail="spread must be single or three")
    reader = _resolve_reader(body.readerId)
    sid = f"ts_{uuid.uuid4().hex[:12]}"
    sess = {
        "id": sid,
        "userId": user["id"],
        "deckId": body.deckId,
        "readerId": str(reader.get("id") or reader.get("characterId")),
        "readerName": reader.get("name"),
        "reader": reader,
        "spread": body.spread,
        "drawn": [],
        "seed": random.randrange(1, 10_000_000),
        "createdAt": int(time.time() * 1000),
    }
    db.TAROT_SESSIONS[sid] = sess
    persist_touch()
    return {"success": True, "session": _public_session(sess)}


@router.get("/tarot/sessions/{session_id}")
def get_session(session_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    sess = db.TAROT_SESSIONS.get(session_id)
    if not sess or sess.get("userId") != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": _public_session(sess)}


@router.post("/tarot/sessions/{session_id}/draw")
def draw_cards(
    session_id: str,
    body: DrawBody,
    user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    sess = db.TAROT_SESSIONS.get(session_id)
    if not sess or sess.get("userId") != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    need = body.count if body.count is not None else _spread_count(sess["spread"])
    need = max(1, min(3, int(need)))
    if sess.get("drawn"):
        # idempotent: return existing draw
        return {"success": True, "drawn": sess["drawn"], "session": _public_session(sess)}

    cards = deck_cards(_base())
    rng = random.Random(sess.get("seed") or time.time())
    picks = rng.sample(cards, k=min(need, len(cards)))
    positions = ["Present"] if need == 1 else ["Past", "Present", "Future"]
    drawn: List[Dict[str, Any]] = []
    for i, c in enumerate(picks):
        reversed_ = rng.random() < 0.28
        meaning = c["reversed"] if reversed_ else c["upright"]
        drawn.append(
            {
                "cardId": c["id"],
                "name": c["name"],
                "number": c["number"],
                "orientation": "reversed" if reversed_ else "upright",
                "position": positions[i] if i < len(positions) else f"Card {i+1}",
                "meaning": meaning,
                "imageUrl": c["imageUrl"],
            }
        )
    sess["drawn"] = drawn
    persist_touch()
    return {"success": True, "drawn": drawn, "session": _public_session(sess)}


@router.post("/tarot/sessions/{session_id}/read")
def read_spread(
    session_id: str,
    body: ReadBody,
    user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    sess = db.TAROT_SESSIONS.get(session_id)
    if not sess or sess.get("userId") != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    if not sess.get("drawn"):
        raise HTTPException(status_code=400, detail="Draw cards first")

    reader = sess.get("reader") or _default_reader()
    card_lines = []
    for d in sess["drawn"]:
        card_lines.append(
            f"- {d['position']}: {d['name']} ({d['orientation']}) — {d['meaning']}"
        )
    cards_block = "\n".join(card_lines)
    lang = body.language or "hinglish"
    prompt_extra = (
        f"You are {reader.get('name')}, a tarot reader ({reader.get('persona')}). "
        f"Speak {lang}. Be warm, practical, never fear-monger. "
        "Do NOT invent different cards than listed. Keep reading under 180 words. "
        "End with one gentle action tip. Disclaimer: guidance only, not medical/legal advice.\n\n"
        f"Drawn cards:\n{cards_block}"
    )
    pandit = {
        **reader,
        "prompt": (reader.get("prompt") or "") + "\n" + prompt_extra,
    }
    history = [
        {"role": "user", "text": body.question},
    ]
    profiles = db.FAMILY.get(user["id"], []) or []
    active = next((p for p in profiles if p.get("active")), None)
    effective_user = dict(user)
    if active:
        effective_user["name"] = active.get("name") or effective_user.get("name")
        effective_user["dob"] = active.get("dob") or effective_user.get("dob")
        effective_user["place"] = active.get("place") or effective_user.get("place")
        if active.get("tob"):
            effective_user["birthTime"] = active.get("tob")
            effective_user["birthTimeUnknown"] = False

    text, provider = generate_reply(
        pandit=pandit,
        history=history,
        user_text=body.question,
        user=effective_user,
    )
    blocks: List[Dict[str, Any]] = [
        {"type": "tarot_cards", "items": sess["drawn"]},
        {"type": "text", "text": text},
        {
            "type": "mantra",
            "title": "Soft tip",
            "text": "Is reading ko guidance maano — final decision apni vivek se lo.",
        },
    ]
    sess["lastReading"] = {
        "question": body.question,
        "text": text,
        "provider": provider,
        "at": int(time.time() * 1000),
    }
    persist_touch()
    return {
        "success": True,
        "text": text,
        "blocks": blocks,
        "provider": provider,
        "session": _public_session(sess),
        "reader": {"id": sess.get("readerId"), "name": sess.get("readerName")},
    }
