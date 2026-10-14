from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.product import Product

c = TestClient(app)
db = SessionLocal()
ids = {p.slug: p.id for p in db.query(Product).filter(Product.slug.isnot(None)).all()}
seed_id = db.query(Product.id).filter(Product.slug.is_(None)).order_by(Product.id).first()[0]
earbud_count = db.query(Product).filter(Product.category == "earbuds", Product.is_active.is_(True)).count()
total = db.query(Product).filter(Product.is_active.is_(True)).count()

r = c.get("/products?limit=100")
rows = r.json()
print("list:", r.status_code, len(rows) == total, all("brand" in x and "mrp" in x for x in rows), "(expect 200 True True)")

d = c.get(f"/products/{ids['boot-airbuds-141-gen-2']}").json()
print("boot detail:", d["brand"], d["price"], d["mrp"], len(d["specs"]), [x["doc_type"] for x in d["documents"]],
      len(d["highlights"]), d["in_the_box"], "(expect Boot 1299.0 3990.0 18 [user_guide, troubleshooting, faq] 6 [])")
print("spec order:", d["specs"][0]["group_name"], d["specs"][0]["name"], "(expect General Product type)")
print("document text present:", all(len(x["content"]) > 200 for x in d["documents"]), "(expect True)")

j = c.get(f"/products/{ids['jibel-go-4']}").json()
print("jibel detail:", j["slug"], j["price"], len(j["specs"]), j["in_the_box"], "(expect jibel-go-4 3499.0 14 two items)")

s = c.get(f"/products/{seed_id}").json()
print("seed product:", s["brand"], s["mrp"], s["specs"], s["documents"], s["highlights"], "(expect None None [] [] None)")

print("brand filter:", [x["name"] for x in c.get("/products?brand=jibel").json()], "(expect ['Jibel Go 4'])")
print("no such brand:", c.get("/products?brand=nobody").json(), "(expect [])")
print("subcategory filter:", [x["name"] for x in c.get("/products?subcategory=On-Ear").json()], "(expect ['Soney SH-C520'])")
print("category filter:", len(c.get("/products?category=earbuds").json()) == earbud_count, "(expect True)")
print("missing product:", c.get("/products/99999").status_code, "(expect 404)")

try:
    db.query(Product).filter(Product.slug == "jibel-go-4").update({"is_active": False})
    db.commit()
    print("archived detail:", c.get(f"/products/{ids['jibel-go-4']}").status_code,
          "| list size:", len(c.get("/products?limit=100").json()) == total - 1, "(expect 404 | True)")
finally:
    db.query(Product).filter(Product.slug == "jibel-go-4").update({"is_active": True})
    db.commit()
print("restored:", c.get(f"/products/{ids['jibel-go-4']}").status_code, "(expect 200)")
db.close()
