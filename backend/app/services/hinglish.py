import re

# Roman-script Hindi words -> English, used ONLY to build the retrieval query.
_MAP = [
    (r"\bnahi\s+ho\s+raha\s+h(?:ai|e)\b", "not working"),
    (r"\bnahi\s+ho\s+rahe\s+h(?:ai|e)\b", "not working"),
    (r"\bnahi\s+ho\s+rahe\b", "not working"),
    (r"\bnahi\s+ho\s+raha\b", "not working"),
    (r"\bnahi\s+chal\s+raha\b", "not working"),
    (r"\bkaam\s+nahi\s+kar\s+raha\b", "not working"),
    (r"\bkitni\s+der\b", "how long"),
    (r"\bkitne\s+saal\b", "how many years"),
    (r"\bkitne\s+din\b", "how many days"),
    (r"\bkitna\b", "how much"),
    (r"\bmein\s+(.+?)\s+hai\s+kya\b", r"has \1"),
    (r"\bhai\s+kya\b", "does it have"),
    (r"\bchalti\s+hai\b", "last"),
    (r"\bcharge\s+nahi\b", "not charging"),
    (r"\bconnect\s+nahi\b", "not connecting"),
    (r"\bse\b", "with"),
    (r"\bmera\b|\bmere\b|\bmeri\b", "my"),
    (r"\bki\b|\bka\b|\bke\b", ""),
    (r"\bkya\b|\bhai\b|\bhoti\b|\bho\b", ""),
]


def to_english_query(text: str) -> str:
    """Rewrites common Hinglish phrases so retrieval matches the English documents."""
    out = text
    for pattern, repl in _MAP:
        out = re.sub(pattern, repl, out, flags=re.I)
    return " ".join(out.split())
