from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.ml import rag
from app.models.product import Product
from app.models.user import User
from app.services.security import create_access_token

c = TestClient(app)
db = SessionLocal()
uid = db.query(User).filter(User.email == "admin@gmail.com").one().id
admin = {"Authorization": f"Bearer {create_access_token({'sub': str(uid)})}"}
p = db.query(Product).filter(Product.slug == "jibel-go-4").one()
pid, name = p.id, p.name
db.close()


def sources():
    return rag.indexed_chunk_counts()


def starting(d, prefix):
    return [s for s in d if s.startswith(prefix)]


rag.retrieve("warm up", top_k=1)
before = sources()
print("Jibel chunk sources at start:", len(starting(before, "Jibel Go 4")), "(expect 3)")

try:
    r = c.delete(f"/admin/products/{pid}", headers=admin)
    after = sources()
    print("archive:", r.status_code, "| Jibel gone:", starting(after, "Jibel") == [], "| others kept:", len(after) == len(before) - 3,
          "(expect 200 | True | True)")
    res = rag.retrieve("is the Jibel Go 4 waterproof", top_k=3)
    print("chatbot no longer sees it:", all(not x["source"].startswith("Jibel") for x in res), "(expect True)")

    r = c.post(f"/admin/products/{pid}/restore", headers=admin)
    print("restore:", r.status_code, "| chunks back:", sources() == before, "(expect 200 | True)")
    res = rag.retrieve("is the Jibel Go 4 waterproof", top_k=3)
    print("chatbot sees it again:", any(x["source"].startswith("Jibel") for x in res), "(expect True)")

    r = c.patch(f"/admin/products/{pid}", json={"name": "Jibel Go 4 Test"}, headers=admin)
    print("rename:", r.status_code, "| labels follow the name:", len(starting(sources(), "Jibel Go 4 Test")) == 3, "(expect 200 | True)")
finally:
    c.patch(f"/admin/products/{pid}", json={"name": name}, headers=admin)
    c.post(f"/admin/products/{pid}/restore", headers=admin)

print("final state restored:", sources() == before, "(expect True)")
