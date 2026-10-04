from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal
from app.main import app
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.routers.orders import CartAdd, add_to_cart, confirm_order
from app.services.security import create_access_token, hash_password

c = TestClient(app)
BASE = "/admin/stats"
db = SessionLocal()


def hdr(email):
    uid = db.query(User).filter(User.email == email).one().id
    return {"Authorization": f"Bearer {create_access_token({'sub': str(uid)})}"}


def scalar(sql):
    return db.execute(text(sql)).scalar()


def grouped(sql):
    return {k: int(v) for k, v in db.execute(text(sql)).all()}


def nonzero(d):
    return {k: v for k, v in d.items() if v}


admin = hdr("admin@gmail.com")
normal = hdr("user@example.com")
SOLD = "('confirmed','shipped','delivered')"

print("no token:", c.get(BASE).status_code, "(expect 401)")
print("normal user:", c.get(BASE, headers=normal).status_code, "(expect 403)")
print("top=0:", c.get(f"{BASE}?top=0", headers=admin).status_code, "(expect 422)")
print("threshold -1:", c.get(f"{BASE}?low_stock_threshold=-1", headers=admin).status_code, "(expect 422)")


def check_against_sql(s):
    ok = {}
    ok["users"] = s["users"] == {
        "total": scalar("select count(*) from users"),
        "admins": scalar("select count(*) from users where is_admin"),
    }
    t = s["tickets"]
    ok["tickets"] = (
        t["total"] == scalar("select count(*) from tickets")
        and nonzero(t["by_status"]) == grouped("select status, count(*) from tickets group by status")
        and t["by_category"] == grouped("select category, count(*) from tickets group by category")
        and t["by_sentiment"] == grouped("select sentiment, count(*) from tickets group by sentiment")
        and t["by_source"] == grouped("select source, count(*) from tickets group by source")
    )
    o = s["orders"]
    ok["orders"] = (
        nonzero(o["by_status"]) == grouped("select status, count(*) from orders where status <> 'pending' group by status")
        and o["total"] == scalar("select count(*) from orders where status <> 'pending'")
        and round(o["revenue"], 2) == round(float(scalar(f"select coalesce(sum(total),0) from orders where status in {SOLD}")), 2)
        and o["units_sold"] == int(scalar(f"select coalesce(sum(oi.quantity),0) from order_items oi join orders o on o.id = oi.order_id where o.status in {SOLD}"))
        and o["pending_carts"] == scalar("select count(*) from orders where status = 'pending'")
    )
    p = s["products"]
    th = p["low_stock_threshold"]
    ok["products"] = (
        p["active"] == scalar("select count(*) from products where is_active")
        and p["archived"] == scalar("select count(*) from products where not is_active")
        and p["out_of_stock"] == scalar("select count(*) from products where is_active and stock = 0")
        and p["low_stock"] == scalar(f"select count(*) from products where is_active and stock > 0 and stock <= {th}")
    )
    raw_top = db.execute(text(
        f"select oi.product_id, sum(oi.quantity) u from order_items oi join orders o on o.id = oi.order_id "
        f"where o.status in {SOLD} group by oi.product_id order by u desc, oi.product_id limit 5"
    )).all()
    ok["top_products"] = [(x["product_id"], x["units_sold"]) for x in s["top_products"]] == [(r[0], int(r[1])) for r in raw_top]
    return ok


s0 = c.get(BASE, headers=admin).json()
for key, value in check_against_sql(s0).items():
    print(f"matches SQL, {key}:", value, "(expect True)")
print("known statuses present:", {"open", "in_progress", "resolved"} <= set(s0["tickets"]["by_status"]) and {"confirmed", "shipped", "delivered", "cancelled"} <= set(s0["orders"]["by_status"]), "(expect True)")
s_big = c.get(f"{BASE}?low_stock_threshold=1000", headers=admin).json()
print("threshold 1000 low stock:", s_big["products"]["low_stock"] == s_big["products"]["active"] - s_big["products"]["out_of_stock"], "(expect True)")
print("top=1:", len(c.get(f"{BASE}?top=1", headers=admin).json()["top_products"]) <= 1, "(expect True)")

prod = db.query(Product).filter(Product.name == "USB-C Fast Charging Cable").one()
pid, orig = prod.id, prod.stock
user = User(email="zz_stats_test@example.com", hashed_password=hash_password("unused-test-pass"), full_name="Stats Test")
db.add(user)
db.commit()
db.refresh(user)

try:
    add_to_cart(CartAdd(product_id=pid, quantity=2), user=user, db=db)
    s1 = c.get(BASE, headers=admin).json()
    print("pending cart counted:", s1["orders"]["pending_carts"] == s0["orders"]["pending_carts"] + 1 and s1["orders"]["total"] == s0["orders"]["total"], "(expect True)")
    oid = confirm_order(user=user, db=db)["order_id"]

    s2 = c.get(BASE, headers=admin).json()
    print("after confirm:",
          s2["users"]["total"] == s0["users"]["total"] + 1,
          s2["orders"]["by_status"]["confirmed"] == s0["orders"]["by_status"]["confirmed"] + 1,
          round(s2["orders"]["revenue"] - s0["orders"]["revenue"], 2) == 798.0,
          s2["orders"]["units_sold"] == s0["orders"]["units_sold"] + 2,
          s2["orders"]["pending_carts"] == s0["orders"]["pending_carts"],
          "(expect True True True True True)")
    for key, value in check_against_sql(s2).items():
        if not value:
            print("MISMATCH after confirm:", key)

    r = c.patch(f"/admin/orders/{oid}/status", json={"status": "cancelled"}, headers=admin)
    s3 = c.get(BASE, headers=admin).json()
    print("after cancel:",
          r.status_code == 200,
          s3["orders"]["by_status"]["cancelled"] == s0["orders"]["by_status"]["cancelled"] + 1,
          s3["orders"]["by_status"]["confirmed"] == s0["orders"]["by_status"]["confirmed"],
          round(s3["orders"]["revenue"] - s0["orders"]["revenue"], 2) == 0.0,
          s3["orders"]["units_sold"] == s0["orders"]["units_sold"],
          "(expect True True True True True)")
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
print("cleanup:", p.stock == orig, p.is_active, "| temp user gone:", db.query(User).filter(User.email == "zz_stats_test@example.com").count() == 0, "(expect True True | True)")
db.close()
