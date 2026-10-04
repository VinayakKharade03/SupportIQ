from app.database import SessionLocal
from app.models.product import Product
from app.ml import product_search as ps

QUERY = "usb c fast charging cable"
db = SessionLocal()
p = db.query(Product).filter(Product.name == "USB-C Fast Charging Cable").one()
pid = p.id

ps.build_product_index()
print("indexed:", len(ps._state[1]), "(expect 10)")
print("cable found:", pid in [r["id"] for r in ps.search_products(QUERY, top_k=10)], "(expect True)")

try:
    p.is_active = False
    db.commit()
    ps.build_product_index()
    print("indexed after archive:", len(ps._state[1]), "(expect 9)")
    print("cable hidden:", pid not in [r["id"] for r in ps.search_products(QUERY, top_k=10)], "(expect True)")
finally:
    p = db.get(Product, pid)
    p.is_active = True
    db.commit()
    ps.build_product_index()

print("indexed after restore:", len(ps._state[1]), "(expect 10)")
print("cable back:", pid in [r["id"] for r in ps.search_products(QUERY, top_k=10)], "(expect True)")
db.close()
