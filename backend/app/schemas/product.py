from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    description: str
    price: float
    stock: int
    created_at: datetime | None = None
