# Campus Customs Ops Desk — Design Notes

The dashboard in `frontend/` (React + Vite + TypeScript) is the human side of the agent team. Every value on screen comes from the FastAPI routes in `backend/main.py`. Nothing is hardcoded or mocked.

## The idea: a night-game control room

The brief was *Afro, sporty, nerdy, polished, a little playful*. I treated the desk like the operations room of a team playing a night game:

- **Sporty:** the five agents are a **roster**. The ticket run is the **play-by-play**. Their reports are the **box score**. The cash balance is the **scoreboard**.
- **Nerdy:** under that metaphor, everything is real system data, including MCP tool calls with their arguments, delegation depth, usage counts and audit outcomes.
- **Polished:** a deep-navy floor, ivory type and one disciplined accent colour keep it calm enough to use for real.
- **Afro:** the personality is in the geometry. It's a woven zig-zag motif and shape-coded agents, not flags or "safari" decoration.

## Overall layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ CAMPUS CUSTOMS   [shop today] [your calls] [team LED]   [ $3,400.00 ]  Reset │  ← scoreboard bar
│▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼▲▼│  ← roster stripe
├──────────────┬───────────────────────────────────────────┬───────────────────┤
│ TICKET BOARD │ ROSTER  (5 player cards, live status)     │ YOUR CALL         │
│  #101  ◉     │───────────────────────────────────────────│  (approval cards) │
│  #102        │ PLAY-BY-PLAY                              │───────────────────│
│  #103        │  timeline of agent steps, passes and      │ BOX SCORE         │
│  [Run team]  │  MCP tool chips, indented by depth        │  Boss's final call│
│  legend      │                                           │  per-agent lines  │
│              │                                           │  drafts (unsent)  │
└──────────────┴───────────────────────────────────────────┴───────────────────┘
```

The columns read left to right in the order you work: **pick a ticket → watch the team → make your call and read the result**.

- **The header is a scoreboard bar.** It holds the shop's date (`desk.date_today`, not the computer clock), how many approvals are waiting, whether the team is live, and the checking balance in the biggest number on the page.
- **The middle column is the busiest part of the screen.** The roster sits above the timeline, so you can glance at who is acting and then read what they did.
- **The right column is the human column.** Decisions sit on top and results below.
- **The layout fits one screen.** On a laptop it stays one screen tall, and only the timeline and the right column scroll, so the cash and the approval desk never scroll away. Below 1440px wide, the columns tighten and the roster switches to short names (INV, ACCT, FAC, CS). Below 1180px, the right column moves under the others.

## How the five agents read differently

Each agent has four identity cues, so you never rely on colour alone. That also helps colour-blind users.

| Agent | Colour | Shape | Jersey | Icon | Why |
|---|---|---|---|---|---|
| Boss | periwinkle `#7c9cff` | ◆ diamond | **01** | crown | The captain wears number one, and the diamond points both ways, like routing. The blue nods to Yale without copying Yale Blue. |
| Inventory | cyan `#2ad4e4` | ■ square | **07** | package | Boxes and stock: a square, stackable shape. |
| Accounting | rose `#f06bc8` | ● circle | **10** | calculator | The coin shape. |
| Facilities | terracotta `#ff7a4d` | ⬢ hexagon | **04** | building | A building block, in a brick and earth tone. |
| Customer Service | violet `#b18cff` | 💬 speech bubble | **23** | chat | The voice of the shop. |

**Where the identities appear:**
- **Jersey badges.** Each badge is the agent's shape filled with its colour, with the jersey number in heavy italic condensed type, like a uniform number. Badges appear in the roster, on every timeline row, in delegation arrows, on approval cards ("prepared by"), on drafts and in the box score.
- **Roster cards** have a colour bar across the top and a live status ("Thinking…", "Ran check_stock", "Waiting on Accounting", "Done"). The agent currently working gets a glow and a small bouncing dot. Agents that weren't called are dimmed as "on the bench", which shows at a glance that delegation was targeted, not "Boss calls everyone".
- **Timeline lanes** are coloured by agent and indented by delegation depth. A Boss → Inventory → Accounting chain reads as three steps of indentation.

**Agent colours are never reused for status.** Gold, green and the live red belong only to the human or the ticket state, so no agent can be mistaken for a status.

## Open, being worked, needs you, resolved

Tickets have one main state plus one flag:

| State | Treatment |
|---|---|
| **Open** | Ivory edge and an outlined "Open" pill. Nothing has happened yet. |
| **Being worked** | The left edge becomes **animated broadcast stripes** in live red, with a spinning "Being worked" pill and a pulsing **LIVE** light in the header. |
| **Resolved** | Green edge, a filled green "Resolved" pill with a check, and quieter text, so done tickets fade back. |
| **Needs you** (flag) | A solid **saffron ribbon** across the bottom of the card: "1 approval waiting on you". It is added to any ticket with a pending payment, including resolved ones. |

