"""Demo data: two accounts and an office / electronics product catalog."""

import os
import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import hash_password
from models import Order, OrderEvent, OrderItem, Product, User, now

DEMO_USERS = [
    ("Admin", "admin@smartorders.local", "admin123", "admin"),
    ("Demo Customer", "customer@smartorders.local", "customer123", "customer"),
]

# sku, name, aliases, category, unit, price (INR), stock, reorder level
CATALOG = [
    ("ELC-101", "Wireless Mouse", "mouse, cordless mouse, wireless mice, computer mouse", "Electronics", "pcs", 549, 120, 20),
    ("ELC-102", "Mechanical Keyboard", "keyboard, gaming keyboard, mech keyboard", "Electronics", "pcs", 2499, 40, 10),
    ("ELC-103", "USB-C Cable 1m", "usb c cable, type c cable, usb-c cord, charging cable", "Electronics", "pcs", 299, 300, 50),
    ("ELC-104", "HDMI Cable 2m", "hdmi cable, hdmi cord, hdmi wire", "Electronics", "pcs", 399, 150, 30),
    ("ELC-105", "24-inch LED Monitor", "monitor, led monitor, 24 inch monitor, display screen", "Electronics", "pcs", 9999, 18, 5),
    ("ELC-106", "Laptop Stand", "laptop holder, notebook stand", "Electronics", "pcs", 1299, 60, 10),
    ("ELC-107", "Webcam HD 1080p", "webcam, web camera, hd camera", "Electronics", "pcs", 1899, 35, 8),
    ("ELC-108", "Bluetooth Headset", "headset, headphones, bluetooth headphones", "Electronics", "pcs", 1599, 8, 10),
    ("ELC-109", "Power Bank 10000mAh", "power bank, portable charger", "Electronics", "pcs", 1199, 70, 15),
    ("ELC-110", "32GB Pen Drive", "pen drive, usb drive, flash drive, pendrive", "Electronics", "pcs", 449, 200, 40),
    ("ELC-111", "AA Batteries (Pack of 4)", "aa battery, aa batteries, battery pack, batteries", "Electronics", "packs", 180, 250, 50),
    ("ELC-112", "Extension Board 4-Socket", "extension board, extension cord, power strip, spike guard", "Electronics", "pcs", 649, 45, 10),
    ("OFC-201", "A4 Paper Ream (500 sheets)", "a4 paper, paper ream, printing paper, a4 sheets, copier paper", "Office", "reams", 320, 400, 80),
    ("OFC-202", "Blue Ball Pen (Box of 10)", "ball pen, blue pen, pens, pen box", "Office", "boxes", 100, 500, 100),
    ("OFC-203", "Spiral Notebook A5", "notebook, spiral notebook, notepad, register", "Office", "pcs", 85, 600, 100),
    ("OFC-204", "Stapler with Pins", "stapler, stapling machine", "Office", "pcs", 220, 90, 20),
    ("OFC-205", "Whiteboard Marker Set", "whiteboard marker, marker set, markers, board marker", "Office", "sets", 260, 6, 15),
    ("OFC-206", "Sticky Notes Pack", "sticky notes, post it notes, post-it", "Office", "packs", 120, 300, 50),
    ("OFC-207", "Office File Folder", "file folder, document folder, files", "Office", "pcs", 60, 800, 100),
    ("OFC-208", "Desk Organizer", "desk tidy, pen stand, organizer", "Office", "pcs", 450, 55, 10),
    ("FUR-301", "Ergonomic Office Chair", "office chair, chair, ergonomic chair, revolving chair", "Furniture", "pcs", 7499, 12, 4),
    ("FUR-302", "Study Table", "table, desk, office desk, work table", "Furniture", "pcs", 5999, 10, 3),
    ("PNT-401", "Laser Printer Toner", "toner, printer toner, toner cartridge, cartridge", "Printing", "pcs", 2199, 25, 6),
    ("PNT-402", "Inkjet Ink Bottle Set", "ink bottle, printer ink, ink set", "Printing", "sets", 799, 40, 10),
]


def seed(db: Session) -> None:
    """Insert demo users and products if the database is empty."""
    if db.scalar(select(User).limit(1)) is None:
        for name, email, password, role in DEMO_USERS:
            db.add(User(name=name, email=email, password_hash=hash_password(password), role=role))
    if db.scalar(select(Product).limit(1)) is None:
        for sku, name, aliases, category, unit, price, stock, reorder in CATALOG:
            db.add(Product(sku=sku, name=name, aliases=aliases, category=category, unit=unit,
                           price=price, stock=stock, reorder_level=reorder))
    db.commit()
    if os.environ.get("DEMO_ORDERS", "1") != "0" and db.scalar(select(Order).limit(1)) is None:
        seed_demo_orders(db)


DEMO_TEXTS = {
    "text": "Please send {lines}.",
    "email": "Dear team,\nPlease process this order: {lines}.\nRegards",
    "pdf": "PURCHASE ORDER\n{lines}",
}


def seed_demo_orders(db: Session, count: int = 18) -> None:
    """Fictional order history for the last 7 days so the dashboard has something to show."""
    rng = random.Random(42)
    customer = db.scalar(select(User).where(User.role == "customer"))
    products = list(db.scalars(select(Product).where(Product.stock > 20)))
    statuses = ["delivered"] * 6 + ["shipped"] * 4 + ["confirmed"] * 5 + ["cancelled"] * 1
    for n in range(count):
        created = now() - timedelta(days=rng.randint(0, 6), hours=rng.randint(0, 9), minutes=rng.randint(0, 59))
        source = rng.choice(["text", "text", "email", "email", "pdf"])
        status = statuses[n % len(statuses)]
        chosen = rng.sample(products, rng.randint(1, 4))
        order = Order(customer_id=customer.id, source=source, status=status, created_at=created,
                      priority="high" if rng.random() < 0.2 else "normal",
                      processed_at=created + timedelta(seconds=rng.uniform(1.2, 2.4)))
        lines, scores = [], []
        for p in chosen:
            qty = rng.randint(1, 8)
            score = rng.choice([100, 100, 100, 95, 92.3, 90, 86.7])
            reserved = status != "cancelled"
            order.items.append(OrderItem(product_id=p.id, quantity=qty, unit_price=p.price, match_score=score,
                                         status="reserved" if reserved else "pending"))
            if reserved:
                p.stock -= qty
            lines.append(f"{qty} {p.name}")
            scores.append(score)
        order.raw_text = DEMO_TEXTS[source].format(lines=", ".join(lines))
        order.total = round(sum(i.quantity * i.unit_price for i in order.items), 2)
        order.ai_confidence = round(sum(scores) / len(scores), 1)
        order.events.append(OrderEvent(time=created, message=f"Order received via {source} (demo data)"))
        order.events.append(OrderEvent(time=order.processed_at, message="Stock reserved. Order confirmed"))
        if status != "confirmed":
            order.events.append(OrderEvent(time=order.processed_at, message=f"Status changed to {status}"))
        db.add(order)
    db.commit()
