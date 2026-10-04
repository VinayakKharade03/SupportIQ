from typing import Dict, List

from pydantic import BaseModel


class UserStats(BaseModel):
    total: int
    admins: int


class TicketStats(BaseModel):
    total: int
    by_status: Dict[str, int]
    by_category: Dict[str, int]
    by_sentiment: Dict[str, int]
    by_source: Dict[str, int]


class OrderStats(BaseModel):
    total: int
    by_status: Dict[str, int]
    revenue: float
    units_sold: int
    pending_carts: int


class ProductStats(BaseModel):
    active: int
    archived: int
    out_of_stock: int
    low_stock: int
    low_stock_threshold: int


class TopProduct(BaseModel):
    product_id: int
    name: str
    units_sold: int
    revenue: float


class AdminStats(BaseModel):
    users: UserStats
    tickets: TicketStats
    orders: OrderStats
    products: ProductStats
    top_products: List[TopProduct]
