import os
import subprocess
import sys

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.database import SessionLocal
from app.main import app
from app.models.order import Order, OrderItem  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.product import Product, ProductImage

folder = sys.argv[1]
SLUGS = ["boot-airbuds-141-gen-2", "jibel-go-4", "soney-sh-c520"]
PNG = b"\x89PNG\r\n\x1a\n"
c = TestClient(app)


def run_import(*flags):
    r = subprocess.run([sys.executable, "import_images.py", folder, *flags], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def counts():
    db = SessionLocal()
    try:
        rows = {p.slug: db.query(ProductImage).filter(ProductImage.product_id == p.id).count()
                for p in db.query(Product).filter(Product.slug.in_(SLUGS)).all()}
        return rows
    finally:
        db.close()


start = counts()
code, out = run_import("--dry-run")
print("dry run:", code, out.count("ADD") + out.count("REPLACE"), "| saved nothing:", counts() == start, "(expect 0 3 | True)")
code, out = run_import()
print("import:", code, counts(), "(expect 0, 3 images each)")
code, out = run_import()
print("second import, no duplicates:", code == 0 and counts() == {s: 3 for s in SLUGS}, "(expect True)")

rows = c.get("/products?limit=100").json()
by_slug = {r["slug"]: r for r in rows if r["slug"]}
print("list has image_url for new products:", all(by_slug[s]["image_url"] for s in SLUGS), "(expect True)")
seed = next(r for r in rows if r["slug"] is None)
print("seed product has none:", seed["image_url"], "(expect None)")

pid = by_slug["jibel-go-4"]["id"]
d = c.get(f"/products/{pid}").json()
imgs = d["images"]
print("detail images:", len(imgs), [i["is_primary"] for i in imgs], all(i["url"].startswith("/products/images/") for i in imgs),
      d["image_url"] == imgs[0]["url"], "(expect 3 [True, False, False] True True)")

r = c.get(imgs[0]["url"])
db = SessionLocal()
size = db.get(ProductImage, imgs[0]["id"]).size_bytes
db.close()
print("serve image:", r.status_code, r.headers.get("content-type"), r.content.startswith(PNG), len(r.content) == size,
      "max-age" in r.headers.get("cache-control", ""), "(expect 200 image/png True True True)")
print("missing image:", c.get("/products/images/999999").status_code, "(expect 404)")

try:
    db = SessionLocal()
    db.query(Product).filter(Product.id == pid).update({"is_active": False})
    db.commit()
    db.close()
    print("archived product's image:", c.get(imgs[0]["url"]).status_code, "(expect 404)")
finally:
    db = SessionLocal()
    db.query(Product).filter(Product.id == pid).update({"is_active": True})
    db.commit()
    db.close()
print("restored:", c.get(imgs[0]["url"]).status_code, "(expect 200)")

db = SessionLocal()
p = db.get(Product, pid)
first = p.images[0]
print("picture bytes not loaded with the product:", "data" in inspect(first).unloaded, "(expect True)")
db.close()
