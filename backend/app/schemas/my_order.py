from datetime import datetime
from typing import List

from pydantic import BaseModel


class MyOrderItem(BaseModel):
    product_id: int
    name: str
    quantity: int
    unit_price: float
    line_total: float


class MyOrderSummary(BaseModel):
    id: int
    status: str
    total: float
    units: int
    created_at: datetime | None = None


class MyOrderDetail(MyOrderSummary):
    items: List[MyOrderItem]
