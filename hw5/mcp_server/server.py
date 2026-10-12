"""Campus Customs MCP server.

The single source of shop facts and shop actions for the agent team. Every tool
works on the working copy data/campus_customs_new.db. The original
data/campus_customs.db is only ever read, by reset_working_database, to restore
the working copy; it is never modified.

Shop rules enforced in code (not just in prompts):
- "Today" is desk.date_today, never the system clock.
- Lead times come only from vendors.lead_days.
- A vendor with an open invoice cannot be sent a purchase order.
- Agents can only *request* payments. Money moves only in decide_payment, which
  needs a named human approver and refuses any payment the cash cannot cover.
- Cash only goes out; nothing here adds money.
- Customer and vendor messages are saved as drafts and never sent.
"""

import calendar
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"
ORIGINAL_DB_PATH = DB_PATH.with_name("campus_customs.db")

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}
TICKET_STATUSES = ("open", "in_progress", "waiting_approval", "blocked", "resolved")
# Which agents may write a draft to which audience.
DRAFT_AUTHORS = {
    "customer": {"customer_service"},
    "vendor": {"inventory", "accounting"},
    "landlord": {"facilities", "accounting"},
}

mcp = FastMCP("campus-customs")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _require_db() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")


@contextmanager
def _read():
    """Read-only connection, so lookup tools cannot change shop data."""
    _require_db()
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _write():
    """Read-write connection in one transaction: commit on success, roll back on any error."""
    _require_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_board_tables() -> None:
    """Add the approval queue and draft board to the working copy if a reset removed them."""
    with _write() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY,
                kind TEXT NOT NULL CHECK (kind IN ('invoice', 'rent', 'purchase_order')),
                ref_id INTEGER,
                vendor_id INTEGER,
                sku TEXT,
                size TEXT,
                qty INTEGER,
                amount REAL NOT NULL,
                ticket_id INTEGER,
                requested_by TEXT NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected', 'refused')),
                created_at TEXT NOT NULL,
                decided_by TEXT,
                decided_at TEXT,
                decision_note TEXT,
                payment_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY,
                ticket_id INTEGER,
                audience TEXT NOT NULL CHECK (audience IN ('customer', 'vendor', 'landlord')),
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                author TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL
            );
            """
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today(conn: sqlite3.Connection) -> date:
    """The shop's definition of today comes from desk.date_today, not the system clock."""
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()["date_today"])


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _cash(conn: sqlite3.Connection, account: str = "checking") -> float | None:
    row = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    return row["balance"] if row else None


def _pending_total(conn: sqlite3.Connection) -> float:
    return conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM approvals WHERE status = 'pending'"
    ).fetchone()["t"]


def _open_invoices(conn: sqlite3.Connection, vendor_id: int, today: date) -> list[dict]:
    rows = conn.execute(
        "SELECT id, amount, due_date, status, description FROM invoices "
        "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
        (vendor_id,),
    ).fetchall()
    return [
        {**dict(r), "days_overdue": max((today - date.fromisoformat(r["due_date"])).days, 0)}
        for r in rows
    ]


def _cash_check(conn: sqlite3.Connection, amount: float) -> dict:
    balance = _cash(conn)
    pending = _pending_total(conn)
    return {
        "checking_balance": balance,
        "already_pending": pending,
        "cash_covers_this_payment": balance is not None and balance >= amount,
        "cash_covers_all_pending_including_this": balance is not None and balance >= pending + amount,
    }


# ---------------------------------------------------------------------------
# Lookup tools (read-only)
# ---------------------------------------------------------------------------

