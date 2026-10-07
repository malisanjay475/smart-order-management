"""
Offline NLP engine: turns a free-text order (chat message, email or PDF
purchase order) into structured order lines matched to the product catalog.

Pipeline
  1. read_document()     text from .txt / .eml / .pdf (in memory)
  2. split_segments()    one candidate order line per segment
  3. parse_quantity()    digits, "x5", "qty: 5", number words, "two dozen"
  4. clean_product_text  drop prices, units and filler words
  5. match_product()     fuzzy match (RapidFuzz) against product names + aliases
  6. extract_order()     merge duplicates, flag unmatched lines, detect priority / date
No internet connection or API key is needed.
"""

import io
import re
from email import policy
from email.parser import BytesParser

import pdfplumber
from rapidfuzz import fuzz, process, utils

MATCH_THRESHOLD = 72     # minimum fuzzy score (0-100) to accept a match
SURE_THRESHOLD = 85      # accept a line with no quantity only if this sure
MAX_QUANTITY = 10_000

NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "twenty-five": 25, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "couple": 2, "pair": 2,
}
MULTIPLIERS = {"dozen": 12, "dozens": 12, "hundred": 100}

UNITS = {
    "pcs", "pc", "piece", "pieces", "unit", "units", "nos", "no", "number", "numbers",
    "box", "boxes", "pack", "packs", "packet", "packets", "carton", "cartons",
    "set", "sets", "bottle", "bottles", "roll", "rolls", "kg", "kgs", "ream", "reams",
    "qty", "quantity", "x", "each", "item", "items", "dozen", "dozens", "half",
}
FILLER = {
    "please", "pls", "plz", "kindly", "send", "sending", "need", "needs", "needed",
    "want", "wanted", "require", "requires", "required", "order", "ordering", "place",
    "us", "we", "i", "our", "my", "would", "like", "to", "of", "the", "for", "also",
    "some", "add", "supply", "deliver", "delivered", "dispatch", "can", "you", "get",
    "me", "buy", "more", "another", "and", "with", "by", "asap", "urgent", "urgently",
    "immediately", "hi", "hello", "dear", "team", "thanks", "thank", "regards", "sir",
    "madam", "on", "in", "at", "this", "week", "today", "tomorrow", "is", "are", "be",
    "will", "shall", "it", "them", "these", "those", "new", "total", "approx", "around",
}
SKIP_LINE = re.compile(  # header fields of an email or purchase order
    r"^\s*(subject|from|to|cc|date|sent|po number|po no|invoice no|gstin|phone|tel|mobile|"
    r"email|address|ship to|bill to)\s*:",
    re.I,
)
SIGN_OFF = re.compile(r"^\s*(regards|best regards|thanks|thank you|sincerely|cheers)\b", re.I)
GREETING = re.compile(r"^\s*(hi|hello|hey|dear)\b[\w .]{0,30}?(,|$)\s*", re.I)
STANDALONE_INT = re.compile(r"(?<![\w.,\-])(\d+)(?![\w\-]|[.,]\d)")
PRICE = re.compile(r"(?:₹|rs\.?|inr|\$|@)\s*\d[\d,]*(?:\.\d+)?|\b\d[\d,]*\.\d{1,2}\b", re.I)
SKU = re.compile(r"\b[A-Z]{2,4}-\d{2,5}\b")
SERIAL = re.compile(r"^\s*(?:\d{1,2}[.)]|[-*•>]|#\d+)\s+")
PRIORITY = re.compile(r"\b(urgent|urgently|asap|immediately|rush|priority|by today)\b", re.I)
DELIVERY = re.compile(
    r"\b(?:by|before|on or before|deliver(?:y)? (?:by|on))\s+"
    r"((?:mon|tues|wednes|thurs|fri|satur|sun)day|tomorrow|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+[a-z]{3,9}|[a-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?|"
    r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)",
    re.I,
)


class DocumentError(Exception):
    """Raised when an uploaded file cannot be read."""


