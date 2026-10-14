import os
import pickle

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

INDEX_DIR = os.path.join(os.path.dirname(__file__), "index")
INDEX_PATH = os.path.join(INDEX_DIR, "support_docs.index")
META_PATH = os.path.join(INDEX_DIR, "support_docs_meta.pkl")

_embedder = None
_state = None  # (faiss index, metadata dict), always swapped in as one unit


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def _load():
    global _state
    get_embedder()
    if _state is None:
        index = faiss.read_index(INDEX_PATH)
        with open(META_PATH, "rb") as f:
            meta = pickle.load(f)
        _state = (index, meta)


def reload_index(index, meta):
    """Swap in a freshly built index and its metadata as one unit."""
    global _state
    _state = (index, meta)


def indexed_chunk_counts():
    """Returns {source filename: number of chunks} for the index currently in use."""
    _load()
    counts = {}
    for source in _state[1]["sources"]:
        counts[source] = counts.get(source, 0) + 1
    return counts


def _product_of(source):
    """Product name from a label like 'Jibel Go 4 - FAQ', or None for the generic .txt documents."""
    if source.endswith(".txt"):
        return None
    return source.rsplit(" - ", 1)[0]


def _products_in_query(query, sources):
    """Products the question names, by full name or by model (the name without its brand)."""
    q = query.lower()
    found = set()
    for name in {_product_of(s) for s in sources} - {None}:
        model = name.split(" ", 1)[1] if " " in name else name
        if name.lower() in q or (len(model) >= 4 and model.lower() in q):
            found.add(name)
    return found


def retrieve(query: str, top_k: int = 3):
    """Returns the top_k most relevant chunks for a query, with their sources.
    If the question names a product, only that product's chunks and the generic
    documents are used, so two products' facts never get mixed in one answer."""
    _load()
    index, meta = _state
    wanted = _products_in_query(query, meta["sources"])
    fetch = min(index.ntotal, max(top_k * 15, 60)) if wanted else top_k
    query_vec = get_embedder().encode([query]).astype("float32")
    distances, indices = index.search(query_vec, fetch)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        source = meta["sources"][idx]
        product = _product_of(source)
        if wanted and product is not None and product not in wanted:
            continue
        results.append({
            "text": meta["chunks"][idx],
            "source": source,
            "distance": float(dist),
        })
        if len(results) == top_k:
            break
    return results
