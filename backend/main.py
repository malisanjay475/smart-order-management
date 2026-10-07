"""
AI-Powered Smart Order Management System: REST API (FastAPI).

Run:  uvicorn main:app --reload      (from the backend folder)
Docs: http://127.0.0.1:8000/docs     (interactive Swagger UI)
"""

import os
from collections import Counter
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

import worker
from auth import create_token, get_current_user, hash_password, require_admin, verify_password
from database import Base, SessionLocal, engine, get_db
from models import Order, OrderEvent, OrderItem, Product, User, now
from nlp import DocumentError, extract_order, read_document
from seed import seed

MAX_UPLOAD = 5 * 1024 * 1024
ORDER_STATUSES = ["received", "processing", "confirmed", "on_hold", "shipped", "delivered", "cancelled"]
# Allowed manual status changes by an admin
TRANSITIONS = {
    "confirmed": {"shipped", "cancelled"},
    "on_hold": {"cancelled"},
    "received": {"cancelled"},
    "shipped": {"delivered"},
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    task = worker.start()
    yield
    task.cancel()


app = FastAPI(title="Smart Order Management API", version="1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    password: str = Field(min_length=6, max_length=100)


class LoginIn(BaseModel):
    email: str
    password: str


class ProductIn(BaseModel):
    sku: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    aliases: str = ""
    category: str = "General"
    unit: str = "pcs"
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    reorder_level: int = Field(default=10, ge=0)


class ProductPatch(BaseModel):
    price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    reorder_level: int | None = Field(default=None, ge=0)
    aliases: str | None = None


class OrderLineIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=10_000)
    confidence: float = Field(default=100, ge=0, le=100)


class OrderIn(BaseModel):
    source: str = "text"
    raw_text: str = ""
    priority: str = "normal"
    items: list[OrderLineIn] = Field(min_length=1)

    @field_validator("source")
    @classmethod
    def valid_source(cls, v):
        if v not in {"text", "email", "pdf", "manual"}:
            raise ValueError("source must be text, email, pdf or manual")
        return v

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v):
        if v not in {"normal", "high"}:
            raise ValueError("priority must be normal or high")
        return v


class StatusIn(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role}


def product_out(p: Product) -> dict:
    return {
        "id": p.id, "sku": p.sku, "name": p.name, "aliases": p.aliases, "category": p.category,
        "unit": p.unit, "price": p.price, "stock": p.stock, "reorder_level": p.reorder_level,
        "low_stock": p.stock <= p.reorder_level,
    }


def order_out(o: Order, detail: bool = False) -> dict:
    data = {
        "id": o.id, "code": o.code, "customer": o.customer.name, "source": o.source,
        "status": o.status, "priority": o.priority, "total": o.total,
        "ai_confidence": o.ai_confidence, "item_count": len(o.items),
        "created_at": o.created_at.isoformat() + "Z",
        "processed_at": o.processed_at.isoformat() + "Z" if o.processed_at else None,
    }
    if detail:
        data["raw_text"] = o.raw_text
        data["items"] = [
            {
                "product_id": i.product_id, "sku": i.product.sku, "name": i.product.name,
                "quantity": i.quantity, "unit": i.product.unit, "unit_price": i.unit_price,
                "line_total": round(i.quantity * i.unit_price, 2), "match_score": i.match_score,
                "status": i.status,
            }
            for i in o.items
        ]
        data["events"] = [{"time": e.time.isoformat() + "Z", "message": e.message} for e in o.events]
    return data


def load_order(db: Session, order_id: int) -> Order:
    order = db.scalar(
        select(Order).where(Order.id == order_id).options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.events), selectinload(Order.customer),
        )
    )
    if order is None:
        raise HTTPException(404, "Order not found.")
    return order


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower())):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(name=body.name.strip(), email=body.email.lower(),
                password_hash=hash_password(body.password), role="customer")
    db.add(user)
    db.commit()
    return {"token": create_token(user), "user": user_out(user)}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    return {"token": create_token(user), "user": user_out(user)}


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


