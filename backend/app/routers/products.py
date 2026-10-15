from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import Product, ProductImage
from app.schemas.product import ProductDetail, ProductOut

router = APIRouter()

DOC_ORDER = {"user_guide": 0, "troubleshooting": 1, "faq": 2}


def _image_url(image_id: int) -> str:
    return f"/products/images/{image_id}"


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
    products = query.order_by(Product.id).offset(offset).limit(limit).all()

    primary = {}
    ids = [p.id for p in products]
    if ids:
        rows = (
            db.query(ProductImage.product_id, ProductImage.id)
            .filter(ProductImage.product_id.in_(ids), ProductImage.is_primary.is_(True))
            .all()
        )
        primary = {product_id: image_id for product_id, image_id in rows}

    out = []
    for p in products:
        item = ProductOut.model_validate(p)
        image_id = primary.get(p.id)
        item.image_url = _image_url(image_id) if image_id else None
        out.append(item)
    return out


@router.get("/images/{image_id}")
def get_image(image_id: int, db: Session = Depends(get_db)):
    image = (
        db.query(ProductImage)
        .join(Product, Product.id == ProductImage.product_id)
        .filter(ProductImage.id == image_id, Product.is_active.is_(True))
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(
        content=bytes(image.data),
        media_type=image.content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    # Built here, while the database session is still open, so the specs, documents and images load
    detail = ProductDetail.model_validate(product)
    detail.documents.sort(key=lambda d: DOC_ORDER.get(d.doc_type, 99))
    for image in detail.images:
        image.url = _image_url(image.id)
    primary = next((i for i in detail.images if i.is_primary), None)
    detail.image_url = primary.url if primary else None
    return detail
