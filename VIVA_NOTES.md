# Viva Notes: AI-Powered Smart Order Management System

Sanjay · UID O22BCA16074 · BCA Semester 5 · Chandigarh University

## 30-second introduction

"My major project is an AI-Powered Smart Order Management System. Businesses receive orders as WhatsApp-style messages, emails and PDF purchase orders, and staff type them into the system by hand, which is slow and error-prone. My system reads the order in plain language, uses NLP to find each product and quantity, even with spelling mistakes, and matches them to the product catalog. The order then goes on a queue, where a background worker checks and reserves stock automatically. Admins get a live dashboard with analytics and inventory alerts. It is built with React, FastAPI, SQLite and RapidFuzz, it works offline, and it has 18 automated tests."

## Likely questions and answers

**1. What problem does your project solve?**
Manual order entry from messages, emails and PDFs is slow and causes mistakes in product names and quantities. My system automates the reading, matching, stock checking and status tracking, while a person can still review and correct the result.

**2. Where is the "AI" in your project?**
In the Natural Language Processing engine (`nlp.py`). It splits free text into order lines, understands quantities written in many ways ("4x", "qty: 25", "three", "two dozen"), cleans the text, and uses fuzzy string matching to find the right product even when the spelling is wrong. It also gives a confidence score for every match and detects priority and delivery dates.

**3. What is fuzzy matching?**
Finding strings that are similar but not exactly equal. It is based on **edit distance (Levenshtein distance)**: the minimum number of insertions, deletions or substitutions needed to turn one string into the other. "keybord" → "keyboard" needs one insertion, so they are very similar.

**4. Which algorithm does RapidFuzz's WRatio use?**
WRatio (weighted ratio) runs several comparisons and takes the best weighted score: a simple ratio (normalized Levenshtein similarity), a partial ratio (best matching substring) and token-based ratios that ignore word order and repeated words. The score is 0 to 100.

**5. Why a threshold of 72?**
I tried it on sample orders with spelling mistakes and on ordinary sentences with no products. 72 accepted the typos ("wireles mouse" scores 92, "keybords" 93) while rejecting unrelated text. A higher threshold risks missing badly spelled items; a lower one risks false matches. I also require at least half the words of the line to belong to the product name, so a sentence like "for our new office" does not match "Office File Folder".

**6. Why not use ChatGPT or another LLM?**
An LLM needs an API key, internet, and costs money per request, and its output can vary. My approach is free, works offline, is fast (milliseconds), and always gives the same result for the same input, which makes it easy to test. An LLM is listed in my future scope for more complex sentences.

**7. How do you read a PDF?**
With pdfplumber, in memory. It returns the text of every page; table rows come as lines like "1 ELC-105 24-inch LED Monitor 6 9,999.00". My parser removes the price and SKU, skips the leading serial number and takes the quantity.

**8. How does the order queue work?**
When an order is placed, the API saves it with status "received" and puts its ID on an `asyncio.Queue`, then answers immediately. A background worker task takes IDs from the queue one by one, checks stock and reserves it, and sets the status to "confirmed" or "on hold". This is the **producer–consumer** pattern.

**9. Why process orders asynchronously?**
So the user does not wait while stock is checked, and so many orders arriving together are handled one at a time in order, without two orders reserving the same stock. In a large system the same idea is used with Redis, RabbitMQ or Celery.

**10. What happens if there is not enough stock?**
The order goes "on hold" and the timeline says which item is short. When the admin increases stock, all orders on hold are put back on the queue and confirmed automatically if stock is now enough.

**11. What is FastAPI and why did you choose it?**
A modern Python web framework for building APIs. It is fast (built on ASGI and async), validates input automatically with Pydantic, and generates interactive API documentation (Swagger UI at `/docs`). Python also has the best NLP libraries.