# ---------------------------------------------------------------------------
# 1. Reading documents
# ---------------------------------------------------------------------------
def read_document(filename: str, data: bytes) -> tuple[str, str]:
    """Return (source, text) for a .txt, .eml or .pdf file given as bytes."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            raise DocumentError("This file is not a valid PDF.")
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            raise DocumentError("This PDF could not be opened.") from exc
        if len(text.strip()) < 5:
            raise DocumentError("No readable text in this PDF (it may be a scanned image).")
        return "pdf", text
    if name.endswith(".eml"):
        msg = BytesParser(policy=policy.default).parsebytes(data)
        body = msg.get_body(preferencelist=("plain", "html"))
        text = body.get_content() if body else ""
        text = re.sub(r"<[^>]+>", " ", text)  # strip HTML tags if only HTML was sent
        return "email", f"Subject: {msg.get('subject', '')}\n{text}"
    if name.endswith(".txt"):
        return "text", data.decode("utf-8", errors="ignore")
    raise DocumentError("Only .txt, .eml and .pdf files are supported.")


# ---------------------------------------------------------------------------
# 2-4. Segments, quantities, product text
# ---------------------------------------------------------------------------
def split_segments(text: str) -> list[str]:
    """Split the text into candidate order lines: by line, sentence, comma, ';', 'and', '&', '+'."""
    segments = []
    for line in text.splitlines():
        if not line.strip() or SKIP_LINE.match(line):
            continue
        if SIGN_OFF.match(line):
            break  # everything after "Regards" is the signature
        line = SERIAL.sub("", GREETING.sub("", line))
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            for part in re.split(r",(?!\d)|;|\s+\band\b\s+|\s+&\s+|\s+\+\s+|\|", sentence, flags=re.I):
                part = part.strip(" .:-\t")
                if part:
                    segments.append(part)
    return segments


def _singular(word: str) -> str:
    irregular = {"mice": "mouse", "knives": "knife", "batteries": "battery"}
    if word in irregular:
        return irregular[word]
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and re.search(r"(xes|ches|shes|sses)$", word):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def normalize(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return " ".join(_singular(w) for w in words)


def parse_quantity(text: str) -> tuple[int | None, str, bool]:
    """
    Find the quantity in a segment.
    Returns (quantity or None, text without it, strong) where strong is False
    for a weak hint like "a" / "an" that ordinary sentences also contain.
    """
    patterns = [
        r"\b(?:qty|quantity)\s*[:=\-]?\s*(\d+)\b",
        r"\b(\d+)\s*(?:x|×)(?=\s|$)",
        r"(?:^|\s)(?:x|×)\s*(\d+)\b",
    ]
    matches = [re.search(p, text, re.I) for p in patterns]
    m = next((x for x in matches if x), None)
    if m is None:
        ints = list(STANDALONE_INT.finditer(text))
        # Table rows like "1  Laptop Stand  6": the leading number is a serial number.
        if len(ints) >= 2 and not text[: ints[0].start()].strip():
            ints = ints[1:]
        m = ints[0] if ints else None
    if m:
        qty = int(m.group(1))
        rest = text[: m.start()] + " " + text[m.end():]
        if re.search(r"\b(dozen|dozens)\b", rest, re.I):
            qty *= 12
        return qty, rest, True

    words = re.findall(r"[a-z\-]+", text.lower())
    if "half" in words and ("dozen" in words or "dozens" in words):
        return 6, text, True
    qty, strong = None, False
    for i, word in enumerate(words):
        if word in NUMBER_WORDS and word not in MULTIPLIERS:
            nxt = words[i + 1] if i + 1 < len(words) else ""
            qty = NUMBER_WORDS[word]
            strong = word not in ("a", "an") or nxt in MULTIPLIERS
            if nxt in MULTIPLIERS:
                qty *= MULTIPLIERS[nxt]
            if strong:
                break
            continue  # keep looking: "a box of two ..." should find "two"
        if word in MULTIPLIERS:
            qty, strong = MULTIPLIERS[word], True
            break
    return qty, text, strong


def clean_product_text(text: str) -> str:
    text = PRICE.sub(" ", text)
    words = [
        w for w in normalize(text).split()
        if w not in FILLER and w not in UNITS and w not in NUMBER_WORDS and _singular(w) not in UNITS
        and not w.isdigit()
    ]
    return " ".join(words)


# ---------------------------------------------------------------------------
# 5. Fuzzy matching against the catalog
# ---------------------------------------------------------------------------
def build_index(products) -> dict:
    """Map every normalized name / alias to its product."""
    index = {}
    for p in products:
        for term in [p.name, *p.alias_list]:
            key = normalize(term)
            if key:
                index.setdefault(key, p)
    return index


def word_coverage(query: str, choice: str) -> float:
    """Share of the query's words that (fuzzily) appear in the choice."""
    q_words, c_words = query.split(), choice.split()
    if not q_words:
        return 0.0
    hits = sum(1 for q in q_words if any(fuzz.ratio(q, c) >= 75 for c in c_words))
    return hits / len(q_words)


