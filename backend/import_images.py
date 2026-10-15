import argparse
import os
import re
import sys

from app.database import SessionLocal
from app.models.user import User  # noqa: F401
from app.models.order import Order, OrderItem  # noqa: F401
from app.models.product import Product, ProductImage

MAX_BYTES = 2 * 1024 * 1024
TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def natural(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def looks_like(content_type, data):
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def load_folder(root, db):
    items, errors = [], []
    for folder in sorted(os.listdir(root)):
        path = os.path.join(root, folder)
        if not os.path.isdir(path):
            continue
        product = db.query(Product).filter(Product.slug == folder).first()
        if product is None:
            errors.append(f"{folder}: no product with this slug (import the catalog first)")
            continue
        names = [f for f in sorted(os.listdir(path), key=natural) if os.path.splitext(f)[1].lower() in TYPES]
        if not names:
            errors.append(f"{folder}: no images found")
            continue
        files = []
        for name in names:
            content_type = TYPES[os.path.splitext(name)[1].lower()]
            with open(os.path.join(path, name), "rb") as f:
                data = f.read()
            if not data:
                errors.append(f"{folder}/{name}: empty file")
            elif len(data) > MAX_BYTES:
                errors.append(f"{folder}/{name}: larger than 2 MB")
            elif not looks_like(content_type, data):
                errors.append(f"{folder}/{name}: content does not match its {content_type} extension")
            else:
                files.append((name, content_type, data))
        items.append((product, files))
    return items, errors


def main():
    parser = argparse.ArgumentParser(description="Import product images from a folder into the database")
    parser.add_argument("folder", help="folder with one subfolder per product slug")
    parser.add_argument("--dry-run", action="store_true", help="show what would happen and save nothing")
    args = parser.parse_args()
    if not os.path.isdir(args.folder):
        sys.exit(f"Folder not found: {args.folder}")

    db = SessionLocal()
    try:
        items, errors = load_folder(args.folder, db)
        if errors:
            print("Problems found, nothing imported:")
            for e in errors:
                print(" -", e)
            sys.exit(1)
        if not items:
            sys.exit("No product folders found")
        for product, files in items:
            action = "REPLACE" if product.images else "ADD"
            product.images = [
                ProductImage(
                    filename=name, content_type=ct, size_bytes=len(data), data=data,
                    alt=f"{product.name}, image {i + 1}", position=i, is_primary=(i == 0),
                )
                for i, (name, ct, data) in enumerate(files)
            ]
            db.flush()
            total_kb = sum(len(d) for _, _, d in files) / 1024
            print(f"{action} {product.slug} | {len(files)} images | {total_kb:.0f} KB")
        if args.dry_run:
            db.rollback()
            print("Dry run: nothing was saved.")
            return
        db.commit()
        print(f"Imported images for {len(items)} product(s).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
