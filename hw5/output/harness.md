# Campus Customs — Agent Harness

## Architecture at a Glance

```
 React dashboard (frontend/, Vite :5173)
        │  fetch, with CORS for localhost:5173
        ▼
 FastAPI backend (backend/main.py, :8000) ──── output/audit_trail.json (append-only)
        │                         │
        │ DashboardMCP            │ run_ticket() → five PydanticAI agents (gpt-6-luna via Portkey)
        │ (human actions, reads)  │ each agent sees an allowlisted slice of the same MCP server
        ▼                         ▼
 Campus Customs MCP server (mcp_server/server.py, FastMCP, stdio)
        │  the only code that touches the database; shop rules are enforced here
        ▼
 data/campus_customs_new.db  (working copy) ◄── reset from ── data/campus_customs.db (never modified)
```

| Layer | Files | Started by |
|---|---|---|
| Database | `data/campus_customs.db`, `data/campus_customs_new.db` | — |
| MCP server | `mcp_server/server.py`, `mcp_server/README.md` | Launched over stdio by the backend and by Claude Code (`.mcp.json`) |
| Agents | `backend/agents.py`, `backend/mcp_client.py`, `backend/models.py`, `backend/llm.py`, `backend/audit.py`, `backend/prompts/*.md` | `POST /api/run`, or `python -m backend.agents <id>` |
| API | `backend/main.py` | `uvicorn main:app --reload --port 8000`, run from `backend/` |
| Dashboard | `frontend/src/**` | `npm run dev`, run from `frontend/` |

## Databases

| File | Role |
|---|---|
| `data/campus_customs.db` | Original data pack. Never modified; used only to reset the working copy. |
| `data/campus_customs_new.db` | Working copy. The MCP server and FastAPI backend read and write this file. |

The working copy was created as a byte-for-byte copy of the original (identical SHA-256: `23686a90…f360a`). It is reset from the original through `POST /api/reset` (MCP tool `reset_working_database`). It now holds the results of the Problem 9 full run. The original still has its original SHA-256.

## Database Tables

All fields below were read from the database schema (`sqlite_master` / `PRAGMA`), not assumed.

### `desk`
**Fields:** `date_today` (TEXT, NOT NULL), `notes` (TEXT)

**Why it matters:** `date_today` (`2026-08-31`) is the shop's only definition of "today", so every agent uses it — not the system clock — to decide whether rent or an invoice is overdue.

### `tickets`
**Fields:** `id` (INTEGER PK), `type` (TEXT), `requester` (TEXT), `subject` (TEXT), `sku` (TEXT), `size` (TEXT), `qty` (INTEGER), `lease_id` (INTEGER → `leases.id`), `invoice_id` (INTEGER → `invoices.id`), `status` (TEXT), `notes` (TEXT), `created_at` (TEXT)

**Why it matters:** This is the board the Boss reads; `type` drives routing, and the `sku`/`size`/`qty`, `lease_id` and `invoice_id` columns tell the specialist agents exactly which rows in the other tables a ticket touches.

### `inventory`
**Fields:** `sku` (TEXT), `name` (TEXT), `size` (TEXT), `qty` (INTEGER), `location` (TEXT) — primary key (`sku`, `size`)

**Why it matters:** Inventory checks stock per SKU *and* size here (e.g. `CC-TEE-WHITE` S has 0 while M has 5), which decides whether an order can be filled now or needs a restock.

### `pricing`
**Fields:** `sku` (TEXT PK), `unit_cost` (REAL), `list_price` (REAL)

**Why it matters:** Accounting uses `unit_cost` vs. `list_price` to compute margins for discount requests and to price purchase orders for restocks.

### `vendors`
**Fields:** `id` (INTEGER PK), `name` (TEXT), `specialty` (TEXT), `lead_days` (INTEGER)

**Why it matters:** Inventory matches a product to a vendor by `specialty` and must quote restock timing only from `lead_days` — lead times are never invented.

