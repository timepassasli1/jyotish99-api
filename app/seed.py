"""Seed pandits, home feed, plans, horoscope — shapes mirror Astro99 CharacterData / HomeSectionType."""
from __future__ import annotations

from app import db

# name, persona, is_vedic, rating, gender
PANDIT_NAMES = [
    ("Ramdutt Astro", "Vedic Astrologer", True, "4.9", "male"),
    ("Pandit Rajesh Joshi", "Kundli Expert", True, "4.8", "male"),
    ("Mata Ananya Devi", "Tarot & Palmistry", False, "4.7", "female"),
    ("Guru Devansh", "Numerology Guide", False, "4.6", "male"),
    ("Acharya Meera", "Love & Relationship", True, "4.9", "female"),
    ("Pandit Suresh Shastri", "Career Guidance", True, "4.5", "male"),
    ("Kavya Tarot", "Daily Tarot Reader", False, "4.8", "female"),
    ("Acharya Nitin", "Muhurat Specialist", True, "4.7", "male"),
    ("Pandita Shweta", "Remedies & Mantra", True, "4.6", "female"),
    ("Arjun Mystic", "Dream Analysis", False, "4.4", "male"),
    ("Acharya Priya", "Child Astrology", True, "4.8", "female"),
    ("Pandit Mohan Ji", "Business Horoscope", True, "4.5", "male"),
]


SERVICES = [
    "Kundli Analysis",
    "Career Guidance",
    "Love & Marriage",
    "Remedies",
    "Muhurat",
    "Tarot Reading",
]

REVIEW_TEMPLATES = [
    ("Ankit S.", "Bahut accurate prediction mili. Thank you guruji!"),
    ("Priya M.", "Patience se samjhaya, remedies kaam aayi."),
    ("Rahul K.", "Career ke bare me clear direction diya."),
    ("Sneha R.", "Chat quick thi aur answers practical the."),
    ("Vikram D.", "Marriage timing bilkul sahi nikla."),
]


