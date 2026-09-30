ORDER_KEYWORDS = [
    "order", "buy", "purchase", "add to cart", "checkout",
    "how much", "price", "cost", "want to get", "looking to buy",
]


def classify_intent(text: str) -> str:
    """Returns 'order' or 'support'. Simple keyword-based for now;
    can be upgraded to an LLM-based classifier later."""
    lowered = text.lower()
    for keyword in ORDER_KEYWORDS:
        if keyword in lowered:
            return "order"
    return "support"
