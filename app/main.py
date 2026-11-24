from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.llm import provider_status
from app.routers import astrology, auth, chat, family, home, payments
from app.routers.admin import public_router as tracking_public_router
from app.routers.admin import router as admin_router
from app.seed import seed
from app.ops_store import seed_demo_users, seed_ops_defaults
from app.persist import load_all, save_all
from app.settings_store import load_settings

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def _load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

app = FastAPI(title="Astro99 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth.router)
app.include_router(home.router)
app.include_router(chat.router)
app.include_router(astrology.router)
app.include_router(payments.router)
app.include_router(family.router)
app.include_router(admin_router)
app.include_router(tracking_public_router)


@app.on_event("startup")
def on_startup() -> None:
    host = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    from app import db

    restored = False
    try:
        restored = load_all()
    except Exception:  # noqa: BLE001
        restored = False

    # Always refresh catalog (pandits/images); user data kept if restored
    seed(base_url=host)
    seed_ops_defaults()
    if not restored or len(db.USERS) == 0:
        seed_demo_users()
    try:
        save_all()
    except Exception:  # noqa: BLE001
        pass
    # sync free message limit from admin settings
    try:
        limit = int(load_settings().get("app", {}).get("freeMessageLimit") or 5)
        db.FREE_MESSAGE_LIMIT = limit
    except Exception:  # noqa: BLE001
        pass
    # Testing: hard paywall + message recharge off while SKIP_PAYWALL=1
    if os.environ.get("SKIP_PAYWALL", "0") == "1":
        try:
            from app import ops_store as ops

            ops.FEATURE_FLAGS["paywall_enabled"] = False
        except Exception:  # noqa: BLE001
            pass
        for q in db.QUOTAS.values():
            q["unlimited"] = True
            q["is_premium"] = True


@app.get("/health")
def health():
    return {"ok": True, "service": "astro99-api", "chat": provider_status()}


@app.get("/")
def root():
    return RedirectResponse(url="/admin/")


@app.get("/admin")
def admin_redirect():
    return RedirectResponse(url="/admin/")