When the team finishes a run, the backend marks the ticket `resolved`: the team has done everything it can. The Boss's own status (for example `waiting_approval`) is kept in the ticket note and shown on the Boss's final call. A payment that still needs a human is shown by the saffron ribbon, so "resolved" and "needs you" stay separate. If a run hits a usage limit or errors, the ticket is **not** marked resolved.

A legend at the bottom of the board and a tally in its header ("2 open · 0 live · 1 done") make the states readable without guessing.

## Cash and approvals

**Saffron gold is reserved for one thing: a human decision.** Nothing else on the page uses it, so when gold appears it means *you*.

- **The approval desk** ("Your call") turns gold-tinted when anything is waiting. Each request is a **cream ticket stub** that stands out against the dark room. It has a zig-zag gold band on top, the amount in big italic numbers, what it pays for, the agent's stated reason, and who prepared it.
- **Each card previews the cash impact**: cash now → after paying. If cash can't cover the payment, the card turns pink and warns that the pay tool will refuse it.
- **Approving takes two deliberate steps.** You enter your name once (remembered for next time). **Approve** turns into a green, pulsing **Confirm: pay $840**, which times out after 6 seconds if you don't click. That is the explicit human click `POST /api/approvals/{id}/approve` requires, and agents have no way to press it.
- **The scoreboard** is the largest number on the page. It shows the live `cash_accounts.balance`, plus a small meter for "pending $X → leaves $Y".
- **After a payment, the scoreboard counts down** from the old balance to the new one (for example $3,400.00 to $2,560.00) and flashes red. A red delta line appears underneath: "−$840.00 · was $3,400 · Vendor invoice #501 approved". The approval is also logged in the timeline as a gold **human call** row, so the trace shows exactly where a person stepped in.

## Distinctive details

- **Roster stripe.** The zig-zag band under the header is a woven-textile style chevron built from the **five agent colours**. It works as decoration and as a key to the team. The same zig-zag edges the approval cards in gold, tying "the team" and "your call" together visually.
- **Sports language, used lightly.** "Run the team", "Tip-off", "pass", "reports back", "Final whistle", "Box score", "On the bench". It's playful but always describes real system events: run start, delegation, `agent_end`, `ticket_end`, an uncalled agent.
- **Tool-call chips.** Every MCP call appears as a monospace chip such as `check_stock(sku=CC-TEE-WHITE, size=S, qty_needed=1)`, with an outcome badge (`ok`, `refused`, `blocked`, `error`). The key result fields appear underneath (`qty_on_hand=0 shortage=1`, `can_ship=false lead_days=5`). You can audit the agents' reasoning without opening the JSON.
- **Compact or full trace.** Compact hides rows that repeat the next row ("Chose to call: x" right before the tool call). Full trace shows every audited step.
- **Run clock.** Timestamps are relative to tip-off (`+0:42`), so you can read the pace of the run.
- **Box score with usage.** It shows model calls, tool calls and tokens for the run, plus each agent's summary, blockers and the tools it used. Uncalled agents are listed as "Bench".
- **Drafts stamped NOT SENT.** Customer and vendor drafts sit in the box score under a slanted red rubber stamp, a reminder that nothing leaves the building.
- **Reset needs two clicks** ("Click again to reset") and is disabled while a run is live.
- **Fonts.** *Barlow Condensed* (heavy italic, like jersey numbers) gives the athletic energy. *IBM Plex Sans* keeps the body readable. *IBM Plex Mono* is used for anything that is data: SKUs, tool calls and dates. All fonts are bundled locally, so the dashboard works offline.
- **Motion with a purpose.** Each motion carries information: the live light, the moving stripes, the bouncing dot on the active agent, rows sliding into the timeline, the countdown on the scoreboard. The page respects `prefers-reduced-motion`.

## Why these choices

- **A dark room for watching, a bright card for deciding.** The agents' work is a stream you monitor, which is easier on the eyes in a dark, low-contrast room. The approval is a moment you act on, so it is the one bright, warm object on the screen.
- **Shape and number as well as colour** keep five agents distinct at a glance and for colour-blind users.
- **A sports metaphor** gives energy and a vocabulary people already know (roster, play-by-play, box score, scoreboard) without turning the desk into a sports website. The type and stripes carry the athletic feel. There are no balls, courts or team logos.
- **The Afro-inspired geometry is abstract**: woven chevrons, shape-coded identities and warm earth and saffron accents. It brings personality without stereotypes, flags or generic "African" patterns.
- **A Yale feel without copying Yale**: navy, ivory and a serif-free collegiate weight, but no Yale Blue, crest or "Y". It is the Campus Customs brand.