# ---------------------------------------------------------------------------
# Products / inventory
# ---------------------------------------------------------------------------
@app.get("/api/products")
def list_products(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return [product_out(p) for p in db.scalars(select(Product).order_by(Product.sku))]


@app.post("/api/products", status_code=201)
def create_product(body: ProductIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if db.scalar(select(Product).where(Product.sku == body.sku.upper())):
        raise HTTPException(409, "A product with this SKU already exists.")
    product = Product(**{**body.model_dump(), "sku": body.sku.upper()})
    db.add(product)
    db.commit()
    return product_out(product)


@app.patch("/api/products/{product_id}")
def update_product(product_id: int, body: ProductPatch, db: Session = Depends(get_db),
                   _admin: User = Depends(require_admin)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found.")
    restocked = body.stock is not None and body.stock > product.stock
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    db.commit()
    retried = worker.retry_on_hold() if restocked else []
    return {**product_out(product), "orders_retried": len(retried)}


# ---------------------------------------------------------------------------
# AI extraction + orders
# ---------------------------------------------------------------------------
@app.post("/api/orders/extract")
async def extract(text: str = Form(""), file: UploadFile | None = File(None),
                  db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """Read a free-text order / email / PDF and return the matched order lines (nothing is saved)."""
    source = "text"
    if file is not None and file.filename:
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "File is too large. The limit is 5 MB.")
        try:
            source, text = read_document(file.filename, data)
        except DocumentError as exc:
            raise HTTPException(400, str(exc))
    if len(text.strip()) < 3:
        raise HTTPException(400, "Type an order or upload a .txt, .eml or .pdf file.")
    products = list(db.scalars(select(Product)))
    result = extract_order(text, products)
    return {"source": source, "raw_text": text, **result}


@app.post("/api/orders", status_code=201)
def create_order(body: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    merged: dict[int, OrderLineIn] = {}
    for line in body.items:
        if line.product_id in merged:
            merged[line.product_id].quantity += line.quantity
        else:
            merged[line.product_id] = line.model_copy()

    order = Order(customer_id=user.id, source=body.source, raw_text=body.raw_text[:20000],
                  priority=body.priority, status="received")
    total = 0.0
    for line in merged.values():
        product = db.get(Product, line.product_id)
        if product is None:
            raise HTTPException(400, f"Product {line.product_id} does not exist.")
        order.items.append(OrderItem(product_id=product.id, quantity=line.quantity,
                                     unit_price=product.price, match_score=line.confidence))
        total += product.price * line.quantity
    order.total = round(total, 2)
    order.ai_confidence = round(sum(l.confidence for l in merged.values()) / len(merged), 1)
    order.events.append(OrderEvent(message=f"Order received via {body.source} and added to the processing queue"))
    db.add(order)
    db.commit()
    worker.enqueue(order.id)
    return order_out(load_order(db, order.id), detail=True)


@app.get("/api/orders")
def list_orders(status: str | None = None, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    query = select(Order).options(selectinload(Order.items), selectinload(Order.customer)).order_by(Order.id.desc())
    if user.role != "admin":
        query = query.where(Order.customer_id == user.id)
    if status:
        query = query.where(Order.status == status)
    return [order_out(o) for o in db.scalars(query)]


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = load_order(db, order_id)
    if user.role != "admin" and order.customer_id != user.id:
        raise HTTPException(404, "Order not found.")
    return order_out(order, detail=True)


@app.patch("/api/orders/{order_id}/status")
def change_status(order_id: int, body: StatusIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    order = load_order(db, order_id)
    is_owner = order.customer_id == user.id
    if user.role != "admin":
        # customers may only cancel their own orders before they ship
        if not is_owner or body.status != "cancelled":
            raise HTTPException(403, "Only an admin can change this status.")
    allowed = TRANSITIONS.get(order.status, set())
    if body.status not in allowed:
        raise HTTPException(400, f"Cannot change an order from '{order.status}' to '{body.status}'.")

    if body.status == "cancelled" and order.status == "confirmed":
        for item in order.items:  # give reserved stock back
            item.product.stock += item.quantity
            item.status = "pending"
        order.events.append(OrderEvent(message="Reserved stock returned to inventory"))
    order.status = body.status
    order.events.append(OrderEvent(message=f"Status changed to {body.status} by {user.name}"))
    db.commit()
    return order_out(load_order(db, order.id), detail=True)


# ---------------------------------------------------------------------------
# Dashboard analytics
# ---------------------------------------------------------------------------
@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    orders = list(db.scalars(select(Order).options(selectinload(Order.items).selectinload(OrderItem.product))))
    products = list(db.scalars(select(Product)))
    counted = [o for o in orders if o.status != "cancelled"]
    revenue = sum(o.total for o in counted if o.status in ("confirmed", "shipped", "delivered"))

    by_status = Counter(o.status for o in orders)
    by_source = Counter(o.source for o in orders)
    today = now().date()
    per_day = []
    for back in range(6, -1, -1):
        day = today - timedelta(days=back)
        day_orders = [o for o in counted if o.created_at.date() == day]
        per_day.append({"date": day.isoformat(), "orders": len(day_orders),
                        "revenue": round(sum(o.total for o in day_orders), 2)})

    sold = Counter()
    for o in counted:
        for i in o.items:
            sold[i.product.name] += i.quantity

    low = sorted((p for p in products if p.stock <= p.reorder_level), key=lambda p: p.stock / max(p.reorder_level, 1))
    times = [(o.processed_at - o.created_at).total_seconds() for o in orders if o.processed_at]
    return {
        "total_orders": len(orders),
        "revenue": round(revenue, 2),
        "pending": by_status.get("received", 0) + by_status.get("processing", 0) + by_status.get("on_hold", 0),
        "avg_confidence": round(sum(o.ai_confidence for o in orders) / len(orders), 1) if orders else 0,
        "avg_processing_seconds": round(sum(times) / len(times), 1) if times else 0,
        "queue_length": worker.queue.qsize() if worker.queue else 0,
        "by_status": {s: by_status.get(s, 0) for s in ORDER_STATUSES},
        "by_source": dict(by_source),
        "per_day": per_day,
        "top_products": [{"name": n, "quantity": q} for n, q in sold.most_common(5)],
        "low_stock": [product_out(p) for p in low],
        "inventory_value": round(sum(p.price * p.stock for p in products), 2),
    }


# ---------------------------------------------------------------------------
# Serve the built React dashboard (frontend/dist)
# ---------------------------------------------------------------------------
DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(os.path.join(DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found")
    index = os.path.join(DIST, "index.html")
    candidate = os.path.join(DIST, path)
    if path and os.path.isfile(candidate) and os.path.abspath(candidate).startswith(os.path.abspath(DIST)):
        return FileResponse(candidate)
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "API is running. Build the frontend (see README) or open /docs."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000)
