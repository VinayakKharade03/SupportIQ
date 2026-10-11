import argparse
import json
import os
import sys
from decimal import Decimal

from app.database import SessionLocal
from app.models.user import User  # noqa: F401
from app.models.order import Order, OrderItem  # noqa: F401
from app.models.product import Product, ProductDocument, ProductSpec

# Used only when a product.json has no price_inr / mrp_inr. Sample prices for fictional products.
DEFAULT_PRICES = {
    "boot-airbuds-141-gen-2": ("1299", "3990"),
    "jibel-go-4": ("3499", "4999"),
    "soney-sh-c520": ("3990", "5990"),
}
DOCS = [
    ("guide.md", "user_guide", "User guide"),
    ("troubleshooting.md", "troubleshooting", "Troubleshooting"),
    ("faq.md", "faq", "FAQ"),
]
LIMITS = {"slug": 100, "brand": 80, "name": 150, "category": 50, "subcategory": 50, "tagline": 200}
REQUIRED = ["slug", "brand", "name", "category", "description"]


def read_text(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read().replace("\r\n", "\n").strip()


def load_folder(root):
    items, errors = [], []
    for folder in sorted(os.listdir(root)):
        pj = os.path.join(root, folder, "product.json")
        if not os.path.exists(pj):
            continue
        with open(pj, encoding="utf-8-sig") as f:
            data = json.load(f)
        label = data.get("slug", folder)

        for key in REQUIRED:
            if not str(data.get(key) or "").strip():
                errors.append(f"{label}: missing {key}")
        for key, limit in LIMITS.items():
            if len(str(data.get(key) or "")) > limit:
                errors.append(f"{label}: {key} is longer than {limit}")

        specs = data.get("specs") or []
        for s in specs:
            if not (s.get("group") and s.get("name") and s.get("value")):
                errors.append(f"{label}: incomplete spec {s}")
            elif len(s["group"]) > 50 or len(s["name"]) > 100 or len(s["value"]) > 300:
                errors.append(f"{label}: spec too long {s['name']}")

        docs = {}
        for filename, doc_type, title in DOCS:
            path = os.path.join(root, folder, filename)
            text = read_text(path) if os.path.exists(path) else ""
            if not text:
                errors.append(f"{label}: {filename} missing or empty")
            docs[doc_type] = (title, text)

        default_price, default_mrp = DEFAULT_PRICES.get(data.get("slug"), (None, None))
        price = data.get("price_inr") if data.get("price_inr") is not None else default_price
        mrp = data.get("mrp_inr") if data.get("mrp_inr") is not None else default_mrp
        if price is None:
            errors.append(f"{label}: no price (set price_inr or add it to DEFAULT_PRICES)")
        elif mrp is not None and Decimal(str(mrp)) < Decimal(str(price)):
            errors.append(f"{label}: mrp is lower than price")

        items.append({
            "data": data, "specs": specs, "docs": docs,
            "price": Decimal(str(price)) if price is not None else None,
            "mrp": Decimal(str(mrp)) if mrp is not None else None,
            "stock": int(data.get("demo_stock", 0)),
        })
    return items, errors


def upsert(db, item):
    d = item["data"]
    product = db.query(Product).filter(Product.slug == d["slug"]).first()
    created = product is None
    if created:
        product = Product(slug=d["slug"], stock=item["stock"], is_active=True)
        db.add(product)

    product.name = d["name"]
    product.brand = d["brand"]
    product.category = d["category"]
    product.subcategory = d.get("subcategory")
    product.tagline = d.get("tagline")
    product.description = d["description"]
    product.highlights = d.get("highlights") or []
    product.in_the_box = d.get("in_the_box") or []
    product.price = item["price"]
    product.mrp = item["mrp"]
    db.flush()

    product.specs = [
        ProductSpec(group_name=s["group"], name=s["name"], value=s["value"], position=i)
        for i, s in enumerate(item["specs"])
    ]
    existing = {doc.doc_type: doc for doc in product.documents}
    for doc_type, (title, text) in item["docs"].items():
        if doc_type in existing:
            existing[doc_type].title = title
            existing[doc_type].content = text
        else:
            product.documents.append(ProductDocument(doc_type=doc_type, title=title, content=text))
    db.flush()
    return "CREATE" if created else "UPDATE"


def main():
    parser = argparse.ArgumentParser(description="Import the sample catalog folder into the database")
    parser.add_argument("folder", help="folder that contains one subfolder per product")
    parser.add_argument("--dry-run", action="store_true", help="show what would happen and save nothing")
    args = parser.parse_args()

    if not os.path.isdir(args.folder):
        sys.exit(f"Folder not found: {args.folder}")
    items, errors = load_folder(args.folder)
    if errors:
        print("Problems found, nothing imported:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    if not items:
        sys.exit("No product folders found (each needs a product.json)")

    db = SessionLocal()
    try:
        for item in items:
            action = upsert(db, item)
            d = item["data"]
            print(f"{action} {d['slug']} | {d['brand']} {d['name']} | Rs {item['price']} (MRP {item['mrp']}) | "
                  f"{len(item['specs'])} specs | docs: {', '.join(item['docs'])}")
        if args.dry_run:
            db.rollback()
            print("Dry run: nothing was saved.")
            return
        db.commit()
        print(f"Imported {len(items)} product(s).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    from app.ml.product_search import build_product_index
    build_product_index()
    print("Chat product index rebuilt.")


if __name__ == "__main__":
    main()
