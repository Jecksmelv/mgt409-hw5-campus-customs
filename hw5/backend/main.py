"""FastAPI backend for the Campus Customs dashboard.

Start it from inside backend/ (with the project .venv active):
    uvicorn main:app --reload --port 8000

Every shop fact and shop action goes through the Campus Customs MCP server:
the agents use their own MCP connection (backend/mcp_client.py) and this API
uses a DashboardMCP connection. Nothing here opens the database.

The approval route is the only code path that executes a payment or purchase:
it is the only caller of the human-only MCP tool decide_payment.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# Allow `uvicorn main:app` from inside backend/ as well as `backend.main:app` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import audit  # noqa: E402
from backend.agents import new_run_id, run_ticket  # noqa: E402
from backend.llm import MODEL_NAME  # noqa: E402
from backend.mcp_client import DashboardMCP, ShopToolError  # noqa: E402
from backend.models import RunCounters, TicketDecision  # noqa: E402

shop = DashboardMCP()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await shop.start()
    try:
        yield
    finally:
        await shop.stop()


app = FastAPI(title="Campus Customs Operations API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Run state: one ticket run at a time, so cash checks and the audit trail stay in order.
# ---------------------------------------------------------------------------

class RunState(BaseModel):
    running: bool = False
    ticket_id: int | None = None
    run_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    decision: TicketDecision | None = None
    reports: list[dict[str, Any]] = Field(default_factory=list, description="Each agent's structured output.")
    usage: dict[str, int] = Field(default_factory=dict)
    marked_resolved: bool = False
    error: str | None = None


current_run = RunState()
runs_by_ticket: dict[int, RunState] = {}  # latest run per ticket, kept in memory for the dashboard
_run_task: asyncio.Task | None = None
_counters: RunCounters | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _run_in_background(state: RunState, counters: RunCounters) -> None:
    try:
        state.decision = await run_ticket(state.ticket_id, run_id=state.run_id, counters=counters)
        if not counters.limit_hit:
            # The team has finished its work on the ticket, so the desk marks it resolved.
            # Payments the team prepared stay in the approval queue until a human decides.
            d = state.decision
            note = (f"Agent run {state.run_id} finished. Boss's final call ({d.final_status}): {d.decision}"
                    + (f" Pending human approval: {d.approval_ids}." if d.approval_ids else ""))
            args = {"ticket_id": state.ticket_id, "status": "resolved", "note": note, "agent": "boss"}
            result = await shop.call("update_ticket", args)
            state.marked_resolved = True
            audit.record_desk(state.run_id, state.ticket_id, "ticket_resolved",
                              f"Run finished cleanly; ticket {state.ticket_id} marked resolved.",
                              tool="update_ticket", tool_args=args, result=audit.short(result))
    except Exception as exc:  # network, model or MCP failure: record it, don't crash the API
        state.error = f"{type(exc).__name__}: {exc}"
        audit.record_human("system", "run_error",
                           f"Run {state.run_id} on ticket {state.ticket_id} failed: {state.error}",
                           ticket_id=state.ticket_id, outcome="error")
    finally:
        state.reports = list(counters.reports)
        state.usage = dict(counters.usage)
        state.running = False
        state.finished_at = _now()


async def _shop(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return await shop.call(name, args)
    except ShopToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _require_idle(action: str) -> None:
    if current_run.running:
        raise HTTPException(status_code=409,
                            detail=f"Cannot {action} while ticket {current_run.ticket_id} is being worked.")


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    ticket_id: int


class ApproveRequest(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the person approving.")
    confirm: bool = Field(description="Must be true: the person explicitly clicked Approve.")
    note: str = ""


class RejectRequest(BaseModel):
    rejected_by: str = Field(min_length=1)
    note: str = ""


class ResetRequest(BaseModel):
    confirm: bool = Field(description="Must be true to reset the working database.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "Campus Customs Operations API",
        "model": MODEL_NAME,
        "routes": [f"{', '.join(sorted(r.methods - {'HEAD'}))} {r.path}" for r in app.routes
                   if getattr(r, "methods", None) and r.path.startswith("/api")],
    }


@app.get("/api/tickets")
async def get_tickets() -> dict[str, Any]:
    data = await _shop("list_tickets")
    for t in data["tickets"]:
        t["state"] = "resolved" if t["status"] == "resolved" else "open"
        t["being_worked"] = current_run.running and current_run.ticket_id == t["id"]
    return data


@app.post("/api/run", status_code=202)
async def start_run(body: RunRequest) -> RunState:
    global _run_task, current_run, _counters
    _require_idle("start another run")
    ticket = await _shop("get_ticket", {"ticket_id": body.ticket_id})
    if not ticket.get("found"):
        raise HTTPException(status_code=404, detail=f"No ticket {body.ticket_id}.")
    run_id = new_run_id()
    current_run = RunState(running=True, ticket_id=body.ticket_id, run_id=run_id, started_at=_now())
    runs_by_ticket[body.ticket_id] = current_run
    _counters = RunCounters()
    _run_task = asyncio.create_task(_run_in_background(current_run, _counters))
    return current_run


def _live(state: RunState) -> RunState:
    """While a run is going, include the agent reports collected so far."""
    if state.running and _counters is not None and state is current_run:
        return state.model_copy(update={"reports": list(_counters.reports)})
    return state


@app.get("/api/run")
async def get_run() -> RunState:
    return _live(current_run)


@app.get("/api/runs/{ticket_id}")
async def get_ticket_run(ticket_id: int) -> RunState | None:
    """Latest run of one ticket since the API started (null if none), with each agent's report."""
    state = runs_by_ticket.get(ticket_id)
    return _live(state) if state else None


