"""
Automated tests. TC01-TC12 are the test cases shown in the project report and slides.
Run from the backend folder:  python -m pytest -v
"""

import os
import sys
import tempfile
import time

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
SAMPLES = os.path.join(ROOT, "samples")

# Use a throw-away database and no artificial delay before importing the app.
_tmp = tempfile.mkdtemp()
os.environ["DB_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["PROCESS_DELAY"] = "0"
os.environ["DEMO_ORDERS"] = "0"
sys.path.insert(0, BACKEND)
sys.path.insert(0, SAMPLES)

from fastapi.testclient import TestClient  # noqa: E402

import make_samples  # noqa: E402
from main import app  # noqa: E402
from nlp import parse_quantity  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def sample_files():
    make_samples.main()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # runs start-up: tables, demo data, background worker
        yield c


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture(scope="session")
def admin(client):
    token = login(client, "admin@smartorders.local", "admin123").json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def customer(client):
    token = login(client, "customer@smartorders.local", "customer123").json()["token"]
    return {"Authorization": f"Bearer {token}"}


def extract(client, headers, text=None, filename=None):
    files = None
    if filename:
        with open(os.path.join(SAMPLES, filename), "rb") as fh:
            files = {"file": (filename, fh.read())}
    return client.post("/api/orders/extract", data={"text": text or ""}, files=files, headers=headers)


def product(client, headers, sku):
    return next(p for p in client.get("/api/products", headers=headers).json() if p["sku"] == sku)


def wait_for(client, headers, order_id, done=("confirmed", "on_hold"), timeout=5):
    """The worker runs in the background, so poll until the order leaves the queue."""
    end = time.time() + timeout
    while time.time() < end:
        order = client.get(f"/api/orders/{order_id}", headers=headers).json()
        if order["status"] in done:
            return order
        time.sleep(0.05)
    raise AssertionError(f"order {order_id} still {order['status']}")


def place(client, headers, lines, source="text"):
    body = {"source": source, "raw_text": "test", "items": lines}
    res = client.post("/api/orders", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------- Test cases from the report ----------------

def test_tc01_login_valid(client):
    res = login(client, "admin@smartorders.local", "admin123")
    assert res.status_code == 200
    assert res.json()["user"]["role"] == "admin"
    assert res.json()["token"].count(".") == 2  # a JWT has three parts


def test_tc02_login_wrong_password(client):
    res = login(client, "admin@smartorders.local", "wrong-pass")
    assert res.status_code == 401


def test_tc03_customer_blocked_from_admin(client, customer):
    assert client.get("/api/dashboard", headers=customer).status_code == 403
    assert client.get("/api/dashboard").status_code == 401  # not logged in


def test_tc04_extract_plain_text(client, customer):
    res = extract(client, customer, "Please send 10 wireless mice and 5 USB-C cables")
    items = {i["sku"]: i["quantity"] for i in res.json()["items"]}
    assert items == {"ELC-101": 10, "ELC-103": 5}


def test_tc05_typos_and_number_words(client, customer):
    res = extract(client, customer, "need three keybords and 2 dozen A4 paper reams")
    items = {i["sku"]: i["quantity"] for i in res.json()["items"]}
    assert items == {"ELC-102": 3, "OFC-201": 24}


def test_tc06_pdf_purchase_order(client, customer):
    body = extract(client, customer, filename="sample_po.pdf").json()
    assert body["source"] == "pdf"
    items = {i["sku"]: i["quantity"] for i in body["items"]}
    assert items == {"ELC-105": 6, "ELC-106": 6, "ELC-107": 6, "OFC-203": 50, "PNT-401": 3}


def test_tc07_email_with_unknown_item(client, customer):
    body = extract(client, customer, filename="sample_email.eml").json()
    assert body["source"] == "email"
    assert len(body["items"]) == 4
    assert body["unmatched"][0]["text"] == "1 quantum flux capacitor"
    assert body["delivery_hint"] == "15 Oct"


def test_tc08_in_stock_order_confirmed(client, admin, customer):
    before = product(client, admin, "OFC-204")["stock"]
    order = place(client, customer, [{"product_id": product(client, admin, "OFC-204")["id"], "quantity": 5}])
    assert order["status"] == "received"  # API answers at once; the worker does the rest
    done = wait_for(client, customer, order["id"])
    assert done["status"] == "confirmed"
    assert product(client, admin, "OFC-204")["stock"] == before - 5


def test_tc09_out_of_stock_goes_on_hold_then_restock(client, admin, customer):
    headset = product(client, admin, "ELC-108")  # only 8 in stock
    order = place(client, customer, [{"product_id": headset["id"], "quantity": 50}])
    assert wait_for(client, customer, order["id"])["status"] == "on_hold"
    res = client.patch(f"/api/products/{headset['id']}", json={"stock": 100}, headers=admin)
    assert res.json()["orders_retried"] >= 1
    assert wait_for(client, customer, order["id"], done=("confirmed",))["status"] == "confirmed"


def test_tc10_cancel_returns_stock(client, admin, customer):
    stapler = product(client, admin, "OFC-204")
    order = place(client, customer, [{"product_id": stapler["id"], "quantity": 4}])
    wait_for(client, customer, order["id"])
    res = client.patch(f"/api/orders/{order['id']}/status", json={"status": "cancelled"}, headers=customer)
    assert res.json()["status"] == "cancelled"
    assert product(client, admin, "OFC-204")["stock"] == stapler["stock"]


def test_tc11_wrong_file_type(client, customer):
    res = client.post("/api/orders/extract", files={"file": ("photo.jpg", b"\xff\xd8\xff" + b"0" * 100)},
                      headers=customer)
    assert res.status_code == 400
    assert "supported" in res.json()["detail"]


def test_tc12_empty_order_rejected(client, customer):
    assert extract(client, customer, "  ").status_code == 400
    res = client.post("/api/orders", json={"items": []}, headers=customer)
    assert res.status_code == 422


# ---------------- Extra tests ----------------

def test_customer_sees_only_own_orders(client, admin, customer):
    res = client.post("/api/auth/register", json={"name": "Other User", "email": "other@example.com",
                                                   "password": "secret12"})
    other = {"Authorization": f"Bearer {res.json()['token']}"}
    mine = place(client, customer, [{"product_id": product(client, admin, "OFC-203")["id"], "quantity": 1}])
    assert client.get(f"/api/orders/{mine['id']}", headers=other).status_code == 404
    assert client.get("/api/orders", headers=other).json() == []


def test_duplicate_registration(client):
    res = client.post("/api/auth/register", json={"name": "Copy", "email": "customer@smartorders.local",
                                                   "password": "secret12"})
    assert res.status_code == 409


def test_illegal_status_change(client, admin, customer):
    order = place(client, customer, [{"product_id": product(client, admin, "OFC-207")["id"], "quantity": 1}])
    wait_for(client, customer, order["id"])
    assert client.patch(f"/api/orders/{order['id']}/status", json={"status": "delivered"},
                        headers=admin).status_code == 400
    assert client.patch(f"/api/orders/{order['id']}/status", json={"status": "shipped"},
                        headers=customer).status_code == 403
    assert client.patch(f"/api/orders/{order['id']}/status", json={"status": "shipped"},
                        headers=admin).json()["status"] == "shipped"


def test_noise_text_gives_no_items(client, customer):
    body = extract(client, customer, "We have a meeting tomorrow, please call me").json()
    assert body["items"] == [] and body["unmatched"] == []


def test_quantity_parser():
    assert parse_quantity("qty: 25 wireless mouse")[0] == 25
    assert parse_quantity("laptop stand x 3")[0] == 3
    assert parse_quantity("half a dozen markers")[0] == 6
    assert parse_quantity("1 Laptop Stand 6")[0] == 6  # table row: serial, name, qty


def test_dashboard_numbers(client, admin):
    data = client.get("/api/dashboard", headers=admin).json()
    assert data["total_orders"] >= 5
    assert data["by_status"]["cancelled"] >= 1
    assert len(data["per_day"]) == 7
    assert 0 < data["avg_confidence"] <= 100
