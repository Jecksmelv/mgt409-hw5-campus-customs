"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

Full connectivity: every agent has the same `delegate` tool and can hand work to
any other agent. Each agent loop runs through `run_agent`, which logs every model
step to output/audit_trail.json; MCP tool calls are logged in mcp_client.py.

Run one ticket from the command line (from the hw5 folder):
    .venv\\Scripts\\python -m backend.agents 101
"""

import asyncio
import os
import sys
import uuid
from functools import lru_cache

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import Agent, RunContext  # noqa: E402
from pydantic_ai.exceptions import UsageLimitExceeded  # noqa: E402
from pydantic_ai.messages import TextPart, ToolCallPart  # noqa: E402
from pydantic_ai.settings import ModelSettings  # noqa: E402
from pydantic_ai.usage import RunUsage, UsageLimits  # noqa: E402

from . import audit  # noqa: E402
from .llm import MODEL_NAME, PROJECT_DIR, get_model  # noqa: E402
from .mcp_client import shop_mcp, toolset_for  # noqa: E402
from .models import (  # noqa: E402
    AGENT_NAMES,
    AgentName,
    AgentReport,
    DelegationResult,
    RunCounters,
    TeamDeps,
    TicketDecision,
)

PROMPTS_DIR = PROJECT_DIR / "backend" / "prompts"

# ---------------------------------------------------------------------------
# Limits that cap token use and stop runaway loops. All apply per ticket run,
# because every agent loop on a ticket shares one RunUsage.
# ---------------------------------------------------------------------------
MAX_DELEGATION_DEPTH = 2            # Boss -> A -> B, no deeper
MAX_DELEGATIONS_PER_TICKET = 8      # total hand-offs across all agents
MAX_MODEL_REQUESTS_PER_TICKET = 40  # model calls across all agent loops
MAX_TOOL_CALLS_PER_TICKET = 60      # MCP + delegate calls across all agent loops
MAX_TOTAL_TOKENS_PER_TICKET = 250_000
MAX_OUTPUT_TOKENS_PER_RESPONSE = 4_000
MAX_TASK_CHARS = 2_000              # longest delegation brief accepted

MODEL_SETTINGS = ModelSettings(max_tokens=MAX_OUTPUT_TOKENS_PER_RESPONSE, parallel_tool_calls=False)


def ticket_limits() -> UsageLimits:
    return UsageLimits(
        request_limit=MAX_MODEL_REQUESTS_PER_TICKET,
        tool_calls_limit=MAX_TOOL_CALLS_PER_TICKET,
        total_tokens_limit=MAX_TOTAL_TOKENS_PER_TICKET,
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def load_prompt(agent: AgentName) -> str:
    return (PROMPTS_DIR / f"{agent}.md").read_text(encoding="utf-8")


def runtime_context(ctx: RunContext[TeamDeps]) -> str:
    d = ctx.deps
    others = [a for a in AGENT_NAMES if a != d.agent and a not in d.chain]
    chain = " -> ".join(d.chain + [d.agent])
    remaining = MAX_DELEGATIONS_PER_TICKET - d.counters.delegations
    can_delegate = d.depth < MAX_DELEGATION_DEPTH and remaining > 0
    return (
        f"## Run context\n"
        f"- You are: {d.agent}\n"
        f"- Ticket: {d.ticket_id}\n"
        f"- Delegation chain so far: {chain}\n"
        f"- You may delegate to: {', '.join(others) if can_delegate else 'nobody (limit reached), finish with what you have'}\n"
        f"- Delegations left for this ticket: {max(remaining, 0)}\n"
        f"- Get every shop fact from an MCP tool. Never guess a number, date, stock level or lead time.\n"
        f"- Facts in your brief that came from an MCP tool earlier in this run are already verified. Don't "
        f"re-check them; call tools only for facts you don't have yet. Delegate only for new work outside your "
        f"role, never just to have a fact confirmed again."
    )


# ---------------------------------------------------------------------------
# Delegation (full connectivity)
# ---------------------------------------------------------------------------

async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> DelegationResult:
    """Hand part of this ticket to another agent and wait for its report.

    Args:
        to_agent: The agent to delegate to: boss, inventory, accounting, facilities or customer_service.
        task: A specific brief: what you need, the facts you already have (with numbers), and what to return.
    """
    d = ctx.deps
    refusal = None
    if to_agent == d.agent:
        refusal = "You cannot delegate to yourself."
    elif to_agent in d.chain:
        refusal = (f"{to_agent} is already waiting on you in this chain ({' -> '.join(d.chain + [d.agent])}). "
                   f"Return your report instead of delegating back.")
    elif d.depth + 1 > MAX_DELEGATION_DEPTH:
        refusal = f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. Finish with what you have."
    elif d.counters.delegations >= MAX_DELEGATIONS_PER_TICKET:
        refusal = f"Delegation limit for this ticket ({MAX_DELEGATIONS_PER_TICKET}) reached. Finish with what you have."
    elif len(task) > MAX_TASK_CHARS:
        refusal = f"Task brief is longer than {MAX_TASK_CHARS} characters. Shorten it."
    if refusal:
        audit.record(d, "guardrail", f"Delegation to {to_agent} refused: {refusal}",
                     delegated_to=to_agent, outcome="limit")
        return DelegationResult(to_agent=to_agent, ok=False, error=refusal)

    d.counters.delegations += 1
    audit.record(d, "delegation", task, delegated_to=to_agent)
    child = TeamDeps(
        run_id=d.run_id,
        ticket_id=d.ticket_id,
        agent=to_agent,
        depth=d.depth + 1,
        chain=d.chain + [d.agent],
        counters=d.counters,
    )
    report = await run_agent(to_agent, task, child, usage=ctx.usage)
    return DelegationResult(to_agent=to_agent, ok=True, report=report)


# ---------------------------------------------------------------------------
# The five agents
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def build_agent(name: AgentName) -> Agent[TeamDeps, AgentReport | TicketDecision]:
    return Agent(
        get_model(),
        name=name,
        deps_type=TeamDeps,
        output_type=TicketDecision if name == "boss" else AgentReport,
        instructions=[load_prompt(name), runtime_context],
        toolsets=[toolset_for(name)],
        tools=[delegate],
        model_settings=MODEL_SETTINGS,
        retries=2,
    )


async def run_agent(name: AgentName, task: str, deps: TeamDeps, usage: RunUsage) -> AgentReport | TicketDecision:
    """Run one agent loop, logging each model step. Usage is shared across the whole ticket."""
    agent = build_agent(name)
    audit.record(deps, "agent_start", task)
    async with agent.iter(task, deps=deps, usage=usage, usage_limits=ticket_limits()) as run:
        async for node in run:
            if Agent.is_call_tools_node(node):
                said = " ".join(p.content for p in node.model_response.parts if isinstance(p, TextPart)).strip()
                calls = [p.tool_name for p in node.model_response.parts if isinstance(p, ToolCallPart)]
                detail = said or (f"Chose to call: {', '.join(calls)}" if calls else "(no text)")
                audit.record(deps, "model_step", detail, result=f"tool calls: {calls}" if calls else None)
    output = run.result.output
    said = output.decision if isinstance(output, TicketDecision) else output.summary
    audit.record(deps, "agent_end", said, result=audit.short(output.model_dump(), audit.MAX_DETAIL_CHARS))
    deps.counters.reports.append({"agent": name, "depth": deps.depth, "output": output.model_dump()})
    return output


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_ticket(ticket_id: int, run_id: str | None = None,
                     counters: RunCounters | None = None) -> TicketDecision:
    """Have the Boss work one ticket end to end. Returns the Boss's final call.

    Pass your own RunCounters to watch agent reports and usage while the run is going.
    """
    deps = TeamDeps(run_id=run_id or new_run_id(), ticket_id=ticket_id, agent="boss",
                    counters=counters or RunCounters())
    audit.record(deps, "ticket_start", f"Team picks up ticket {ticket_id} (model {MODEL_NAME}).")
    task = (
        f"Work ticket {ticket_id}. Read it with get_ticket, decide which agents need to act and in what order, "
        f"delegate, then make the final call and record it on the ticket with update_ticket."
    )
    usage = RunUsage()
    try:
        async with shop_mcp:  # one MCP server process for the whole ticket
            decision = await run_agent("boss", task, deps, usage)
    except UsageLimitExceeded as exc:
        deps.counters.limit_hit = True
        audit.record(deps, "guardrail", f"Ticket run stopped by usage limit: {exc}", outcome="limit")
        decision = TicketDecision(
            ticket_id=ticket_id, final_status="blocked",
            decision="Stopped: the agent loop hit its usage limit before finishing.",
            rationale=str(exc), open_items=["A human should review this ticket and the audit trail."],
        )
    deps.counters.usage = {"requests": usage.requests, "tool_calls": usage.tool_calls,
                           "total_tokens": usage.total_tokens}
    audit.record(deps, "ticket_end", decision.decision,
                 result=f"status={decision.final_status}; requests={usage.requests}; "
                        f"tool_calls={usage.tool_calls}; tokens={usage.total_tokens}")
    return decision


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit("Usage: python -m backend.agents <ticket_id>")
    result = asyncio.run(run_ticket(int(sys.argv[1])))
    print(result.model_dump_json(indent=2))
