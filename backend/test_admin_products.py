from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.ml import product_search as ps
from app.models.product import Product
from app.models.user import User
from app.services.security import create_access_token

c = TestClient(app)
BASE = "/admin/products"


def auth(email):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            raise SystemExit(f"User {email} not found")
        return {"Authorization": f"Bearer {create_access_token({'sub': str(u.id)})}"}
    finally:
        db.close()


admin = auth("admin@gmail.com")
normal = auth("user@example.com")

print("no token:", c.get(BASE).status_code, "(expect 401)")
print("normal user:", c.get(BASE, headers=normal).status_code, "(expect 403)")
print("admin list:", len(c.get(BASE, headers=admin).json()), "(expect 10)")

payload = {
    "name": "Zzz Test Gadget",
    "category": "Accessory",
    "description": "Temporary product created by the admin products test.",
    "price": 123.45,
    "stock": 5,
}

print("blank name:", c.post(BASE, json={**payload, "name": "   "}, headers=admin).status_code, "(expect 422)")
print("zero price:", c.post(BASE, json={**payload, "price": 0}, headers=admin).status_code, "(expect 422)")
print("negative stock:", c.post(BASE, json={**payload, "stock": -1}, headers=admin).status_code, "(expect 422)")
print("missing field:", c.post(BASE, json={"name": "x"}, headers=admin).status_code, "(expect 422)")

db = SessionLocal()
pid = None
try:
    r = c.post(BASE, json=payload, headers=admin)
    body = r.json()
    print("create:", r.status_code, body.get("price"), body.get("is_active"), body.get("category"), "(expect 201 123.45 True accessory)")
    pid = body["id"]


    def in_index():
        return any(x["id"] == pid for x in ps.search_products("Zzz Test Gadget", top_k=50))


    print("in chat index:", in_index(), "(expect True)")
    print("public list:", len(c.get("/products").json()), "(expect 11)")

    r = c.patch(f"{BASE}/{pid}", json={"price": 99.5, "stock": 7}, headers=admin)
    print("patch:", r.status_code, r.json().get("price"), r.json().get("stock"), "(expect 200 99.5 7)")
    indexed = next(x for x in ps.search_products("Zzz Test Gadget", top_k=50) if x["id"] == pid)
    print("index price updated:", indexed["price"], "(expect 99.5)")
    print("empty patch:", c.patch(f"{BASE}/{pid}", json={}, headers=admin).status_code, "(expect 422)")
    print("null name:", c.patch(f"{BASE}/{pid}", json={"name": None}, headers=admin).status_code, "(expect 422)")
    print("negative stock patch:", c.patch(f"{BASE}/{pid}", json={"stock": -5}, headers=admin).status_code, "(expect 422)")

    r = c.delete(f"{BASE}/{pid}", headers=admin)
    print("archive:", r.status_code, r.json().get("is_active"), "(expect 200 False)")
    print("gone from chat index:", not in_index(), "(expect True)")
    print("public list:", len(c.get("/products").json()), "(expect 10)")
    print("public detail:", c.get(f"/products/{pid}").status_code, "(expect 404)")
    print("admin detail:", c.get(f"{BASE}/{pid}", headers=admin).status_code, "(expect 200)")
    archived = c.get(f"{BASE}?is_active=false", headers=admin).json()
    print("archived filter:", [x["id"] for x in archived] == [pid], "(expect True)")
    print("archive again:", c.delete(f"{BASE}/{pid}", headers=admin).status_code, "(expect 200)")

    r = c.post(f"{BASE}/{pid}/restore", headers=admin)
    print("restore:", r.status_code, r.json().get("is_active"), "(expect 200 True)")
    print("back in chat index:", in_index(), "(expect True)")
    print("public detail:", c.get(f"/products/{pid}").status_code, "(expect 200)")

    for label, method, url in [
        ("get", c.get, f"{BASE}/99999"),
        ("patch", lambda u, **k: c.patch(u, json={"stock": 1}, **k), f"{BASE}/99999"),
        ("delete", c.delete, f"{BASE}/99999"),
        ("restore", c.post, f"{BASE}/99999/restore"),
    ]:
        print(f"missing {label}:", method(url, headers=admin).status_code, "(expect 404)")
finally:
    if pid:
        db.query(Product).filter(Product.id == pid).delete()
        db.commit()
    db.close()
    ps.build_product_index()

print("after cleanup:", len(c.get(BASE, headers=admin).json()), "(expect 10)")
