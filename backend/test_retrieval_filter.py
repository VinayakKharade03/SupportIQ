from app.ml import rag

rag.retrieve("warm up", top_k=1)
meta = rag._state[1]
bad = [s for s, c in zip(meta["sources"], meta["chunks"]) if all(l.startswith("#") or not l.strip() for l in c.split("\n"))]
sizes = [len(c) for c in meta["chunks"]]
print("chunks:", len(sizes), "| shortest:", min(sizes), "| longest:", max(sizes))
print("heading-only chunks:", len(bad), "(expect 0)")

CASES = [
    ("how do I factory reset the Boot Airbuds 141 Gen 2", "Boot", "reset button"),
    ("how long does the Soney SH-C520 battery last", "Soney", "50 hours"),
    ("how long does the battery last on the SH-C520", "Soney", "50 hours"),
    ("does the Jibel Go 4 have an aux input", "Jibel", "aux"),
    ("how long does the battery last on the Go 4", "Jibel", "7 hours"),
    ("how do I initialize the Soney SH-C520", "Soney", "initialize"),
]
for q, brand, needle in CASES:
    res = rag.retrieve(q, top_k=3)
    only_this = all(r["source"].endswith(".txt") or r["source"].startswith(brand) for r in res)
    has_text = any(needle in r["text"].lower() for r in res)
    print("PASS" if only_this and has_text else "CHECK", "| only this product:", only_this, "| has the answer:", has_text, "|", q,
          [(r["source"], round(r["distance"], 2)) for r in res])

res = rag.retrieve("how long is the warranty", top_k=3)
print("PASS" if res[0]["source"] == "warranty_policy.txt" else "CHECK", "| no product named:", [(r["source"], round(r["distance"], 2)) for r in res])