**12. What is a REST API?**
A way for programs to communicate over HTTP using resources (URLs) and methods: GET to read, POST to create, PATCH to update, DELETE to remove. My React frontend talks to the FastAPI backend this way, using JSON.

**13. What is JWT and how is login secured?**
JSON Web Token: a signed token with three parts (header, payload, signature). After login the server signs a token holding the user ID and role, valid for 8 hours. The browser sends it in the `Authorization: Bearer` header. The server checks the signature, so the token cannot be changed. Passwords are never stored in plain text; they are hashed with **PBKDF2-SHA256 with a random salt and 120,000 iterations**.

**14. How do roles work?**
Each user is an admin or a customer. A FastAPI dependency `require_admin` blocks admin-only routes with error 403. Customers can only see their own orders, and can only cancel them.

**15. Explain your database design.**
Five tables: **User** (name, email, password hash, role), **Product** (SKU, name, aliases, price, stock, reorder level), **Order** (customer, source, status, priority, total, AI confidence), **OrderItem** (order, product, quantity, price at the time of order, match score) and **OrderEvent** (timeline). Order to OrderItem is one-to-many; Product to OrderItem is one-to-many. I store the unit price in OrderItem so old orders keep their price even if the product price changes later.

**16. What is an ORM?**
Object-Relational Mapping. SQLAlchemy lets me use Python classes instead of writing SQL by hand; it creates the tables and queries. It also protects against SQL injection because values are sent as parameters.

**17. Why SQLite? Can it scale?**
SQLite needs no server, so the project runs on any laptop. Because I use SQLAlchemy, switching to MySQL or PostgreSQL only needs a different `DB_URL`.

**18. What is the order life cycle?**
Received → Processing → Confirmed → Shipped → Delivered. An order can also be On hold (not enough stock) or Cancelled. Only allowed changes are accepted; for example, a received order cannot jump to delivered. Cancelling a confirmed order returns the stock.

**19. How did you test the project?**
18 automated tests with pytest and FastAPI's TestClient, using a separate temporary database. They cover login, roles, text/email/PDF extraction, typos, the queue, on hold and restock, cancellation and invalid input. I also tested the full flow manually in the browser.

**20. What is "human in the loop"?**
The AI suggests the order lines with confidence scores, but a person reviews and can correct them before the order is placed. This prevents wrong orders when the AI is unsure.

**21. What was the hardest part?**
Making the extraction accurate. For example, in PDF tables the serial number was read as the quantity, and the comma in "9,999.00" split the line in two. I fixed these with rules for serial numbers and by not splitting on commas between digits, and added test cases for each one.

**22. How is the frontend built?**
React with Vite, as a single-page app with pages for Login, Dashboard, AI Order Intake, Orders and Inventory. Charts are drawn with SVG and CSS, with no chart library. The dashboard and orders refresh automatically every few seconds so you can watch the queue work.

**23. What are the limitations?**
Scanned PDFs need OCR. Products must be in the catalog. Very complex sentences, such as "same as last time but double the paper", are not understood. The queue runs inside one server process.

**24. What is the future scope?**
OCR for scanned orders, WhatsApp and email inbox integration, an LLM for complex sentences, demand forecasting for restocking, invoices and payments, Hindi/Hinglish orders, and Redis or Celery for a multi-server queue.

**25. What did you learn?**
Building a full-stack app with an API, a database and authentication; NLP techniques like tokenizing and fuzzy matching; asynchronous programming with queues; and writing automated tests.

## Key numbers to remember

- Match threshold: **72 / 100**; at least **50%** of words must belong to the product name
- Catalog: **24 products**, 4 categories (Electronics, Office, Furniture, Printing)
- Tests: **18**, all passing (TC01–TC12 plus 6 extra)
- Password hashing: **PBKDF2-SHA256, 120,000 iterations**; token valid **8 hours**
- Upload limit: **5 MB**; file types: **.txt, .eml, .pdf**
- Demo worker delay: **1.5 seconds** (so the queue is visible)
