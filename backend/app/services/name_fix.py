import difflib
import re
import time

from app.database import SessionLocal
from app.models.product import Product

# Known Whisper mishearings in this catalog. Order matters.
_RULES = [
    # product name misheard variants -> Jibel
    (re.compile(r"\b(?:g[- ]?bell|gbl|gibel|jebel|jibble|gabel|jibil)\b", re.I), "Jibel"),
    (re.compile(r"\b(?:soni|sony|sonny|sonie)\b", re.I), "Soney"),
    # "Jibel Go for" / "Jibel Go4" / "Jibel Go four" -> "Jibel Go 4"
    (re.compile(r"\b(Jibel Go)\s*(?:for|four|4)\b", re.I), r"\1 4"),
    # "card" is almost always "cart" in a shop, unless it is a real kind of card
    (re.compile(
        r"(?<!credit )(?<!debit )(?<!gift )(?<!sim )(?<!sd )(?<!memory )"
        r"(?<!sound )(?<!graphics )\bcards?\b", re.I),
     "cart"),
]

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_MIN_LEN = 4
_CUTOFF = 0.7
_TTL = 60.0

_vocab = {}  # lowercase word -> catalog spelling
_loaded_at = 0.0


def _load_vocab() -> dict:
    global _vocab, _loaded_at
    if _vocab and time.time() - _loaded_at < _TTL:
        return _vocab
    db = SessionLocal()
    try:
        names = [n for (n,) in db.query(Product.brand).filter(Product.is_active.is_(True), Product.brand.isnot(None)).all()]
    except Exception as e:
        print(f"[NAMEFIX] could not load catalog names: {e}")
        return _vocab
    finally:
        db.close()
    vocab = {}
    for name in names:
        for w in re.split(r"[\s\-]+", name):
            if len(w) >= _MIN_LEN and w.isalpha():
                vocab[w.lower()] = w
    _vocab, _loaded_at = vocab, time.time()
    return _vocab


def _fuzzy(text: str) -> str:
    vocab = _load_vocab()
    if not vocab:
        return text
    keys = list(vocab)

    def repl(m):
        word = m.group(0)
        low = word.lower()
        if len(word) < _MIN_LEN or low in vocab:
            return word
        hit = difflib.get_close_matches(low, keys, n=1, cutoff=_CUTOFF)
        return vocab[hit[0]] if hit else word

    return _WORD.sub(repl, text)


def fix(text: str) -> str:
    """Corrects common speech-recognition mistakes before intent routing."""
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return _fuzzy(text)
