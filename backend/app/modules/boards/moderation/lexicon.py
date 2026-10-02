# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The word and phrase lists the local scorer matches against.

A deliberately small baseline for Czech and English, not a finished
dictionary: extend it as the community's actual problems show up. All
entries are *folded* (lowercase, no diacritics - see text.fold) and words
are matched as whole words, so "class" or "Scunthorpe" never trip on a
shorter word hidden inside them. Phrases are regular expressions over the
folded text.
"""

import re

# --- Single words (exact, folded) -----------------------------------------------

PROFANITY = frozenset(
    {
        # English
        "fuck", "fucks", "fucked", "fucker", "fuckers", "fucking", "fuckin", "motherfucker",
        "motherfucking", "fck", "fuk", "shit", "shits", "shitty", "shithead", "bullshit",
        "bitch", "bitches", "bastard", "bastards", "asshole", "assholes", "arsehole", "dick",
        "dickhead", "cunt", "cunts", "slut", "sluts", "whore", "whores", "wanker", "twat",
        # Czech
        "kurva", "kurvy", "kurvo", "kurev", "kurvit", "zkurveny", "zkurvena", "zkurvysyn",
        "kokot", "kokote", "kokoti", "kokoty", "pica", "pico", "pice", "pici", "picus",
        "picovina", "curak", "curaku", "curaci", "hovno", "hovna", "hovnu", "zasrany",
        "zasrane", "zasrat", "posrany", "jebat", "jebany", "jebnuty", "vyjebany", "pojeb",
        "mrdat", "mrdka", "sracka", "srac",
    }
)  # fmt: skip

INSULTS = frozenset(
    {
        # English
        "idiot", "idiots", "moron", "morons", "imbecile", "dumbass", "retard", "retarded",
        # Czech
        "debil", "debile", "debilove", "idioti", "blbec", "blbce", "kreten", "kretene",
        "pitomec", "magor", "magore",
    }
)  # fmt: skip

SLURS = frozenset(
    {
        "nigger", "niggers", "nigga", "niggas", "faggot", "faggots", "kike", "chink", "spic",
        "tranny", "negr", "negri", "buzerant", "buzeranti", "teplous",
    }
)  # fmt: skip

# --- Phrases (regular expressions over folded text) -----------------------------

HATE_PHRASES = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b(?:heil\s+hitler|sieg\s+heil|white\s+power)\b",
        r"\b(?:smrt|death\s+to)\s+(?:all\s+|vsem\s+)?(?:jews?|zidum|muslims?|muslimum|blacks?|negrum|cikanum|gays?|homosexualum)\b",
    )
)

THREATS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b(?:i\s*'?\s*ll|i\s+will|i\s+am\s+going\s+to|i\s*'?\s*m\s+going\s+to|we\s*'?\s*ll|we\s+will|gonna)\s+(?:kill|murder|rape|stab|shoot|beat)\s+(?:you|u|him|her|them)\b",
        r"\b(?:kill|murder|rape)\s+(?:yourself|urself)\b",
        r"\bkys\b",
        r"\bgo\s+(?:and\s+)?die\b",
        r"\bhope\s+you\s+die\b",
        r"\bzabiju\s+(?:te|tebe|vas|ho|ji|je)\b",
        r"\bzabij\s+se\b",
        r"\bzdechni\b",
        r"\bpodriznu\s+(?:te|tebe|vas)\b",
    )
)

SPAM_PHRASES = tuple(
    re.compile(r"\b" + re.escape(phrase) + r"\b")
    for phrase in (
        "click here", "buy now", "free money", "make money fast", "earn money", "limited offer",
        "act now", "casino", "viagra", "crypto giveaway", "bitcoin", "telegram", "whatsapp",
        "kup nyni", "vydelek", "bez rizika", "sazky", "kasino", "kliknete", "kliknete zde",
    )
)  # fmt: skip

# --- Patterns for links and personal data (over folded text) --------------------

URL = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|\b[a-z0-9-]{2,}\.(?:com|net|org|cz|sk|io|ru|xyz|top|info|biz|shop|ly|me|cc|tk)\b(?:/\S*)?"
)
EMAIL = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
# Nine digits in groups of three, optionally with a country prefix - a date
# like 2026-10-02 (4-2-2) deliberately does not match.
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\d{3}[\s.-]?){2}\d{3}(?!\d)")