### `leases`
**Fields:** `id` (INTEGER PK), `space_name` (TEXT), `landlord` (TEXT), `monthly_rent` (REAL), `next_due` (TEXT), `notes` (TEXT)

**Why it matters:** Facilities uses `monthly_rent` and `next_due` to handle rent tickets and must advance `next_due` after an approved rent payment is made.

### `cash_accounts`
**Fields:** `name` (TEXT PK), `balance` (REAL), `date` (TEXT)

**Why it matters:** The pay tool checks `balance` before every payment and refuses any payment that would push it below zero; it is the only source of cash, and money only flows out.

### `payments`
**Fields:** `id` (INTEGER PK), `kind` (TEXT), `ref_id` (INTEGER), `amount` (REAL), `account` (TEXT), `paid_at` (TEXT), `approved_by` (TEXT, NOT NULL)

**Why it matters:** It is empty at the start and becomes the audit trail of executed payments; `approved_by` is required, so no payment row can exist without a named human approver.

### `invoices`
**Fields:** `id` (INTEGER PK), `vendor_id` (INTEGER → `vendors.id`), `amount` (REAL), `due_date` (TEXT), `status` (TEXT), `description` (TEXT)

**Why it matters:** Any `open` invoice for a vendor blocks new shipments from that vendor, so Accounting must check this before Inventory can restock, and mark the invoice paid once an approved payment is made.

### `approvals` (added by the MCP server)
**Fields:** `id` (INTEGER PK), `kind` (`invoice` / `rent` / `purchase_order`), `ref_id` (INTEGER), `vendor_id` (INTEGER), `sku` (TEXT), `size` (TEXT), `qty` (INTEGER), `amount` (REAL), `ticket_id` (INTEGER), `requested_by` (TEXT), `reason` (TEXT), `status` (`pending` / `approved` / `rejected` / `refused`), `created_at`, `decided_by`, `decided_at`, `decision_note` (TEXT), `payment_id` (INTEGER)

**Why it matters:** This is the human approval queue. Agents can only add `pending` rows. A row becomes `approved`, with a `payment_id`, only when a person approves it in the dashboard and the payment is actually executed.

### `drafts` (added by the MCP server)
**Fields:** `id` (INTEGER PK), `ticket_id` (INTEGER), `audience` (`customer` / `vendor` / `landlord`), `recipient`, `subject`, `body`, `author` (TEXT), `status` (always `draft`), `created_at`

**Why it matters:** These are the board's unsent outreach messages. Customer, vendor and landlord messages live only here, so nothing reaches a real person.

These two tables are not in the original data pack. `mcp_server/server.py` creates them (`CREATE TABLE IF NOT EXISTS`) in the working copy on start-up and after every reset.

## Starting State Snapshot

| Item | Value |
|---|---|
| Today (`desk.date_today`) | 2026-08-31 |
| Cash (`checking`) | $3,400.00 |
| Open invoice 501 | $840.00 to Bulldog Print Co, due 2026-08-28 — **overdue by 3 days** |
| Lease 1 rent | $2,400.00 to Elm City Properties, due 2026-09-02 (in 2 days) |
| Payments recorded | none |

## The Three Open Tickets

### Ticket 101 — `customer_order` — Tauhid Zaman, "Bulldog tee"
Needs 1 × `CC-TEE-WHITE`, size S.

| Linked table | What it shows |
|---|---|
| `inventory` | `CC-TEE-WHITE` / S has **qty 0** (Aisle B) → cannot fill from stock. |
| `vendors` | Apparel reprint → **Bulldog Print Co** (id 1), `lead_days` = 5. |
| `invoices` (via `invoice_id` 501) | Bulldog Print Co has **open, overdue** invoice 501 ($840, "Rush reprint CC-TEE-WHITE S"). Under shop rules the vendor will not ship until it is paid. |
| `pricing` | Unit cost $8.00, list price $28.00 — the cost of a restock PO. |
| `cash_accounts` / `payments` | Paying invoice 501 needs human approval and enough cash; a paid invoice adds a `payments` row and flips the invoice status. |

