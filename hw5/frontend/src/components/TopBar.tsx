import { useEffect, useRef, useState } from "react";
import { RotateCcw, TrendingDown } from "lucide-react";
import type { Cash } from "../types";
import { money } from "../util";

/** Animate a number from its previous value to the new one, scoreboard style. */
function useTween(value: number | null, ms = 900): number | null {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (value === null) return;
    const start = from.current ?? value;
    if (start === value) { setShown(value); from.current = value; return; }
    const t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(start + (value - start) * eased);
      if (p < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return shown;
}

export interface CashChange { before: number; after: number; label: string; at: number }

function CashScoreboard({ cash, change }: { cash: Cash | null; change: CashChange | null }) {
  const shown = useTween(cash?.balance ?? null);
  const fresh = change && Date.now() - change.at < 12000;
  const pendingShare = cash && cash.balance > 0 ? Math.min(1, cash.pending_total / cash.balance) : 0;
  return (
    <div className={`scoreboard ${fresh ? "scoreboard--hit" : ""}`} aria-live="polite">
      <div className="scoreboard-label">
        Checking <span className="mono">cash_accounts</span>
      </div>
      <div className="scoreboard-value">{shown === null ? "—" : money(shown)}</div>
      {cash && (
        <div className="scoreboard-meter" title={`${money(cash.pending_total)} waiting for approval`}>
          <span className="meter-track"><span className="meter-fill" style={{ width: `${pendingShare * 100}%` }} /></span>
          <span className="mono">
            {cash.pending_total > 0
              ? <>pending {money(cash.pending_total, false)} → leaves <b>{money(cash.balance_after_pending, false)}</b></>
              : "nothing pending"}
          </span>
        </div>
      )}
      {fresh && change && (
        <div className="cash-delta" key={change.at}>
          <TrendingDown size={14} /> {money(change.after - change.before)}
          <span className="cash-delta-was">was {money(change.before, false)} · {change.label}</span>
        </div>
      )}
    </div>
  );
}

interface Props {
  shopToday: string | null;
  cash: Cash | null;
  cashChange: CashChange | null;
  pendingCount: number;
  running: boolean;
  online: boolean;
  onReset: () => void;
}

export default function TopBar({ shopToday, cash, cashChange, pendingCount, running, online, onReset }: Props) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(t);
  }, [armed]);

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark" aria-hidden>
          <svg viewBox="0 0 40 40"><path d="M5 28 L13 12 L20 28 L27 12 L35 28" /></svg>
        </div>
        <div>
          <div className="brand-name">Campus Customs</div>
          <div className="brand-sub">Operations Desk · Chapel St.</div>
        </div>
      </div>

      <div className="topbar-stats">
        <div className="stat">
          <div className="stat-label">Shop today</div>
          <div className="stat-value mono">{shopToday ?? "—"}</div>
          <div className="stat-foot">desk.date_today</div>
        </div>
        <div className={`stat ${pendingCount ? "stat--alert" : ""}`}>
          <div className="stat-label">Your calls</div>
          <div className="stat-value">{pendingCount}</div>
          <div className="stat-foot">{pendingCount === 1 ? "approval waiting" : "approvals waiting"}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Team</div>
          <div className={`led ${running ? "led--live" : online ? "led--idle" : "led--off"}`}>
            <i /> {running ? "Live" : online ? "Ready" : "Offline"}
          </div>
          <div className="stat-foot mono">gpt-6-luna</div>
        </div>
      </div>

      <CashScoreboard cash={cash} change={cashChange} />

      <button
        className={`reset ${armed ? "reset--armed" : ""}`}
        disabled={running}
        onClick={() => (armed ? (setArmed(false), onReset()) : setArmed(true))}
        title="Restore data/campus_customs_new.db from the original database"
      >
        <RotateCcw size={15} /> {armed ? "Click again to reset" : "Reset DB"}
      </button>
    </header>
  );
}
