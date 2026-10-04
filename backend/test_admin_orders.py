from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.routers.orders import CartAdd, add_to_cart, confirm_order
from app.services.security import create_access_token, hash_password

c = TestClient(app)
BASE = "/admin/orders"


def hdr(uid):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid)})}"}


db = SessionLocal()
admin = hdr(db.query(User).filter(User.email == "admin@gmail.com").one().id)
normal = hdr(db.query(User).filter(User.email == "user@example.com").one().id)
prod = db.query(Product).filter(Product.name == "USB-C Fast Charging Cable").one()
pid, orig = prod.id, prod.stock
user = User(email="zz_orders_test@example.com", hashed_password=hash_password("unused-test-pass"), full_name="Orders Test")
db.add(user)
db.commit()
db.refresh(user)


def stock():
    return db.query(Product.stock).filter(Product.id == pid).scalar()


def patch(oid, status):
    return c.patch(f"{BASE}/{oid}/status", json={"status": status}, headers=admin)


try:
    add_to_cart(CartAdd(product_id=pid, quantity=2), user=user, db=db)
    a_id = confirm_order(user=user, db=db)["order_id"]
    add_to_cart(CartAdd(product_id=pid, quantity=1), user=user, db=db)
    c_id = confirm_order(user=user, db=db)["order_id"]
    p_id = add_to_cart(CartAdd(product_id=pid, quantity=1), user=user, db=db)["order_id"]
    print("setup stock:", stock() == orig - 3, "(expect True)")

    print("no token:", c.get(BASE).status_code, "(expect 401)")
    print("normal user:", c.get(BASE, headers=normal).status_code, "(expect 403)")

    ids = [o["id"] for o in c.get(BASE, headers=admin).json()]
    print("list shows confirmed, hides pending:", a_id in ids and c_id in ids and p_id not in ids, "(expect True)")
    ids = [o["id"] for o in c.get(f"{BASE}?status=pending", headers=admin).json()]
    print("pending filter:", p_id in ids and a_id not in ids, "(expect True)")
    ids = [o["id"] for o in c.get(f"{BASE}?user_id={user.id}", headers=admin).json()]
    print("user filter:", sorted(ids) == sorted([a_id, c_id]), "(expect True)")
    print("bad filter:", c.get(f"{BASE}?status=nonsense", headers=admin).status_code, "(expect 422)")

    d = c.get(f"{BASE}/{a_id}", headers=admin).json()
    print("detail:", d["status"], d["user_email"], d["total"], len(d["items"]), d["items"][0]["name"], d["items"][0]["line_total"],
          "(expect confirmed zz_orders_test@example.com 798.0 1 USB-C Fast Charging Cable 798.0)")
    print("missing order:", c.get(f"{BASE}/99999", headers=admin).status_code, "(expect 404)")

    print("set confirmed:", patch(a_id, "confirmed").status_code, "(expect 422)")
    print("set pending:", patch(a_id, "pending").status_code, "(expect 422)")
    print("skip to delivered:", patch(a_id, "delivered").status_code, "(expect 400)")
    print("change pending cart:", patch(p_id, "shipped").status_code, "(expect 400)")
    print("missing patch:", patch(99999, "shipped").status_code, "(expect 404)")

    r = patch(c_id, "cancelled")
    print("cancel C:", r.status_code, r.json().get("status"), stock() == orig - 2, "(expect 200 cancelled True)")
    r = patch(c_id, "cancelled")
    print("cancel C again:", r.status_code, stock() == orig - 2, "(expect 400 True)")

    r = patch(a_id, "shipped")
    print("ship A:", r.status_code, r.json().get("status"), "(expect 200 shipped)")
    r = patch(a_id, "cancelled")
    print("cancel shipped A:", r.status_code, stock() == orig - 2, "(expect 400 True)")
    r = patch(a_id, "delivered")
    print("deliver A:", r.status_code, r.json().get("status"), "(expect 200 delivered)")
    r = patch(a_id, "cancelled")
    print("cancel delivered A:", r.status_code, stock() == orig - 2, "(expect 400 True)")
finally:
    db.rollback()
    for o in db.query(Order).filter(Order.user_id == user.id).all():
        db.delete(o)
    db.flush()
    db.delete(user)
    p = db.get(Product, pid)
    p.stock = orig
    p.is_active = True
    db.commit()
    db.close()

db = SessionLocal()
p = db.get(Product, pid)
print("cleanup:", p.stock == orig, p.is_active, "| temp user gone:", db.query(User).filter(User.email == "zz_orders_test@example.com").count() == 0, "(expect True True | True)")
db.close()
