from app.ml.intent_router import classify_intent

ORDER = [
    "where is my order", "where's my package", "track my parcel", "when will my package arrive",
    "cancel my order", "cancel order 12", "remove the soundbar from my cart", "clear my cart",
    "show my orders", "add earbuds to cart", "confirm order", "how much are earbuds under 2000",
]
SUPPORT = [
    "how long is the warranty", "my earbuds wont connect to bluetooth", "how do i remove the ear tips",
    "where can i find the manual", "i want a refund", "my package is damaged", "where is my warranty card",
]
bad = [(t, classify_intent(t)) for t in ORDER if classify_intent(t) != "order"]
bad += [(t, classify_intent(t)) for t in SUPPORT if classify_intent(t) != "support"]
print("router:", "all correct" if not bad else bad, "(expect all correct)")
