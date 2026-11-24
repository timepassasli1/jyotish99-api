"""Live chat completions.

Original Astro99: Livo `complete-chat/v1.1` + GEMINI (server-side).
Clone default: DeepSeek (OpenAI-compatible) when DEEPSEEK_API_KEY is set.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from app.astro_coach import few_shot_messages, master_system


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _ollama_up() -> bool:
    base = _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        _http_json("GET", f"{base}/api/tags", timeout=2)
        return True
    except Exception:  # noqa: BLE001
        return False


def provider_status() -> Dict[str, Any]:
    deepseek = bool(_env("DEEPSEEK_API_KEY"))
    gemini = bool(_env("GEMINI_API_KEY"))
    ollama = _ollama_up()
    preferred = _env("CHAT_PROVIDER", "auto").lower()
    if preferred == "auto":
        if deepseek:
            pick = "deepseek"
        elif gemini:
            pick = "gemini"
        elif ollama:
            pick = "ollama"
        else:
            pick = "pollinations"
    else:
        pick = preferred
    return {
        "deepseek": deepseek,
        "gemini": gemini,
        "ollama": ollama,
        "pollinations": True,
        "preferred": pick,
    }


def _pandit_gender(pandit: Dict[str, Any]) -> str:
    g = (pandit.get("gender") or "").strip().lower()
    if g in {"female", "f", "woman", "girl"}:
        return "female"
    if g in {"male", "m", "man", "boy"}:
        return "male"
    name = (pandit.get("name") or "").lower()
    female_markers = (
        "mata",
        "devi",
        "pandita",
        "ananya",
        "meera",
        "kavya",
        "shweta",
        "priya",
        "rani",
        "maa ",
    )
    if any(m in name for m in female_markers):
        return "female"
    return "male"


def _voice_lines(gender: str) -> str:
    if gender == "female":
        return (
            "GENDER VOICE (MANDATORY): You are female. "
            "Use ONLY feminine Hindi: main karti hoon / dekh rahi hoon / sun rahi hoon / kehti hoon / sochti hoon. "
            "NEVER use masculine: karta/dekh raha/sun raha/kehta/sochta. "
            "Refer to yourself as Mata/didi tone when natural."
        )
    return (
        "GENDER VOICE (MANDATORY): You are male. "
        "Use masculine Hindi: main karta hoon / dekh raha hoon / kehta hoon."
    )


def _user_profile_block(user: Optional[Dict[str, Any]]) -> str:
    if not user:
        return (
            "SEEKER PROFILE: unknown.\n"
            "If birth/name details missing for a precise answer, ASK one missing detail — do not invent."
        )
    fields = {
        "name": user.get("name"),
        "gender": user.get("gender"),
        "dob": user.get("dob"),
        "birthTime": None if user.get("birthTimeUnknown") else user.get("birthTime"),
        "birthTimeUnknown": user.get("birthTimeUnknown"),
        "place": user.get("place"),
        "marriageStatus": user.get("marriageStatus"),
        "occupation": user.get("occupation"),
        "language": user.get("language"),
    }
    known = [f"{k}={v}" for k, v in fields.items() if v not in (None, "", False)]
    missing = [k for k, v in fields.items() if k != "birthTimeUnknown" and v in (None, "")]
    lines = [
        "SEEKER PROFILE (use only these facts — never invent birth data/charts):",
        ("- " + "; ".join(known)) if known else "- (almost empty profile)",
    ]
    if missing:
        lines.append(f"- Missing fields: {', '.join(missing)}")
    lines.append(
        "RULES: Address by name if known. Tie advice to dob/place/occupation/marriageStatus when present. "
        "Continue the conversation thread — reference their last messages. No generic 'hawa mein' predictions. "
        "NEVER claim exact planets/houses/dasha/transits for this user unless DOB + birthplace are known "
        "(and birth time if claiming houses/lagna). If missing, ask for it and stop inventing."
    )
    return "\n".join(lines)


def _enforce_gender_voice(text: str, gender: str) -> str:
    """First-person Hindi gender fixes so female pandits never sound male."""
    t = (text or "").strip()
    if not t:
        return t

    if gender == "female":
        to_fem = {
            "karta": "karti",
            "kehta": "kehti",
            "bolta": "bolti",
            "deta": "deti",
            "leta": "leti",
            "sochta": "sochti",
            "samajhta": "samajhti",
            "chahta": "chahti",
            "sakta": "sakti",
        }
        for a, b in to_fem.items():
            t = re.sub(rf"\b{a}\s+(hoon|hun|hūn)\b", rf"{b} \1", t, flags=re.IGNORECASE)
        t = re.sub(
            r"\b(dekh|sun|keh|bol|kar)\s+raha\s+(hoon|hun|hūn)\b",
            r"\1 rahi \2",
            t,
            flags=re.IGNORECASE,
        )
        t = re.sub(r"\braha\s+(hoon|hun|hūn)\b", r"rahi \1", t, flags=re.IGNORECASE)
        for a, b in {
            "karunga": "karungi",
            "dunga": "dungi",
            "bataunga": "bataungi",
            "dekhunga": "dekhungi",
            "sununga": "sunungi",
            "jaunga": "jaungi",
        }.items():
            t = re.sub(rf"\b{a}\b", b, t, flags=re.IGNORECASE)
    else:
        to_masc = {
            "karti": "karta",
            "kehti": "kehta",
            "bolti": "bolta",
            "deti": "deta",
            "leti": "leta",
            "sochti": "sochta",
            "samajhti": "samajhta",
            "chahti": "chahta",
            "sakti": "sakta",
        }
        for a, b in to_masc.items():
            t = re.sub(rf"\b{a}\s+(hoon|hun|hūn)\b", rf"{b} \1", t, flags=re.IGNORECASE)
        t = re.sub(
            r"\b(dekh|sun|keh|bol|kar)\s+rahi\s+(hoon|hun|hūn)\b",
            r"\1 raha \2",
            t,
            flags=re.IGNORECASE,
        )
        t = re.sub(r"\brahi\s+(hoon|hun|hūn)\b", r"raha \1", t, flags=re.IGNORECASE)
        for a, b in {
            "karungi": "karunga",
            "dungi": "dunga",
            "bataungi": "bataunga",
            "dekhungi": "dekhunga",
            "sunungi": "sununga",
            "jaungi": "jaunga",
        }.items():
            t = re.sub(rf"\b{a}\b", b, t, flags=re.IGNORECASE)
    return t


def generate_reply(
    *,
    pandit: Dict[str, Any],
    history: List[Dict[str, Any]],
    user_text: str,
    user: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Return (reply_text, provider_name)."""
    system = _system_prompt(pandit, user, user_text)
    messages = _to_messages(system, history, user_text, pandit=pandit, user=user)
    preferred = _env("CHAT_PROVIDER", "auto").lower()
    gender = _pandit_gender(pandit)

    # DEMO quality lock: DeepSeek → Gemini → trained template.
    # Skip ollama/pollinations unless explicitly CHAT_PROVIDER=ollama|pollinations
    # (tiny local models were producing weird non-pandit answers).
    if preferred == "auto":
        order = ["deepseek", "gemini", "template"]
    elif preferred == "template":
        order = ["template"]
    elif preferred in {"ollama", "pollinations"}:
        order = [preferred, "deepseek", "gemini", "template"]
    else:
        order = [preferred, "deepseek", "gemini", "template"]

    reply = ""
    provider = "template"
    for name in order:
        if name == "deepseek":
            if not _env("DEEPSEEK_API_KEY"):
                continue
            try:
                reply, provider = _deepseek_generate(messages), "deepseek"
                break
            except Exception:  # noqa: BLE001 — try next provider (e.g. ollama)
                continue
        if name == "gemini":
            if not _env("GEMINI_API_KEY"):
                continue
            try:
                reply, provider = _gemini_generate(system, messages), "gemini"
                break
            except Exception:  # noqa: BLE001
                continue
        if name == "ollama":
            try:
                reply, provider = _ollama_generate(system, messages), "ollama"
                break
            except Exception:  # noqa: BLE001
                continue
        if name == "pollinations":
            try:
                reply, provider = _pollinations_generate(messages), "pollinations"
                break
            except Exception:  # noqa: BLE001
                continue
        if name == "template":
            reply, provider = _template_reply(pandit, user_text, history, user), "template"
            break
    else:
        reply, provider = _template_reply(pandit, user_text, history, user), "template"

    return _enforce_gender_voice(reply, gender), provider


