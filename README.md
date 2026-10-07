# AI-Powered Smart Order Management System

A full-stack web application that reads orders written in plain language (a chat message, an email or a PDF purchase order), uses Natural Language Processing to find each product and quantity, checks stock, and processes the order automatically through a background queue. Admins get a live dashboard, order tracking and inventory management.

**Major Project · BCA · Chandigarh University**
Sanjay · UID O22BCA16074

---

## Features

- **AI order intake**: paste text or upload a `.pdf`, `.eml` or `.txt` file
  - Finds quantities written as digits, `4x`, `qty: 25`, number words (`three`) and `two dozen` / `half a dozen`
  - Fuzzy matching handles spelling mistakes (`keybords` → Mechanical Keyboard) and other names (`mice`, `post-it`, `spike guard`)
  - Reads SKU codes and tables in PDF purchase orders; ignores serial numbers and prices
  - Detects **priority** (urgent, ASAP) and **delivery date** (by Friday, 15 Oct, 20/10/2026)
  - Lists lines it could not match ("Not in the catalog") so a person can map them
  - **Human in the loop**: every extracted line shows a confidence score and can be corrected before the order is placed
- **Asynchronous processing**: orders go on a queue; a background worker checks and reserves stock, then sets the status to *Confirmed* or *On hold*
- Orders on hold are **retried automatically** when stock is added
- **Order life cycle**: Received → Processing → Confirmed → Shipped → Delivered (or Cancelled / On hold), with a timeline of every event
- **JWT login with roles**: admins see everything; customers place and track only their own orders
- **Dashboard**: orders per day, revenue, status breakdown, channel split, average AI confidence, processing time, low-stock alerts, top products
- **Inventory**: search, edit price and stock, add products with extra names the AI should recognise
- Works offline: **no API key or internet connection needed**
- Interactive API documentation at `/docs` (Swagger UI)

## Tech stack

| Part | Technology | Why |
|---|---|---|
| Frontend | React 18 + Vite | Fast, component-based single-page app |
| Backend | Python + FastAPI | Async REST API, automatic validation and Swagger docs |
| Database | SQLite + SQLAlchemy 2 (ORM) | Zero setup; can switch to MySQL / PostgreSQL by changing `DB_URL` |
| NLP | Regular expressions + RapidFuzz | Fast, offline fuzzy string matching |
| PDF reading | pdfplumber | Reliable text extraction from purchase orders |
| Email reading | Python `email` module | Parses `.eml` files |
| Auth | JWT (PyJWT) + PBKDF2-SHA256 password hashing | Stateless, secure login with roles |
| Queue | `asyncio.Queue` + background worker | Orders are processed without blocking the API |
| Testing | pytest + FastAPI TestClient | 18 automated tests, including TC01–TC12 |

## How the AI extraction works

1. **Read the document**: text from the message, the body of the email or every page of the PDF.
2. **Split into candidate lines**: by line, sentence, comma, semicolon, "and", "&", "+" and table columns. Email headers and signatures are skipped.
3. **Find the quantity**: `qty: 25`, `4x`, `x 3`, a standalone number (a leading serial number in a table row is skipped), number words, and dozens.
4. **Clean the product text**: remove prices (₹, Rs, 9,999.00), SKU codes, units (pcs, nos, boxes) and filler words (please, send, need), and turn plurals into singular.
5. **Match to the catalog**: RapidFuzz `WRatio` compares the text with every product name and alias. A match needs a score of **72 or more**, and at least half the words must belong to the product name. If a SKU code is present it is matched directly with 100% confidence.
6. **Combine**: repeated products are added together, and the average confidence, priority and delivery date are returned for review.

## Folder structure

```
smart-order-management/
├── backend/
│   ├── main.py           # FastAPI app: auth, products, orders, dashboard; serves the frontend
│   ├── nlp.py            # NLP engine: read documents, quantities, fuzzy matching
│   ├── worker.py         # asyncio queue + background order processor
│   ├── models.py         # database tables (User, Product, Order, OrderItem, OrderEvent)
│   ├── database.py       # SQLAlchemy engine and session
│   ├── auth.py           # password hashing, JWT, role checks
│   ├── seed.py           # demo users, 24-product catalog, demo order history
│   ├── requirements.txt
│   └── tests/test_api.py # TC01–TC12 + extra tests
├── frontend/
│   └── src/
│       ├── App.jsx                 # layout, navigation, login state
│       ├── api.js                  # fetch wrapper with the JWT token
│       ├── pages/                  # Login, Dashboard, NewOrder, Orders, Inventory
│       ├── components/ui.jsx       # status chips, confidence bars, charts
│       └── styles.css
├── samples/make_samples.py         # creates a chat order, an email and a PDF purchase order
├── run.bat / run.sh                # one-click start
└── VIVA_NOTES.md                   # likely viva questions with answers
```

