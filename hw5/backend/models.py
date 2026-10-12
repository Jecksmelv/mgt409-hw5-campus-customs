"""Shared structured types for the Campus Customs agent team."""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

TicketStatus = Literal["open", "in_progress", "waiting_approval", "blocked", "resolved"]

AuditEvent = Literal[
    "ticket_start",      # the team picks up a ticket
    "agent_start",       # one agent loop begins
    "model_step",        # one model response inside an agent loop
    "mcp_tool_call",     # an MCP tool call and its result
    "delegation",        # one agent hands work to another
    "agent_end",         # one agent loop ends with its structured output
    "ticket_end",        # the Boss's final call on the ticket
    "guardrail",         # a limit or safety rule stopped something
    "run_error",         # a ticket run crashed (network, model or server error)
    "human_decision",    # a person approved or rejected a payment through the API
    "reset",             # a person reset the working database through the API
    "ticket_resolved",   # the desk marked a ticket resolved after a clean agent run
]
AuditOutcome = Literal["ok", "refused", "blocked", "error", "limit"]


class AgentReport(BaseModel):
    """What a specialist agent hands back after working on its part of a ticket."""

    agent: AgentName
    ticket_id: int
    summary: str = Field(description="One or two sentences on what you found and did.")
    facts: list[str] = Field(default_factory=list, description="Shop facts you relied on, each from an MCP tool result.")
    actions_taken: list[str] = Field(default_factory=list, description="MCP actions you performed (requests, drafts, ticket updates).")
    approval_ids: list[int] = Field(default_factory=list, description="Approval-queue ids you created. Empty if none.")
    draft_ids: list[int] = Field(default_factory=list, description="Draft ids you saved. Empty if none.")
    blockers: list[str] = Field(default_factory=list, description="Anything stopping progress, such as an open vendor invoice.")
    needs_human: bool = Field(description="True if a human must approve or decide something before this can move forward.")
    recommendation: str = Field(description="What you recommend should happen next.")


class TicketDecision(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int
    final_status: TicketStatus
    decision: str = Field(description="The final call, in plain language.")
    rationale: str = Field(description="Why, citing the facts the team found.")
    agents_consulted: list[AgentName] = Field(default_factory=list)
    approval_ids: list[int] = Field(default_factory=list, description="Approval-queue ids waiting on a human.")
    draft_ids: list[int] = Field(default_factory=list, description="Drafts on the board for a human to review.")
    open_items: list[str] = Field(default_factory=list, description="What still has to happen before the ticket is fully closed.")


class DelegationResult(BaseModel):
    """What the delegate tool returns to the agent that delegated."""

    to_agent: AgentName
    ok: bool
    report: AgentReport | TicketDecision | None = Field(
        default=None, description="A specialist's AgentReport, or a TicketDecision if the Boss was asked.")
    error: str | None = None


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json."""

    timestamp: str
    run_id: str
    ticket_id: int | None
    agent: str
    depth: int = Field(description="0 for the Boss's own loop, +1 for each delegation hop.")
    step: int = Field(description="Running step number within the ticket run.")
    event: AuditEvent
    detail: str = Field(description="What the agent decided, said, or was asked to do.")
    delegated_to: str | None = None
    tool: str | None = None
    tool_args: dict[str, Any] | None = None
    result: str | None = Field(default=None, description="Short version of the result.")
    outcome: AuditOutcome = "ok"


@dataclass
class RunCounters:
    """Mutable counters shared by every agent loop working on the same ticket."""

    step: int = 0
    delegations: int = 0
    reports: list[dict[str, Any]] = field(default_factory=list)  # every agent's structured output, in order
    limit_hit: bool = False
    usage: dict[str, int] = field(default_factory=dict)

    def next_step(self) -> int:
        self.step += 1
        return self.step


@dataclass
class TeamDeps:
    """Dependencies passed into each agent loop (PydanticAI deps)."""

    run_id: str
    ticket_id: int
    agent: AgentName
    depth: int = 0
    chain: list[AgentName] = field(default_factory=list)
    counters: RunCounters = field(default_factory=RunCounters)
