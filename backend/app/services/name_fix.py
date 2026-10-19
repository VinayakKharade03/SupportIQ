import re

# Whisper Small mishears these in this catalog. Order matters.
_RULES = [
    # product name misheard variants -> Jibel
    (re.compile(r"\b(?:g[- ]?bell|gibel|jebel|jibble|gabel|jibil)\b", re.I), "Jibel"),
    # "Jibel Go for" -> "Jibel Go 4"
    (re.compile(r"\b(Jibel Go) for\b", re.I), r"\1 4"),
    # "card" is almost always "cart" in a shop, unless it is a real kind of card
    (re.compile(
        r"(?<!credit )(?<!debit )(?<!gift )(?<!sim )(?<!sd )(?<!memory )"
        r"(?<!sound )(?<!graphics )\bcards?\b", re.I),
     "cart"),
]


def fix(text: str) -> str:
    """Corrects common speech-recognition mistakes before intent routing."""
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return text