def match_product(product_text: str, index: dict):
    """Return (product, score 0-100) for the best catalog match, or (None, best score)."""
    if not product_text or not index:
        return None, 0.0
    results = process.extract(
        product_text, list(index.keys()), scorer=fuzz.WRatio, processor=utils.default_process, limit=5
    )
    if not results:
        return None, 0.0
    best = results[0][1]
    # Several near-equal scores ("mouse" vs "wireless mouse" / "mouse pad"):
    # prefer the one whose whole wording is closest.
    close = [r for r in results if r[1] >= best - 3]
    choice = max(close, key=lambda r: (fuzz.token_sort_ratio(product_text, r[0]), r[1]))
    score = round(float(choice[1]), 1)
    # Most words of the line must belong to the product name, otherwise a long
    # sentence that merely contains "office" would match "Office File Folder".
    if score < MATCH_THRESHOLD or word_coverage(product_text, choice[0]) < 0.5:
        return None, score
    return index[choice[0]], score


# ---------------------------------------------------------------------------
# 6. Full extraction
# ---------------------------------------------------------------------------
def extract_order(text: str, products) -> dict:
    index = build_index(products)
    by_sku = {p.sku.upper(): p for p in products}
    lines: dict[int, dict] = {}
    unmatched = []

    for segment in split_segments(text):
        sku_match = SKU.search(segment)
        working = SKU.sub(" ", PRICE.sub(" ", segment))
        qty, rest, strong = parse_quantity(working)
        product_text = clean_product_text(rest)

        product, score = None, 0.0
        if sku_match and sku_match.group(0).upper() in by_sku:
            product, score = by_sku[sku_match.group(0).upper()], 100.0
        elif product_text:
            product, score = match_product(product_text, index)

        if product is None:
            if strong and product_text and not DELIVERY.search(segment):
                unmatched.append({"text": segment, "quantity": qty})
            continue
        if not strong and score < SURE_THRESHOLD:
            continue  # probably ordinary sentence text, not an order line

        qty = max(1, min(qty or 1, MAX_QUANTITY))
        if product.id in lines:
            lines[product.id]["quantity"] += qty
            lines[product.id]["confidence"] = min(lines[product.id]["confidence"], score)
            lines[product.id]["source_text"] += " | " + segment
        else:
            lines[product.id] = {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "unit": product.unit,
                "quantity": qty,
                "unit_price": product.price,
                "in_stock": product.stock,
                "confidence": score,
                "source_text": segment,
            }

    items = list(lines.values())
    for item in items:
        item["line_total"] = round(item["quantity"] * item["unit_price"], 2)
        item["available"] = item["in_stock"] >= item["quantity"]

    delivery = DELIVERY.search(text)
    confidence = round(sum(i["confidence"] for i in items) / len(items), 1) if items else 0.0
    return {
        "items": items,
        "unmatched": unmatched,
        "priority": "high" if PRIORITY.search(text) else "normal",
        "delivery_hint": delivery.group(1) if delivery else None,
        "estimated_total": round(sum(i["line_total"] for i in items), 2),
        "confidence": confidence,
    }
