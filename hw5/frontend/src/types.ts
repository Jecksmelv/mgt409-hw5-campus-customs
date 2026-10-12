// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";
export type TicketStatus = "open" | "in_progress" | "waiting_approval" | "blocked" | "resolved";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: TicketStatus;
  notes: string | null;
  created_at: string;
  state: "open" | "resolved";
  being_worked: boolean;
}

export interface TicketsResponse {
  shop_today: string;
  tickets: Ticket[];
}

export interface AgentReport {
  agent: AgentName;
  ticket_id: number;
  summary: string;
  facts: string[];
  actions_taken: string[];
  approval_ids: number[];
  draft_ids: number[];
  blockers: string[];
  needs_human: boolean;
  recommendation: string;
}

export interface TicketDecision {
  ticket_id: number;
  final_status: TicketStatus;
  decision: string;
  rationale: string;
  agents_consulted: AgentName[];
  approval_ids: number[];
  draft_ids: number[];
  open_items: string[];
}

export interface RunState {
  running: boolean;
  ticket_id: number | null;
  run_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  decision: TicketDecision | null;
  reports: { agent: AgentName; depth: number; output: AgentReport | TicketDecision }[];
  usage: { requests?: number; tool_calls?: number; total_tokens?: number };
  marked_resolved: boolean;
  error: string | null;
}

export type AuditEventType =
  | "ticket_start" | "agent_start" | "model_step" | "mcp_tool_call" | "delegation"
  | "agent_end" | "ticket_end" | "guardrail" | "run_error" | "human_decision" | "reset";

export interface AuditEvent {
  index: number;
  timestamp: string;
  run_id: string;
  ticket_id: number | null;
  agent: string;
  depth: number;
  step: number;
  event: AuditEventType;
  detail: string;
  delegated_to: string | null;
  tool: string | null;
  tool_args: Record<string, unknown> | null;
  result: string | null;
  outcome: "ok" | "refused" | "blocked" | "error" | "limit";
}

export interface EventsResponse {
  events: AuditEvent[];
  last_index: number;
  running: boolean;
  last_reset_index: number;
}

export interface Approval {
  id: number;
  kind: "invoice" | "rent" | "purchase_order";
  ref_id: number | null;
  vendor_id: number | null;
  sku: string | null;
  size: string | null;
  qty: number | null;
  amount: number;
  ticket_id: number | null;
  requested_by: string;
  reason: string | null;
  status: "pending" | "approved" | "rejected" | "refused";
  created_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  payment_id: number | null;
}

export interface Payment {
  id: number;
  kind: string;
  ref_id: number | null;
  amount: number;
  account: string;
  paid_at: string;
  approved_by: string;
}

export interface Cash {
  account: string;
  balance: number;
  as_of: string;
  shop_today: string;
  pending_total: number;
  balance_after_pending: number;
  payments_made: Payment[];
}

export interface Draft {
  id: number;
  ticket_id: number | null;
  audience: "customer" | "vendor" | "landlord";
  recipient: string;
  subject: string;
  body: string;
  author: string;
  status: string;
  created_at: string;
}
