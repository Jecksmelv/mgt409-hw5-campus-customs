// Visual identity for the five agents: colour, shape, jersey number, icon and role line.
// Shape and number carry identity as well as colour, so agents stay distinct for colour-blind users.
import { Building2, Calculator, Crown, MessageCircle, Package, UserRound, type LucideIcon } from "lucide-react";
import type { AgentName } from "./types";

export type Shape = "diamond" | "square" | "circle" | "hex" | "bubble" | "ring";

export interface AgentIdentity {
  key: AgentName | "human";
  name: string;
  rosterName: string;
  short: string;
  role: string;
  number: string;
  color: string;
  shape: Shape;
  Icon: LucideIcon;
}

export const AGENTS: Record<AgentName, AgentIdentity> = {
  boss: {
    key: "boss", name: "Boss", rosterName: "Boss", short: "BOSS", role: "Captain · routes the play, makes the final call",
    number: "01", color: "var(--a-boss)", shape: "diamond", Icon: Crown,
  },
  inventory: {
    key: "inventory", name: "Inventory", rosterName: "Inventory", short: "INV", role: "Stockroom · SKU × size, vendors, lead days",
    number: "07", color: "var(--a-inventory)", shape: "square", Icon: Package,
  },
  accounting: {
    key: "accounting", name: "Accounting", rosterName: "Accounting", short: "ACCT", role: "Ledger · cash, margins, approval requests",
    number: "10", color: "var(--a-accounting)", shape: "circle", Icon: Calculator,
  },
  facilities: {
    key: "facilities", name: "Facilities", rosterName: "Facilities", short: "FAC", role: "Shop floor · lease, rent, the space",
    number: "04", color: "var(--a-facilities)", shape: "hex", Icon: Building2,
  },
  customer_service: {
    key: "customer_service", name: "Customer Service", rosterName: "Cust. Service", short: "CS", role: "Voice · customer drafts, never sent",
    number: "23", color: "var(--a-cs)", shape: "bubble", Icon: MessageCircle,
  },
};

export const AGENT_ORDER: AgentName[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];

const HUMAN: AgentIdentity = {
  key: "human", name: "You", rosterName: "You", short: "YOU", role: "Human desk", number: "—",
  color: "var(--ivory)", shape: "ring", Icon: UserRound,
};

export function identityOf(agent: string): AgentIdentity {
  if (agent.startsWith("human:")) return { ...HUMAN, name: agent.slice(6) || "You" };
  return AGENTS[agent as AgentName] ?? { ...HUMAN, name: agent, short: agent.slice(0, 4).toUpperCase() };
}

/** Jersey-style badge: the agent's shape filled with its colour, with its number or icon inside. */
export function AgentBadge({ agent, size = 30, showIcon = false }: { agent: string; size?: number; showIcon?: boolean }) {
  const id = identityOf(agent);
  const { Icon } = id;
  return (
    <span
      className={`badge shape-${id.shape}`}
      style={{ "--c": id.color, width: size, height: size, fontSize: size * 0.42 } as React.CSSProperties}
      title={`${id.name} — ${id.role}`}
      aria-label={id.name}
    >
      {showIcon ? <Icon size={size * 0.5} strokeWidth={2.4} /> : <span className="badge-num">{id.number}</span>}
    </span>
  );
}
