import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CircleAlert, CircleCheck, X } from "lucide-react";
import { API_BASE, ApiError, api } from "./api";
import type { Approval, AuditEvent, Cash, Draft, RunState, Ticket } from "./types";
import TopBar, { type CashChange } from "./components/TopBar";
import TicketBoard from "./components/TicketBoard";
import Roster from "./components/Roster";
import PlayByPlay from "./components/PlayByPlay";
import ApprovalDesk from "./components/ApprovalDesk";
import BoxScore from "./components/BoxScore";
import { approvalTitle, money } from "./util";

type Toast = { kind: "ok" | "err"; text: string; at: number };

function useInterval(fn: () => void, ms: number) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    const id = setInterval(() => saved.current(), ms);
    return () => clearInterval(id);
  }, [ms]);
}

const errText = (e: unknown) => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [shopToday, setShopToday] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [cashChange, setCashChange] = useState<CashChange | null>(null);
  const [liveRun, setLiveRun] = useState<RunState | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [ticketRun, setTicketRun] = useState<RunState | null>(null);
  const [ticketEvents, setTicketEvents] = useState<AuditEvent[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [online, setOnline] = useState(true);
  const [starting, setStarting] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const lastIndex = useRef(-1);
  const [resetIndex, setResetIndex] = useState(-1);
  const lastCash = useRef<number | null>(null);
  const pendingLabel = useRef("payment");

  const running = liveRun?.running ?? false;
  const runningTicket = running ? liveRun!.ticket_id : null;

  const notify = (kind: Toast["kind"], text: string) => setToast({ kind, text, at: Date.now() });

  // ---- board-wide data: tickets, approvals, cash, run state ----
  const refreshBoard = useCallback(async () => {
    try {
      const [t, a, c, r] = await Promise.all([api.tickets(), api.approvals("pending"), api.cash(), api.run()]);
      setTickets(t.tickets);
      setShopToday(t.shop_today);
      setApprovals(a.approvals);
      if (lastCash.current !== null && c.balance < lastCash.current) {
        setCashChange({ before: lastCash.current, after: c.balance, label: pendingLabel.current, at: Date.now() });
      }
      lastCash.current = c.balance;
      setCash(c);
      setLiveRun(r);
      setOnline(true);
      setSelected(s => s ?? t.tickets[0]?.id ?? null);
    } catch {
      setOnline(false);
    }
  }, []);

  // ---- selected ticket: its events (incremental), last run, drafts ----
  const refreshTicket = useCallback(async (id: number) => {
    try {
      const ev = await api.events({ ticketId: id, after: lastIndex.current });
      setResetIndex(ev.last_reset_index);
      if (ev.events.length) {
        lastIndex.current = ev.events[ev.events.length - 1].index;
        setTicketEvents(prev => [...prev, ...ev.events]);
      }
      const [d, run] = await Promise.all([api.drafts(id), api.ticketRun(id).catch(() => null)]);
      setDrafts(d.drafts);
      setTicketRun(run);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => { refreshBoard(); }, [refreshBoard]);
  useEffect(() => {
    if (selected === null) return;
    lastIndex.current = -1;
    setTicketEvents([]);
    setTicketRun(null);
    setDrafts([]);
    refreshTicket(selected);
  }, [selected, refreshTicket]);

  useInterval(refreshBoard, running ? 1500 : 4000);
  useInterval(() => selected !== null && refreshTicket(selected), running && runningTicket === selected ? 1000 : 5000);

  // When a run ends, pull everything once more so the resolved state and summaries land immediately.
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !running) {
      refreshBoard();
      if (selected !== null) refreshTicket(selected);
      if (liveRun?.error) notify("err", `Run failed: ${liveRun.error}`);
      else if (liveRun?.ticket_id) notify("ok", `Ticket #${liveRun.ticket_id} resolved by the team.`);
    }
    wasRunning.current = running;
  }, [running]); // eslint-disable-line react-hooks/exhaustive-deps

  // Only the latest run of the selected ticket since the last database reset,
  // plus human actions on the ticket since that run began.
  const runEvents = useMemo(() => {
    const since = ticketEvents.filter(e => e.index > resetIndex);
    const starts = since.filter(e => e.event === "ticket_start");
    const last = starts[starts.length - 1];
    if (!last) return since.filter(e => e.run_id === "human");
    return since.filter(e => e.run_id === last.run_id || (e.run_id === "human" && e.index > last.index));
  }, [ticketEvents, resetIndex]);

  // ---- actions ----
  const startRun = async (id: number) => {
    setStarting(true);
    try {
      setLiveRun(await api.startRun(id));
      setSelected(id);
    } catch (e) {
      notify("err", errText(e));
    } finally {
      setStarting(false);
    }
  };

  const approve = async (a: Approval, by: string) => {
    pendingLabel.current = `${approvalTitle(a)} approved`;
    try {
      const res = await api.approve(a.id, by);
      notify("ok", `Paid ${money(a.amount)} · checking now ${money(Number(res.checking_balance_after))}`);
    } catch (e) {
      notify("err", `Not paid: ${errText(e)}`);
    }
    await refreshBoard();
    if (selected !== null) await refreshTicket(selected);
  };

  const reject = async (a: Approval, by: string) => {
    try {
      await api.reject(a.id, by);
      notify("ok", `Rejected ${approvalTitle(a)}. No money moved.`);
    } catch (e) {
      notify("err", errText(e));
    }
    await refreshBoard();
    if (selected !== null) await refreshTicket(selected);
  };

  const reset = async () => {
    try {
      await api.reset();
      lastCash.current = null;
      setCashChange(null);
      notify("ok", "Working database restored from the original. Clean slate.");
    } catch (e) {
      notify("err", errText(e));
    }
    await refreshBoard();
    if (selected !== null) { lastIndex.current = -1; setTicketEvents([]); await refreshTicket(selected); }
  };

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6000);
    return () => clearTimeout(t);
  }, [toast]);

  const isLiveTicket = running && runningTicket === selected;

  return (
    <div className="app">
      <TopBar shopToday={shopToday} cash={cash} cashChange={cashChange} pendingCount={approvals.length}
        running={running} online={online} onReset={reset} />
      <div className="stripe" aria-hidden />

      {!online && (
        <div className="offline">
          <CircleAlert size={16} /> Can't reach the backend at <span className="mono">{API_BASE}</span>. Start it from
          <span className="mono">backend/</span> with <span className="mono">uvicorn main:app --reload --port 8000</span>.
        </div>
      )}

      <main className="grid">
        <TicketBoard tickets={tickets} approvals={approvals} selected={selected} runningTicket={runningTicket}
          starting={starting} onSelect={setSelected} onRun={startRun} />

        <div className="center">
          <Roster events={runEvents} running={isLiveTicket} />
          <PlayByPlay events={runEvents} running={isLiveTicket} ticketId={selected} />
        </div>

        <div className="right">
          <ApprovalDesk approvals={approvals} cash={cash} selectedTicket={selected} onApprove={approve} onReject={reject} />
          <BoxScore run={ticketRun} events={runEvents} drafts={drafts} />
        </div>
      </main>

      {toast && (
        <div className={`toast toast--${toast.kind}`} key={toast.at} role="status">
          {toast.kind === "ok" ? <CircleCheck size={16} /> : <CircleAlert size={16} />}
          <span>{toast.text}</span>
          <button onClick={() => setToast(null)} aria-label="Dismiss"><X size={14} /></button>
        </div>
      )}
    </div>
  );
}