**Agents involved:** Inventory (stock + vendor), Accounting (invoice 501, restock PO), Customer Service (draft reply with an honest ETA based on the 5-day lead time).

### Ticket 102 — `rent_notice` — Elm City Properties, "Rent due"
"Shop rent due in 2 days."

| Linked table | What it shows |
|---|---|
| `leases` (via `lease_id` 1) | Chapel Street shop, $2,400/month, `next_due` 2026-09-02 → due in 2 days relative to `desk.date_today`; not yet overdue. |
| `cash_accounts` | $3,400 covers rent. |
| `payments` | Rent payment requires human approval, then a `payments` row (`kind` rent, `ref_id` 1) and `leases.next_due` advanced. |

**Agents involved:** Facilities (lease), Accounting (cash check + payment for approval).

### Ticket 103 — `price_override` — Yale AI Club, "Bulk hoodie discount"
Wants 20 × `CC-HOOD-NAVY`, size M, with a bulk discount.

| Linked table | What it shows |
|---|---|
| `inventory` | `CC-HOOD-NAVY` / M has **qty 8** → a **12-unit shortage**. |
| `pricing` | Unit cost $22.00, list price $58.00 → $36.00 margin per unit (62%); this bounds any discount. |
| `vendors` | Apparel → **Bulldog Print Co**, `lead_days` = 5. |
| `invoices` | Same vendor as ticket 101, so open invoice 501 also blocks restocking these hoodies. |
| `cash_accounts` | A 12-unit restock costs 12 × $22 = $264. |

**Agents involved:** Inventory (shortage + vendor), Accounting (margin, discount ceiling, PO), Boss (final call on the discount), Customer Service (draft offer to the club).

## Cross-Ticket Constraints

- **One vendor blocks two tickets.** Tickets 101 and 103 both depend on Bulldog Print Co, which will not ship while invoice 501 is open.
- **Cash is tight.** Invoice 501 ($840) + rent ($2,400) = $3,240, leaving **$160** of the $3,400. That is not enough for the $264 hoodie restock on top, so the agents must prioritize, and the pay tool must refuse anything that would go negative.
- **No inflow.** No revenue is modeled, so the plan cannot assume cash from the hoodie sale or the tee order.

## First Three MCP Tools (Problem 3)

These were the first tools, one per open ticket. The full current tool list is in **All MCP Tools** below.

### `check_stock(sku, size, qty_needed)`
- **Reads:** `inventory`
- **Unlocks:** Ticket **101** (Tauhid Zaman, 1 × `CC-TEE-WHITE` size S)
- **Why it is the right tool:** Ticket 101 is a customer order for one specific size, and stock is keyed by SKU *and* size, so this tool confirms that `CC-TEE-WHITE` / S has 0 on hand (shortage 1) even though M, L and XL are in stock. That is the fact that turns the ticket from "hand it over" into a restock from Bulldog Print Co.

### `get_rent_status(lease_id)`
- **Reads:** `leases`, `desk`, `cash_accounts`
- **Unlocks:** Ticket **102** (Elm City Properties, rent notice, `lease_id` 1)
- **Why it is the right tool:** Ticket 102 only says "rent due in 2 days", so this tool checks that claim against the lease itself: $2,400 due 2026-09-02, 2 days after `desk.date_today` (not overdue), with $3,400 in checking to cover it. That gives Facilities and Accounting what they need to prepare the rent payment for approval.

### `quote_bulk_order(sku, qty, discount_pct)`
- **Reads:** `pricing`
- **Unlocks:** Ticket **103** (Yale AI Club, 20 × `CC-HOOD-NAVY`, bulk discount request)
- **Why it is the right tool:** Ticket 103 is a price-override request, so the Boss needs margins from real cost data. This tool prices the 20 hoodies at the $22 unit cost and $58 list price for any proposed discount (for example 15% → $49.30 each, $546 order margin) and flags the 62.1% break-even discount, so no counter-offer goes below cost.

## Agent Team

