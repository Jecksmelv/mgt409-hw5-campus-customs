import { CircleCheck, Hand, LoaderCircle, Play } from "lucide-react";
import type { Approval, Ticket } from "../types";
import { TICKET_TYPE, deskState, ticketLine } from "../util";

const STATE_LABEL = { working: "Being worked", resolved: "Resolved", open: "Open" } as const;

interface Props {
  tickets: Ticket[];
  approvals: Approval[];
  selected: number | null;
  runningTicket: number | null;
  starting: boolean;
  onSelect: (id: number) => void;
  onRun: (id: number) => void;
}

export default function TicketBoard({ tickets, approvals, selected, runningTicket, starting, onSelect, onRun }: Props) {
  const counts = { open: 0, working: 0, resolved: 0 };
  tickets.forEach(t => counts[deskState(t, runningTicket)]++);

  return (
    <aside className="panel board">
      <div className="panel-head">
        <h2>Ticket board</h2>
        <div className="tally mono">
          <span className="tally-open">{counts.open} open</span>
          <span className="tally-working">{counts.working} live</span>
          <span className="tally-resolved">{counts.resolved} done</span>
        </div>
      </div>

      <div className="tickets">
        {tickets.map(t => {
          const state = deskState(t, runningTicket);
          const waiting = approvals.filter(a => a.ticket_id === t.id);
          const isSel = selected === t.id;
          return (
            <div
              key={t.id}
              role="button"
              tabIndex={0}
              className={`ticket ticket--${state} ${waiting.length ? "ticket--needs-you" : ""} ${isSel ? "ticket--selected" : ""}`}
              onClick={() => onSelect(t.id)}
              onKeyDown={e => (e.key === "Enter" || e.key === " ") && onSelect(t.id)}
            >
              <div className="ticket-top">
                <span className="ticket-id">#{t.id}</span>
                <span className={`pill pill--${state}`}>
                  {state === "working" && <LoaderCircle size={12} className="spin" />}
                  {state === "resolved" && <CircleCheck size={12} />}
                  {STATE_LABEL[state]}
                </span>
              </div>
              <div className="ticket-subject">{t.subject}</div>
              <div className="ticket-meta">
                <span>{TICKET_TYPE[t.type] ?? t.type}</span>
                <span className="dot" />
                <span>{t.requester}</span>
              </div>
              <div className="ticket-line mono">{ticketLine(t)}</div>
              {waiting.length > 0 && (
                <div className="needs-you">
                  <Hand size={13} /> {waiting.length} approval{waiting.length > 1 ? "s" : ""} waiting on you
                </div>
              )}
              {isSel && (
                <button
                  className="run-btn"
                  disabled={runningTicket !== null || starting}
                  onClick={e => { e.stopPropagation(); onRun(t.id); }}
                >
                  {state === "working"
                    ? <><LoaderCircle size={15} className="spin" /> Team on the floor…</>
                    : <><Play size={15} fill="currentColor" /> {t.status === "resolved" ? "Run the team again" : "Run the team"}</>}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div className="legend">
        <span><i className="sw sw--open" /> Open</span>
        <span><i className="sw sw--working" /> Being worked</span>
        <span><i className="sw sw--needs" /> Needs you</span>
        <span><i className="sw sw--resolved" /> Resolved</span>
      </div>
    </aside>
  );
}
