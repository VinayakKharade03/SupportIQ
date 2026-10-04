import faiss
from sentence_transformers import SentenceTransformer

from app.database import SessionLocal
from app.models.product import Product

_model = None
_state = None  # (faiss index, list of product dicts), swapped in as one unit


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def build_product_index():
    """Load active products from the DB and (re)build the in-memory FAISS index."""
    global _state
    db = SessionLocal()
    try:
        rows = (
            db.query(Product)
            .filter(Product.is_active.is_(True))
            .order_by(Product.id)
            .all()
        )
        products = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "price": float(p.price),
                "stock": p.stock,
            }
            for p in rows
        ]
    finally:
        db.close()

    if not products:
        _state = None
        return

    texts = [f"{p['name']}. {p['category']}. {p['description']}" for p in products]
    embeddings = _get_model().encode(texts, normalize_embeddings=True).astype("float32")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    _state = (index, products)


def search_products(query: str, top_k: int = 3):
    """Return the top_k active products most similar to the query, with a similarity score."""
    state = _state
    if state is None:
        build_product_index()
        state = _state
    if state is None:
        return []

    index, products = state
    q = _get_model().encode([query], normalize_embeddings=True).astype("float32")
    scores, ids = index.search(q, min(top_k, len(products)))
    return [
        {**products[i], "score": float(s)}
        for s, i in zip(scores[0], ids[0])
        if i != -1
    ]
