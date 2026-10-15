from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, LargeBinary, Numeric, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.orm import deferred, relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # catalog details (all optional)
    slug = Column(String(100), unique=True, index=True, nullable=True)
    brand = Column(String(80), nullable=True)
    subcategory = Column(String(50), nullable=True)
    tagline = Column(String(200), nullable=True)
    mrp = Column(Numeric(10, 2), nullable=True)
    highlights = Column(JSON, nullable=True)
    in_the_box = Column(JSON, nullable=True)

    specs = relationship(
        "ProductSpec", back_populates="product",
        cascade="all, delete-orphan", order_by="ProductSpec.position",
    )
    documents = relationship(
        "ProductDocument", back_populates="product", cascade="all, delete-orphan",
    )
    images = relationship(
        "ProductImage", back_populates="product",
        cascade="all, delete-orphan", order_by="ProductImage.position",
    )


class ProductSpec(Base):
    __tablename__ = "product_specs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    group_name = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    value = Column(String(300), nullable=False)
    position = Column(Integer, nullable=False, server_default=text("0"))

    product = relationship("Product", back_populates="specs")


class ProductDocument(Base):
    __tablename__ = "product_documents"
    __table_args__ = (UniqueConstraint("product_id", "doc_type", name="uq_product_document_type"),)

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(20), nullable=False)  # user_guide, troubleshooting, faq
    title = Column(String(150), nullable=False)
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="documents")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(200), nullable=False)
    content_type = Column(String(50), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    alt = Column(String(200), nullable=True)
    position = Column(Integer, nullable=False, server_default=text("0"))
    is_primary = Column(Boolean, nullable=False, server_default=text("false"))
    data = deferred(Column(LargeBinary, nullable=False))  # only loaded when the picture itself is served

    product = relationship("Product", back_populates="images")
