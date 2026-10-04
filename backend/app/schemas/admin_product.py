from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Price = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
Stock = Annotated[int, Field(ge=0)]


class AdminProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    description: str
    price: float
    stock: int
    is_active: bool
    created_at: datetime | None = None


class ProductCreate(BaseModel):
    name: Name
    category: Category
    description: Description
    price: Price
    stock: Stock = 0


class ProductUpdate(BaseModel):
    name: Optional[Name] = None
    category: Optional[Category] = None
    description: Optional[Description] = None
    price: Optional[Price] = None
    stock: Optional[Stock] = None

    @model_validator(mode="after")
    def check_fields(self):
        provided = self.model_fields_set
        if not provided:
            raise ValueError("Provide at least one field to update")
        for field in provided:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
