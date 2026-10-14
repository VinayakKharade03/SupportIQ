from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.product import Product

c = TestClient(app)
db = SessionLocal()
p = db.query(Product).filter(Product.name == "USB-C Fast Charging Cable").one()
pid = p.id


def count():
    return len(c.get("/products?limit=100").json())


before = count()
print("detail:", c.get(f"/products/{pid}").status_code, "(expect 200)")
try:
    p.is_active = False
    db.commit()
    print("list after archive:", count() == before - 1, "(expect True)")
    print("detail after archive:", c.get(f"/products/{pid}").status_code, "(expect 404)")
    print("accessory category:", len(c.get("/products?category=accessory").json()), "(expect 0)")
finally:
    p = db.get(Product, pid)
    p.is_active = True
    db.commit()
print("list after restore:", count() == before, "(expect True)")
print("detail after restore:", c.get(f"/products/{pid}").status_code, "(expect 200)")
db.close()
