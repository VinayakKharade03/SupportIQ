from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.routers.orders import get_current_user
from app.schemas.my_order import MyOrderDetail, MyOrderItem, MyOrderSummary

router = APIRouter()

PlacedStatus = Literal["confirmed", "shipped", "delivered", "cancelled"]


def _summary(order: Order) -> MyOrderSummary:
    return MyOrderSummary(
        id=order.id,
        status=order.status,
        total=float(order.total),
        units=sum(i.quantity for i in order.items),
        created_at=order.created_at,
    )


def _detail(db: Session, order: Order) -> MyOrderDetail:
    items = []
    for i in order.items:
        product = db.get(Product, i.product_id)
        items.append(
            MyOrderItem(
                product_id=i.product_id,
                name=product.name if product else "Unknown",
                quantity=i.quantity,
                unit_price=float(i.unit_price),
                line_total=float(i.unit_price * i.quantity),
            )
        )
    return MyOrderDetail(**_summary(order).model_dump(), items=items)


@router.get("", response_model=List[MyOrderSummary])
def list_my_orders(
    status: Optional[PlacedStatus] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.user_id == user.id, Order.status != "pending")
    )
    if status:
        query = query.filter(Order.status == status)
    orders = (
        query.order_by(Order.created_at.desc(), Order.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_summary(o) for o in orders]


@router.get("/{order_id:int}", response_model=MyOrderDetail)
def get_my_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user.id, Order.status != "pending")
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return _detail(db, order)


@router.post("/{order_id:int}/cancel", response_model=MyOrderDetail)
def cancel_my_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Lock the order row so a double click or a simultaneous admin change cannot restore stock twice
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user.id)
        .with_for_update()
        .first()
    )
    if not order or order.status == "pending":
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "confirmed":
        raise HTTPException(
            status_code=400,
            detail=f"An order that is {order.status} cannot be cancelled",
        )

    for item in sorted(order.items, key=lambda i: i.product_id):
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .one()
        )
        product.stock += item.quantity

    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return _detail(db, order)
