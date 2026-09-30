from app.ml.rag import retrieve

results = retrieve("my earbuds wont connect to bluetooth")
for r in results:
    source = r["source"]
    text = r["text"][:100]
    print(f"[{source}] {text}...")
