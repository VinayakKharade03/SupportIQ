from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.routers.orders import CartAdd, add_to_cart, confirm_order, view_cart
from app.services import order_chat
from app.services.order_agent import LOGIN_REPLY, handle_order
from app.services.security import create_access_token, hash_password

c = TestClient(app)
db = SessionLocal()
CABLE, LITE, PRO = "USB-C Fast Charging Cable", "Wireless Earbuds Lite", "Wireless Earbuds Pro"
ids = {n: db.query(Product.id).filter(Product.name == n).scalar() for n in (CABLE, LITE, PRO)}
orig = {n: db.query(Product.stock).filter(Product.id == i).scalar() for n, i in ids.items()}
ua = User(email="zz_chat_a@example.com", hashed_password=hash_password("unused-test-pass"), full_name="Chat A")
ub = User(email="zz_chat_b@example.com", hashed_password=hash_password("unused-test-pass"), full_name="Chat B")
db.add_all([ua, ub])
db.commit()
db.refresh(ua)
db.refresh(ub)


def say(msg, u=None):
    return handle_order(msg, u or ua, db)


def add(name, qty=1, u=None):
    add_to_cart(CartAdd(product_id=ids[name], quantity=qty), user=u or ua, db=db)


def cart_count():
    return len(view_cart(user=ua, db=db)["items"])


def stock(name):
    db.expire_all()
    return db.query(Product.stock).filter(Product.id == ids[name]).scalar()


def status(oid):
    db.expire_all()
    return db.query(Order.status).filter(Order.id == oid).scalar()


def set_active(name, value):
    db.query(Product).filter(Product.id == ids[name]).update({"is_active": value})
    db.commit()


try:
    print("anonymous:", [handle_order(m, None, None) == LOGIN_REPLY for m in
          ("remove the cable from my cart", "where is my order", "cancel order 1")], "(expect [True, True, True])")

    add(CABLE); add(LITE); add(PRO)
    r = say("remove the earbuds from my cart")
    print("ambiguous:", "Which" in r and LITE in r and PRO in r, cart_count() == 3, "(expect True True)")
    r = say("remove the earbuds lite from my cart")
    print("remove one:", f"Removed {LITE}" in r, cart_count() == 2, "(expect True True)")
    r = say("remove the soundbar from my cart")
    print("not in cart:", "couldn't find that in your cart" in r, cart_count() == 2, "(expect True True)")
    r = say("remove the cable from my cart and add earbuds to cart")
    print("mixed request:", "one thing at a time" in r, cart_count() == 2, "(expect True True)")
    set_active(CABLE, False)
    r = say("remove the usb c cable from my cart")
    set_active(CABLE, True)
    print("archived item removable:", f"Removed {CABLE}" in r, cart_count() == 1, "(expect True True)")
    r = say("remove it from my cart")
    print("remove it:", "now empty" in r, cart_count() == 0, "(expect True True)")
    print("empty cart:", say("remove it from my cart") == "Your cart is empty.", "(expect True)")
    add(LITE); add(PRO)
    r = say("clear my cart")
    print("clear cart:", "emptied" in r, cart_count() == 0, "(expect True True)")
    add(CABLE); add(LITE)
    r = say("clear the cable from my cart")
    print("clear one item only:", f"Removed {CABLE}" in r, cart_count() == 1, "(expect True True)")
    r = say("remove everything from my cart")
    print("remove everything:", "emptied" in r, cart_count() == 0, "(expect True True)")

    add(CABLE, 2); o1 = confirm_order(user=ua, db=db)["order_id"]
    add(LITE); o2 = confirm_order(user=ua, db=db)["order_id"]
    add(PRO, u=ub); ob = confirm_order(user=ub, db=db)["order_id"]
    print("setup stock:", stock(CABLE) == orig[CABLE] - 2, "(expect True)")

    for m in ("where is my order", "where is my package", "show my orders"):
        r = say(m)
        print(f"status '{m}':", "Your recent orders" in r and f"#{o1}" in r and f"#{o2}" in r and "Here's what I found" not in r, "(expect True)")
    print("status by number:", f"Order #{o1} is confirmed" in say(f"status of order {o1}"), "(expect True)")
    print("status missing:", "couldn't find order #99999" in say("status of order 99999"), "(expect True)")
    print("status of B's order:", "couldn't find" in say(f"status of order {ob}"), "(expect True)")

    r = say("cancel my order")
    print("cancel list:", f"#{o1}" in r and f"#{o2}" in r and "which one" in r.lower(), "(expect True)")
    r = say(f"cancel order {o1}")
    print("cancel asks first:", f"yes, cancel order {o1}" in r, status(o1) == "confirmed", stock(CABLE) == orig[CABLE] - 2, "(expect True True True)")
    r = say(f"yes, don't cancel order {o1}")
    print("negation does not cancel:", "yes, cancel order" in r, status(o1) == "confirmed", "(expect True True)")
    r1, r2 = say(f"cancel order {ob}"), say(f"yes, cancel order {ob}")
    print("B's order safe:", "couldn't find" in r1, "couldn't find" in r2, status(ob) == "confirmed", "(expect True True True)")
    r = say(f"yes, cancel order {o1}")
    print("cancel confirmed:", f"Order #{o1} has been cancelled" in r, status(o1) == "cancelled", stock(CABLE) == orig[CABLE], "(expect True True True)")
    print("cancel again:", "already cancelled" in say(f"yes, cancel order {o1}"), stock(CABLE) == orig[CABLE], "(expect True True)")
    db.query(Order).filter(Order.id == o2).update({"status": "shipped"})
    db.commit()
    r = say(f"cancel order {o2}")
    print("shipped order:", "is shipped" in r and "can't be cancelled" in r, "(expect True)")
    print("nothing cancellable:", "don't have any orders that can be cancelled" in say("cancel my order"), "(expect True)")

    nones = ["cancel my warranty", "how do i remove the ear tips", "my cart is empty, add earbuds to cart",
             "confirm my order", "place my order", "show my cart", "add earbuds to my cart", "can i cancel the subscription"]
    print("support phrases untouched:", all(order_chat.handle(m, ua, db, LOGIN_REPLY) is None for m in nones), "(expect True)")

    hdr = {"Authorization": f"Bearer {create_access_token({'sub': str(ua.id)})}"}
    r = c.post("/support/chat", json={"message": "where is my order"}, headers=hdr)
    print("end to end /support/chat:", r.status_code, "recent orders" in r.json().get("reply", "").lower(), "(expect 200 True)")

    r = say("add 1 usb c fast charging cable to my cart")
    print("regression add:", f"Added 1 x {CABLE}" in r, "(expect True)")
    print("regression show cart:", "Your cart:" in say("show my cart"), "(expect True)")
    print("regression remove:", f"Removed {CABLE}" in say("remove the cable from my cart"), "(expect True)")
    print("regression confirm empty:", "Cart is empty" in say("confirm order"), "(expect True)")
finally:
    db.rollback()
    for u in (ua, ub):
        for o in db.query(Order).filter(Order.user_id == u.id).all():
            db.delete(o)
    db.flush()
    db.delete(ua)
    db.delete(ub)
    for n, i in ids.items():
        p = db.get(Product, i)
        p.stock = orig[n]
        p.is_active = True
    db.commit()
    db.close()

db = SessionLocal()
ok = all(db.query(Product.stock).filter(Product.id == i).scalar() == orig[n] for n, i in ids.items())
gone = db.query(User).filter(User.email.like("zz_chat_%")).count() == 0
print("cleanup:", ok, "| temp users gone:", gone, "(expect True | True)")
db.close()
