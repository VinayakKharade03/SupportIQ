import faiss
from sentence_transformers import SentenceTransformer

from app.database import SessionLocal
from app.models.product import Product

_model = None
_index = None
_products = []


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def build_product_index():
    """Load products from the DB and (re)build the in-memory FAISS index."""
    global _index, _products
    db = SessionLocal()
    try:
        rows = db.query(Product).order_by(Product.id).all()
        _products = [
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

    if not _products:
        _index = None
        return

    texts = [f"{p['name']}. {p['category']}. {p['description']}" for p in _products]
    embeddings = _get_model().encode(texts, normalize_embeddings=True).astype("float32")
    _index = faiss.IndexFlatIP(embeddings.shape[1])
    _index.add(embeddings)


def search_products(query: str, top_k: int = 3):
    """Return the top_k products most similar to the query, with a similarity score."""
    if _index is None:
        build_product_index()
    if _index is None:
        return []

    q = _get_model().encode([query], normalize_embeddings=True).astype("float32")
    scores, ids = _index.search(q, min(top_k, len(_products)))
    return [
        {**_products[i], "score": float(s)}
        for s, i in zip(scores[0], ids[0])
        if i != -1
    ]
