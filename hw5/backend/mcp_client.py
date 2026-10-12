"""Connection from the agent team to the Campus Customs MCP server.

All shop facts and shop actions come through this one MCP connection to
mcp_server/server.py (which uses data/campus_customs_new.db). The backend has
no database code of its own.

Each agent sees only the MCP tools on its allowlist. Every call is audited, and
identity arguments (requested_by / author / agent) are filled in from the real
calling agent so a model cannot act under another agent's name.
"""

import asyncio
import sys
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset
from pydantic_ai.toolsets import AbstractToolset

from . import audit
from .llm import PROJECT_DIR
from .models import AgentName, TeamDeps

SERVER_SCRIPT = PROJECT_DIR / "mcp_server" / "server.py"

# Tools only a human (through the API) may call: the pay tool and the database reset.
# No agent allowlist includes them, and _audited_call blocks them by name as well.
HUMAN_ONLY_TOOLS = {"decide_payment", "reset_working_database"}

# Arguments that identify who is acting. The backend overwrites them with the calling agent.
IDENTITY_ARGS = ("requested_by", "author", "agent")

AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": {
        "get_ticket", "list_open_tickets", "get_cash_position", "list_approvals", "list_drafts",
        "update_ticket",
    },
    "inventory": {
        "get_ticket", "check_stock", "list_inventory", "list_vendors", "get_vendor_status",
        "save_draft",
    },
    "accounting": {
        "get_ticket", "get_cash_position", "list_invoices", "get_vendor_status", "quote_bulk_order",
        "list_approvals", "request_payment", "create_purchase_order", "save_draft",
    },
    "facilities": {
        "get_ticket", "get_rent_status", "list_approvals", "save_draft",
    },
    "customer_service": {
        "get_ticket", "check_stock", "list_inventory", "quote_bulk_order", "list_drafts", "save_draft",
    },
}
assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_TOOLS.values())


def _outcome(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("blocked"):
            return "blocked"
        if result.get("refused"):
            return "refused"
        if result.get("ok") is False or result.get("found") is False:
            return "error"
    return "ok"


async def _audited_call(ctx: RunContext[TeamDeps], call_tool: CallToolFunc, name: str, args: dict[str, Any]) -> Any:
    deps = ctx.deps
    if name in HUMAN_ONLY_TOOLS:
        audit.record(deps, "guardrail", f"Blocked agent call to human-only tool {name}.",
                     tool=name, tool_args=args, outcome="blocked")
        return {"ok": False, "refused": True, "error": f"{name} can only be used by a human approver."}

    args = dict(args)
    for key in IDENTITY_ARGS:
        if key in args:
            args[key] = deps.agent

    try:
        result = await call_tool(name, args)
    except Exception as exc:
        audit.record(deps, "mcp_tool_call", f"Called {name}.", tool=name, tool_args=args,
                     result=audit.short(str(exc)), outcome="error")
        raise
    audit.record(deps, "mcp_tool_call", f"Called {name}.", tool=name, tool_args=args,
                 result=audit.short(result), outcome=_outcome(result))
    return result


def _transport() -> StdioTransport:
    return StdioTransport(command=sys.executable, args=[str(SERVER_SCRIPT)], cwd=str(PROJECT_DIR))


# One MCP server process shared by all five agents.
shop_mcp = MCPToolset(
    _transport(),
    id="campus-customs",
    process_tool_call=_audited_call,
    tool_error_behavior="retry",
    max_retries=1,
)


def toolset_for(agent: AgentName) -> AbstractToolset[TeamDeps]:
    allowed = AGENT_TOOLS[agent]
    return shop_mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)


class ShopToolError(RuntimeError):
    """The MCP server reported an error for a dashboard call."""


class DashboardMCP:
    """The API's own MCP connection, used for dashboard reads and human actions.

    It talks to the same MCP server as the agents, so the API has no database
    code either. One connection stays open for the life of the API process.
    """

    def __init__(self) -> None:
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._client = Client(_transport())
        await self._client.__aenter__()

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def call(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            if self._client is None or not self._client.is_connected():
                await self.start()
            result = await self._client.call_tool(name, args or {}, raise_on_error=False)
        if result.is_error:
            text = " ".join(getattr(c, "text", "") for c in result.content)
            raise ShopToolError(f"{name} failed: {text}")
        return result.structured_content or {}
