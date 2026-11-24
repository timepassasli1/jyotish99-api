"""Classic Major Arcana deck (22) — text meanings only; faces use card-back art (no RW copyright)."""
from __future__ import annotations

from typing import Any, Dict, List

# Public-domain style meanings (editorial, not copied from a single copyrighted deck booklet).
MAJOR_ARCANA: List[Dict[str, Any]] = [
    {
        "id": "fool",
        "name": "The Fool",
        "number": 0,
        "upright": "Nayi shuruaat, trust the journey, halka risk lo.",
        "reversed": "Laaparwahi / impulsive step — pehle soch ke chalo.",
    },
    {
        "id": "magician",
        "name": "The Magician",
        "number": 1,
        "upright": "Tools tumhare paas hain — focus se manifest karo.",
        "reversed": "Talent waste / manipulation — intention clear rakho.",
    },
    {
        "id": "high_priestess",
        "name": "The High Priestess",
        "number": 2,
        "upright": "Inner voice strong hai — intuition pe bharosa.",
        "reversed": "Secrets / confusion — facts check karo.",
    },
    {
        "id": "empress",
        "name": "The Empress",
        "number": 3,
        "upright": "Abundance, care, creative growth.",
        "reversed": "Block creativity / self-care kam — rest lo.",
    },
    {
        "id": "emperor",
        "name": "The Emperor",
        "number": 4,
        "upright": "Structure, leadership, solid plans.",
        "reversed": "Control issues / rigid rules — soft bano.",
    },
    {
        "id": "hierophant",
        "name": "The Hierophant",
        "number": 5,
        "upright": "Guidance, tradition, mentor ki baat maano.",
        "reversed": "Blind tradition break karo — apna path.",
    },
    {
        "id": "lovers",
        "name": "The Lovers",
        "number": 6,
        "upright": "Connection, choice of heart, alignment.",
        "reversed": "Mismatch / tough choice — values pe decide.",
    },
    {
        "id": "chariot",
        "name": "The Chariot",
        "number": 7,
        "upright": "Willpower se jeet — direction clear rakho.",
        "reversed": "Scattered energy — one goal pe focus.",
    },
    {
        "id": "strength",
        "name": "Strength",
        "number": 8,
        "upright": "Patience + soft power wins.",
        "reversed": "Self-doubt — confidence rebuild karo.",
    },
    {
        "id": "hermit",
        "name": "The Hermit",
        "number": 9,
        "upright": "Alone time for clarity — reflect.",
        "reversed": "Isolation zyada — thoda connect karo.",
    },
    {
        "id": "wheel",
        "name": "Wheel of Fortune",
        "number": 10,
        "upright": "Luck shift — opportunity aa rahi hai.",
        "reversed": "Delay / cycle — patience, then move.",
    },
    {
        "id": "justice",
        "name": "Justice",
        "number": 11,
        "upright": "Fair outcome, truth, contracts clear.",
        "reversed": "Bias / unfair deal — document everything.",
    },
    {
        "id": "hanged",
        "name": "The Hanged Man",
        "number": 12,
        "upright": "Pause for new perspective.",
        "reversed": "Stuck feeling — release one attachment.",
    },
    {
        "id": "death",
        "name": "Death",
        "number": 13,
        "upright": "Ending → transformation (not literal).",
        "reversed": "Resisting change — let go gently.",
    },
    {
        "id": "temperance",
        "name": "Temperance",
        "number": 14,
        "upright": "Balance, healing, middle path.",
        "reversed": "Extremes — pace slow down.",
    },
    {
        "id": "devil",
        "name": "The Devil",
        "number": 15,
        "upright": "Attachment / temptation — awareness.",
        "reversed": "Breaking free from bad habit.",
    },
    {
        "id": "tower",
        "name": "The Tower",
        "number": 16,
        "upright": "Sudden shake-up clears false ground.",
        "reversed": "Delayed collapse — prepare early.",
    },
    {
        "id": "star",
        "name": "The Star",
        "number": 17,
        "upright": "Hope, healing, quiet blessings.",
        "reversed": "Faith low — small hope rituals.",
    },
    {
        "id": "moon",
        "name": "The Moon",
        "number": 18,
        "upright": "Emotions, dreams, unclear path — wait for light.",
        "reversed": "Confusion clearing — truth near.",
    },
    {
        "id": "sun",
        "name": "The Sun",
        "number": 19,
        "upright": "Clarity, success, joy — shine.",
        "reversed": "Temporary cloud — success delayed not denied.",
    },
    {
        "id": "judgement",
        "name": "Judgement",
        "number": 20,
        "upright": "Wake-up call, second chance, decide.",
        "reversed": "Self-doubt on calling — listen inward.",
    },
    {
        "id": "world",
        "name": "The World",
        "number": 21,
        "upright": "Completion, travel, goal achieved.",
        "reversed": "Almost there — finish loose ends.",
    },
]


DECK_META = {
    "id": "classic_major_v1",
    "name": "Classic Major Arcana",
    "cardCount": len(MAJOR_ARCANA),
    "note": "Major Arcana only (22). Card faces use branded back art (no Rider–Waite faces).",
}


def deck_cards(base_url: str) -> List[Dict[str, Any]]:
    back = f"{base_url.rstrip('/')}/static/tarot_card_back.webp"
    out = []
    for c in MAJOR_ARCANA:
        out.append(
            {
                **c,
                "imageUrl": back,  # intentional until licensed faces exist
                "backImageUrl": back,
            }
        )
    return out
