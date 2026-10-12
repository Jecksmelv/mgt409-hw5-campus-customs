import { useState } from "react";
import { ChevronDown, Flag, Mail, Terminal } from "lucide-react";
import { AGENTS, AGENT_ORDER, AgentBadge } from "../agents";
import type { AgentName, AgentReport, AuditEvent, Draft, RunState, TicketDecision } from "../types";

interface Props {
  run: RunState | null;
  events: AuditEvent[];
  drafts: Draft[];
}

/** Per-agent summaries for the selected ticket: the Boss's final call, then each specialist's report. */
export default function BoxScore({ run, events, drafts }: Props) {
  const decision = run?.decision ?? null;
  const reports = (run?.reports ?? []).filter(r => r.agent !== "boss").map(r => r.output as AgentReport);
  // If the API restarted and lost the run state, fall back to the agent_end lines in the audit trail.
  const fallback = (agent: AgentName) => events.filter(e => e.agent === agent && e.event === "agent_end").map(e => e.detail);

  const involved = AGENT_ORDER.filter(a => a !== "boss" && events.some(e => e.agent === a));
  const bossEnd = events.filter(e => e.agent === "boss" && e.event === "agent_end").pop()?.detail;

  return (
    <section className="panel box">
      <div className="panel-head"><h2>Box score</h2>
        {run?.usage?.total_tokens ? (
          <span className="mono muted">{run.usage.requests} calls · {run.usage.tool_calls} tools · {(run.usage.total_tokens / 1000).toFixed(1)}k tok</span>
        ) : null}
      </div>

      {(decision || bossEnd) && <FinalCall decision={decision} fallback={bossEnd} />}

      {involved.length === 0 && !decision && <div className="empty small">Agent summaries show up here after a run.</div>}

      {involved.map(name => {
        const a = AGENTS[name];
        const mine = reports.filter(r => r.agent === name);
        const tools = [...new Set(events.filter(e => e.agent === name && e.event === "mcp_tool_call").map(e => e.tool!))];
        const lines = mine.length ? mine.map(r => r.summary) : fallback(name);
        const blockers = mine.flatMap(r => r.blockers);
        return (
          <div className="line" key={name} style={{ "--c": a.color } as React.CSSProperties}>
            <AgentBadge agent={name} size={26} showIcon />
            <div className="line-body">
              <div className="line-name">{a.name} <span className="mono muted">#{a.number}</span></div>
              {lines.map((l, i) => <p key={i}>{l}</p>)}
              {blockers.length > 0 && <p className="blocker">Blocker: {blockers.join(" · ")}</p>}
              <div className="line-tools">{tools.map(t => <span key={t} className="chip chip--sm mono"><Terminal size={10} />{t}</span>)}</div>
            </div>
          </div>
        );
      })}

      {AGENT_ORDER.filter(a => a !== "boss" && !involved.includes(a)).length > 0 && involved.length > 0 && (
        <div className="bench mono">
          Bench: {AGENT_ORDER.filter(a => a !== "boss" && !involved.includes(a)).map(a => AGENTS[a].name).join(", ")}
        </div>
      )}

      {drafts.length > 0 && <Drafts drafts={drafts} />}
    </section>
  );
}

function FinalCall({ decision, fallback }: { decision: TicketDecision | null; fallback?: string }) {
  return (
    <div className="final" style={{ "--c": AGENTS.boss.color } as React.CSSProperties}>
      <div className="final-head"><Flag size={14} /> Boss's final call
        {decision && <span className={`pill pill--status-${decision.final_status}`}>{decision.final_status.replace("_", " ")}</span>}
      </div>
      <p className="final-text">{decision?.decision ?? fallback}</p>
      {decision?.rationale && <p className="final-why">{decision.rationale}</p>}
      {decision && decision.open_items.length > 0 && (
        <ul className="final-open">{decision.open_items.map((o, i) => <li key={i}>{o}</li>)}</ul>
      )}
    </div>
  );
}

function Drafts({ drafts }: { drafts: Draft[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="drafts">
      <div className="drafts-head"><Mail size={14} /> Drafts on the board <span className="stamp">not sent</span></div>
      {drafts.map(d => (
        <div key={d.id} className={`draft ${open === d.id ? "draft--open" : ""}`}>
          <button className="draft-row" onClick={() => setOpen(open === d.id ? null : d.id)}>
            <AgentBadge agent={d.author} size={16} />
            <span className="draft-to">To {d.recipient}</span>
            <span className="draft-subj">{d.subject}</span>
            <ChevronDown size={14} className="draft-caret" />
          </button>
          {open === d.id && <pre className="draft-body">{d.body}</pre>}
        </div>
      ))}
    </div>
  );
}
