# Astro99 API

FastAPI backend for the Astro99 mobile clone. Mirrors the shipped app surface: OTP auth, home feed sections, pandits/characters, chat with message limits, membership/UPI mock checkout, horoscope, kundli, tarot, stories, family profiles.

## Run

```bash
cd /Users/admin/astro99-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health: http://127.0.0.1:8000/health  
Docs: http://127.0.0.1:8000/docs  

Dev OTP is always `123456`.
