import os
import pickle

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

INDEX_DIR = os.path.join(os.path.dirname(__file__), "index")

_embedder = None
_index = None
_meta = None


def _load():
    global _embedder, _index, _meta
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    if _index is None:
        _index = faiss.read_index(os.path.join(INDEX_DIR, "support_docs.index"))
    if _meta is None:
        with open(os.path.join(INDEX_DIR, "support_docs_meta.pkl"), "rb") as f:
            _meta = pickle.load(f)


def retrieve(query: str, top_k: int = 3):
    """Returns the top_k most relevant chunks for a query, with their sources."""
    _load()
    query_vec = _embedder.encode([query]).astype("float32")
    distances, indices = _index.search(query_vec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        results.append({
            "text": _meta["chunks"][idx],
            "source": _meta["sources"][idx],
            "distance": float(dist),
        })
    return results
