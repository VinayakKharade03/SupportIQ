from app.services.name_fix import fix

cases = [
    # should be corrected
    "what is battery life of G-Bell go for",
    "I want to know something about GBL Go4",
    "tell me about the Soni SH-C520",
    "is the Boat Airbuds good",
    "show my card",
    # should stay unchanged
    "what is the warranty period",
    "my speaker will not charge",
    "the bell is ringing",
    "my credit card was charged",
    "add the wireless earbuds pro to my cart",
    "good morning sound is nice",
]
for s in cases:
    print(f"{s!r}\n   -> {fix(s)!r}")