Built with PydanticAI in `backend/agents.py`. Shared data types are in `backend/models.py`, and the system prompts are in `backend/prompts/`. Every agent uses the one model defined in `backend/llm.py`: **`gpt-6-luna` through Portkey** with `PORTKEY_API_KEY`. There is no fallback model.

| Agent | Prompt | Job | Output type | MCP tools it can see |
|---|---|---|---|---|
| **Boss** | `boss.md` | Reads the ticket, decides which specialist goes first, passes facts between hand-offs, weighs cash across the whole board, makes the final call (discount size, partial fill, payment priority) and records it on the ticket. | `TicketDecision` | `get_ticket`, `list_open_tickets`, `get_cash_position`, `list_approvals`, `list_drafts`, `update_ticket` |
| **Inventory** | `inventory.md` | Checks stock by SKU **and** size, computes shortages, finds sizes on hand as alternatives, matches the product to a vendor by specialty, quotes lead time only from `vendors.lead_days`, and flags a vendor blocked by an open invoice. | `AgentReport` | `get_ticket`, `check_stock`, `list_inventory`, `list_vendors`, `get_vendor_status`, `save_draft` (vendor) |
| **Accounting** | `accounting.md` | Watches cash and invoices, prices margins and discounts, ranks spending when cash is tight, and queues invoice and rent payments and purchase orders **for human approval**. It never moves money. | `AgentReport` | `get_ticket`, `get_cash_position`, `list_invoices`, `get_vendor_status`, `quote_bulk_order`, `list_approvals`, `request_payment`, `create_purchase_order`, `save_draft` (vendor/landlord) |
| **Facilities** | `facilities.md` | Handles the lease, rent and the physical shop. It checks a rent notice against the lease, judges "overdue" against `desk.date_today`, and hands the payment to Accounting. | `AgentReport` | `get_ticket`, `get_rent_status`, `list_approvals`, `save_draft` (landlord) |
| **Customer Service** | `customer_service.md` | Writes customer replies from confirmed facts only, offers in-stock alternatives, and saves them as drafts. It never sends anything. | `AgentReport` | `get_ticket`, `check_stock`, `list_inventory`, `quote_bulk_order`, `list_drafts`, `save_draft` (customer) |

**Full connectivity.** Every agent has the same `delegate(to_agent, task)` tool and can hand work to any other agent. A delegation runs the other agent's own loop and returns its structured report to the caller. Example from a test run: Boss → Facilities → Accounting for the rent notice.

**Prompt revision during the full run.** In Problem 9, the second run of ticket 101 skipped the hand-off to Accounting and misread an executed approval. `boss.md` and `accounting.md` gained two clarifications:
1. When the vendor can ship, have Accounting order exactly the shortage.
2. `approved` with a `payment_id` means the money has moved.

The prompts are read when the backend starts, so the backend was restarted before run 3.

**Agent loop.** `run_agent()` drives each agent with `Agent.iter()`. Each model response is one step: the agent either calls tools (MCP or `delegate`) or returns its structured output. `run_ticket()` starts the Boss and keeps one MCP server process open for the whole ticket.

## All MCP Tools

Server: `mcp_server/server.py` (FastMCP). Every tool uses `data/campus_customs_new.db`. Lookup tools open it read-only, and write tools use one transaction each. The backend has **no database code**: every shop fact and action goes through this MCP connection (`backend/mcp_client.py`).

