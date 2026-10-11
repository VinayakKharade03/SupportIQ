from app.ml import rag

CUTOFF = 1.3
PRODUCT = [
    ("how do I factory reset the Boot Airbuds 141 Gen 2", "Boot Airbuds 141 Gen 2"),
    ("what is the pairing passcode for the Boot Airbuds", "Boot Airbuds 141 Gen 2"),
    ("does the Jibel Go 4 have an aux input", "Jibel Go 4"),
    ("is the Jibel Go 4 waterproof", "Jibel Go 4"),
    ("how long does the Soney SH-C520 battery last", "Soney SH-C520"),
    ("how do I initialize the Soney SH-C520", "Soney SH-C520"),
]
GENERIC = [
    ("how long is the warranty", "warranty_policy.txt"),
    ("my earbuds wont connect to bluetooth", None),
    ("my earbuds are not charging", None),
]
OFF_TOPIC = ["what is the capital of france", "can I pay with a credit card", "who won the cricket world cup"]


def top(q):
    return [(r["source"], round(r["distance"], 2)) for r in rag.retrieve(q, top_k=3)]


print("chunks by source:", rag.indexed_chunk_counts(), chr(10))
for q, want in PRODUCT:
    t = top(q)
    ok = want in t[0][0] and t[0][1] < CUTOFF
    print("PASS" if ok else "CHECK", "|", q, "->", t)
print()
for q, want in GENERIC:
    t = top(q)
    verdict = ("PASS" if want in t[0][0] and t[0][1] < CUTOFF else "CHECK") if want else "(report only)"
    print(verdict, "|", q, "->", t)
print()
for q in OFF_TOPIC:
    t = top(q)
    print("PASS" if t[0][1] > CUTOFF else "CHECK", "|", q, "->", t)
