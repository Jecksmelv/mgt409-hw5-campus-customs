import type { Approval, AuditEvent, Ticket } from "./types";

export const money = (n: number, cents = true) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0 });

export const TICKET_TYPE: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Discount request",
};

export function ticketLine(t: Ticket): string {
  if (t.sku) return `${t.qty ?? 1} × ${t.sku} · size ${t.size}`;
  if (t.lease_id) return `Lease #${t.lease_id}`;
  return t.subject;
}

/** Desk state, in priority order: being worked > resolved > open. Approvals are a separate flag. */
export type DeskState = "working" | "resolved" | "open";

export function deskState(t: Ticket, runningTicket: number | null): DeskState {
  if (runningTicket === t.id) return "working";
  return t.status === "resolved" ? "resolved" : "open";
}

export function approvalTitle(a: Approval): string {
  if (a.kind === "invoice") return `Vendor invoice #${a.ref_id}`;
  if (a.kind === "rent") return `Rent · lease #${a.ref_id}`;
  return `Purchase order · ${a.qty} × ${a.sku} ${a.size}`;
}

export const KIND_LABEL: Record<Approval["kind"], string> = {
  invoice: "Pay invoice",
  rent: "Pay rent",
  purchase_order: "Place purchase order",
};

/** Compact `tool(arg=value, ...)` text for a tool-call chip. Identity args are dropped. */
export function toolSignature(e: AuditEvent): string {
  const args = Object.entries(e.tool_args ?? {})
    .filter(([k]) => !["requested_by", "author", "agent", "reason", "body", "note"].includes(k))
    .map(([k, v]) => `${k}=${typeof v === "string" && v.length > 22 ? v.slice(0, 20) + "…" : String(v)}`);
  return `${e.tool}(${args.join(", ")})`;
}

/** Pull a few readable key=value facts out of a tool result for the trace. */
export function resultHighlights(result: string | null): string[] {
  if (!result) return [];
  const keys = ["qty_on_hand", "shortage", "can_ship", "lead_days", "days_until_due", "is_overdue", "amount",
    "approval_id", "draft_id", "checking_balance", "cash_after_all_pending", "discounted_unit_price",
    "order_margin", "break_even_discount_pct", "status", "error"];
  const out: string[] = [];
  for (const k of keys) {
    const m = result.match(new RegExp(`"${k}":\\s*("([^"]*)"|[-\\d.]+|true|false|null)`));
    if (m) out.push(`${k}=${m[2] ?? m[1]}`);
    if (out.length >= 4) break;
  }
  return out;
}

export function clock(iso: string, start?: string): string {
  if (start) {
    const s = Math.max(0, (Date.parse(iso) - Date.parse(start)) / 1000);
    return `+${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
  }
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