| Tool | Tables | Who can use it | What it does |
|---|---|---|---|
| `get_ticket` | `tickets`, `desk`, `approvals`, `drafts` | all agents | One ticket, the shop's today, and the approvals and drafts already linked to it. |
| `list_tickets` | `tickets`, `desk` | Dashboard API | Every ticket, open or resolved, with its status. |
| `list_open_tickets` | `tickets`, `desk` | Boss | Every ticket not yet resolved. |
| `check_stock` | `inventory` | Inventory, Customer Service | On hand, location and shortage for one SKU in one size. |
| `list_inventory` | `inventory` | Inventory, Customer Service | All sizes of a SKU, to find alternatives. |
| `list_vendors` | `vendors`, `invoices`, `desk` | Inventory | Every vendor's specialty, `lead_days`, open invoices and `can_ship`. |
| `get_vendor_status` | `vendors`, `invoices`, `desk` | Inventory, Accounting | One vendor's lead time, open invoices (with days overdue), `can_ship`, and arrival date if ordered today. |
| `list_invoices` | `invoices`, `vendors`, `desk` | Accounting | Invoices by status, with days overdue counted from `desk.date_today`. |
| `get_cash_position` | `cash_accounts`, `payments`, `approvals`, `desk` | Boss, Accounting | Cash on hand, payments made, requests waiting, and cash left if all are approved. |
| `get_rent_status` | `leases`, `desk`, `cash_accounts` | Facilities | Rent, due date, days until due, overdue or not, and whether cash covers it. |
| `quote_bulk_order` | `pricing` | Accounting, Customer Service | Revenue, cost and margin at list price and at a discount, plus the break-even discount. |
| `list_approvals` | `approvals` | Boss, Accounting, Facilities | The human approval queue. |
| `list_drafts` | `drafts` | Boss, Customer Service | Message drafts on the board. |
| `request_payment` | reads `invoices`/`leases`, `cash_accounts`, `approvals`; writes `approvals` | Accounting | Queues an invoice or rent payment for human approval. The amount comes from the database. Refused if the bill isn't payable or cash can't cover it. |
| `create_purchase_order` | reads `vendors`, `inventory`, `pricing`, `invoices`, `cash_accounts`; writes `approvals` | Accounting | Queues a restock order (qty × `unit_cost`) for approval. Refused if the vendor has an open invoice or cash can't cover it. |
| `save_draft` | writes `drafts` | Customer Service (customer), Inventory and Accounting (vendor), Facilities and Accounting (landlord) | Saves a message as a draft. Nothing is sent. |
| `update_ticket` | `tickets`, `desk` | Boss | Sets the status and appends a dated note. The original notes are kept. |
| `decide_payment` | `approvals`, `cash_accounts`, `payments`, `invoices`, `leases`, `vendors`, `desk` | **human only**, through `POST /api/approvals/{id}/approve` or `/reject` | Approves or rejects a queued request. On approval it re-checks the bill and cash, then in one transaction lowers the balance, adds a `payments` row, and marks the invoice `paid` or moves `leases.next_due` forward a month. Refuses if cash would go negative. |
| `reset_working_database` | copies `campus_customs.db` over `campus_customs_new.db`, then recreates `approvals` and `drafts` | **human only**, through `POST /api/reset` | Restores the working copy to the original values for a clean run. Needs `confirm=true`. |

**Board tables.** The MCP server adds two tables to the working copy: `approvals` (the human approval queue) and `drafts` (unsent messages). It recreates them on start-up if the working copy was reset from the original. The original database is never touched.

## Audit Trail

`output/audit_trail.json` is an append-only JSON array (`backend/audit.py`). Each entry is written as it happens and the file is never wiped. A corrupt file raises an error instead of being overwritten.

| Field | Meaning |
|---|---|
| `timestamp`, `run_id`, `ticket_id` | When it happened, which ticket run, which ticket. |
| `agent`, `depth`, `step` | Who acted, how many delegation hops from the Boss, and the running step number. |
| `event` | `ticket_start`, `agent_start`, `model_step`, `mcp_tool_call`, `delegation`, `agent_end`, `ticket_end`, `guardrail`, or `run_error`. People acting through the API produce `human_decision` and `reset` (agent = `human:<name>`). The desk's automatic close produces `ticket_resolved` (agent = `desk`; added after the full run). |
| `detail` | What the agent decided or said, or the brief it was given. |
| `delegated_to`, `tool`, `tool_args` | The hand-off target, or the MCP tool and the exact arguments sent. |
| `result` | A short version of the tool result or agent output, truncated to 400 characters. |
| `outcome` | `ok`, `refused`, `blocked`, `error`, or `limit`. |

## Safety Guardrails

The rules are enforced **in code at the MCP server**, not only in prompts, so a confused or manipulated model can't get around them.