@app.get("/api/events")
async def get_events(
    after: int = Query(-1, description="Return events with index greater than this (for polling)."),
    ticket_id: int | None = None,
    run_id: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    entries = audit.read_entries()
    events = [
        {"index": i, **e} for i, e in enumerate(entries)
        if i > after
        and (ticket_id is None or e.get("ticket_id") == ticket_id)
        and (run_id is None or e.get("run_id") == run_id)
    ]
    events = events[-limit:]
    resets = [i for i, e in enumerate(entries) if e.get("event") == "reset"]
    return {"events": events, "last_index": len(entries) - 1, "running": current_run.running,
            "last_reset_index": resets[-1] if resets else -1}


@app.get("/api/approvals")
async def get_approvals(
    status: Literal["pending", "approved", "rejected", "refused", "all"] = "pending",
    ticket_id: int | None = None,
) -> dict[str, Any]:
    return await _shop("list_approvals", {"status": status, "ticket_id": ticket_id})


async def _find_approval(approval_id: int) -> dict[str, Any]:
    queue = await _shop("list_approvals", {"status": "all"})
    for a in queue["approvals"]:
        if a["id"] == approval_id:
            return a
    raise HTTPException(status_code=404, detail=f"No approval {approval_id}.")


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: ApproveRequest) -> dict[str, Any]:
    """The only route that executes a prepared payment or purchase order."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Approval needs confirm=true from an explicit human click.")
    _require_idle("approve a payment")
    approval = await _find_approval(approval_id)
    args = {"approval_id": approval_id, "decision": "approve", "decided_by": body.approved_by, "note": body.note}
    result = await _shop("decide_payment", args)
    outcome = "ok" if result.get("ok") else "refused" if result.get("refused") else "error"
    what = f"{approval['kind']} request #{approval_id} for ${approval['amount']:,.2f}"
    said = (f"Approved and paid {what}." if result.get("ok")
            else f"Clicked Approve on {what}, but it was not paid: {result.get('error')}")
    audit.record_human(body.approved_by, "human_decision", said,
                       ticket_id=approval["ticket_id"], tool="decide_payment", tool_args=args,
                       result=audit.short(result), outcome=outcome)
    if not result.get("ok"):
        raise HTTPException(status_code=409 if result.get("refused") else 400, detail=result)
    return result


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: RejectRequest) -> dict[str, Any]:
    approval = await _find_approval(approval_id)
    args = {"approval_id": approval_id, "decision": "reject", "decided_by": body.rejected_by, "note": body.note}
    result = await _shop("decide_payment", args)
    what = f"{approval['kind']} request #{approval_id} for ${approval['amount']:,.2f}"
    said = f"Rejected {what}." if result.get("ok") else f"Tried to reject {what}: {result.get('error')}"
    audit.record_human(body.rejected_by, "human_decision", said,
                       ticket_id=approval["ticket_id"], tool="decide_payment", tool_args=args,
                       result=audit.short(result), outcome="ok" if result.get("ok") else "error")
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@app.get("/api/cash")
async def get_cash() -> dict[str, Any]:
    data = await _shop("get_cash_position")
    checking = next((a for a in data["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=502, detail="No checking account in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "shop_today": data["shop_today"],
        "pending_total": data["pending_total"],
        "balance_after_pending": data["cash_after_all_pending"],
        "payments_made": data["payments_made"],
    }


@app.get("/api/drafts")
async def get_drafts(ticket_id: int | None = None) -> dict[str, Any]:
    return await _shop("list_drafts", {"ticket_id": ticket_id})


@app.post("/api/reset")
async def reset(body: ResetRequest) -> dict[str, Any]:
    global current_run
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Reset needs confirm=true.")
    _require_idle("reset the database")
    result = await _shop("reset_working_database", {"confirm": True})
    audit.record_human("operator", "reset", "Working database restored from data/campus_customs.db.",
                       tool="reset_working_database", result=audit.short(result),
                       outcome="ok" if result.get("ok") else "error")
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result)
    current_run = RunState()
    runs_by_ticket.clear()
    return result
