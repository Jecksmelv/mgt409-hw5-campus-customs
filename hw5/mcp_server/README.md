# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that is the single source of shop facts and shop actions for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). The agents never touch the database directly. Every lookup and every change goes through these tools, and the shop rules (human approval for payments, no negative cash, blocked vendors, drafts only) are enforced here in code.

## Database

All tools use the working copy **`data/campus_customs_new.db`**. The original `data/campus_customs.db` is never modified. It is only read by `reset_working_database`, which copies it over the working copy for a clean run. Lookup tools open the database read-only, and write tools use one transaction each.

On start-up the server adds two board tables to the working copy if they are missing: `approvals` (the human approval queue) and `drafts` (unsent messages).

## Tools

**Lookups (read-only)**

| Tool | What it does |
|---|---|
| `get_ticket(ticket_id)` | One ticket, the shop's today (`desk.date_today`), and the approvals and drafts linked to it. |
| `list_tickets()` | Every ticket, open or resolved, with its status. |
| `list_open_tickets()` | Every ticket that isn't resolved. |
| `check_stock(sku, size, qty_needed=1)` | On hand, location, whether the order can be filled, and the shortage, for one SKU in one size. |
| `list_inventory(sku=None)` | Stock for every size of a SKU, or the whole shop. |
| `list_vendors()` | Every vendor's specialty, `lead_days`, open invoices, and whether it can ship. |
| `get_vendor_status(vendor_id)` | One vendor's lead time, open invoices, `can_ship`, and arrival date if ordered today. |
| `list_invoices(status="open")` | Invoices with vendor name and days overdue from `desk.date_today`. |
| `get_cash_position()` | Cash on hand, payments made, pending approvals, and cash left if all are approved. |
| `get_rent_status(lease_id)` | Rent, landlord, next due date, days until due, overdue or not, and whether cash covers it. |
| `quote_bulk_order(sku, qty, discount_pct=0)` | Revenue, cost and margin at list price and at a discount, plus the break-even discount. |
| `list_approvals(status="pending", ticket_id=None)` | The human approval queue. |
| `list_drafts(ticket_id=None)` | Message drafts on the board. |

**Board actions (agents; no money moves)**

| Tool | What it does |
|---|---|
| `request_payment(kind, ref_id, ticket_id, requested_by, reason)` | Queues an invoice or rent payment for human approval. The amount comes from the database. Refused if the bill isn't payable or cash can't cover it. |
| `create_purchase_order(vendor_id, sku, size, qty, ticket_id, requested_by, reason)` | Queues a restock order (qty × unit cost) for approval. Refused if the vendor has an open invoice or cash can't cover it. |
| `save_draft(ticket_id, audience, recipient, subject, body, author)` | Saves a customer, vendor or landlord message as a draft. Nothing is sent. |
| `update_ticket(ticket_id, status, note, agent)` | Sets a ticket's status and appends a dated note. |

**Human only (called by the API, never by an agent)**

| Tool | What it does |
|---|---|
| `decide_payment(approval_id, decision, decided_by, note="")` | Approves (and executes) or rejects a queued request. It re-checks the bill and cash, then in one transaction lowers the balance, adds a `payments` row, and marks the invoice paid or moves the lease's `next_due` forward. Refuses if cash would go negative. No agent is given this tool. The API calls it from `POST /api/approvals/{id}/approve` or `/reject`. |
| `reset_working_database(confirm=False)` | Restores the working copy from the original database and recreates the board tables. Needs `confirm=true`. The API calls it from `POST /api/reset`. |

## Run

From the `hw5` folder, with the project virtual environment:

```
.venv\Scripts\python mcp_server\server.py
```

The server speaks MCP over stdio. Claude Code connects through `.mcp.json`, and the agent backend starts it from `backend/mcp_client.py`. Dependencies are in the top-level `requirements.txt`.
