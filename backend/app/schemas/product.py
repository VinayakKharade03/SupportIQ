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
    slug: str | None = None
    brand: str | None = None
    subcategory: str | None = None
    tagline: str | None = None
    mrp: float | None = None
    image_url: str | None = None


class SpecOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_name: str
    name: str
    value: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc_type: str
    title: str
    content: str


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alt: str | None = None
    is_primary: bool
    url: str | None = None


class ProductDetail(ProductOut):
    highlights: list[str] | None = None
    in_the_box: list[str] | None = None
    specs: list[SpecOut] = []
    documents: list[DocumentOut] = []
    images: list[ImageOut] = []