**Money**
- **Human approval before any payment.** Agents can only *queue* requests. The one tool that moves money, `decide_payment`, is on no agent's allowlist, and the backend also blocks it by name if an agent somehow calls it. Its only caller is the API's approve route (and the reject route, which moves no money). That route requires an explicit `confirm: true` click and the approver's name. It refuses an approver named after an agent and requires a named human, whose name is stored in `payments.approved_by`.
- **No negative cash.** Requests that cash on hand can't cover are refused when queued, and `decide_payment` checks again at execution time, then refuses and leaves the balance unchanged.
- **Amounts come from the database.** Invoice and rent amounts are read from `invoices`/`leases`, and purchase-order cost is qty × `pricing.unit_cost`, so an agent can't type its own number.
- **Re-check when paying.** `decide_payment` re-validates when it executes. An invoice that is no longer open, or a vendor that has become blocked, is refused.
- **No duplicate requests.** A second identical pending request returns the existing approval id.
- **Atomic updates.** Each payment updates cash, `payments`, and the invoice or lease in a single transaction, or none of them.
- **Cash only goes out.** No tool adds money.

**Vendors and stock**
- **Blocked vendors.** A vendor with an open invoice can't receive a purchase order.
- **Real lead times.** Lead times and arrival dates come only from `vendors.lead_days`, counted from `desk.date_today`.

**Customers and outreach**
- **Nothing is sent.** No tool can email or contact anyone. Customer, vendor and landlord messages are saved as `drafts` with `status = 'draft'` for a human to review and send.
- **Right author for each audience.** Only Customer Service can write customer drafts, which keeps tone and confidentiality consistent. The prompt also forbids revealing invoices, payments, cash or margins to customers.

**Identity and access**
- **No spoofing.** The backend overwrites `requested_by`, `author` and `agent` with the calling agent's real name, so a model can't act under another agent's identity.
- **Least privilege.** Each agent sees only the MCP tools it needs. For example, Customer Service can't queue payments and Inventory can't change tickets.
- **One date.** "Today" is always `desk.date_today`, never the system clock.
- **Traceability.** Every agent step, delegation and tool call, with its arguments and result, is in the audit trail.

**What a real business would add:** spending thresholds that need a second approver, approver login and authentication, alerts on refused or blocked actions, and periodic review of the drafts and the audit trail.

## API Routes

FastAPI app in `backend/main.py`. Start it from inside `backend/` with `uvicorn main:app --reload --port 8000`, then open http://localhost:8000. Every route gets shop data through the MCP server; the API has no database code.

- `GET /` — Service name, model (`gpt-6-luna`) and the list of API routes.
- `GET /api/tickets` — All tickets, each with its status and `state` (`open` or `resolved`), and whether the team is working it now.
- `POST /api/run` `{"ticket_id": 101}` — Starts the multi-agent team on that ticket in the background. Returns `409` if a run is already going.
- `GET /api/run` — State of the current or last run: running or not, `run_id`, the Boss's final decision, each agent's report, usage, or the error.
- `GET /api/runs/{ticket_id}` — The latest run of one ticket since the API started, with every agent's structured report. Returns `null` if the ticket hasn't run. When a run finishes cleanly, the backend marks the ticket `resolved` through the MCP tool `update_ticket`; payments it prepared stay in the approval queue.
- `GET /api/events?after=N&ticket_id=&run_id=&limit=` — Audit-trail events with an index greater than `N`, for polling: what each agent said and did, delegations, and MCP tools with their arguments and results. Also returns `last_reset_index`, so the dashboard can hide runs from before the last reset.
- `GET /api/approvals?status=pending&ticket_id=` — The human approval queue of prepared payments and purchase orders.
- `POST /api/approvals/{id}/approve` `{"approved_by": "...", "confirm": true}` — **The only route that executes a prepared payment or purchase.** It calls `decide_payment`, which moves cash only if it covers the amount, and it logs a `human_decision` audit event.
- `POST /api/approvals/{id}/reject` `{"rejected_by": "..."}` — Rejects a prepared request. No money moves.
- `GET /api/cash` — Current checking balance from `cash_accounts`, plus pending total, balance after pending, and payments made.
- `GET /api/drafts?ticket_id=` — Customer, vendor and landlord drafts on the board. None are ever sent.
- `POST /api/reset` `{"confirm": true}` — Restores `data/campus_customs_new.db` from the untouched `data/campus_customs.db`. Returns `409` while a run is in progress.