@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Read one ticket from the board, plus the shop's today and any approvals or drafts already linked to it."""
    with _read() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"found": False, "ticket_id": ticket_id, "error": "No ticket with this id."}
        approvals = [
            dict(r) for r in conn.execute(
                "SELECT id, kind, ref_id, amount, status, requested_by FROM approvals WHERE ticket_id = ?",
                (ticket_id,),
            )
        ]
        drafts = [
            dict(r) for r in conn.execute(
                "SELECT id, audience, recipient, subject, author FROM drafts WHERE ticket_id = ?",
                (ticket_id,),
            )
        ]
        return {
            "found": True,
            "ticket": dict(row),
            "shop_today": _today(conn).isoformat(),
            "approvals": approvals,
            "drafts": drafts,
        }


@mcp.tool
def list_tickets() -> dict:
    """List every ticket on the board, open or resolved, with its current status."""
    with _read() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at "
            "FROM tickets ORDER BY id"
        ).fetchall()
        return {"shop_today": _today(conn).isoformat(), "tickets": [dict(r) for r in rows]}


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket on the board that is not resolved yet."""
    with _read() as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, status, created_at FROM tickets "
            "WHERE status != 'resolved' ORDER BY id"
        ).fetchall()
        return {"shop_today": _today(conn).isoformat(), "tickets": [dict(r) for r in rows]}


@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int = 1) -> dict:
    """Check on-hand stock for one SKU in one size and report any shortage.

    Use this before promising a customer order. Returns the inventory row and
    how many units are missing to cover qty_needed.
    """
    with _read() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            sizes = [
                r["size"]
                for r in conn.execute("SELECT size FROM inventory WHERE sku = ?", (sku,))
            ]
            return {
                "found": False,
                "sku": sku,
                "size": size,
                "error": "No inventory row for this SKU and size.",
                "sizes_on_file_for_sku": sizes,
            }

    on_hand = row["qty"]
    return {
        "found": True,
        "sku": row["sku"],
        "name": row["name"],
        "size": row["size"],
        "location": row["location"],
        "qty_on_hand": on_hand,
        "qty_needed": qty_needed,
        "can_fill_from_stock": on_hand >= qty_needed,
        "shortage": max(qty_needed - on_hand, 0),
    }


@mcp.tool
def list_inventory(sku: str | None = None) -> dict:
    """List stock for every size of one SKU (or the whole shop if sku is omitted), to find alternatives."""
    with _read() as conn:
        if sku:
            rows = conn.execute(
                "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?", (sku,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT sku, name, size, qty, location FROM inventory").fetchall()
    return {"sku_filter": sku, "rows": [dict(r) for r in rows]}


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty, lead time from the vendors table, and whether it can ship now.

    A vendor cannot ship while it has any open (unpaid) invoice.
    """
    with _read() as conn:
        today = _today(conn)
        vendors = []
        for v in conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"):
            open_inv = _open_invoices(conn, v["id"], today)
            vendors.append({
                **dict(v),
                "open_invoice_ids": [i["id"] for i in open_inv],
                "open_invoice_total": sum(i["amount"] for i in open_inv),
                "can_ship": not open_inv,
            })
    return {"shop_today": today.isoformat(), "vendors": vendors}


@mcp.tool
def get_vendor_status(vendor_id: int) -> dict:
    """Check one vendor before ordering: lead time, open invoices, whether it can ship, and arrival date if ordered today."""
    with _read() as conn:
        v = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        if v is None:
            return {"found": False, "vendor_id": vendor_id, "error": "No vendor with this id."}
        today = _today(conn)
        open_inv = _open_invoices(conn, vendor_id, today)
    can_ship = not open_inv
    return {
        "found": True,
        **dict(v),
        "shop_today": today.isoformat(),
        "open_invoices": open_inv,
        "can_ship": can_ship,
        "blocked_reason": None if can_ship else "Vendor will not ship while an invoice is open and unpaid.",
        "arrival_if_ordered_today": (today + timedelta(days=v["lead_days"])).isoformat() if can_ship else None,
    }


