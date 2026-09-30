from app.ml.product_search import search_products

QUERIES = [
    "cheap earbuds with good battery",
    "something to watch movies with",
    "charging cable",
    "headphones for gaming",
    "waterproof speaker for a party",
]

for q in QUERIES:
    print(f"\n{q}")
    for r in search_products(q, top_k=3):
        print(f"  {r['score']:.3f}  {r['name']}  Rs {r['price']:.0f}")
