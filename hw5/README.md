# Campus Customs — Multi-Agent Operations (MGT 409 · Assignment 5)

An agentic operations desk for **Campus Customs**, a small Yale merch shop. Open tickets (customer orders, rent, unpaid bills, discount requests) are worked by a five-agent team. A human watches the agents in a React dashboard and approves every payment before any money moves.

| Piece | Where | What it does |
|---|---|---|
| MCP server | `mcp_server/server.py` | FastMCP server. It is the only code that reads or writes the shop database, and the shop rules are enforced here. |
| Agent team + API | `backend/` | Five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service) with full delegation, plus a FastAPI backend. |
| Dashboard | `frontend/` | React + Vite + TypeScript operations desk: ticket board, live play-by-play, approvals, cash scoreboard. |
| Database | `data/` | `campus_customs.db` is the original and is never modified. `campus_customs_new.db` is the working copy everything runs on. |

Every AI call uses **`gpt-6-luna`** through **Portkey** with `PORTKEY_API_KEY`. No other model is configured anywhere.

The full design and safety write-up is in [`output/harness.md`](output/harness.md). The dashboard design is explained in [`output/design.md`](output/design.md).

---

## 1. Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- A Portkey API key with access to `gpt-6-luna`

## 2. One-time setup

All commands run from this `hw5/` folder unless noted. Windows commands are shown first; on macOS or Linux, replace `.venv\Scripts\python` with `.venv/bin/python`.

```bash
# Python environment for the MCP server and the backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# Your Portkey key: copy the template, then edit .env and paste your key
copy .env.example .env          # macOS/Linux: cp .env.example .env

# Dashboard dependencies
cd frontend
npm install
cd ..
```

`.env` is gitignored. Never commit it.

## 3. Reset the working database (clean run)

Everything runs on `data/campus_customs_new.db`. To start from the original shop data, copy the untouched original over the working copy. There are three ways to do it:

**a. From the dashboard (easiest):** click **Reset DB** at the top right, then click again to confirm.

**b. Through the API** while the backend is running:

```bash
curl -X POST http://localhost:8000/api/reset -H "Content-Type: application/json" -d "{\"confirm\": true}"
```

**c. By hand**, with the backend stopped:

```bash
copy data\campus_customs.db data\campus_customs_new.db     # macOS/Linux: cp data/campus_customs.db data/campus_customs_new.db
```

Options a and b call the MCP tool `reset_working_database`. All three restore the original values. The MCP server re-adds its two board tables (`approvals`, `drafts`) on its next start.

> The committed `campus_customs_new.db` holds the **results of the graded full run**: three tickets resolved, $3,400.00 → $152.00. **Reset it before doing your own full three-ticket run.**

## 4. Start the MCP server

You normally don't need to start it yourself. **The backend launches it automatically** over stdio, using the same Python as the backend.

To run it on its own (for example, to test the tools):

```bash
.venv\Scripts\python mcp_server\server.py
```

To use it from **Claude Code**, open Claude Code in this `hw5/` folder and approve the `campus-customs` server from [`.mcp.json`](.mcp.json). On macOS or Linux, change `"command"` in `.mcp.json` to `.venv/bin/python`.

See [`mcp_server/README.md`](mcp_server/README.md) for the 19 tools.

## 5. Start the FastAPI backend

```bash
cd backend
..\.venv\Scripts\python -m uvicorn main:app --reload --port 8000
```

With `.venv` activated, `uvicorn main:app --reload --port 8000` works too. The API is at **http://localhost:8000**; open it to see the route list. CORS allows the Vite dev server at `http://localhost:5173`.

## 6. Start the React dashboard

In a second terminal:

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**.

## 7. Doing a full three-ticket run

1. Start the backend (step 5) and the dashboard (step 6).
2. **Reset the database first** (step 3, the **Reset DB** button), so the run starts from the original values: checking $3,400.00 and tickets 101, 102 and 103 open.
3. Type your name in **Approving as** (right column).
4. Select **#101** on the ticket board and click **Run the team**. Watch the roster and the play-by-play as the agents delegate and call MCP tools.
5. When the run finishes, the ticket shows **Resolved**. Any payment or purchase order the agents prepared appears under **Your call**. Click **Approve**, then **Confirm: pay $X**, to execute it. The cash scoreboard drops by that amount. Nothing is paid without that click.
6. Repeat for **#102** and **#103**. Running a ticket again (**Run the team again**) lets the agents act on what changed. For example, once an overdue vendor invoice is paid, they can place the restock order.

Every step is appended to `output/audit_trail.json`.

## Shop rules (enforced in code)

- **Today is `desk.date_today`**, never the computer's clock.
- **Lead times come only from the `vendors` table.**
- **A vendor with an open invoice cannot be sent a purchase order.**
- **Agents can only request payments.** Money moves only through the human approve route (`POST /api/approvals/{id}/approve`), which calls the human-only MCP tool `decide_payment`.
- **The pay tool refuses any payment that cash can't cover.** The balance can never go negative.
- **Cash only goes out.** There is no revenue model.
- **Customer, vendor and landlord messages are drafts only.** Nothing is ever sent.

## Repository layout

```
hw5/
├── AI_prompts.md            prompts used with the AI coding assistant, problem by problem
├── requirements.txt         Python dependencies (MCP server + backend)
├── .env.example             environment variable template (no secrets)
├── .mcp.json                Claude Code connection to the MCP server
├── data/                    original + working SQLite databases
├── mcp_server/              FastMCP server (server.py) + README
├── backend/                 main.py (FastAPI), agents.py, mcp_client.py, models.py, audit.py, llm.py, prompts/
├── frontend/                React + Vite + TypeScript dashboard
└── output/                  harness, smoke test, desk tickets, design, resolved outputs, audit trail, GitHub URL
```

## Outputs

| File | Contents |
|---|---|
| `output/harness.md` | Full system documentation: tables, tools, agents, routes, dashboard, safety, limits |
| `output/mcp_smoke.json` | Real Claude Code calls of the first three MCP tools, checked against the database |
| `output/desk_tickets.html` | Expected vs actual for each ticket, cash ledger, reflection (opens directly in a browser) |
| `output/design.md` | Dashboard design choices |
| `output/resolved_tickets.json` | Final status, outcome, agent contributions and approvals per ticket |
| `output/resolved_board.html` | Real screenshots of the resolved dashboard |
| `output/audit_trail.json` | Append-only log of every agent step, MCP call, delegation and human decision |
| `output/github_url.txt` | This repository's URL |
