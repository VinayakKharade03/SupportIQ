from fastapi import HTTPException

from app.database import SessionLocal
from app.ml import product_search as ps
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.routers.orders import CartAdd, add_to_cart, confirm_order
from app.services.order_agent import handle_order
from app.services.security import hash_password

db = SessionLocal()
prod = db.query(Product).filter(Product.name == "USB-C Fast Charging Cable").one()
pid, orig_stock = prod.id, prod.stock
user = User(email="zz_cart_test@example.com", hashed_password=hash_password("unused-test-pass"), full_name="Cart Test")
db.add(user)
db.commit()
db.refresh(user)


def call(fn, *a, **k):
    try:
        return fn(*a, **k)
    except HTTPException as e:
        db.rollback()
        return (e.status_code, e.detail)


def pending_count():
    return db.query(Order).filter(Order.user_id == user.id, Order.status == "pending").count()


try:
    ps.build_product_index()
    cart = add_to_cart(CartAdd(product_id=pid, quantity=1), user=user, db=db)
    print("add active:", len(cart["items"]), cart["total"], "(expect 1 399.0)")

    p = db.get(Product, pid)
    p.is_active = False
    db.commit()

    print("add archived:", call(add_to_cart, CartAdd(product_id=pid, quantity=1), user=user, db=db), "(expect 400 ... no longer available)")
    print("confirm with archived item:", call(confirm_order, user=user, db=db), "(expect 400 Some items ... no longer available)")
    db.refresh(p)
    print("stock unchanged:", p.stock == orig_stock, "| order still pending:", pending_count() == 1, "(expect True True)")

    reply = handle_order("add 1 usb c fast charging cable to my cart", user, db)
    print("chat, stale index:", reply, "(expect a 'no longer available' message)")

    ps.build_product_index()
    reply = handle_order("add 1 usb c fast charging cable to my cart", user, db)
    print("chat, fresh index:", reply[:60], "(expect 'I couldn't find a matching product...')")
    reply = handle_order("confirm order", user, db)
    print("chat confirm:", reply, "(expect 'Some items ... no longer available')")

    p = db.get(Product, pid)
    p.is_active = True
    db.commit()
    ps.build_product_index()
    result = confirm_order(user=user, db=db)
    db.refresh(p)
    print("confirm after restore:", result["status"], result["total"], "| stock reduced by 1:", p.stock == orig_stock - 1, "(expect confirmed 399.0 | True)")
finally:
    db.rollback()
    for o in db.query(Order).filter(Order.user_id == user.id).all():
        db.delete(o)
    db.flush()
    db.delete(user)
    p = db.get(Product, pid)
    p.stock = orig_stock
    p.is_active = True
    db.commit()
    db.close()
    ps.build_product_index()

db = SessionLocal()
p = db.get(Product, pid)
print("cleanup:", p.stock == orig_stock, p.is_active, "| temp user gone:", db.query(User).filter(User.email == "zz_cart_test@example.com").count() == 0, "(expect True True | True)")
db.close()
