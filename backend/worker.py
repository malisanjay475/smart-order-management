"""
Asynchronous order processing.

New orders are put on an asyncio queue and handled by a background worker,
so the API answers immediately and the heavy work (stock checks, reserving
stock, status updates) happens in the background:

    received -> processing -> confirmed      (every item in stock, stock reserved)
                           -> on_hold        (some items short: waits for restock)
"""

import asyncio
import logging
import os

from sqlalchemy import select

from database import SessionLocal
from models import Order, OrderEvent, now

log = logging.getLogger("worker")
PROCESS_DELAY = float(os.environ.get("PROCESS_DELAY", "1.5"))  # seconds, so the queue is visible in demos

queue: asyncio.Queue | None = None
_loop: asyncio.AbstractEventLoop | None = None


def start() -> asyncio.Task:
    """Create the queue and start the worker on the running event loop (called at app start-up)."""
    global queue, _loop
    queue = asyncio.Queue()
    _loop = asyncio.get_running_loop()
    requeue_pending()
    return asyncio.create_task(run_worker())


def enqueue(order_id: int) -> None:
    """Thread-safe: API handlers run in a thread pool, the queue lives on the event loop."""
    if _loop is None:
        raise RuntimeError("Worker not started")
    _loop.call_soon_threadsafe(queue.put_nowait, order_id)


def add_event(order: Order, message: str) -> None:
    order.events.append(OrderEvent(message=message))


def process_order(order_id: int) -> str:
    """Check stock and reserve it. Runs in a worker thread. Returns the new status."""
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        if order is None or order.status not in ("received", "on_hold"):
            return order.status if order else "missing"

        order.status = "processing"
        add_event(order, "Picked up by the order processing worker")
        db.commit()

        short = [i for i in order.items if i.product.stock < i.quantity]
        if short:
            for item in order.items:
                item.status = "short" if item in short else "pending"
            names = ", ".join(f"{i.product.name} (need {i.quantity}, have {i.product.stock})" for i in short)
            order.status = "on_hold"
            add_event(order, f"On hold: not enough stock for {names}")
        else:
            for item in order.items:
                item.product.stock -= item.quantity
                item.status = "reserved"
            order.status = "confirmed"
            add_event(order, f"Stock reserved for {len(order.items)} item(s). Order confirmed")
            low = [i.product.name for i in order.items if i.product.stock <= i.product.reorder_level]
            if low:
                add_event(order, "Low stock alert: " + ", ".join(low))
        order.processed_at = now()
        db.commit()
        return order.status


def retry_on_hold() -> list[int]:
    """After a restock, put orders that were on hold back on the queue."""
    with SessionLocal() as db:
        ids = list(db.scalars(select(Order.id).where(Order.status == "on_hold").order_by(Order.id)))
    for order_id in ids:
        enqueue(order_id)
    return ids


async def run_worker() -> None:
    while True:
        order_id = await queue.get()
        try:
            if PROCESS_DELAY:
                await asyncio.sleep(PROCESS_DELAY)
            status = await asyncio.to_thread(process_order, order_id)
            log.info("Order %s -> %s", order_id, status)
        except Exception:  # never let one bad order stop the worker
            log.exception("Failed to process order %s", order_id)
        finally:
            queue.task_done()


def requeue_pending() -> None:
    """On start-up, re-queue orders left in 'received' (for example after a crash)."""
    with SessionLocal() as db:
        ids = list(db.scalars(select(Order.id).where(Order.status.in_(["received", "processing"]))))
        for order_id in ids:
            order = db.get(Order, order_id)
            order.status = "received"
            db.commit()
            enqueue(order_id)
