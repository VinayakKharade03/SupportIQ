from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.routers.orders import CartAdd, add_to_cart, confirm_order
from app.services.security import create_access_token, hash_password

c = TestClient(app)
BASE = "/orders"
db = SessionLocal()


def hdr(uid):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid)})}"}


admin = hdr(db.query(User).filter(User.email == "admin@gmail.com").one().id)
prod = db.query(Product).filter(Product.name == "USB-C Fast Charging Cable").one()
pid, orig = prod.id, prod.stock
ua = User(email="zz_my_orders_a@example.com", hashed_password=hash_password("unused-test-pass"), full_name="Orders A")
ub = User(email="zz_my_orders_b@example.com", hashed_password=hash_password("unused-test-pass"), full_name="Orders B")
db.add_all([ua, ub])
db.commit()
db.refresh(ua)
db.refresh(ub)
ha, hb = hdr(ua.id), hdr(ub.id)


def stock():
    return db.query(Product.stock).filter(Product.id == pid).scalar()


def ids(resp):
    return [o["id"] for o in resp.json()]


try:
    add_to_cart(CartAdd(product_id=pid, quantity=2), user=ua, db=db)
    o1 = confirm_order(user=ua, db=db)["order_id"]
    add_to_cart(CartAdd(product_id=pid, quantity=1), user=ua, db=db)
    o2 = confirm_order(user=ua, db=db)["order_id"]
    cart_id = add_to_cart(CartAdd(product_id=pid, quantity=1), user=ua, db=db)["order_id"]
    add_to_cart(CartAdd(product_id=pid, quantity=1), user=ub, db=db)
    ob = confirm_order(user=ub, db=db)["order_id"]
    print("setup stock:", stock() == orig - 4, "(expect True)")

    print("no token list:", c.get(BASE).status_code, "(expect 401)")
    print("no token detail:", c.get(f"{BASE}/{o1}").status_code, "(expect 401)")
    print("no token cancel:", c.post(f"{BASE}/{o1}/cancel").status_code, "(expect 401)")

    print("list, mine only, newest first, no cart:", ids(c.get(BASE, headers=ha)) == [o2, o1], "(expect True)")
    print("list for B:", ids(c.get(BASE, headers=hb)) == [ob], "(expect True)")
    print("status filter:", ids(c.get(f"{BASE}?status=confirmed", headers=ha)) == [o2, o1], "(expect True)")
    print("filter cancelled (none yet):", ids(c.get(f"{BASE}?status=cancelled", headers=ha)) == [], "(expect True)")
    print("filter pending:", c.get(f"{BASE}?status=pending", headers=ha).status_code, "(expect 422)")
    print("filter nonsense:", c.get(f"{BASE}?status=nonsense", headers=ha).status_code, "(expect 422)")
    print("page 1:", ids(c.get(f"{BASE}?limit=1", headers=ha)) == [o2], "| page 2:", ids(c.get(f"{BASE}?limit=1&offset=1", headers=ha)) == [o1], "(expect True | True)")
    print("limit 0:", c.get(f"{BASE}?limit=0", headers=ha).status_code, "(expect 422)")

    d = c.get(f"{BASE}/{o1}", headers=ha).json()
    print("detail:", d["status"], d["total"], d["units"], len(d["items"]), d["items"][0]["name"], d["items"][0]["line_total"],
          "(expect confirmed 798.0 2 1 USB-C Fast Charging Cable 798.0)")
    print("no private fields:", "user_id" not in d and "user_email" not in d, "(expect True)")
    print("B's order via A:", c.get(f"{BASE}/{ob}", headers=ha).status_code, "(expect 404)")
    print("pending cart id:", c.get(f"{BASE}/{cart_id}", headers=ha).status_code, "(expect 404)")
    print("missing order:", c.get(f"{BASE}/99999", headers=ha).status_code, "(expect 404)")
    print("cart route still works:", c.get(f"{BASE}/cart", headers=ha).status_code, "(expect 200)")

    r = c.post(f"{BASE}/{ob}/cancel", headers=ha)
    print("cancel B's order as A:", r.status_code, stock() == orig - 4, db.query(Order.status).filter(Order.id == ob).scalar() == "confirmed", "(expect 404 True True)")
    r = c.post(f"{BASE}/{cart_id}/cancel", headers=ha)
    print("cancel pending cart:", r.status_code, "(expect 404)")
    print("cancel missing:", c.post(f"{BASE}/99999/cancel", headers=ha).status_code, "(expect 404)")

    r = c.post(f"{BASE}/{o2}/cancel", headers=ha)
    print("cancel o2:", r.status_code, r.json().get("status"), stock() == orig - 3, "(expect 200 cancelled True)")
    r = c.post(f"{BASE}/{o2}/cancel", headers=ha)
    print("cancel o2 again:", r.status_code, stock() == orig - 3, "(expect 400 True)")
    print("filter cancelled:", ids(c.get(f"{BASE}?status=cancelled", headers=ha)) == [o2], "(expect True)")

    r = c.patch(f"/admin/orders/{o1}/status", json={"status": "shipped"}, headers=admin)
    print("admin ships o1:", r.status_code, "(expect 200)")
    r = c.post(f"{BASE}/{o1}/cancel", headers=ha)
    print("cancel shipped o1:", r.status_code, stock() == orig - 3, "(expect 400 True)")
    print("o1 still shipped:", c.get(f"{BASE}/{o1}", headers=ha).json()["status"], "(expect shipped)")
finally:
    db.rollback()
    for u in (ua, ub):
        for o in db.query(Order).filter(Order.user_id == u.id).all():
            db.delete(o)
    db.flush()
    db.delete(ua)
    db.delete(ub)
    p = db.get(Product, pid)
    p.stock = orig
    p.is_active = True
    db.commit()
    db.close()

db = SessionLocal()
p = db.get(Product, pid)
gone = db.query(User).filter(User.email.like("zz_my_orders_%")).count() == 0
print("cleanup:", p.stock == orig, p.is_active, "| temp users gone:", gone, "(expect True True | True)")
db.close()