## React Dashboard

`frontend/`: React 19 + Vite + TypeScript. Start it with `npm run dev` and open http://localhost:5173. It calls only the API routes above, through `src/api.ts`, with no hardcoded data. The design rationale is in `output/design.md`.

| Area | Shows | Routes |
|---|---|---|
| Scoreboard bar | Shop date (`desk.date_today`), approvals waiting, team LED (Live/Ready/Offline), **checking balance**, pending total, balance after pending, two-click **Reset DB** | `/api/tickets`, `/api/cash`, `/api/approvals`, `/api/run`, `POST /api/reset` |
| Ticket board | All tickets as Open, Being worked or Resolved, plus a saffron "approval waiting on you" ribbon, and **Run the team** on the selected ticket | `/api/tickets`, `POST /api/run` |
| Roster | Five agent cards, each with a colour, shape and jersey number, showing live status, tool and delegation counts, and benched agents dimmed | `/api/events` |
| Play-by-play | The latest run's timeline, indented by delegation depth: passes, MCP tool chips with arguments, outcomes, the agents' own words, the final whistle, human calls. Compact or full trace. | `/api/events?ticket_id=&after=` |
| Your call | Approval cards with amount, reason, preparing agent, and cash now → after. **Approve → Confirm** needs the approver's name. Reject is also available. | `/api/approvals`, `POST /api/approvals/{id}/approve`, `/reject` |
| Box score | Boss's final call (decision, rationale, open items), each specialist's summary and tools, usage, unsent drafts | `/api/runs/{ticket_id}`, `/api/drafts` |

**Polling.** The board, cash and run state refresh every 1.5 s during a run and every 4 s otherwise. The selected ticket's events refresh every 1 s while it is live. After an approval, cash is re-read right away and the scoreboard counts down to the new balance.

## Human Approval Flow (end to end)

1. An agent (Accounting) calls `request_payment` or `create_purchase_order`. The MCP server checks the bill or vendor and the cash, then adds a `pending` row to `approvals`. **No money moves.**
2. The dashboard shows the request in **Your call** and puts the saffron ribbon on its ticket.
3. A person enters their name and clicks **Approve**, then **Confirm: pay $X** within 6 seconds.
4. `POST /api/approvals/{id}/approve` with `confirm: true` calls the MCP tool `decide_payment`. This is its only caller apart from reject.
5. `decide_payment` re-checks the request and the cash. In one transaction it lowers `cash_accounts.balance`, adds a `payments` row with `approved_by`, and marks the invoice `paid` or moves `leases.next_due` forward. It refuses if cash would go negative.
6. The API logs a `human_decision` audit entry. The dashboard re-reads `/api/cash` and the scoreboard counts down.

## Problem 9 Full Run (summary)

The run was done through the dashboard after a reset. All details are in `output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_tickets.json` and `output/resolved_board.html`.

| Ticket | Agent runs | Human approvals | Cash | Final status |
|---|---|---|---|---|
| 101 | 3 (Boss → Inventory → Accounting → Customer Service) | #1 invoice 501 $840.00 · #2 tee PO $8.00 | −$848.00 | resolved |
| 102 | 1 (Boss → Facilities → Accounting) | #3 rent $2,400.00 | −$2,400.00 | resolved |
| 103 | 1 (Boss → Inventory, Accounting, Customer Service) | none (restock unaffordable) | $0.00 | resolved |

Starting balance **$3,400.00** → ending balance **$152.00**. The ending balance equals `cash_accounts` in `data/campus_customs_new.db`.

## Implementation Constraints and Known Limits

