from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.services.security import decode_access_token

router = APIRouter()
bearer = HTTPBearer()


class CartAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, gt=0)


class CartRemove(BaseModel):
    product_id: int


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_pending_order(db: Session, user_id: int, create: bool = False):
    order = (
        db.query(Order)
        .filter(Order.user_id == user_id, Order.status == "pending")
        .first()
    )
    if order is None and create:
        order = Order(user_id=user_id, status="pending", total=Decimal("0"))
        db.add(order)
        db.flush()
    return order


def recalc_total(order: Order):
    order.total = sum((i.unit_price * i.quantity for i in order.items), Decimal("0"))


def cart_view(db: Session, order):
    if order is None:
        return {"order_id": None, "status": "empty", "items": [], "total": 0.0}
    items = []
    for i in order.items:
        product = db.get(Product, i.product_id)
        items.append(
            {
                "product_id": i.product_id,
                "name": product.name if product else "Unknown",
                "quantity": i.quantity,
                "unit_price": float(i.unit_price),
                "line_total": float(i.unit_price * i.quantity),
            }
        )
    return {
        "order_id": order.id,
        "status": order.status,
        "items": items,
        "total": float(order.total),
    }


@router.post("/cart/add")
def add_to_cart(body: CartAdd, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.get(Product, body.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    order = get_pending_order(db, user.id, create=True)
    item = next((i for i in order.items if i.product_id == body.product_id), None)
    new_qty = body.quantity + (item.quantity if item else 0)

    if new_qty > product.stock:
        raise HTTPException(status_code=400, detail=f"Only {product.stock} in stock for {product.name}")

    if item:
        item.quantity = new_qty
        item.unit_price = product.price
    else:
        order.items.append(
            OrderItem(product_id=product.id, quantity=body.quantity, unit_price=product.price)
        )

    recalc_total(order)
    db.commit()
    return cart_view(db, get_pending_order(db, user.id))


@router.get("/cart")
def view_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return cart_view(db, get_pending_order(db, user.id))


@router.post("/cart/remove")
def remove_from_cart(body: CartRemove, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = get_pending_order(db, user.id)
    item = next((i for i in order.items if i.product_id == body.product_id), None) if order else None
    if not item:
        raise HTTPException(status_code=404, detail="Item not in cart")

    order.items.remove(item)
    recalc_total(order)
    db.commit()
    return cart_view(db, get_pending_order(db, user.id))


@router.post("/confirm")
def confirm_order(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = get_pending_order(db, user.id)
    if order is None or not order.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    for item in order.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .one()
        )
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for {product.name}")
        product.stock -= item.quantity

    order.status = "confirmed"
    recalc_total(order)
    db.commit()
    return {
        "order_id": order.id,
        "status": order.status,
        "total": float(order.total),
        "message": "Order confirmed",
    }
