"""Admin session tokens (not password-as-token)."""
from __future__ import annotations

import secrets
import time
from typing import Dict, Optional, Tuple

# token -> {expires_at, created_at}
_SESSIONS: Dict[str, Dict[str, float]] = {}
TTL_SEC = 12 * 60 * 60  # 12h


def create_session() -> Tuple[str, float]:
    token = secrets.token_urlsafe(32)
    exp = time.time() + TTL_SEC
    _SESSIONS[token] = {"created_at": time.time(), "expires_at": exp}
    _gc()
    return token, exp


def validate_session(token: Optional[str]) -> bool:
    if not token:
        return False
    row = _SESSIONS.get(token)
    if not row:
        return False
    if time.time() > float(row["expires_at"]):
        _SESSIONS.pop(token, None)
        return False
    return True


def revoke_session(token: Optional[str]) -> None:
    if token:
        _SESSIONS.pop(token, None)


def _gc() -> None:
    now = time.time()
    dead = [k for k, v in _SESSIONS.items() if now > float(v["expires_at"])]
    for k in dead:
        _SESSIONS.pop(k, None)