- **One model.** `gpt-6-luna` through Portkey is defined only in `backend/llm.py`, with no fallback model. `PORTKEY_API_KEY` is loaded from `.env` (the project folder, then the course folder) and is never printed or committed (`.gitignore`).
- **Portkey response caching.** The Portkey account has caching on. A run whose inputs match an earlier run gets the earlier model replies back. Run 1 of ticket 101 is an example: it took 11 s and matched a pre-reset test. Its MCP tool calls still ran live against the database.
- **One run at a time.** The API refuses a second run, an approval or a reset while a ticket is being worked. This keeps cash checks and the audit order consistent.
- **Run state is in memory.** `GET /api/run` and `/api/runs/{id}` are lost when the API restarts. The dashboard then rebuilds summaries from `agent_end` lines in the audit trail. Restarting `uvicorn --reload` (for example, by editing a `.py` file) **during a run kills that run**.
- **Prompts load at startup.** Agents are built once per process, so edits to `backend/prompts/*.md` take effect after restarting the backend.
- **The approver's name is not authentication.** The dashboard records the approver's typed name in `payments.approved_by` and the audit trail. A real business would add login and role checks; see Safety Guardrails.
- **No inventory movement.** Purchase orders pay the vendor and record an expected arrival date (`today + lead_days`). Stock is not added until goods arrive, which is outside this model, so `inventory` doesn't change in this homework.
- **Shop date is fixed.** Everything uses `desk.date_today` (2026-08-31). Real timestamps (UTC) appear only in audit entries and in `created_at`/`decided_at` fields.
- **Windows stdio.** The backend starts the MCP server with the same Python interpreter (`sys.executable`), so the project `.venv` must be the one running `uvicorn`.

## Output Files

| File | Problem | Contents |
|---|---|---|
| `AI_prompts.md` | 1 | Every prompt, problem by problem |
| `output/harness.md` | 2–9 | This document |
| `output/mcp_smoke.json` | 4 | Real Claude Code calls of the first three MCP tools, verified against the database |
| `output/audit_trail.json` | 5–9 | Append-only agent and human activity |
| `output/desk_tickets.html` | 6, 9 | Expected vs Actual for each ticket, plus the Cash ledger |
| `output/design.md` | 8 | Dashboard design rationale |
| `output/resolved_tickets.json` | 9 | Final outcome, agent contributions and approvals per ticket |
| `output/resolved_board.html` | 9 | Three real screenshots of the resolved React board |

## Limits on Tokens and Runaway Loops

Set in `backend/agents.py`. They apply **per ticket**, because every agent loop on a ticket shares one usage counter.

| Limit | Value | Why |
|---|---|---|
| Model requests per ticket | 40 | A full discount ticket used 28 in testing, so 40 leaves headroom while capping cost. |
| Tool calls per ticket (MCP + delegate) | 60 | Stops tool-call loops. |
| Total tokens per ticket | 250,000 | A hard spend cap. The test runs used about 45k–78k tokens per ticket. |
| Output tokens per model response | 4,000 | Stops runaway long responses. |
| Delegation depth | 2 (Boss → A → B) | Keeps chains short. |
| Delegations per ticket | 8 | Caps total hand-offs. |
| No delegating back up the chain | — | An agent can't delegate to anyone already waiting on it, which stops A → B → A ping-pong. |
| No self-delegation | — | Prevents trivial loops. |
| Delegation brief length | 2,000 characters | Keeps prompts small. |
| Tool retries | 1 per MCP tool, 2 per agent output | Bad arguments can't cause endless retries. |
| Parallel tool calls | off | One action at a time keeps the audit trail ordered and stops fan-out. |
| Audit result size | 400 characters per entry | Keeps the trail readable. |

When a limit is hit, the run stops cleanly. A `guardrail` entry is logged with `outcome = "limit"`, and the ticket is returned as `blocked` for a human to review. In an early test, ticket 103 hit the 40-request cap because agents kept re-confirming each other's facts. That led to the "no delegating back up the chain" rule and the "don't re-verify facts from your brief" instruction. After the fix the same ticket finished in 28 requests.