def _system_prompt(
    pandit: Dict[str, Any],
    user: Optional[Dict[str, Any]] = None,
    user_text: str = "",
) -> str:
    name = pandit.get("name") or "Pandit Ji"
    persona = pandit.get("persona") or "Vedic Astrologer"
    about = pandit.get("about") or ""
    gender = _pandit_gender(pandit)
    prompt = pandit.get("prompt") or f"You are {name}, a warm Indian {persona}."
    think = (
        "main dekh rahi hoon / sun rahi hoon"
        if gender == "female"
        else "main dekh raha hoon / sun raha hoon"
    )
    return (
        f"{prompt}\n"
        f"Persona: {persona}. {about}\n"
        f"{_voice_lines(gender)}\n"
        f"{_user_profile_block(user)}\n"
        f"{master_system(pandit, user, user_text)}\n"
        "Speak ONLY as this pandit in warm Hinglish (simple Hindi + English).\n"
        "HARD RULES: First sentence must paraphrase the seeker's last message. "
        "If you previously asked something, acknowledge whether they answered. "
        "If birth details are missing for kundli-style claims, ask ONLY for missing DOB/TOB/place and stop — "
        "no planet/house/dasha claims without them.\n"
        "FLOW: 1) Acknowledge question + profile fact. "
        "2) Astro lens from CHART CONTEXT. "
        "3) Clear timing window. "
        "4) One upay. "
        "5) One short follow-up if needed.\n"
        f"Sound thoughtful — natural pause like 'dekho' / '{think}' once if it fits.\n"
        "No markdown, no bullets, no English-only essays, no repeating the same sentence.\n"
        "Never say you are an AI/LLM/DeepSeek/Google/Gemini. Aim 90–140 words."
    )