@mcp.tool
def list_invoices(status: Literal["open", "paid", "all"] = "open") -> dict:
    """List vendor invoices with the vendor name, due date, and days overdue measured from desk.date_today."""
    with _read() as conn:
        today = _today(conn)
        sql = (
            "SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, i.status, i.description "
            "FROM invoices i JOIN vendors v ON v.id = i.vendor_id"
        )
        rows = conn.execute(sql if status == "all" else sql + " WHERE i.status = ?",
                            () if status == "all" else (status,)).fetchall()
    invoices = []
    for r in rows:
        days = (today - date.fromisoformat(r["due_date"])).days
        invoices.append({**dict(r), "days_overdue": max(days, 0) if r["status"] == "open" else 0,
                         "is_overdue": r["status"] == "open" and days > 0})
    return {"shop_today": today.isoformat(), "status_filter": status, "invoices": invoices}


@mcp.tool
def get_cash_position() -> dict:
    """Show cash on hand, payments already made, and payments waiting for human approval.

    There is no revenue in this shop model: cash only goes down.
    """
    with _read() as conn:
        accounts = [dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts")]
        payments = [dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY id")]
        pending = [
            dict(r) for r in conn.execute(
                "SELECT id, kind, ref_id, amount, ticket_id FROM approvals WHERE status = 'pending' ORDER BY id"
            )
        ]
        today = _today(conn)
    total = sum(a["balance"] for a in accounts)
    pending_total = sum(p["amount"] for p in pending)
    return {
        "shop_today": today.isoformat(),
        "cash_accounts": accounts,
        "total_cash": total,
        "payments_made": payments,
        "pending_approvals": pending,
        "pending_total": pending_total,
        "cash_after_all_pending": round(total - pending_total, 2),
    }


@mcp.tool
def get_rent_status(lease_id: int) -> dict:
    """Look up a lease's rent amount and due date against the shop's today and cash on hand.

    Use this for rent notices. Days until due are measured from desk.date_today.
    """
    with _read() as conn:
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"found": False, "lease_id": lease_id, "error": "No lease with this id."}
        today = _today(conn)
        accounts = [
            dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts")
        ]

    days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
    total_cash = sum(a["balance"] for a in accounts)
    return {
        "found": True,
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "notes": lease["notes"],
        "shop_today": today.isoformat(),
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
        "cash_accounts": accounts,
        "cash_covers_rent": total_cash >= lease["monthly_rent"],
    }


@mcp.tool
def quote_bulk_order(sku: str, qty: int, discount_pct: float = 0.0) -> dict:
    """Price a bulk order from the pricing table, with an optional percentage discount.

    Use this before answering a discount request. Shows revenue, cost and margin
    at list price and at the requested discount, so no deal is priced below cost.
    """
    if qty <= 0:
        return {"found": False, "sku": sku, "error": "qty must be positive."}
    if not 0 <= discount_pct < 100:
        return {"found": False, "sku": sku, "error": "discount_pct must be between 0 and 100."}

    with _read() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
    if row is None:
        return {"found": False, "sku": sku, "error": "No pricing row for this SKU."}

    unit_cost = row["unit_cost"]
    list_price = row["list_price"]
    discounted_price = round(list_price * (1 - discount_pct / 100), 2)
    unit_margin = round(discounted_price - unit_cost, 2)
    return {
        "found": True,
        "sku": sku,
        "qty": qty,
        "unit_cost": unit_cost,
        "list_price": list_price,
        "list_unit_margin": round(list_price - unit_cost, 2),
        "list_margin_pct": round((list_price - unit_cost) / list_price * 100, 1),
        "discount_pct": discount_pct,
        "discounted_unit_price": discounted_price,
        "discounted_unit_margin": unit_margin,
        "discounted_margin_pct": round(unit_margin / discounted_price * 100, 1),
        "order_revenue": round(discounted_price * qty, 2),
        "order_cost": round(unit_cost * qty, 2),
        "order_margin": round(unit_margin * qty, 2),
        "break_even_discount_pct": round((1 - unit_cost / list_price) * 100, 1),
        "below_cost": unit_margin < 0,
    }


@mcp.tool
def list_approvals(status: Literal["pending", "approved", "rejected", "refused", "all"] = "pending",
                   ticket_id: int | None = None) -> dict:
    """List payment and purchase-order requests in the human approval queue."""
    with _read() as conn:
        sql, params = "SELECT * FROM approvals WHERE 1 = 1", []
        if status != "all":
            sql += " AND status = ?"
            params.append(status)
        if ticket_id is not None:
            sql += " AND ticket_id = ?"
            params.append(ticket_id)
        rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    return {"status_filter": status, "ticket_id": ticket_id, "approvals": [dict(r) for r in rows]}


@mcp.tool
def list_drafts(ticket_id: int | None = None) -> dict:
    """List message drafts on the board (never sent), optionally for one ticket."""
    with _read() as conn:
        if ticket_id is None:
            rows = conn.execute("SELECT * FROM drafts ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
    return {"ticket_id": ticket_id, "drafts": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Board actions (agents may call these; none of them moves money)
# ---------------------------------------------------------------------------

@mcp.tool
def request_payment(kind: Literal["invoice", "rent"], ref_id: int, ticket_id: int,
                    requested_by: str, reason: str) -> dict:
    """Put a vendor-invoice or rent payment in the human approval queue. No money moves.

    The amount is always taken from the database (invoices.amount or
    leases.monthly_rent). ref_id is the invoice id or lease id. Refused if the
    bill is not payable or cash on hand could not cover it.
    """
    if requested_by not in AGENT_NAMES:
        return {"ok": False, "refused": True, "error": f"Unknown requester {requested_by!r}."}
    with _write() as conn:
        if kind == "invoice":
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if inv is None:
                return {"ok": False, "refused": True, "error": f"No invoice {ref_id}."}
            if inv["status"] != "open":
                return {"ok": False, "refused": True, "error": f"Invoice {ref_id} is {inv['status']}, not open."}
            amount, vendor_id = inv["amount"], inv["vendor_id"]
        else:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return {"ok": False, "refused": True, "error": f"No lease {ref_id}."}
            amount, vendor_id = lease["monthly_rent"], None

        existing = conn.execute(
            "SELECT id FROM approvals WHERE kind = ? AND ref_id = ? AND status = 'pending'", (kind, ref_id)
        ).fetchone()
        if existing:
            return {"ok": True, "duplicate": True, "approval_id": existing["id"],
                    "message": "An identical request is already waiting for approval."}

        cash = _cash_check(conn, amount)
        if not cash["cash_covers_this_payment"]:
            return {"ok": False, "refused": True, "amount": amount, **cash,
                    "error": "Cash on hand cannot cover this payment."}

        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, vendor_id, amount, ticket_id, requested_by, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (kind, ref_id, vendor_id, amount, ticket_id, requested_by, reason, _now()),
        )
    return {"ok": True, "approval_id": cur.lastrowid, "status": "pending", "kind": kind,
            "ref_id": ref_id, "amount": amount, **cash,
            "message": "Waiting for human approval. No money has moved."}


@mcp.tool
def create_purchase_order(vendor_id: int, sku: str, size: str, qty: int, ticket_id: int,
                          requested_by: str, reason: str) -> dict:
    """Prepare a restock purchase order for human approval. No money moves and nothing is sent.

    Cost is qty x pricing.unit_cost. Refused if the vendor has an open invoice
    (it will not ship) or cash on hand could not cover the order.
    """
    if requested_by not in AGENT_NAMES:
        return {"ok": False, "refused": True, "error": f"Unknown requester {requested_by!r}."}
    if qty <= 0:
        return {"ok": False, "refused": True, "error": "qty must be positive."}
    with _write() as conn:
        today = _today(conn)
        v = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if v is None:
            return {"ok": False, "refused": True, "error": f"No vendor {vendor_id}."}
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return {"ok": False, "refused": True, "error": f"No inventory row for {sku} size {size}."}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"ok": False, "refused": True, "error": f"No pricing row for {sku}."}
        open_inv = _open_invoices(conn, vendor_id, today)
        if open_inv:
            return {"ok": False, "refused": True, "blocked": True, "vendor": v["name"],
                    "open_invoices": open_inv,
                    "error": "Vendor will not ship while an invoice is open and unpaid. Pay it first."}

        amount = round(price["unit_cost"] * qty, 2)
        cash = _cash_check(conn, amount)
        if not cash["cash_covers_this_payment"]:
            return {"ok": False, "refused": True, "amount": amount, **cash,
                    "error": "Cash on hand cannot cover this purchase order."}

        cur = conn.execute(
            "INSERT INTO approvals (kind, vendor_id, sku, size, qty, amount, ticket_id, requested_by, reason, created_at) "
            "VALUES ('purchase_order', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vendor_id, sku, size, qty, amount, ticket_id, requested_by, reason, _now()),
        )
    return {"ok": True, "approval_id": cur.lastrowid, "status": "pending", "vendor": v["name"],
            "sku": sku, "size": size, "qty": qty, "unit_cost": price["unit_cost"], "amount": amount,
            "lead_days": v["lead_days"],
            "arrival_if_approved_today": (today + timedelta(days=v["lead_days"])).isoformat(),
            **cash, "message": "Waiting for human approval. Nothing has been ordered or paid."}


@mcp.tool
def save_draft(ticket_id: int, audience: Literal["customer", "vendor", "landlord"], recipient: str,
               subject: str, body: str, author: str) -> dict:
    """Save a message as a draft on the board. Drafts are never emailed or sent to anyone."""
    allowed = DRAFT_AUTHORS[audience]
    if author not in allowed:
        return {"ok": False, "refused": True,
                "error": f"{audience} drafts must be written by {sorted(allowed)}, not {author!r}."}
    with _write() as conn:
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, audience, recipient, subject, body, author, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticket_id, audience, recipient, subject, body, author, _now()),
        )
    return {"ok": True, "draft_id": cur.lastrowid, "status": "draft",
            "message": "Saved as a draft on the board. Nothing was sent."}


