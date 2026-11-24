"""Astrologer "training" layer: chart context, Vedic playbook, few-shots.

Not a fine-tuned model — injects methodology so DeepSeek/Gemini answer like a
practising Indian jyotishi / tarot reader instead of generic chatbot fluff.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Sidereal-ish tropical date ranges for rashi (demo; not Swiss Ephemeris)
_RASHI: List[Tuple[int, int, str, str, str]] = [
    # (month, day_start_inclusive_for_this_sign_until_next), english, hindi, element
    (3, 21, "Aries", "Mesh", "fire"),
    (4, 20, "Taurus", "Vrishabh", "earth"),
    (5, 21, "Gemini", "Mithun", "air"),
    (6, 21, "Cancer", "Kark", "water"),
    (7, 23, "Leo", "Simha", "fire"),
    (8, 23, "Virgo", "Kanya", "earth"),
    (9, 23, "Libra", "Tula", "air"),
    (10, 23, "Scorpio", "Vrischik", "water"),
    (11, 22, "Sagittarius", "Dhanu", "fire"),
    (12, 22, "Capricorn", "Makar", "earth"),
    (1, 20, "Aquarius", "Kumbh", "air"),
    (2, 19, "Pisces", "Meen", "water"),
]

_NAKSHATRA_HINT = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
    "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
    "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
    "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati",
]


def parse_dob(dob: Optional[str]) -> Optional[datetime]:
    if not dob:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(dob).strip()[:10], fmt)
        except ValueError:
            continue
    return None


def sun_rashi(dob: Optional[str]) -> Optional[Dict[str, Any]]:
    """Approximate Surya rashi from DOB (tropical calendar cutovers)."""
    dt = parse_dob(dob)
    if not dt:
        return None
    m, d = dt.month, dt.day
    # (end_month, end_day, english, hindi, element) — inclusive end of each sign
    table = [
        (1, 19, "Capricorn", "Makar", "earth"),
        (2, 18, "Aquarius", "Kumbh", "air"),
        (3, 20, "Pisces", "Meen", "water"),
        (4, 19, "Aries", "Mesh", "fire"),
        (5, 20, "Taurus", "Vrishabh", "earth"),
        (6, 20, "Gemini", "Mithun", "air"),
        (7, 22, "Cancer", "Kark", "water"),
        (8, 22, "Leo", "Simha", "fire"),
        (9, 22, "Virgo", "Kanya", "earth"),
        (10, 22, "Libra", "Tula", "air"),
        (11, 21, "Scorpio", "Vrischik", "water"),
        (12, 21, "Sagittarius", "Dhanu", "fire"),
        (12, 31, "Capricorn", "Makar", "earth"),
    ]
    en, hi, el = "Aries", "Mesh", "fire"
    for em, ed, english, hindi, element in table:
        if (m, d) <= (em, ed):
            en, hi, el = english, hindi, element
            break
    nak = _NAKSHATRA_HINT[dt.timetuple().tm_yday % 27]
    return {
        "english": en,
        "hindi": hi,
        "element": el,
        "nakshatraHint": nak,
        "label": f"{hi} ({en})",
    }


def chart_context(user: Optional[Dict[str, Any]]) -> str:
    if not user:
        return "CHART CONTEXT: none — ask DOB + birth place before deep kundli claims."
    rashi = sun_rashi(user.get("dob"))
    lines = ["CHART CONTEXT (computed from profile — treat as working notes, not full kundli):"]
    if rashi:
        lines.append(
            f"- Approximate Surya rashi: {rashi['label']}, element={rashi['element']}, "
            f"nakshatra hint≈{rashi['nakshatraHint']} (approx; refine if TOB given)."
        )
    else:
        lines.append("- Surya rashi: unknown (no DOB).")
    if user.get("birthTime") and not user.get("birthTimeUnknown"):
        lines.append(f"- Birth time on file: {user.get('birthTime')} — you MAY speak gently about lagna themes.")
    else:
        lines.append("- Birth time missing — do NOT invent lagna/house numbers.")
    if user.get("place"):
        lines.append(f"- Birth/place: {user.get('place')}")
    if user.get("occupation"):
        lines.append(f"- Work lens: {user.get('occupation')}")
    if user.get("marriageStatus"):
        lines.append(f"- Relationship status: {user.get('marriageStatus')}")
    lines.append(
        "If DOB present: ground 1 prediction in rashi/element traits. "
        "Never invent dasha dates, exact degrees, or 'your 7th house Mars is…' without TOB."
    )
    return "\n".join(lines)


def methodology_block(pandit: Dict[str, Any]) -> str:
    persona = (pandit.get("persona") or "").lower()
    vedic = bool(pandit.get("isVedicAstrologer"))
    if "tarot" in persona or (not vedic and "palm" in persona):
        return (
            "METHOD (Tarot/intuitive reader): Read energy + cards metaphorically. "
            "Structure: (1) reflect question, (2) one clear theme, (3) practical next step, "
            "(4) soft upay. No fake planetary degrees. Calm, never fear-monger."
        )
    if "numero" in persona:
        return (
            "METHOD (Numerology): Use name/DOB digit themes (mulank/bhagyank style) if DOB known. "
            "Give 1 number focus + 1 behaviour tip + 1 upay. No kundli house fiction."
        )
    if "love" in persona or "relationship" in persona:
        return (
            "METHOD (Relationship jyotish): Venus/Moon themes in plain language. "
            "Respect marriageStatus. Timing windows as ranges (weeks), not fake exact dates."
        )
    if "career" in persona or "business" in persona:
        return (
            "METHOD (Career): 10th-house themes in plain language + Saturn discipline. "
            "Tie to occupation if known. One action this week + one mantra/upay."
        )
    return (
        "METHOD (Vedic jyotishi): Think like a practising pandit — "
        "rashi nature, dasha as 'life chapter' (only if DOB known, keep vague), "
        "remedies that are simple (mantra, daan, colour, weekday). "
        "Structure EVERY answer: "
        "(1) Empathy + restate sawaal, "
        "(2) Astro lens (rashi/element/life-area) using CHART CONTEXT, "
        "(3) Clear prediction window (days/weeks, not fake clock time), "
        "(4) One concrete upay, "
        "(5) Optional one clarifying question. "
        "Tone: calm senior pandit, Hinglish, no English essay, no markdown."
    )


def playbook_for_question(text: str) -> str:
    lower = (text or "").lower()
    tips: List[str] = []
    if any(k in lower for k in ("job", "career", "naukri", "salary", "promotion", "office")):
        tips.append(
            "Career playbook: speak of 10th-house effort + Mercury communication; "
            "suggest Guruvaar follow-ups; Surya/Gayatri style upay; warn against impulsive resignation."
        )
    if any(k in lower for k in ("marriage", "shadi", "love", "relationship", "boyfriend", "girlfriend")):
        tips.append(
            "Love playbook: Venus/Moon harmony; honest conversation; Shukravaar meetha daan; "
            "no scare about 'manglik curse' unless asked — keep balanced."
        )
    if any(k in lower for k in ("money", "finance", "loan", "property", "wealth", "paise")):
        tips.append(
            "Money playbook: steady Saturn discipline; avoid impulse after sunset; "
            "small regular daan; timing as week windows."
        )
    if any(k in lower for k in ("health", "tension", "anxiety", "sleep", "bimari")):
        tips.append(
            "Health playbook: lifestyle first; Chandra calm; never diagnose disease; "
            "suggest rest, jal, simple mantra — advise doctor for medical issues."
        )
    if any(k in lower for k in ("kundli", "chart", "horoscope", "lagna", "dasha")):
        tips.append(
            "Kundli playbook: if TOB missing, explain limitation and ask time; "
            "give rashi-level reading only; no invented house cusps."
        )
    if not tips:
        tips.append(
            "General playbook: pick the life area they mean; one insight + one upay; "
            "ask one sharp follow-up if vague."
        )
    return "TOPIC PLAYBOOK:\n- " + "\n- ".join(tips)


def few_shot_messages(pandit: Dict[str, Any], user: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """In-context training examples (not stored in chat history)."""
    name = pandit.get("name") or "Pandit Ji"
    female = (pandit.get("gender") or "").lower() == "female" or any(
        x in (pandit.get("name") or "").lower() for x in ("devi", "mata", "ananya", "meera", "kavya", "priya", "shweta")
    )
    see = "dekh rahi hoon" if female else "dekh raha hoon"
    say = "kehti hoon" if female else "kehta hoon"
    uname = ((user or {}).get("name") or "beta").split()[0]
    rashi = sun_rashi((user or {}).get("dob"))
    rashi_bit = rashi["label"] if rashi else "aapki rashi"
    occ = (user or {}).get("occupation") or "kaam"

    good = (
        f"{uname} ji, aapka naukri wala sawaal main samajh {see}. "
        f"{rashi_bit} ke hisaab se agle 3–5 hafte effort dikhane ka phase hai — "
        f"especially {occ} field me follow-up aur skill dikhana. "
        f"Jaldi resignation mat lo. Upay: Guruvaar subah 11 baar Gayatri, peela touch interview pe. "
        f"Ek baat batao — currently interview stage pe ho ya wait kar rahe ho? Main {say}."
    )
    bad_avoid = (
        "NEVER answer like this (bad): "
        "'Planets say you will get job on Tuesday at 4:12pm and Mars in 7th house degree 21...' "
        "or English essays, or fear curses, or ignore their name/DOB."
    )
    return [
        {
            "role": "system",
            "content": (
                f"TRAINING EXAMPLES for {name}. Imitate GOOD style only.\n"
                f"GOOD example reply:\n{good}\n\n{bad_avoid}"
            ),
        },
        {
            "role": "user",
            "content": "Will I get a job soon?",
        },
        {
            "role": "assistant",
            "content": good,
        },
        {
            "role": "user",
            "content": "And what about marriage timing?",
        },
        {
            "role": "assistant",
            "content": (
                f"{uname} ji, shadi/rishta pe main {see} — haste me haan mat bolna. "
                f"Agle 2–4 mahine clarity badhegi agar baat seedhi ho. "
                f"Upay: Shukravaar meetha daan, roz 5 minute bina phone conversation. "
                f"Status confirm karo — serious prospect hai ya abhi explore? Main {say}."
            ),
        },
    ]


def master_system(pandit: Dict[str, Any], user: Optional[Dict[str, Any]], user_text: str) -> str:
    """Full trained system prompt body (appended after persona/voice/profile)."""
    return "\n".join(
        [
            methodology_block(pandit),
            chart_context(user),
            playbook_for_question(user_text),
            (
                "QUALITY BAR: Sound like a real consultation — specific to THIS seeker, "
                "no copy-paste generic lines, no repeating the same upay every turn, "
                "no claiming to be AI. 90–140 words. Hinglish only."
            ),
        ]
    )


def daily_horoscope_for_user(user: Optional[Dict[str, Any]], base: Dict[str, Any]) -> Dict[str, Any]:
    """Personalize seeded horoscope payload by Surya rashi."""
    out = dict(base) if base else {"success": True, "data": {}}
    data = dict(out.get("data") or {})
    rashi = sun_rashi((user or {}).get("dob"))
    name = ((user or {}).get("name") or "").strip()
    if rashi:
        data["sign"] = rashi["label"]
        el = rashi["element"]
        summaries = {
            "fire": "Aaj initiative ka din hai — pehla step aap lo, baaki flow aayega.",
            "earth": "Steady kaam aur practical decisions aaj zyada phal denge.",
            "air": "Baat-cheet aur networking se raasta khulega — short clear messages.",
            "water": "Feelings strong hain — decisions thoda late lo, intuition suno.",
        }
        data["summary"] = summaries.get(el, data.get("summary") or "")
        if name:
            data["summary"] = f"{name.split()[0]} ji — " + data["summary"]
        lucky = dict(data.get("lucky") or {})
        lucky.setdefault("color", "Saffron")
        lucky["number"] = (hash(rashi["hindi"]) % 9) + 1
        data["lucky"] = lucky
        data["rashiMeta"] = rashi
    out["data"] = data
    out["success"] = True
    return out
