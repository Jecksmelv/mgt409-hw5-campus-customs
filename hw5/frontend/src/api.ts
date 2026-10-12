// Thin client for the FastAPI backend. Every value on the dashboard comes from these calls.
import type { Approval, Cash, Draft, EventsResponse, RunState, TicketsResponse } from "./types";

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : (detail as { error?: string })?.error ?? `HTTP ${status}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body);
  return body as T;
}

const post = <T>(path: string, data: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(data) });

export const api = {
  tickets: () => request<TicketsResponse>("/api/tickets"),
  startRun: (ticketId: number) => post<RunState>("/api/run", { ticket_id: ticketId }),
  run: () => request<RunState>("/api/run"),
  ticketRun: (ticketId: number) => request<RunState | null>(`/api/runs/${ticketId}`),
  events: (params: { after?: number; ticketId?: number; runId?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params.after !== undefined) q.set("after", String(params.after));
    if (params.ticketId !== undefined) q.set("ticket_id", String(params.ticketId));
    if (params.runId) q.set("run_id", params.runId);
    q.set("limit", String(params.limit ?? 1000));
    return request<EventsResponse>(`/api/events?${q}`);
  },
  approvals: (status: "pending" | "all" = "pending") =>
    request<{ approvals: Approval[] }>(`/api/approvals?status=${status}`),
  approve: (id: number, approvedBy: string) =>
    post<Record<string, unknown>>(`/api/approvals/${id}/approve`, { approved_by: approvedBy, confirm: true }),
  reject: (id: number, rejectedBy: string) =>
    post<Record<string, unknown>>(`/api/approvals/${id}/reject`, { rejected_by: rejectedBy }),
  cash: () => request<Cash>("/api/cash"),
  drafts: (ticketId?: number) =>
    request<{ drafts: Draft[] }>(`/api/drafts${ticketId !== undefined ? `?ticket_id=${ticketId}` : ""}`),
  reset: () => post<Record<string, unknown>>("/api/reset", { confirm: true }),
};