def seed(base_url: str = "http://127.0.0.1:8000") -> None:
    db.PANDITS.clear()
    for i, (name, persona, vedic, rating, gender) in enumerate(PANDIT_NAMES, start=1):
        years = 8 + (i % 15)
        consultations = 1200 + i * 173
        langs = "Hindi, English" if i % 2 else "Hindi, Sanskrit"
        female = gender == "female"
        # v=2 busts client cache after regenerating portraits
        photo = f"{base_url}/static/pandits/p{i}.webp?v=2"
        photos = [photo] + [
            f"{base_url}/static/pandits/gallery/p{i}_g{g}.webp?v=2" for g in range(3)
        ]
        reviews = [
            {
                "id": f"r-{i}-{j}",
                "name": REVIEW_TEMPLATES[j % len(REVIEW_TEMPLATES)][0],
                "daysAgo": f"{(j + 1) * 3} days ago",
                "rating": 5 if j % 3 else 4,
                "comment": REVIEW_TEMPLATES[j % len(REVIEW_TEMPLATES)][1],
                "avatarUrl": f"{base_url}/static/avatars/a{(j % 6) + 1}.webp?v=2",
            }
            for j in range(4)
        ]
        services = SERVICES[:4] if vedic else ["Tarot Reading", "Love & Marriage", "Career Guidance", "Remedies"]
        voice = (
            "You are a woman. Always use feminine Hindi (main karti hoon, dekh rahi hoon, kehti hoon). Never masculine verbs."
            if female
            else "You are a man. Use masculine Hindi (main karta hoon, dekh raha hoon, kehta hoon)."
        )
        db.PANDITS.append(
            {
                "characterId": i,
                "id": str(i),
                "name": name,
                "gender": gender,
                "persona": persona,
                "personaIconUrl": photo,
                "profileImageUrl": photo,
                "bannerImages": photos[:3],
                "photos": photos,
                "rating": rating,
                "experienceYears": years,
                "consultations": consultations,
                "languages": langs,
                "about": (
                    f"{name} is a trusted {persona.lower()} with {years}+ years of practice. "
                    f"Known for clear guidance in Hindi and practical remedies."
                ),
                "services": services,
                "reviews": reviews,
                "reviewCount": 80 + i * 11,
                "characterType": "vedic" if vedic else "tarot",
                "details": f"A powerhouse of {persona.lower()} to keep your path clear!",
                "prompt": (
                    f"You are {name}, a practising Indian {('woman ' if female else '')}{persona} "
                    f"with {years}+ years of consultation experience on Astro99. {voice} "
                    f"You trained under classical jyotish/tarot discipline: listen first, then rashi-based guidance, "
                    f"then one clear timing window, then one simple upay. Never fear-monger. Warm Hinglish only."
                ),
                "isVedicAstrologer": vedic,
                "intro": {
                    "title": f"Namaste, main {name} hoon",
                    "subtitle": (
                        "Bataiye, aaj aap kya jaanna chahte hain? Main aapki baat dhyan se sunungi."
                        if female
                        else "Bataiye, aaj aap kya jaanna chahte hain? Main aapki baat dhyan se sununga."
                    ),
                },
                "latestMessageText": [
                    "Apna pehla sawaal likhein…",
                    "Haan, aaj ka muhurat accha hai.",
                    "Kundli ke hisaab se sab theek hai.",
                    "Main aapki madad ke liye yahan hoon.",
                ][i % 4],
                "latestMessageTime": ["10:42 PM", "Yesterday", "2:15 PM", "Just now"][i % 4],
                "expertiseTag": "Vedic · Love & Career" if vedic else "Tarot · Guidance",
                "latestMessageTimestamp": 1_700_000_000_000 + i * 1000,
                "menuOptions": [
                    {"id": "clear", "label": "Clear chat"},
                    {"id": "report", "label": "Report"},
                ],
            }
        )

    db.SUGGESTED_QUESTIONS[:] = [
        "Will I get a job soon?",
        "Is this a good time for marriage?",
        "What does my kundli say about career?",
        "Which remedy suits me today?",
        "Tell me today's lucky color",
        "When is the next shubh muhurat?",
    ]

    stories = [
        {
            "id": f"story-{i}",
            "title": title,
            "coverUrl": f"{base_url}/static/stories/s{i}.webp?v=2",
            "pages": [
                {
                    "type": "luck_meter",
                    "title": title,
                    "score": 55 + i * 3,
                    "bands": [
                        {"label": "Low", "from": 0, "to": 40},
                        {"label": "Medium", "from": 40, "to": 70},
                        {"label": "High", "from": 70, "to": 100},
                    ],
                    "body": f"Your {title.lower()} energy looks promising if you stay focused.",
                },
                {
                    "type": "muhurat",
                    "title": "Shubh Samay",
                    "highlights": [
                        {"label": "Best", "range": "10:30 – 12:15"},
                        {"label": "Avoid", "range": "15:00 – 16:30"},
                    ],
                },
                {
                    "type": "mantra",
                    "title": "Today's Mantra",
                    "text": "Om Namah Shivaya",
                    "count": 108,
                },
            ],
        }
        for i, title in enumerate(
            ["Love Luck", "Career Glow", "Wealth Flow", "Health Pulse", "Family Peace", "Travel Luck"],
            start=1,
        )
    ]
    db.STORIES[:] = stories

    db.TAROT_CARDS[:] = [
        {
            "id": f"card-{i}",
            "name": name,
            "meaning": meaning,
            "imageUrl": f"{base_url}/static/tarot_card_back.webp",
            "reversed": False,
        }
        for i, (name, meaning) in enumerate(
            [
                ("The Sun", "Clarity and success are near."),
                ("The Star", "Hope returns after a quiet phase."),
                ("Wheel of Fortune", "A sudden shift favors you."),
                ("The Magician", "You already have the tools."),
                ("Ace of Cups", "New emotional beginnings."),
                ("Strength", "Patience will win today."),
            ],
            start=1,
        )
    ]

    # Order mirrors original new-home recycler sections
    db.HOME_FEED[:] = [
        {
            "type": "HEADER_1",
            "title": "Namaste 🙏",
            "subtitle": "Apni kundli ke bare me puche..",
        },
        {
            "type": "STORIES",
            "title": "Stories",
            "items": [
                {"id": s["id"], "title": s["title"], "coverUrl": s["coverUrl"]} for s in stories
            ],
        },
        {
            "type": "QUESTION_STRIP",
            "title": "Apni kundli ke bare me puche..",
            "items": [{"id": f"q-{i}", "text": q} for i, q in enumerate(db.SUGGESTED_QUESTIONS)],
        },
        {
            "type": "RECENT_CHATS_CAROUSEL",
            "title": "Your Chats",
            "items": db.PANDITS[:6],
        },
        {
            "type": "CARD_ACTIONS_CAROUSEL",
            "title": "Explore",
            "items": [
                {
                    "id": "horoscope",
                    "title": "Daily Horoscope",
                    "route": "/horoscope",
                    "imageUrl": f"{base_url}/static/app_logo.webp",
                },
                {
                    "id": "kundli",
                    "title": "कुंडली देखें",
                    "route": "/kundli",
                    "imageUrl": f"{base_url}/static/digi_icon.png",
                },
                {
                    "id": "tarot",
                    "title": "Daily Tarot",
                    "route": "/tarot",
                    "imageUrl": f"{base_url}/static/tarot_card_back.webp",
                },
                {
                    "id": "stories",
                    "title": "Stories",
                    "route": "/stories",
                    "imageUrl": f"{base_url}/static/stories/s1.webp",
                },
            ],
        },
        {
            "type": "ACTION_BANNER",
            "title": "आपका मेम्बरशिप खत्म हो गया है, रिचार्ज करें",
            "subtitle": "200 Message Limit · ₹1 trial · Autopay ₹199",
            "cta": "Recharge",
            "action": "open_plans",
        },
        {
            "type": "TAROT_READERS_GRID",
            "title": "Tarot Readers",
            "items": [p for p in db.PANDITS if not p["isVedicAstrologer"]],
        },
        {
            "type": "RECENT_CHATS",
            "title": "Astrologers",
            "items": db.PANDITS,
        },
    ]

    db.PLANS[:] = [
        {
            "id": "trial1",
            "name": "10 Minutes trial",
            "price": 1,
            "currency": "INR",
            "messages": 200,
            "durationMinutes": 10,
            "durationDays": 0,
            "durationLabel": "10 minutes",
            "unlimited": False,
            "highlight": True,
            "autopay": True,
            "renewPrice": 199,
            "autoRenewText": "After trial ₹199/month for 200 Message Limit. Cancel anytime. Subscription auto-renews.",
            "benefits": ["10 min trial", "200 messages after renew", "UPI Autopay @ ₹199"],
        },
        {
            "id": "plus",
            "name": "Plus",
            "price": 299,
            "currency": "INR",
            "messages": 200,
            "durationDays": 30,
            "durationLabel": "30 days",
            "unlimited": False,
            "highlight": False,
            "autopay": True,
            "renewPrice": 299,
            "autoRenewText": "After trial ₹199/month for 200 Message Limit. Cancel anytime. Subscription auto-renews.",
            "benefits": ["200 chat messages", "Priority pandits", "Full kundli + tarot", "UPI Autopay"],
        },
        {
            "id": "pro",
            "name": "Pro Unlimited",
            "price": 699,
            "currency": "INR",
            "messages": None,
            "durationDays": 30,
            "durationLabel": "30 days",
            "unlimited": True,
            "highlight": False,
            "autopay": True,
            "renewPrice": 699,
            "autoRenewText": "Cancel anytime. Subscription auto-renews.",
            "benefits": ["Unlimited messages", "All readers", "UPI Autopay"],
        },
    ]

    db.HOROSCOPE.clear()
    db.HOROSCOPE.update(
        {
            "success": True,
            "data": {
                "sign": "Mesh (Aries)",
                "date": "Today",
                "summary": "A strong day for decisive action. Keep conversations short and clear.",
                "categories": [
                    {"type": "love", "title": "Love", "score": 78, "text": "Warm connections open if you initiate."},
                    {"type": "career", "title": "Career", "score": 84, "text": "A mentor notices your consistency."},
                    {"type": "health", "title": "Health", "score": 71, "text": "Hydrate and rest your eyes."},
                    {"type": "finance", "title": "Finance", "score": 66, "text": "Avoid impulse spends after sunset."},
                ],
                "lucky": {
                    "color": "Saffron",
                    "number": 9,
                    "time": "11:00 – 12:30",
                },
            },
        }
    )

    db.ASTROLOGY.clear()
    db.ASTROLOGY.update(
        {
            "success": True,
            "basicDetails": [
                {"label": "Rashi", "value": "Mesh"},
                {"label": "Nakshatra", "value": "Ashwini"},
                {"label": "Lagna", "value": "Simha"},
                {"label": "Manglik", "value": "No"},
            ],
            "planets": [
                {"name": "Sun", "sign": "Meena", "house": 8, "degree": "12°14'"},
                {"name": "Moon", "sign": "Mesh", "house": 9, "degree": "04°02'"},
                {"name": "Mars", "sign": "Kumbha", "house": 7, "degree": "21°40'"},
                {"name": "Mercury", "sign": "Meena", "house": 8, "degree": "28°11'"},
                {"name": "Jupiter", "sign": "Vrishabha", "house": 10, "degree": "16°55'"},
                {"name": "Venus", "sign": "Kumbha", "house": 7, "degree": "09°33'"},
                {"name": "Saturn", "sign": "Kumbha", "house": 7, "degree": "02°18'"},
                {"name": "Rahu", "sign": "Meena", "house": 8, "degree": "14°01'"},
                {"name": "Ketu", "sign": "Kanya", "house": 2, "degree": "14°01'"},
            ],
            "chartImageUrl": f"{base_url}/static/app_logo.webp",
            "sections": [
                {"id": "personality", "title": "Personality", "body": "Bold initiator with strong leadership instincts."},
                {"id": "career", "title": "Career", "body": "Growth accelerates through skilled communication."},
                {"id": "remedies", "title": "Remedies", "body": "Chant Om Namah Shivaya on Mondays; donate red lentils."},
            ],
        }
    )