def _to_messages(
    system: str,
    history: List[Dict[str, Any]],
    user_text: str,
    pandit: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = [{"role": "system", "content": system}]
    # In-context training (few-shots) before live thread
    if pandit:
        msgs.extend(few_shot_messages(pandit, user))
    for m in history[-16:]:
        role = m.get("role")
        text = (m.get("text") or "").strip()
        if not text or text == "…" or role not in {"user", "assistant"}:
            continue
        if m.get("pending"):
            continue
        msgs.append({"role": role, "content": text})
    ut = user_text.strip()
    if not msgs or msgs[-1].get("content") != ut:
        msgs.append({"role": "user", "content": ut})
    return msgs


def _http_json(
    method: str,
    url: str,
    payload: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = 45,
) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read().decode("utf-8", "ignore")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {e.code}: {err[:300]}") from e


def _deepseek_generate(messages: List[Dict[str, str]]) -> str:
    key = _env("DEEPSEEK_API_KEY")
    base = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = _env("DEEPSEEK_MODEL", "deepseek-chat")
    url = f"{base}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.65,
        "max_tokens": 420,
        "stream": False,
    }
    data = _http_json(
        "POST",
        url,
        payload,
        headers={"Authorization": f"Bearer {key}"},
        timeout=60,
    )
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected DeepSeek payload: {json.dumps(data)[:240]}") from exc
    return str(text).strip()


def _gemini_generate(system: str, messages: List[Dict[str, str]]) -> str:
    key = _env("GEMINI_API_KEY")
    model = _env("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    contents: List[Dict[str, Any]] = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.65,
            "maxOutputTokens": 420,
        },
    }
    data = _http_json("POST", url, payload)
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini payload: {json.dumps(data)[:240]}") from exc
    return text.strip()


def _ollama_generate(system: str, messages: List[Dict[str, str]]) -> str:
    base = _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = _env("OLLAMA_MODEL", "llama3.2:1b")
    payload = {
        "model": model,
        "stream": False,
        "messages": messages,
        "options": {"temperature": 0.7, "num_predict": 140, "top_p": 0.9},
    }
    data = _http_json("POST", f"{base}/api/chat", payload, timeout=90)
    msg = (data.get("message") or {}).get("content")
    if not msg:
        raise RuntimeError(f"Unexpected ollama payload: {json.dumps(data)[:240]}")
    return str(msg).strip()


def _pollinations_generate(messages: List[Dict[str, str]]) -> str:
    url = _env("POLLINATIONS_URL", "https://text.pollinations.ai/openai")
    payload = {
        "model": _env("POLLINATIONS_MODEL", "openai"),
        "messages": messages,
    }
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            data = _http_json("POST", url, payload, timeout=60)
            if data.get("status") in {402, 503} or data.get("success") is False:
                raise RuntimeError(data.get("error", {}).get("message") or json.dumps(data)[:200])
            try:
                return data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError, AttributeError) as exc:
                if isinstance(data, str):
                    return data.strip()
                raise RuntimeError(f"Unexpected pollinations payload: {json.dumps(data)[:240]}") from exc
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last) if last else "pollinations failed")


