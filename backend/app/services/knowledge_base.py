import glob
import logging
import os
import pickle
import re
import threading
import uuid
from datetime import datetime, timezone

import faiss
import numpy as np
from fastapi import HTTPException

from app.ml import rag

logger = logging.getLogger(__name__)

# backend/app/services -> repo root -> data/docs (same folder scripts_build_index.py reads)
DOCS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "docs")
)
CHUNK_SIZE = 500  # keep identical to scripts_build_index.py so distances stay comparable
MAX_BYTES = 200 * 1024
FILENAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}\.txt$")
RESERVED_STEMS = (
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

_lock = threading.Lock()


def normalize_filename(name: str) -> str:
    cleaned = (name or "").strip().lower()
    stem = cleaned[:-4] if cleaned.endswith(".txt") else cleaned
    if not FILENAME_RE.match(cleaned) or stem in RESERVED_STEMS:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename. Use letters, numbers, '-' or '_' (max 64 characters) and end with .txt",
        )
    return cleaned


def chunk_text(text, chunk_size=CHUNK_SIZE):
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _doc_files():
    return sorted(glob.glob(os.path.join(DOCS_DIR, "*.txt")))


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _write_bytes(path, data):
    tmp = f"{path}.{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _revert(path, backup):
    """Put a document back the way it was (or remove it if it did not exist)."""
    try:
        if backup is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            _write_bytes(path, backup)
    except OSError:
        logger.exception("Could not revert %s", path)


def rebuild_index():
    """Rebuild the support index from every .txt in DOCS_DIR, save it, and swap it into
    the running server. Same method as scripts_build_index.py. Caller must hold _lock."""
    files = _doc_files()
    chunks, sources = [], []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        for chunk in chunk_text(text):
            chunks.append(chunk)
            sources.append(os.path.basename(filepath))
    if not chunks:
        raise HTTPException(status_code=400, detail="No document content to index")

    embeddings = np.array(rag.get_embedder().encode(chunks)).astype("float32")
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    meta = {"chunks": chunks, "sources": sources}

    os.makedirs(rag.INDEX_DIR, exist_ok=True)
    tmp_index = os.path.join(rag.INDEX_DIR, "support_docs.tmp.index")
    tmp_meta = os.path.join(rag.INDEX_DIR, "support_docs_meta.tmp.pkl")
    faiss.write_index(index, tmp_index)
    with open(tmp_meta, "wb") as f:
        pickle.dump(meta, f)
    os.replace(tmp_index, rag.INDEX_PATH)
    os.replace(tmp_meta, rag.META_PATH)
    rag.reload_index(index, meta)
    return len(files), len(chunks)


def list_documents():
    try:
        counts = rag.indexed_chunk_counts()
    except FileNotFoundError:
        counts = {}
    docs = []
    for path in _doc_files():
        name = os.path.basename(path)
        stat = os.stat(path)
        docs.append(
            {
                "filename": name,
                "size_bytes": stat.st_size,
                "chunks": counts.get(name, 0),
                "indexed": name in counts,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            }
        )
    return {
        "documents": docs,
        "total_chunks": sum(counts.values()),
        "in_sync": set(counts) == {d["filename"] for d in docs},
    }


def read_document(filename: str) -> str:
    path = os.path.join(DOCS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Document not found")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_document(filename: str, text: str, overwrite: bool) -> bool:
    """Save a document and rebuild the index. Returns True if an existing one was replaced."""
    path = os.path.join(DOCS_DIR, filename)
    os.makedirs(DOCS_DIR, exist_ok=True)
    with _lock:
        existed = os.path.exists(path)
        if existed and not overwrite:
            raise HTTPException(
                status_code=409,
                detail=f"{filename} already exists. Upload again with overwrite=true to replace it",
            )
        backup = _read_bytes(path) if existed else None
        try:
            _write_bytes(path, text.encode("utf-8"))
            rebuild_index()
        except HTTPException:
            _revert(path, backup)
            raise
        except Exception:
            _revert(path, backup)
            logger.exception("Knowledge base update failed; change reverted")
            raise HTTPException(
                status_code=500,
                detail="Rebuilding the search index failed, so the change was reverted",
            )
    return existed


def delete_document(filename: str) -> None:
    path = os.path.join(DOCS_DIR, filename)
    with _lock:
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Document not found")
        if len(_doc_files()) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last document: the chatbot needs at least one",
            )
        backup = _read_bytes(path)
        os.remove(path)
        try:
            rebuild_index()
        except HTTPException:
            _revert(path, backup)
            raise
        except Exception:
            _revert(path, backup)
            logger.exception("Knowledge base delete failed; change reverted")
            raise HTTPException(
                status_code=500,
                detail="Rebuilding the search index failed, so the delete was reverted",
            )


def rebuild_all():
    with _lock:
        try:
            return rebuild_index()
        except HTTPException:
            raise
        except Exception:
            logger.exception("Manual index rebuild failed")
            raise HTTPException(status_code=500, detail="Rebuilding the search index failed")
