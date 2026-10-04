import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.product_search import build_product_index
from app.models.product import Product
from app.schemas.admin_product import AdminProductOut, ProductCreate, ProductUpdate
from app.services.permissions import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_admin)])


def _refresh_index():
    """Rebuild the chat product index. A failure is logged, never raised,
    because the database change has already been saved."""
    try:
        build_product_index()
    except Exception:
        logger.exception("Product index rebuild failed")


def _get_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("", response_model=List[AdminProductOut])
def list_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Product)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(Product.name.ilike(pattern), Product.category.ilike(pattern))
        )
    if category:
        query = query.filter(Product.category == category.lower())
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    return query.order_by(Product.id).offset(offset).limit(limit).all()


@router.get("/{product_id}", response_model=AdminProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, product_id)


@router.post("", response_model=AdminProductOut, status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["category"] = data["category"].lower()
    product = Product(**data)
    db.add(product)
    db.commit()
    db.refresh(product)
    _refresh_index()
    return product


@router.patch("/{product_id}", response_model=AdminProductOut)
def update_product(
    product_id: int, body: ProductUpdate, db: Session = Depends(get_db)
):
    product = _get_or_404(db, product_id)
    data = body.model_dump(exclude_unset=True)
    if "category" in data:
        data["category"] = data["category"].lower()
    for key, value in data.items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    _refresh_index()
    return product


@router.delete("/{product_id}", response_model=AdminProductOut)
def archive_product(product_id: int, db: Session = Depends(get_db)):
    product = _get_or_404(db, product_id)
    if product.is_active:
        product.is_active = False
        db.commit()
        db.refresh(product)
        _refresh_index()
    return product


@router.post("/{product_id}/restore", response_model=AdminProductOut)
def restore_product(product_id: int, db: Session = Depends(get_db)):
    product = _get_or_404(db, product_id)
    if not product.is_active:
        product.is_active = True
        db.commit()
        db.refresh(product)
        _refresh_index()
    return product
