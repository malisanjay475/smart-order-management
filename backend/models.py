"""Database tables."""

from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="customer")  # admin | customer
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[str] = mapped_column(Text, default="")  # comma-separated other names
    category: Mapped[str] = mapped_column(String(60), default="General")
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    price: Mapped[float] = mapped_column(Float)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=10)

    @property
    def alias_list(self):
        return [a.strip() for a in self.aliases.split(",") if a.strip()]


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(20), default="text")  # text | email | pdf
    raw_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # normal | high
    total: Mapped[float] = mapped_column(Float, default=0)
    ai_confidence: Mapped[float] = mapped_column(Float, default=0)  # average match score of the items
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped[User] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    events: Mapped[list["OrderEvent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderEvent.id"
    )

    @property
    def code(self):
        return f"ORD-{1000 + self.id}"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    match_score: Mapped[float] = mapped_column(Float, default=100)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | reserved | short

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class OrderEvent(Base):
    """Timeline of what happened to an order (shown in the dashboard)."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    time: Mapped[datetime] = mapped_column(DateTime, default=now)
    message: Mapped[str] = mapped_column(String(300))

    order: Mapped[Order] = relationship(back_populates="events")