@mcp.tool
def update_ticket(ticket_id: int, status: Literal["open", "in_progress", "waiting_approval", "blocked", "resolved"],
                  note: str, agent: str) -> dict:
    """Set a ticket's status and append a dated note (the original ticket notes are kept)."""
    if agent not in AGENT_NAMES:
        return {"ok": False, "refused": True, "error": f"Unknown agent {agent!r}."}
    with _write() as conn:
        row = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"ok": False, "error": f"No ticket {ticket_id}."}
        line = f"[{_today(conn).isoformat()} {agent}] {note}"
        notes = f"{row['notes']}\n{line}" if row["notes"] else line
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
    return {"ok": True, "ticket_id": ticket_id, "status": status, "note_added": line}


# ---------------------------------------------------------------------------
# Human-only tools. The backend never gives these to an agent.
# ---------------------------------------------------------------------------

@mcp.tool
def decide_payment(approval_id: int, decision: Literal["approve", "reject"], decided_by: str,
                   note: str = "") -> dict:
    """HUMAN ONLY. Approve (and execute) or reject a pending payment request.

    On approval this re-checks the bill and the cash, then in one transaction:
    lowers cash_accounts.balance, adds a payments row, and marks the invoice paid
    or moves the lease's next_due forward a month. Refuses if cash would go negative.
    """
    decided_by = decided_by.strip()
    if not decided_by or decided_by.lower() in AGENT_NAMES:
        return {"ok": False, "refused": True, "error": "decided_by must name the human approver."}
    with _write() as conn:
        a = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if a is None:
            return {"ok": False, "error": f"No approval {approval_id}."}
        if a["status"] != "pending":
            return {"ok": False, "error": f"Approval {approval_id} is already {a['status']}."}

        def close(status: str, decision_note: str, payment_id: int | None = None) -> None:
            conn.execute(
                "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ?, decision_note = ?, payment_id = ? "
                "WHERE id = ?",
                (status, decided_by, _now(), decision_note, payment_id, approval_id),
            )

        if decision == "reject":
            close("rejected", note or "Rejected by human approver.")
            return {"ok": True, "approval_id": approval_id, "status": "rejected", "money_moved": False}

        today = _today(conn)
        # Re-validate: the bill may have changed since the agent asked.
        if a["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (a["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                close("refused", "Invoice is no longer open.")
                return {"ok": False, "refused": True, "money_moved": False, "error": "Invoice is no longer open."}
        if a["kind"] == "purchase_order" and _open_invoices(conn, a["vendor_id"], today):
            close("refused", "Vendor has an open invoice and will not ship.")
            return {"ok": False, "refused": True, "money_moved": False,
                    "error": "Vendor has an open invoice and will not ship."}

        balance = _cash(conn)
        if balance is None or balance < a["amount"]:
            close("refused", f"Insufficient cash: balance {balance}, payment {a['amount']}.")
            return {"ok": False, "refused": True, "money_moved": False, "checking_balance": balance,
                    "amount": a["amount"], "error": "Not enough cash. Payment refused; balance unchanged."}

        new_balance = round(balance - a["amount"], 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = 'checking'",
                     (new_balance, today.isoformat()))
        ref_id = a["ref_id"] if a["kind"] != "purchase_order" else a["id"]
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, 'checking', ?, ?)",
            (a["kind"], ref_id, a["amount"], today.isoformat(), decided_by),
        )
        effect = {}
        if a["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (a["ref_id"],))
            effect = {"invoice_id": a["ref_id"], "invoice_status": "paid"}
        elif a["kind"] == "rent":
            due = conn.execute("SELECT next_due FROM leases WHERE id = ?", (a["ref_id"],)).fetchone()["next_due"]
            new_due = _add_month(date.fromisoformat(due)).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, a["ref_id"]))
            effect = {"lease_id": a["ref_id"], "previous_due": due, "next_due": new_due}
        else:
            lead = conn.execute("SELECT lead_days FROM vendors WHERE id = ?", (a["vendor_id"],)).fetchone()["lead_days"]
            effect = {"purchase_order_for": f"{a['qty']} x {a['sku']} {a['size']}",
                      "expected_arrival": (today + timedelta(days=lead)).isoformat()}
        close("approved", note or "Approved and paid.", cur.lastrowid)

    return {"ok": True, "approval_id": approval_id, "status": "approved", "money_moved": True,
            "payment_id": cur.lastrowid, "amount": a["amount"], "checking_balance_after": new_balance, **effect}


@mcp.tool
def reset_working_database(confirm: bool = False) -> dict:
    """HUMAN ONLY. Restore data/campus_customs_new.db from the untouched original for a clean run.

    Wipes every approval, draft, payment and ticket update made since the last reset.
    """
    if not confirm:
        return {"ok": False, "refused": True, "error": "Pass confirm=true to reset the working database."}
    if not ORIGINAL_DB_PATH.exists():
        return {"ok": False, "error": f"Original database not found: {ORIGINAL_DB_PATH}"}
    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    _ensure_board_tables()
    with _read() as conn:
        balance = _cash(conn)
        tickets = [dict(r) for r in conn.execute("SELECT id, status FROM tickets ORDER BY id")]
        today = _today(conn).isoformat()
    return {"ok": True, "message": "Working database restored from the original.",
            "shop_today": today, "checking_balance": balance, "tickets": tickets}


_ensure_board_tables()

if __name__ == "__main__":
    mcp.run(show_banner=False)
