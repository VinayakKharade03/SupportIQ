from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.admin_order import (
    AdminOrderDetail,
    AdminOrderItemOut,
    AdminOrderSummary,
    OrderStatus,
    OrderStatusUpdate,
)
from app.services.permissions import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])

# current status -> statuses an admin may move it to
TRANSITIONS = {
    "confirmed": {"shipped", "cancelled"},
    "shipped": {"delivered"},
}


def _summary(order: Order, user: User | None) -> AdminOrderSummary:
    return AdminOrderSummary(
        id=order.id,
        user_id=order.user_id,
        user_email=user.email if user else None,
        status=order.status,
        total=float(order.total),
        units=sum(i.quantity for i in order.items),
        created_at=order.created_at,
    )


def _detail(db: Session, order: Order) -> AdminOrderDetail:
    user = db.get(User, order.user_id)
    items = []
    for i in order.items:
        product = db.get(Product, i.product_id)
        items.append(
            AdminOrderItemOut(
                product_id=i.product_id,
                name=product.name if product else "Unknown",
                quantity=i.quantity,
                unit_price=float(i.unit_price),
                line_total=float(i.unit_price * i.quantity),
            )
        )
    base = _summary(order, user).model_dump()
    return AdminOrderDetail(
        **base, user_name=user.full_name if user else None, items=items
    )


@router.get("", response_model=List[AdminOrderSummary])
def list_orders(
    status: Optional[OrderStatus] = None,
    user_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Order).options(selectinload(Order.items))
    if status:
        query = query.filter(Order.status == status)
    else:
        query = query.filter(Order.status != "pending")
    if user_id is not None:
        query = query.filter(Order.user_id == user_id)
    orders = (
        query.order_by(Order.created_at.desc(), Order.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    ids = {o.user_id for o in orders}
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}
    )
    return [_summary(o, users.get(o.user_id)) for o in orders]


@router.get("/{order_id}", response_model=AdminOrderDetail)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _detail(db, order)


@router.patch("/{order_id}/status", response_model=AdminOrderDetail)
def update_order_status(
    order_id: int, body: OrderStatusUpdate, db: Session = Depends(get_db)
):
    # Lock the order row so two admins cannot change it at the same time
    order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if body.status not in TRANSITIONS.get(order.status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change an order from {order.status} to {body.status}",
        )

    if body.status == "cancelled":
        for item in order.items:
            product = (
                db.query(Product)
                .filter(Product.id == item.product_id)
                .with_for_update()
                .one()
            )
            product.stock += item.quantity

    order.status = body.status
    db.commit()
    db.refresh(order)
    return _detail(db, order)
