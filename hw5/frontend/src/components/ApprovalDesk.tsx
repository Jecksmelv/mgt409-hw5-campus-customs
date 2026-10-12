import { useEffect, useState } from "react";
import { BadgeCheck, Ban, Hand, LoaderCircle, ShieldCheck, TriangleAlert } from "lucide-react";
import { AgentBadge, identityOf } from "../agents";
import type { Approval, Cash } from "../types";
import { KIND_LABEL, approvalTitle, money } from "../util";

interface Props {
  approvals: Approval[];
  cash: Cash | null;
  selectedTicket: number | null;
  onApprove: (a: Approval, by: string) => Promise<void>;
  onReject: (a: Approval, by: string) => Promise<void>;
}

function ApprovalCard({ a, cash, by, focus, onApprove, onReject }: {
  a: Approval; cash: Cash | null; by: string; focus: boolean;
  onApprove: Props["onApprove"]; onReject: Props["onReject"];
}) {
  const [stage, setStage] = useState<"idle" | "confirm" | "busy">("idle");
  useEffect(() => {
    if (stage !== "confirm") return;
    const t = setTimeout(() => setStage("idle"), 6000);
    return () => clearTimeout(t);
  }, [stage]);

  const before = cash?.balance ?? 0;
  const after = before - a.amount;
  const covered = after >= 0;
  const req = identityOf(a.requested_by);
  const noName = !by.trim();

  const act = async (fn: () => Promise<void>) => {
    setStage("busy");
    try { await fn(); } finally { setStage("idle"); }
  };

  return (
    <article className={`ask ${focus ? "ask--focus" : ""} ${!covered ? "ask--short" : ""}`}>
      <div className="ask-band" aria-hidden />
      <div className="ask-top">
        <span className="ask-kind"><Hand size={13} /> {KIND_LABEL[a.kind]}</span>
        <span className="mono muted">#{a.id} · ticket {a.ticket_id ?? "—"}</span>
      </div>
      <div className="ask-amount">{money(a.amount)}</div>
      <div className="ask-title">{approvalTitle(a)}</div>
      {a.reason && <p className="ask-reason">“{a.reason}”</p>}
      <div className="ask-by">
        <AgentBadge agent={a.requested_by} size={18} /> prepared by <b style={{ color: req.color }}>{req.name}</b>
      </div>

      <div className="impact mono">
        <div><small>cash now</small>{money(before, false)}</div>
        <div className="impact-arrow">→</div>
        <div className={covered ? "" : "neg"}><small>after paying</small>{money(after, false)}</div>
      </div>
      {!covered && (
        <div className="ask-warn"><TriangleAlert size={14} /> Not enough cash. The pay tool will refuse this.</div>
      )}

      <div className="ask-actions">
        {stage === "confirm" ? (
          <button className="approve approve--confirm" onClick={() => act(() => onApprove(a, by.trim()))}>
            <ShieldCheck size={16} /> Confirm: pay {money(a.amount, false)}
          </button>
        ) : (
          <button className="approve" disabled={stage === "busy" || noName} onClick={() => setStage("confirm")}
            title={noName ? "Enter your name above first" : "Approve this payment"}>
            {stage === "busy" ? <LoaderCircle size={16} className="spin" /> : <BadgeCheck size={16} />} Approve
          </button>
        )}
        <button className="reject" disabled={stage === "busy" || noName} onClick={() => act(() => onReject(a, by.trim()))}>
          <Ban size={14} /> Reject
        </button>
      </div>
    </article>
  );
}

export default function ApprovalDesk({ approvals, cash, selectedTicket, onApprove, onReject }: Props) {
  const [by, setBy] = useState(() => localStorage.getItem("cc.approver") ?? "");
  useEffect(() => { localStorage.setItem("cc.approver", by); }, [by]);
  const ordered = [...approvals].sort((x, y) => Number(y.ticket_id === selectedTicket) - Number(x.ticket_id === selectedTicket));

  return (
    <section className={`panel desk ${approvals.length ? "desk--live" : ""}`}>
      <div className="panel-head">
        <h2><Hand size={16} /> Your call</h2>
        <span className="mono muted">{approvals.length} waiting</span>
      </div>
      <p className="desk-note">
        Agents can only <b>prepare</b> payments. Nothing leaves checking until you approve it here.
      </p>
      <label className="approver">
        <span>Approving as</span>
        <input value={by} onChange={e => setBy(e.target.value)} placeholder="Your name" maxLength={40} />
      </label>
      <div className="asks">
        {ordered.length === 0 && <div className="empty small">No payments waiting. The desk is clear.</div>}
        {ordered.map(a => (
          <ApprovalCard key={a.id} a={a} cash={cash} by={by} focus={a.ticket_id === selectedTicket}
            onApprove={onApprove} onReject={onReject} />
        ))}
      </div>
    </section>
  );
}
