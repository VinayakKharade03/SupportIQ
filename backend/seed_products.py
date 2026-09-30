from decimal import Decimal

from app.database import SessionLocal
from app.models.user import User  # noqa: F401
from app.models.product import Product
from app.models.order import Order, OrderItem  # noqa: F401

PRODUCTS = [
    ("Wireless Earbuds Pro", "earbuds", "True wireless earbuds with active noise cancellation, Bluetooth 5.3, and up to 30 hours of battery life with the charging case. Touch controls and a built-in microphone for calls.", "3499.00", 40),
    ("Wireless Earbuds Lite", "earbuds", "Budget true wireless earbuds with clear sound, Bluetooth 5.2, and around 20 hours of playback with the case. Lightweight fit for everyday use.", "1499.00", 60),
    ("Neckband Bluetooth Headset", "neckband", "Bluetooth neckband with magnetic earbuds, up to 40 hours of playback, fast charging, and vibration alerts for calls.", "1299.00", 50),
    ("Over-Ear Wireless Headphones", "headphones", "Foldable over-ear wireless headphones with soft ear cushions, deep bass, Bluetooth 5.0, and up to 60 hours of battery life.", "2999.00", 25),
    ("Wired Earphones with Mic", "earphones", "Wired in-ear earphones with a 3.5mm jack, inline microphone, and volume controls. Works with phones, laptops, and tablets.", "499.00", 100),
    ("Portable Bluetooth Speaker Mini", "speaker", "Pocket-sized Bluetooth speaker with punchy sound, 12 hours of playback, and a built-in microphone for speakerphone calls.", "1199.00", 45),
    ("Portable Bluetooth Speaker Max", "speaker", "Large waterproof Bluetooth speaker with 20W output, 24 hours of playback, party lights, and a carry strap.", "3999.00", 20),
    ("Soundbar 2.1", "soundbar", "2.1 channel soundbar with a wireless subwoofer, HDMI ARC, Bluetooth, and 120W total output for TV and movies.", "6999.00", 15),
    ("Gaming Headset", "headset", "Over-ear gaming headset with a detachable boom microphone, surround sound, RGB lighting, and a comfortable adjustable headband.", "2499.00", 30),
    ("USB-C Fast Charging Cable", "accessory", "1 meter braided USB-C fast charging cable, supports up to 60W charging and data transfer. Compatible with most earbuds cases and speakers.", "399.00", 150),
]


def main():
    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            print("Products already exist, skipping seed.")
            return
        for name, category, description, price, stock in PRODUCTS:
            db.add(Product(name=name, category=category, description=description, price=Decimal(price), stock=stock))
        db.commit()
        print(f"Seeded {len(PRODUCTS)} products.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
