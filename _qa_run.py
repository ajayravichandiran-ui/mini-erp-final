"""Manual QA helper: exercise ERP routes against local Flask."""
import sqlite3
import sys
from urllib.parse import urljoin

import requests

BASE = "http://127.0.0.1:5000"
DB = r"c:\Users\AJAY RAVICHANDIRAN\Desktop\mini-erp\erp_database.db"
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name} {detail}")


def main():
    s = requests.Session()

    # Invalid login
    r = s.post(f"{BASE}/login", data={"username": "nope", "password": "nope"}, allow_redirects=True)
    check("invalid login stays on login", "Invalid" in r.text or r.url.endswith("/login"), r.url)

    # Valid login
    r = s.post(f"{BASE}/login", data={"username": "admin", "password": "password123"}, allow_redirects=True)
    check("admin login", "Inventory overview" in r.text, r.url)

    pages = [
        ("/", "Inventory overview"),
        ("/orders", "Order to Cash"),
        ("/suppliers", "Supplier"),
        ("/repairs", "Repair"),
        ("/p2p", "Procure"),
        ("/finance", "Finance"),
        ("/settings", "System Settings"),
        ("/search?q=Laptop", "Laptop"),
        ("/api/inventory", "success"),
    ]
    for path, needle in pages:
        r = s.get(f"{BASE}{path}")
        ok = r.status_code == 200 and needle.lower() in r.text.lower() and "Internal Server Error" not in r.text
        check(f"GET {path}", ok, f"status={r.status_code} title-ish")

    # Search empty / miss
    r = s.get(f"{BASE}/search", params={"q": "zzz-no-such-item"})
    check("search miss does not 500", r.status_code == 200, str(r.status_code))

    # Update stock for QA widget
    r = s.post(f"{BASE}/update_item/QA Test Widget 928", data={"new_stock": "11"}, allow_redirects=True)
    check("update QA stock", r.status_code == 200 and "QA Test Widget 928" in r.text, str(r.status_code))

    # Create sales order
    r = s.post(
        f"{BASE}/add_order",
        data={"customer": "QA Browser Corp", "product_name": "QA Test Widget 928", "quantity": "2"},
        allow_redirects=True,
    )
    check("create sales order", r.status_code == 200 and "QA Browser Corp" in r.text, str(r.status_code))

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM orders WHERE customer=? ORDER BY id DESC LIMIT 1", ("QA Browser Corp",))
    row = cur.fetchone()
    check("sales order in DB", bool(row), str(row))
    order_id = row[0] if row else None

    if order_id:
        r = s.post(
            f"{BASE}/o2c/delivery/add",
            data={
                "order_id": str(order_id),
                "delivery_date": "2026-10-31",
                "carrier": "QA Carrier",
                "tracking_number": "QA-TRACK-1",
            },
            allow_redirects=True,
        )
        check("outbound delivery", r.status_code == 200 and "Dispatched" in r.text, str(r.status_code))

        r = s.post(
            f"{BASE}/o2c/invoice/add",
            data={
                "order_id": str(order_id),
                "invoice_number": "INV-QA-928",
                "amount": "99.98",
                "due_date": "2026-11-30",
            },
            allow_redirects=True,
        )
        check("AR invoice", r.status_code == 200 and "INV-QA-928" in r.text, str(r.status_code))

        cur.execute("SELECT id FROM customer_invoices WHERE invoice_number=?", ("INV-QA-928",))
        inv = cur.fetchone()
        if inv:
            r = s.post(f"{BASE}/o2c/invoice/pay/{inv[0]}", allow_redirects=True)
            check("mark invoice paid", r.status_code == 200 and "paid" in r.text.lower(), str(r.status_code))

    # Suppliers
    r = s.post(
        f"{BASE}/suppliers",
        data={"name": "QA Vendor LLC", "contact": "555-0100", "email": "qa@vendor.test"},
        allow_redirects=True,
    )
    check("add supplier via POST /suppliers", r.status_code == 200 and "QA Vendor LLC" in r.text, str(r.status_code))
    cur.execute("SELECT id FROM suppliers WHERE name=?", ("QA Vendor LLC",))
    sup = cur.fetchone()
    if sup:
        r = s.post(f"{BASE}/suppliers/delete/{sup[0]}", allow_redirects=False)
        check("delete supplier UI URL /suppliers/delete/<id>", r.status_code in (200, 302), f"status={r.status_code}")
        if r.status_code == 404:
            check("delete supplier UI URL /suppliers/delete/<id>", False, "404 — template/route mismatch")
        r2 = s.post(f"{BASE}/delete_supplier/{sup[0]}", allow_redirects=True)
        check("delete supplier actual route /delete_supplier/<id>", r2.status_code == 200, str(r2.status_code))

    # Repairs
    r = s.post(
        f"{BASE}/repairs/add",
        data={
            "client_name": "QA Client",
            "client_contact": "555-0199",
            "device": "QA Laptop",
            "issue": "Won't boot",
            "estimated_cost": "80",
            "priority": "high",
        },
        allow_redirects=True,
    )
    check("add repair", r.status_code == 200 and "QA Client" in r.text, str(r.status_code))
    cur.execute("SELECT id FROM repairs WHERE client_name=? ORDER BY id DESC LIMIT 1", ("QA Client",))
    rep = cur.fetchone()
    if rep:
        r = s.post(f"{BASE}/repairs/update/{rep[0]}", data={"new_status": "in_progress"}, allow_redirects=True)
        check("update repair status", r.status_code == 200, str(r.status_code))
        r = s.post(f"{BASE}/repairs/delete/{rep[0]}", allow_redirects=True)
        check("delete repair", r.status_code == 200, str(r.status_code))

    # P2P
    r = s.post(
        f"{BASE}/p2p/pr/add",
        data={
            "item_name": "QA Cable",
            "quantity": "5",
            "required_date": "2026-10-15",
            "department": "QA",
            "reason": "testing",
        },
        allow_redirects=True,
    )
    check("P2P add PR", r.status_code == 200, str(r.status_code))
    cur.execute("SELECT id FROM purchase_requisitions WHERE item_name=? ORDER BY id DESC LIMIT 1", ("QA Cable",))
    pr = cur.fetchone()
    cur.execute("SELECT id FROM suppliers LIMIT 1")
    any_sup = cur.fetchone()
    if pr and any_sup:
        r = s.post(
            f"{BASE}/p2p/rfq/add",
            data={
                "pr_id": str(pr[0]),
                "supplier_id": str(any_sup[0]),
                "quoted_price": "10",
                "delivery_days": "7",
                "notes": "qa",
            },
            allow_redirects=True,
        )
        check("P2P add RFQ", r.status_code == 200, str(r.status_code))
        cur.execute("SELECT id FROM rfqs WHERE pr_id=? ORDER BY id DESC LIMIT 1", (pr[0],))
        rfq = cur.fetchone()
        if rfq:
            r = s.post(
                f"{BASE}/p2p/po/add",
                data={
                    "rfq_id": str(rfq[0]),
                    "item_name": "QA Cable",
                    "quantity": "5",
                    "unit_price": "10",
                    "delivery_date": "2026-10-20",
                },
                allow_redirects=True,
            )
            check("P2P add PO", r.status_code == 200, str(r.status_code))
            cur.execute("SELECT id FROM purchase_orders WHERE rfq_id=? ORDER BY id DESC LIMIT 1", (rfq[0],))
            po = cur.fetchone()
            if po:
                r = s.post(
                    f"{BASE}/p2p/grn/add",
                    data={
                        "po_id": str(po[0]),
                        "received_qty": "5",
                        "received_date": "2026-10-21",
                        "condition": "good",
                        "product_name": "QA Test Widget 928",
                        "remarks": "qa",
                    },
                    allow_redirects=True,
                )
                check("P2P add GRN", r.status_code == 200, str(r.status_code))
                r = s.post(
                    f"{BASE}/p2p/invoice/add",
                    data={
                        "po_id": str(po[0]),
                        "invoice_number": "VIN-QA-1",
                        "amount": "50",
                        "invoice_date": "2026-10-22",
                        "due_date": "2026-11-22",
                        "notes": "qa",
                    },
                    allow_redirects=True,
                )
                check("P2P vendor invoice", r.status_code == 200 and "VIN-QA-1" in r.text, str(r.status_code))

    # Finance memo
    r = s.post(
        f"{BASE}/finance/add_memo",
        data={"memo_type": "Credit", "customer": "QA Browser Corp", "amount": "5", "reason": "qa test"},
        allow_redirects=True,
    )
    check("finance add memo", r.status_code == 200 and "QA Browser Corp" in r.text, str(r.status_code))

    # Worker cannot access finance
    s2 = requests.Session()
    s2.post(f"{BASE}/login", data={"username": "worker", "password": "worker123"})
    r = s2.get(f"{BASE}/finance", allow_redirects=True)
    check("worker blocked from finance", r.status_code == 200 and "Access Denied" in r.text or r.url.rstrip("/").endswith("") and "Inventory" in r.text, r.url)

    # Settings hardware endpoint mentioned in UI
    r = s.get(f"{BASE}/api/hardware_update")
    check("GET /api/hardware_update exists", r.status_code != 404, f"status={r.status_code}")

    r = s.get(f"{BASE}/logout", allow_redirects=True)
    check("logout", r.url.endswith("/login") or "Access System" in r.text, r.url)

    # Protected page after logout
    r = s.get(f"{BASE}/orders", allow_redirects=True)
    check("orders requires login", "login" in r.url.lower() or "Access System" in r.text, r.url)

    conn.close()

    failed = [x for x in results if not x[1]]
    print("\n==== SUMMARY ====")
    print(f"passed={len(results)-len(failed)} failed={len(failed)} total={len(results)}")
    for name, ok, detail in failed:
        print(f"FAIL: {name} :: {detail}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
