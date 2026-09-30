import re

ORDER_KEYWORDS = [
    "order", "buy", "purchase", "add to cart", "checkout",
    "how much", "price", "cost", "want to get", "looking to buy",
    "confirm", "cart", "cheap",
]

# "under 2000", "below rs 1500", "less than 3000": a price limit means shopping
PRICE_LIMIT_PATTERN = re.compile(r"\b(?:under|below|less than|within|up to|upto)\s*(?:rs\.?)?\s*\d")


def classify_intent(text: str) -> str:
    """Returns 'order' or 'support'. Simple keyword-based for now;
    can be upgraded to an LLM-based classifier later."""
    lowered = text.lower()
    for keyword in ORDER_KEYWORDS:
        if keyword in lowered:
            return "order"
    if PRICE_LIMIT_PATTERN.search(lowered):
        return "order"
    return "support"
