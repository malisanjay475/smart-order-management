"""Create sample orders for testing: a chat message, an email (.eml) and a PDF purchase order.
Run:  python samples/make_samples.py     (needs: pip install reportlab)
All company and person names are fictional."""

import os
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))

CHAT_ORDER = """Hi, please send 10 wireless mice, 5 USB-C cables and three keybords.
Also need 2 dozen A4 paper reams urgently by Friday."""

EMAIL_BODY = """Dear Sales Team,

Hope you are doing well. Please process the following order for our new office:

- 4x HDMI cable 2m
- Ergonomic office chair 2 nos
- half a dozen whiteboard markers
- 20 sticky notes
- 1 quantum flux capacitor

Kindly deliver by 15 Oct.

Regards,
Neha Kapoor
Purchase Manager, Bluepeak Technologies (fictional)
"""

PO_ROWS = [
    ("1", "ELC-105", "24-inch LED Monitor", "6", "9,999.00"),
    ("2", "ELC-106", "Laptop Stand", "6", "1,299.00"),
    ("3", "ELC-107", "Webcam HD 1080p", "6", "1,899.00"),
    ("4", "OFC-203", "Spiral Notebook A5", "50", "85.00"),
    ("5", "PNT-401", "Laser Printer Toner", "3", "2,199.00"),
]


def write_text():
    with open(os.path.join(HERE, "sample_order.txt"), "w", encoding="utf-8") as fh:
        fh.write(CHAT_ORDER + "\n")


def write_email():
    msg = EmailMessage()
    msg["From"] = "neha.kapoor@bluepeak.example"
    msg["To"] = "orders@smartorders.example"
    msg["Subject"] = "Purchase order - new office setup"
    msg.set_content(EMAIL_BODY)
    with open(os.path.join(HERE, "sample_email.eml"), "wb") as fh:
        fh.write(bytes(msg))


def write_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(os.path.join(HERE, "sample_po.pdf"), pagesize=A4)
    table = Table([("S.No", "SKU", "Description", "Qty", "Unit Price (Rs)")] + PO_ROWS,
                  colWidths=[40, 70, 200, 50, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    doc.build([
        Paragraph("PURCHASE ORDER", styles["Title"]),
        Paragraph("PO Number: PO-2026-0457", styles["Normal"]),
        Paragraph("From: Orion Learning Centre (fictional), Mohali", styles["Normal"]),
        Spacer(1, 16),
        table,
        Spacer(1, 16),
        Paragraph("Please deliver on or before 20/10/2026.", styles["Normal"]),
    ])


def main():
    write_text()
    write_email()
    write_pdf()


if __name__ == "__main__":
    main()
    print("Created sample_order.txt, sample_email.eml and sample_po.pdf in", HERE)
