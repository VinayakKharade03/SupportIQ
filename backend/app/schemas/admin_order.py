from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel

OrderStatus = Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]
SettableStatus = Literal["shipped", "delivered", "cancelled"]


class AdminOrderSummary(BaseModel):
    id: int
    user_id: int
    user_email: str | None = None
    status: str
    total: float
    units: int
    created_at: datetime | None = None


class AdminOrderItemOut(BaseModel):
    product_id: int
    name: str
    quantity: int
    unit_price: float
    line_total: float


class AdminOrderDetail(AdminOrderSummary):
    user_name: str | None = None
    items: List[AdminOrderItemOut]


class OrderStatusUpdate(BaseModel):
    status: SettableStatus
