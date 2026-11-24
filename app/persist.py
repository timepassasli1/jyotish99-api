"""SQLite persistence for core runtime stores (survives API restart)."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "data" / "astro99.db"
_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS kv (
          ns TEXT NOT NULL,
          key TEXT NOT NULL,
          value TEXT NOT NULL,
          PRIMARY KEY (ns, key)
        )
        """
    )
    c.commit()
    return c


def save_all() -> None:
    from app import db
    from app import ops_store as ops

    payload = {
        "USERS": db.USERS,
        "SESSIONS": {k: v for k, v in db.SESSIONS.items()},  # user sessions
        "OTPS": db.OTPS,
        "FAMILY": db.FAMILY,
        "CHATS": db.CHATS,
        "QUOTAS": db.QUOTAS,
        "MEMBERSHIPS": db.MEMBERSHIPS,
        "ORDERS": db.ORDERS,
        "PLANS": db.PLANS,
        "SUGGESTED_QUESTIONS": db.SUGGESTED_QUESTIONS,
        "ops": {
            "PROMOS": ops.PROMOS,
            "FEATURE_FLAGS": ops.FEATURE_FLAGS,
            "PUSH_CAMPAIGNS": ops.PUSH_CAMPAIGNS,
            "AUDIT_LOG": ops.AUDIT_LOG[:200],
            "SUPPORT_NOTES": ops.SUPPORT_NOTES,
            "BANNED": ops.BANNED,
            "ANNOUNCEMENTS": ops.ANNOUNCEMENTS,
            "WEBHOOKS": ops.WEBHOOKS,
        },
    }
    with _LOCK:
        c = _conn()
        try:
            c.execute(
                "INSERT OR REPLACE INTO kv(ns, key, value) VALUES (?,?,?)",
                ("core", "snapshot", json.dumps(payload)),
            )
            c.commit()
        finally:
            c.close()


def load_all() -> bool:
    from app import db
    from app import ops_store as ops

    with _LOCK:
        c = _conn()
        try:
            row = c.execute(
                "SELECT value FROM kv WHERE ns=? AND key=?",
                ("core", "snapshot"),
            ).fetchone()
        finally:
            c.close()
    if not row:
        return False
    try:
        data = json.loads(row[0])
    except Exception:  # noqa: BLE001
        return False

    def _load(name: str, target: Any) -> None:
        src = data.get(name)
        if src is None:
            return
        if isinstance(target, dict):
            target.clear()
            target.update(src)
        elif isinstance(target, list):
            target.clear()
            target.extend(src)

    _load("USERS", db.USERS)
    _load("SESSIONS", db.SESSIONS)
    _load("OTPS", db.OTPS)
    _load("FAMILY", db.FAMILY)
    _load("CHATS", db.CHATS)
    _load("QUOTAS", db.QUOTAS)
    _load("MEMBERSHIPS", db.MEMBERSHIPS)
    _load("ORDERS", db.ORDERS)
    if data.get("PLANS"):
        db.PLANS.clear()
        db.PLANS.extend(data["PLANS"])
    if data.get("SUGGESTED_QUESTIONS"):
        db.SUGGESTED_QUESTIONS.clear()
        db.SUGGESTED_QUESTIONS.extend(data["SUGGESTED_QUESTIONS"])

    op = data.get("ops") or {}
    for name, target in [
        ("PROMOS", ops.PROMOS),
        ("PUSH_CAMPAIGNS", ops.PUSH_CAMPAIGNS),
        ("AUDIT_LOG", ops.AUDIT_LOG),
        ("ANNOUNCEMENTS", ops.ANNOUNCEMENTS),
        ("WEBHOOKS", ops.WEBHOOKS),
    ]:
        if op.get(name) is not None:
            target.clear()
            target.extend(op[name])
    if op.get("FEATURE_FLAGS"):
        ops.FEATURE_FLAGS.clear()
        ops.FEATURE_FLAGS.update(op["FEATURE_FLAGS"])
    if op.get("SUPPORT_NOTES"):
        ops.SUPPORT_NOTES.clear()
        ops.SUPPORT_NOTES.update(op["SUPPORT_NOTES"])
    if op.get("BANNED"):
        ops.BANNED.clear()
        ops.BANNED.update(op["BANNED"])
    return True


def touch() -> None:
    """Best-effort persist after mutations."""
    try:
        save_all()
    except Exception:  # noqa: BLE001
        pass
