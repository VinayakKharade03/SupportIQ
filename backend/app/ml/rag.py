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


def retrieve(query: str, top_k: int = 3):
    """Returns the top_k most relevant chunks for a query, with their sources."""
    _load()
    index, meta = _state
    query_vec = get_embedder().encode([query]).astype("float32")
    distances, indices = index.search(query_vec, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        results.append({
            "text": meta["chunks"][idx],
            "source": meta["sources"][idx],
            "distance": float(dist),
        })
    return results
