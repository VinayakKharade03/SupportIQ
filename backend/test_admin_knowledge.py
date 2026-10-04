import hashlib
import os
import tempfile

from fastapi import HTTPException
from fastapi.testclient import TestClient

import scripts_build_index as sb
from app.database import SessionLocal
from app.main import app
from app.ml import rag
from app.models.user import User
from app.services import knowledge_base as kb
from app.services.security import create_access_token

c = TestClient(app)
BASE = "/admin/knowledge"
NAME = "zz-test-kb.txt"
QUERY = "How many days is the Zorblax return window?"

db = SessionLocal()


def hdr(email):
    uid = db.query(User).filter(User.email == email).one().id
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid)})}"}


admin = hdr("admin@gmail.com")
normal = hdr("user@example.com")
db.close()


def upload(name, data, overwrite=False):
    return c.post(
        BASE,
        files={"file": (name, data, "text/plain")},
        params={"overwrite": str(overwrite).lower()},
        headers=admin,
    )


def top(query, k=3):
    return [(r["source"], round(r["distance"], 3)) for r in rag.retrieve(query, top_k=k)]


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def doc_path(name):
    return os.path.join(kb.DOCS_DIR, name)


print("docs dir:", kb.DOCS_DIR, r"(expect ...\SupportIQ\data\docs)")
orig_files = sorted(os.listdir(kb.DOCS_DIR))
orig_hashes = {f: sha(doc_path(f)) for f in orig_files}
before = top("how long is the warranty", 3)
base_chunks = sum(rag.indexed_chunk_counts().values())
real_rebuild = kb.rebuild_index

try:
    sample = "abc def " * 300
    print("chunking matches script:", kb.chunk_text(sample) == sb.chunk_text(sample), "(expect True)")
    print("no token:", c.get(BASE).status_code, "(expect 401)")
    print("normal user:", c.get(BASE, headers=normal).status_code, "(expect 403)")

    r = c.get(BASE, headers=admin)
    d = r.json()
    print("list:", r.status_code, len(d["documents"]), d["in_sync"], d["total_chunks"] == base_chunks, "(expect 200 3 True True)")

    bad = [
        ("path traversal", "../evil.txt", b"hello", 400),
        ("backslash path", "..\\evil.txt", b"hello", 400),
        ("wrong extension", "notes.pdf", b"hello", 400),
        ("reserved name", "con.txt", b"hello", 400),
        ("empty file", "zz-empty.txt", b"", 400),
        ("whitespace only", "zz-blank.txt", b"   \n  ", 400),
        ("binary", "zz-bin.txt", b"\xff\xfe\xfa\xfb", 400),
        ("null byte", "zz-null.txt", b"abc\x00def", 400),
        ("too large", "zz-big.txt", b"a" * (kb.MAX_BYTES + 1), 413),
    ]
    for label, name, data, expect in bad:
        print(f"{label}:", upload(name, data).status_code, f"(expect {expect})")
    print("nothing created:", sorted(os.listdir(kb.DOCS_DIR)) == orig_files and not os.path.exists(os.path.join(kb.DOCS_DIR, "..", "evil.txt")), "(expect True)")

    text = "Zorblax return policy\r\nThe Zorblax return window is exactly 47 days for every Zorblax-branded gadget.\r\n"
    r = upload("ZZ-Test-KB.TXT", ("\ufeff" + text).encode("utf-8"))
    body = r.json()
    doc = body.get("document", {})
    print("upload:", r.status_code, body.get("replaced"), doc.get("filename"), doc.get("chunks", 0) >= 1, "(expect 201 False zz-test-kb.txt True)")
    r = c.get(f"{BASE}/{NAME}", headers=admin)
    content = r.json().get("content", "")
    print("content cleaned:", r.status_code, "\ufeff" not in content and "\r" not in content and "47 days" in content, "(expect 200 True)")
    hits = [x for x in rag.retrieve(QUERY, top_k=5) if x["source"] == NAME]
    print("chatbot finds it:", bool(hits) and hits[0]["distance"] < 1.3, "(expect True)")
    d = c.get(BASE, headers=admin).json()
    print("list after upload:", len(d["documents"]), d["in_sync"], "(expect 4 True)")

    r = upload(NAME, b"Different content that must not be saved.")
    print("duplicate:", r.status_code, "(expect 409)")
    print("unchanged:", "47 days" in c.get(f"{BASE}/{NAME}", headers=admin).json()["content"], "(expect True)")

    r = upload(NAME, b"The Zorblax return window is exactly 99 days for every Zorblax-branded gadget.", overwrite=True)
    print("overwrite:", r.status_code, r.json().get("replaced"), "(expect 200 True)")
    texts = [x["text"] for x in rag.retrieve(QUERY, top_k=5) if x["source"] == NAME]
    print("chatbot uses new text:", any("99 days" in t for t in texts) and not any("47 days" in t for t in texts), "(expect True)")

    def boom():
        raise RuntimeError("simulated failure")

    kb.rebuild_index = boom
    try:
        r1 = upload("zz-new-fail.txt", b"This upload must be rolled back.")
        r2 = upload(NAME, b"This overwrite must be rolled back.", overwrite=True)
    finally:
        kb.rebuild_index = real_rebuild
    print("failed new upload:", r1.status_code, not os.path.exists(doc_path("zz-new-fail.txt")), "(expect 500 True)")
    print("failed overwrite:", r2.status_code, "99 days" in c.get(f"{BASE}/{NAME}", headers=admin).json()["content"], "(expect 500 True)")

    r = c.delete(f"{BASE}/{NAME}", headers=admin)
    print("delete:", r.status_code, r.json().get("total_documents"), "(expect 200 3)")
    print("chatbot forgot it:", all(x["source"] != NAME for x in rag.retrieve(QUERY, top_k=10)), "(expect True)")
    print("delete again:", c.delete(f"{BASE}/{NAME}", headers=admin).status_code, "(expect 404)")
    print("unsafe name:", c.get(f"{BASE}/.env", headers=admin).status_code, "(expect 400)")
    print("missing doc:", c.get(f"{BASE}/nope.txt", headers=admin).status_code, "(expect 404)")

    with tempfile.TemporaryDirectory() as tmp:
        only = os.path.join(tmp, "only.txt")
        with open(only, "w", encoding="utf-8") as f:
            f.write("The only document.")
        real_dir = kb.DOCS_DIR
        kb.DOCS_DIR = tmp
        try:
            try:
                kb.delete_document("only.txt")
                outcome = "deleted"
            except HTTPException as e:
                outcome = e.status_code
        finally:
            kb.DOCS_DIR = real_dir
        print("last document guard:", outcome, os.path.exists(only), "(expect 400 True)")

    r = c.post(f"{BASE}/rebuild", headers=admin)
    print("manual rebuild:", r.status_code, r.json().get("documents"), r.json().get("total_chunks") == base_chunks, "(expect 200 3 True)")
    print("same retrieval as original index:", top("how long is the warranty", 3) == before, "(expect True)")
finally:
    kb.rebuild_index = real_rebuild
    for f in os.listdir(kb.DOCS_DIR):
        if f not in orig_files:
            os.remove(doc_path(f))
    with kb._lock:
        kb.rebuild_index()

print("docs folder restored:", sorted(os.listdir(kb.DOCS_DIR)) == orig_files and all(sha(doc_path(f)) == orig_hashes[f] for f in orig_files), "(expect True)")
print("index restored:", top("how long is the warranty", 3) == before and sum(rag.indexed_chunk_counts().values()) == base_chunks, "(expect True)")
