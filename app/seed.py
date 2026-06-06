"""Seed demo outlets and products on first startup."""
from sqlalchemy.orm import Session

from app.models import Outlet, Product


def ean13(prefix12: str) -> str:
    """Append a valid EAN-13 check digit to a 12-digit prefix."""
    digits = [int(d) for d in prefix12]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits))
    return prefix12 + str((10 - total % 10) % 10)


CATALOG = [
    # (12-digit barcode prefix, name, category, price MRP, gst %, emoji, stock)
    ("890101000001", "Parle-G Gold Biscuits 200g", "Snacks", 35.0, 18.0, "🍪", 120),
    ("890101000002", "Amul Taaza Toned Milk 1L", "Dairy", 54.0, 0.0, "🥛", 80),
    ("890101000003", "Tata Salt Iodised 1kg", "Grocery", 28.0, 5.0, "🧂", 200),
    ("890101000004", "Aashirvaad Whole Wheat Atta 5kg", "Grocery", 245.0, 5.0, "🌾", 60),
    ("890101000005", "Maggi 2-Min Noodles 280g", "Snacks", 60.0, 18.0, "🍜", 150),
    ("890101000006", "Colgate MaxFresh Toothpaste 150g", "Personal Care", 95.0, 18.0, "🪥", 90),
    ("890101000007", "Surf Excel Easy Wash 1kg", "Household", 140.0, 18.0, "🧺", 70),
    ("890101000008", "Fortune Sunflower Oil 1L", "Grocery", 130.0, 5.0, "🛢️", 100),
    ("890101000009", "Red Label Tea 250g", "Beverages", 145.0, 5.0, "🍵", 85),
    ("890101000010", "Britannia Whole Wheat Bread 400g", "Bakery", 40.0, 0.0, "🍞", 50),
    ("890101000011", "Dettol Liquid Handwash 200ml", "Personal Care", 99.0, 18.0, "🧼", 110),
    ("890101000012", "Coca-Cola 750ml", "Beverages", 40.0, 28.0, "🥤", 140),
    ("890101000013", "Lay's India's Magic Masala 90g", "Snacks", 30.0, 12.0, "🥔", 160),
    ("890101000014", "Cadbury Dairy Milk Silk 150g", "Snacks", 180.0, 18.0, "🍫", 75),
]

OUTLETS = [
    ("DMart — Adajan", "Adajan Gam Road, Surat, Gujarat 395009", "🏬"),
    ("DMart — Vesu", "VIP Road, Vesu, Surat, Gujarat 395007", "🏪"),
]


def seed_if_empty(db: Session) -> None:
    if db.query(Outlet).first():
        return
    for name, address, emoji in OUTLETS:
        outlet = Outlet(name=name, address=address, emoji=emoji)
        db.add(outlet)
        db.flush()
        for prefix, pname, category, price, gst, pemoji, stock in CATALOG:
            db.add(Product(
                outlet_id=outlet.id,
                barcode=ean13(prefix),
                name=pname,
                category=category,
                price=price,
                gst_percent=gst,
                emoji=pemoji,
                stock=stock,
            ))
    db.commit()
