import os
import glob
import pickle

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "docs")
INDEX_DIR = os.path.join(os.path.dirname(__file__), "app", "ml", "index")
os.makedirs(INDEX_DIR, exist_ok=True)

CHUNK_SIZE = 500  # characters per chunk, simple splitting for now


def chunk_text(text, chunk_size=CHUNK_SIZE):
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def build_index():
    print("Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    all_chunks = []
    all_sources = []

    doc_files = glob.glob(os.path.join(DOCS_DIR, "*.txt"))
    print(f"Found {len(doc_files)} doc(s): {[os.path.basename(f) for f in doc_files]}")

    for filepath in doc_files:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = chunk_text(text)
        all_chunks.extend(chunks)
        all_sources.extend([os.path.basename(filepath)] * len(chunks))

    print(f"Total chunks: {len(all_chunks)}")
    print("Embedding chunks...")
    embeddings = model.encode(all_chunks, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    faiss.write_index(index, os.path.join(INDEX_DIR, "support_docs.index"))
    with open(os.path.join(INDEX_DIR, "support_docs_meta.pkl"), "wb") as f:
        pickle.dump({"chunks": all_chunks, "sources": all_sources}, f)

    print(f"Index built with {index.ntotal} vectors, saved to {INDEX_DIR}")


if __name__ == "__main__":
    build_index()
