import { useEffect, useRef, useState } from "react";
import { ArrowRight, Flag, Hand, MessageSquareText, ShieldAlert, Terminal, TriangleAlert, Whistle } from "lucide-react";
import { AgentBadge, identityOf } from "../agents";
import type { AuditEvent } from "../types";
import { clock, resultHighlights, toolSignature } from "../util";

const OUTCOME_LABEL = { ok: "ok", refused: "refused", blocked: "blocked", error: "error", limit: "limit" } as const;

function Row({ e, start }: { e: AuditEvent; start?: string }) {
  const id = identityOf(e.agent);
  const style = { "--c": id.color, "--depth": e.depth } as React.CSSProperties;
  const time = <span className="pbp-time mono">{clock(e.timestamp, start)}</span>;

  if (e.event === "ticket_start") {
    return <div className="pbp-divider">{time}<Whistle size={14} /> Tip-off · {e.detail}</div>;
  }
  if (e.event === "ticket_end") {
    return (
      <div className="pbp-row pbp-final" style={style}>
        {time}<Flag size={15} className="pbp-icon" />
        <div className="pbp-body">
          <div className="pbp-head"><b>Final whistle</b><span className="mono pbp-usage">{e.result}</span></div>
          <p>{e.detail}</p>
        </div>
      </div>
    );
  }
  if (e.event === "human_decision" || e.event === "reset") {
    return (
      <div className="pbp-row pbp-human" style={style}>
        {time}<Hand size={15} className="pbp-icon" />
        <div className="pbp-body">
          <div className="pbp-head"><b>{id.name}</b><span className="tag tag--human">human call</span>
            <span className={`outcome outcome--${e.outcome}`}>{OUTCOME_LABEL[e.outcome]}</span></div>
          <p>{e.detail}</p>
        </div>
      </div>
    );
  }
  if (e.event === "guardrail" || e.event === "run_error") {
    return (
      <div className="pbp-row pbp-guard" style={style}>
        {time}<ShieldAlert size={15} className="pbp-icon" />
        <div className="pbp-body"><div className="pbp-head"><b>{e.event === "run_error" ? "Run error" : "Guardrail"}</b>
          <span className={`outcome outcome--${e.outcome}`}>{e.outcome}</span></div><p>{e.detail}</p></div>
      </div>
    );
  }

  let body: React.ReactNode;
  if (e.event === "delegation") {
    const to = identityOf(e.delegated_to ?? "");
    body = (
      <>
        <div className="pbp-head">
          <b style={{ color: id.color }}>{id.short}</b>
          <ArrowRight size={14} className="pass-arrow" />
          <AgentBadge agent={e.delegated_to ?? ""} size={18} />
          <b style={{ color: to.color }}>{to.short}</b>
          <span className="tag">pass</span>
        </div>
        <p className="pbp-brief">{e.detail}</p>
      </>
    );
  } else if (e.event === "mcp_tool_call") {
    const hl = resultHighlights(e.result);
    body = (
      <>
        <div className="pbp-head">
          <span className="chip mono"><Terminal size={12} /> {toolSignature(e)}</span>
          <span className={`outcome outcome--${e.outcome}`}>{OUTCOME_LABEL[e.outcome]}</span>
        </div>
        {hl.length > 0 && <div className="kv mono">{hl.map(h => <span key={h}>{h}</span>)}</div>}
      </>
    );
  } else if (e.event === "agent_end") {
    body = (
      <>
        <div className="pbp-head"><b style={{ color: id.color }}>{id.name}</b><span className="tag">reports back</span></div>
        <p>{e.detail}</p>
      </>
    );
  } else if (e.event === "agent_start") {
    body = <div className="pbp-head"><b style={{ color: id.color }}>{id.name}</b><span className="tag">takes the ticket</span></div>;
  } else {
    body = (
      <div className="pbp-say"><MessageSquareText size={13} /> {e.detail}</div>
    );
  }

  return (
    <div className={`pbp-row pbp-${e.event}`} style={style}>
      {time}
      <AgentBadge agent={e.agent} size={24} />
      <div className="pbp-body">{body}</div>
    </div>
  );
}

/** Rows that repeat what the next row already shows are hidden in the compact trace. */
function isNoise(e: AuditEvent, prev?: AuditEvent): boolean {
  if (e.event === "model_step" && e.detail.startsWith("Chose to call")) return true;
  if (e.event === "agent_start" && prev?.event === "delegation") return true;
  return false;
}

interface Props { events: AuditEvent[]; running: boolean; ticketId: number | null }

export default function PlayByPlay({ events, running, ticketId }: Props) {
  const [full, setFull] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const start = events.find(e => e.event === "ticket_start")?.timestamp;
  const shown = full ? events : events.filter((e, i) => !isNoise(e, events[i - 1]));

  useEffect(() => {
    const el = scroller.current;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 160) el.scrollTop = el.scrollHeight;
  }, [shown.length]);

  return (
    <section className="panel pbp">
      <div className="panel-head">
        <h2>Play-by-play {ticketId && <span className="mono muted">· ticket #{ticketId}</span>}</h2>
        <div className="seg">
          <button className={!full ? "on" : ""} onClick={() => setFull(false)}>Compact</button>
          <button className={full ? "on" : ""} onClick={() => setFull(true)}>Full trace</button>
        </div>
      </div>
      <div className="pbp-scroll" ref={scroller}>
        {!ticketId && <div className="empty">Pick a ticket on the board.</div>}
        {ticketId && !events.length && !running && (
          <div className="empty">
            <TriangleAlert size={18} /> No agent activity for this ticket yet. Hit <b>Run the team</b> to tip off.
          </div>
        )}
        {shown.map(e => <Row key={e.index} e={e} start={start} />)}
        {running && <div className="typing"><i /><i /><i /> agents working</div>}
      </div>
    </section>
  );
}