def _template_reply(
    pandit: Dict[str, Any],
    text: str,
    history: List[Dict[str, Any]],
    user: Optional[Dict[str, Any]] = None,
) -> str:
    name = pandit.get("name") or "Pandit Ji"
    female = _pandit_gender(pandit) == "female"
    lower = text.lower()
    prior_user = [m.get("text", "") for m in history if m.get("role") == "user"]
    follow = len(prior_user) > 1
    uname = ((user or {}).get("name") or "").strip()
    dob = (user or {}).get("dob")
    place = (user or {}).get("place")
    occ = (user or {}).get("occupation")
    mstatus = (user or {}).get("marriageStatus")
    tob = None if (user or {}).get("birthTimeUnknown") else (user or {}).get("birthTime")
    address = f"{uname} ji, " if uname else ""
    profile_bit = ""
    if dob or place or occ:
        bits = []
        if dob:
            bits.append(f"DOB {dob}")
        if place:
            bits.append(f"{place} se")
        if occ:
            bits.append(f"{occ} background")
        profile_bit = " (" + ", ".join(bits) + ")"

    # feminine / masculine verb packs
    if female:
        see, say, do_, listen, think = (
            "dekh rahi hoon",
            "kehti hoon",
            "karti hoon",
            "sun rahi hoon",
            "sochti hoon",
        )
        give = "deti hoon"
        speak = "bolti hoon"
    else:
        see, say, do_, listen, think = (
            "dekh raha hoon",
            "kehta hoon",
            "karta hoon",
            "sun raha hoon",
            "sochta hoon",
        )
        give = "deta hoon"
        speak = "bolta hoon"

    if any(k in lower for k in ("job", "career", "naukri", "salary", "promotion")):
        hook = f"{address}main aapka career sawaal dheere se {see}."
        if occ:
            hook += f" Aap {occ} field me ho, isliye advice usi angle se {give}."
        elif not dob:
            return (
                f"{address}career ke liye exact direction chahiye to pehle DOB "
                f"(aur city) batao — bina uske main hawa me prediction nahi {do_}. "
                f"Abhi general tip: is hafte impulsive resignation mat lo, Guruvaar pe follow-up try karo."
            )
        base = (
            f"{hook}{profile_bit} Agle 21–45 din active dikh rahe hain — "
            "opportunity ya follow-up ke signs hain. Jaldi switch mat lo. "
            "Upay: subah Surya mantra 11 baar, interview se pehle peela/kesari touch, "
            f"Guruvaar ko ek important mail/call complete karo — main {say}."
        )
    elif any(k in lower for k in ("marriage", "shadi", "love", "relationship", "boyfriend", "girlfriend")):
        status = f" Aapki status ({mstatus}) ko dhyan me rakhte hue {speak}." if mstatus else ""
        if not dob and not mstatus:
            return (
                f"{address}rishton pe clear baat {do_}, lekin pehle marriage status aur DOB batao — "
                f"bina uske generic love line nahi {give}. "
                f"Abhi: dil ki baat seedhe bolo, badi commitment 1–2 hafta rok lo."
            )
        base = (
            f"{address}suno, rishton wali energy abhi sensitive hai.{status} "
            f"Main {see} — clarity badhegi, lekin abhi honest conversation better hai. "
            f"Upay: Shukravaar meetha daan. Main {say}."
        )
    elif any(k in lower for k in ("lucky", "color", "rang", "number")):
        base = (
            f"{address}main pehle aapki energy {see}, phir number {give}. "
            f"Aaj lucky color kesari/saffron, number 9"
            + (f" — {place} vibe ke saath" if place else "")
            + f". Subah warm tone pehno; pehla kaam 11:00–12:30 try karo. Main {say}."
        )
    elif any(k in lower for k in ("kundli", "chart", "horoscope", "lagna")):
        if not dob or not place:
            miss = []
            if not dob:
                miss.append("date of birth")
            if not place:
                miss.append("birth place")
            if not tob:
                miss.append("birth time (approx OK)")
            return (
                f"{address}kundli ke liye mujhe {', '.join(miss)} chahiye. "
                f"Bina iske house-by-house reading hawa me nahi {do_}. "
                f"Details bhejo, phir main clearly {see}."
            )
        base = (
            f"{address}aapka chart ({dob}"
            + (f", {tob}" if tob else "")
            + f", {place}) ke hisaab se {see}. "
            f"Lagna bold moves support karta hai, lekin rush se nahi. "
            f"Tip: 12 baje se pehle important kaam finish karo. Main {say}."
        )
    elif any(k in lower for k in ("remedy", "upay", "mantra", "puja")):
        base = (
            f"{address}upay jaldbazi se nahi, consistency se kaam {do_}. "
            f"Main {say}: 11 din subah Hanuman Chalisa, til ka diya, anna daan. "
            "Tension ho to raat 5 minute shwas. Routine mat todo."
        )
    elif any(k in lower for k in ("muhurat", "shubh", "timing")):
        base = (
            f"{address}timing ka sawaal hai to main jaldi nahi {speak}. "
            f"Agle 3 din dopahar se pehle better window hai"
            + (f" — {place} ke din-chakra ko bhi soft rakhte hue" if place else "")
            + f". Mangalvaar vivad avoid; Guruvaar meetings better. Main {say}."
        )
    else:
        ask = "career, love, health, ya money"
        base = (
            f"{address}namaste — main {listen}, thoda {think}, phir jawab {give}. "
            f"Aaj pehle chhota action better hai"
            + (f", especially with your {occ} path" if occ else "")
            + f". Sawaal {ask} me specific karo taaki exact upay de sakun — "
            f"hawa me prediction nahi {do_}."
        )

    if follow:
        prev = (prior_user[-2] or "")[:60]
        base += (
            f" Pehli baat ('{prev}…') ko dhyan me rakhte hue {speak} — "
            "ek theme pe focused raho."
        )
    return base


