import { AGENTS, AGENT_ORDER, AgentBadge } from "../agents";
import type { AgentName, AuditEvent } from "../types";

type Live = { label: string; tone: "bench" | "active" | "tool" | "pass" | "done" };

/** What each agent is doing right now, from the latest events of the run. */
function liveStatus(agent: AgentName, events: AuditEvent[], running: boolean): Live {
  const mine = events.filter(e => e.agent === agent);
  if (!mine.length) return { label: running ? "On the bench" : "Not called", tone: "bench" };
  const last = mine[mine.length - 1];
  const finished = last.event === "agent_end" || last.event === "ticket_end";
  if (!running || finished) return { label: "Done", tone: "done" };
  if (last.event === "delegation") return { label: `Waiting on ${AGENTS[last.delegated_to as AgentName]?.name ?? last.delegated_to}`, tone: "pass" };
  if (last.event === "mcp_tool_call") return { label: `Ran ${last.tool}`, tone: "tool" };
  return { label: "Thinking…", tone: "active" };
}

export default function Roster({ events, running }: { events: AuditEvent[]; running: boolean }) {
  // The agent holding the ball is whoever produced the latest event and hasn't finished.
  const latest = running ? [...events].reverse().find(e => AGENTS[e.agent as AgentName]) : undefined;
  return (
    <div className="roster">
      {AGENT_ORDER.map(name => {
        const a = AGENTS[name];
        const s = liveStatus(name, events, running);
        const tools = events.filter(e => e.agent === name && e.event === "mcp_tool_call").length;
        const passes = events.filter(e => e.agent === name && e.event === "delegation").length;
        const onBall = latest?.agent === name && s.tone !== "pass";
        return (
          <div key={name} className={`player player--${s.tone} ${onBall ? "player--ball" : ""}`} style={{ "--c": a.color } as React.CSSProperties}>
            <AgentBadge agent={name} size={34} />
            <div className="player-body">
              <div className="player-name" title={a.name}><span className="long">{a.rosterName}</span><span className="short">{a.short}</span></div>
              <div className="player-status">{s.label}</div>
              <div className="player-stats mono" title="MCP tool calls · delegations">
                {tools} tools · {passes} pass
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