## How to run

You need **Python 3.10 or newer**. Node.js 18+ is needed only to build or change the frontend.

### Quick start (from the ZIP, frontend already built)

- **Windows**: double-click `run.bat`
- **Mac / Linux**: `bash run.sh`

Then open **http://127.0.0.1:8000** and click **Admin demo** or **Customer demo**.

| Role | Email | Password |
|---|---|---|
| Admin | admin@smartorders.local | admin123 |
| Customer | customer@smartorders.local | customer123 |

### If you cloned this from GitHub

The repository holds the source only. Build the frontend and create the sample files once:

```bash
cd frontend
npm install
npm run build              # creates frontend/dist, which FastAPI serves
cd ..
python samples/make_samples.py
```

Then use `run.bat` / `run.sh`, or the manual steps below.

### Manual steps

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

- App: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

The database file `backend/orders.db` is created on the first run with demo data. Delete it to start fresh.

### Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `DB_URL` | `sqlite:///backend/orders.db` | Any SQLAlchemy database URL |
| `SECRET_KEY` | development value | **Change this** before real use: signs the login tokens |
| `PROCESS_DELAY` | `1.5` | Seconds the worker waits, so the queue is visible in a demo |
| `DEMO_ORDERS` | `1` | Set to `0` to start without demo order history |

### Changing the frontend

```bash
cd frontend
npm run dev        # live reload on http://localhost:5173 (keep the backend running on 8000)
npm run build      # rebuild frontend/dist
```

## Run the tests

```bash
cd backend
python -m pytest -v
```

Expected: **18 passed**.

| ID | Test | Expected result |
|---|---|---|
| TC01 | Log in with correct details | Token issued, role = admin |
| TC02 | Log in with wrong password | 401 error |
| TC03 | Customer opens admin dashboard | 403 error (401 if not logged in) |
| TC04 | "Please send 10 wireless mice and 5 USB-C cables" | Mouse × 10, USB-C cable × 5 |
| TC05 | Typos and number words: "three keybords and 2 dozen A4 paper reams" | Keyboard × 3, A4 paper × 24 |
| TC06 | PDF purchase order with a table | All 5 lines with correct quantities |
| TC07 | Email with an unknown item | 4 items matched, unknown item listed, delivery date found |
| TC08 | Order with enough stock | Confirmed by the worker, stock reduced |
| TC09 | Order larger than stock, then restock | On hold, then confirmed automatically |
| TC10 | Cancel a confirmed order | Stock returned |
| TC11 | Upload a .jpg file | 400 error: file type not supported |
| TC12 | Empty text / order with no items | 400 / 422 error |

## Main API endpoints

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | anyone | Create a customer account |
| POST | `/api/auth/login` | anyone | Get a JWT token |
| GET | `/api/products` | logged in | Product catalog with stock |
| POST / PATCH | `/api/products`, `/api/products/{id}` | admin | Add product / change price or stock |
| POST | `/api/orders/extract` | logged in | AI extraction from text or a file (nothing is saved) |
| POST | `/api/orders` | logged in | Place an order (goes on the queue) |
| GET | `/api/orders`, `/api/orders/{id}` | logged in | List / view orders (customers see only their own) |
| PATCH | `/api/orders/{id}/status` | admin (customer: cancel only) | Ship, deliver or cancel |
| GET | `/api/dashboard` | admin | Analytics for the dashboard |

## Limitations and future scope

- Scanned (image) PDFs need OCR (for example Tesseract), which is not included yet.
- The matcher knows only products in the catalog; a trained NER model or an LLM could understand more complex sentences.
- Future ideas: WhatsApp / email inbox integration, demand forecasting for restocking, invoices and payments, Hindi and Hinglish orders, Redis or Celery for a multi-server queue.
