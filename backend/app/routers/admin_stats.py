from typing import Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.admin_stats import (
    AdminStats,
    OrderStats,
    ProductStats,
    TicketStats,
    TopProduct,
    UserStats,
)
from app.services.permissions import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])

SOLD_STATUSES = ("confirmed", "shipped", "delivered")
TICKET_STATUSES = ("open", "in_progress", "resolved")
ORDER_STATUSES = ("confirmed", "shipped", "delivered", "cancelled")


def _grouped(db: Session, column, *filters) -> Dict[str, int]:
    query = db.query(column, func.count())
    for f in filters:
        query = query.filter(f)
    return {key: count for key, count in query.group_by(column).all()}


def _with_zeros(counts: Dict[str, int], keys) -> Dict[str, int]:
    result = {k: 0 for k in keys}
    result.update(counts)
    return result


@router.get("", response_model=AdminStats)
def get_stats(
    top: int = Query(5, ge=1, le=20),
    low_stock_threshold: int = Query(10, ge=0),
    db: Session = Depends(get_db),
):
    users = UserStats(
        total=db.query(func.count(User.id)).scalar(),
        admins=db.query(func.count(User.id)).filter(User.is_admin.is_(True)).scalar(),
    )

    tickets = TicketStats(
        total=db.query(func.count(Ticket.id)).scalar(),
        by_status=_with_zeros(_grouped(db, Ticket.status), TICKET_STATUSES),
        by_category=_grouped(db, Ticket.category),
        by_sentiment=_grouped(db, Ticket.sentiment),
        by_source=_grouped(db, Ticket.source),
    )

    order_counts = _with_zeros(
        _grouped(db, Order.status, Order.status != "pending"), ORDER_STATUSES
    )
    revenue = (
        db.query(func.coalesce(func.sum(Order.total), 0))
        .filter(Order.status.in_(SOLD_STATUSES))
        .scalar()
    )
    units_sold = (
        db.query(func.coalesce(func.sum(OrderItem.quantity), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status.in_(SOLD_STATUSES))
        .scalar()
    )
    orders = OrderStats(
        total=sum(order_counts.values()),
        by_status=order_counts,
        revenue=float(revenue),
        units_sold=int(units_sold),
        pending_carts=db.query(func.count(Order.id))
        .filter(Order.status == "pending")
        .scalar(),
    )

    active = Product.is_active.is_(True)
    products = ProductStats(
        active=db.query(func.count(Product.id)).filter(active).scalar(),
        archived=db.query(func.count(Product.id))
        .filter(Product.is_active.is_(False))
        .scalar(),
        out_of_stock=db.query(func.count(Product.id))
        .filter(active, Product.stock == 0)
        .scalar(),
        low_stock=db.query(func.count(Product.id))
        .filter(active, Product.stock > 0, Product.stock <= low_stock_threshold)
        .scalar(),
        low_stock_threshold=low_stock_threshold,
    )

    rows = (
        db.query(
            OrderItem.product_id,
            Product.name,
            func.sum(OrderItem.quantity).label("units"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(Order.status.in_(SOLD_STATUSES))
        .group_by(OrderItem.product_id, Product.name)
        .order_by(desc("units"), OrderItem.product_id)
        .limit(top)
        .all()
    )
    top_products = [
        TopProduct(
            product_id=r.product_id,
            name=r.name,
            units_sold=int(r.units),
            revenue=float(r.revenue),
        )
        for r in rows
    ]

    return AdminStats(
        users=users,
        tickets=tickets,
        orders=orders,
        products=products,
        top_products=top_products,
    )
