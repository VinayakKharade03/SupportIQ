from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductDetail, ProductOut

router = APIRouter()

DOC_ORDER = {"user_guide": 0, "troubleshooting": 1, "faq": 2}


@router.get("", response_model=List[ProductOut])
def list_products(
    category: Optional[str] = None,
    brand: Optional[str] = None,
    subcategory: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(Product.is_active.is_(True))
    if category:
        query = query.filter(Product.category == category)
    if brand:
        query = query.filter(func.lower(Product.brand) == brand.lower())
    if subcategory:
        query = query.filter(func.lower(Product.subcategory) == subcategory.lower())
    return query.order_by(Product.id).offset(offset).limit(limit).all()


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    # Built here, while the database session is still open, so the specs and documents load
    detail = ProductDetail.model_validate(product)
    detail.documents.sort(key=lambda d: DOC_ORDER.get(d.doc_type, 99))
    return detail