def enrich_blocks(
    *,
    pandit: Dict[str, Any],
    user_text: str,
    reply_text: str,
) -> List[Dict[str, Any]]:
    """Build rich chat cells matching original Astro99 message cell types."""
    lower = (user_text or "").lower()
    blocks: List[Dict[str, Any]] = [{"type": "text", "text": reply_text}]

    if any(k in lower for k in ("lucky", "color", "rang", "number")):
        blocks.append({"type": "lucky", "color": "Saffron", "number": 9, "time": "11:00–12:30"})
    if any(k in lower for k in ("muhurat", "shubh", "timing", "muhurat")):
        blocks.append(
            {
                "type": "muhurat",
                "title": "Shubh muhurat",
                "window": "Subah 9:00 – 11:30",
                "note": "Mangalvaar pe naya vivad avoid karein",
            }
        )
    if any(k in lower for k in ("remedy", "upay", "mantra", "puja", "chalisa")):
        blocks.append(
            {
                "type": "mantra",
                "title": "Mantra / Upay",
                "text": "11 din subah Hanuman Chalisa · til ka diya · anna daan",
            }
        )
    if any(k in lower for k in ("kundli", "chart", "lagna", "house")):
        blocks.append(
            {
                "type": "calculation",
                "title": "Quick chart notes",
                "rows": [
                    {"label": "Lagna", "value": "Bold moves OK"},
                    {"label": "Focus", "value": "Before noon"},
                    {"label": "Need", "value": "Exact birth time"},
                ],
            }
        )
    if any(k in lower for k in ("job", "career", "marriage", "love", "naukri", "shadi")):
        blocks.append(
            {
                "type": "action",
                "title": "Aage kya karein?",
                "options": [
                    {"id": "remedy", "label": "Remedy / upay batao"},
                    {"id": "timing", "label": "Shubh timing?"},
                    {"id": "more", "label": "Aur detail chahiye"},
                ],
            }
        )

    # Always offer related experts (original recommended_experts cell)
    others = [p for p in db_pandits_safe() if str(p.get("id")) != str(pandit.get("id"))][:3]
    if others:
        blocks.append(
            {
                "type": "experts",
                "title": "Recommended experts",
                "items": [
                    {
                        "id": str(p["id"]),
                        "name": p.get("name"),
                        "persona": p.get("persona"),
                        "imageUrl": p.get("profileImageUrl"),
                    }
                    for p in others
                ],
            }
        )
    return blocks


def db_pandits_safe() -> List[Dict[str, Any]]:
    try:
        from app import db

        return list(db.PANDITS)
    except Exception:  # noqa: BLE001
        return []
