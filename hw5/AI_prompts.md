# AI Prompts — Assignment 5: Campus Customs Multi-Agent Operations

This is a running log of the prompts I gave my AI coding assistant, added as I worked through each problem.

---

## Project Setup (context before Problem 1)

**Prompt:**

> I'm working on Assignment 5, Campus Customs Multi-Agent Operations....Work on HW 5 folder
>
> The setting is Campus Customs, and I need to build an agentic operations system for the shop. Open tickets land on a board for things like customer orders, rent, unpaid bills, discount requests, and other operational issues.
>
> The assignment has three pieces that need to work together:
> 1. an MCP server
> 2. a FastAPI backend running a multi-agent team
> 3. a React dashboard where a human can watch the agents work and approve requests when needed
>
> The agent team has full connectivity, so any agent can delegate work to any other agent. The main agents are:
>
> - Boss: reads each ticket, decides which agent should work on it, coordinates where needed, and makes final calls
> - Inventory: checks stock by SKU and size, identifies shortages, and figures out which vendor can restock
> - Accounting: monitors cash and invoices, checks margins, and prepares payments or purchase orders for human approval
> - Facilities: handles the physical shop side, including leases, rent, and similar issues
> - Customer Service: drafts messages for customers
>
> I'll give you the assignment one problem at a time. Only work on the problem I give you and don't jump ahead. I'll describe each problem in my own words, and I want us to build on the same project as we go.
>
> The provided data pack contains:
>
> data/campus_customs.db
>
> This is the original shop database. It contains tables including: desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, invoices
>
> Our tools will update the database as tickets get resolved.
>
> Before doing work that changes the database, make a working copy called: data/campus_customs_new.db
>
> Point the MCP server and backend to that working copy. Keep data/campus_customs.db untouched so I can always reset to the original state.
>
> There are several shop rules that need to be treated as hard constraints throughout the assignment:
>
> - desk.date_today is the shop's definition of "today." Use that field when deciding whether something is overdue.
> - Vendor lead times must come from the vendors table. Do not invent lead times.
> - A vendor will not ship new product while there is still an open unpaid invoice with that vendor.
> - Any payment requires human approval before it is executed. This is important for the rubric, so do not bypass the approval step.
> - If an approved payment is actually made, update the relevant database table or tables so the database reflects what happened.
> - If there is not enough cash to make a payment, the pay tool must refuse it. Never allow a negative cash balance.
> - Cash only goes out in this homework. There is no revenue model, so do not invent incoming cash.
> - Before we do a full run to resolve the tickets, reset the working database back to the original values so the run starts from a clean state.
> - Do not actually email customers or contact real vendors. Any customer messages, vendor communication, or similar outreach should remain as drafts on the board.
>
> For every AI call in this assignment, use my PORTKEY_API_KEY through Portkey.
>
> Use only: gpt-6-luna
>
> Do not use any other model anywhere in the code or during runs. The assignment specifically checks this and points can be deducted if another model appears.
>
> As we work, keep the overall architecture consistent across the MCP server, FastAPI multi-agent backend, React dashboard, database, and approval flow. Do not create parallel versions of things unless a later problem explicitly requires it.
>
> The final submission will be a public GitHub repository. The last problem will give the exact required file tree, so for now keep the project organized and avoid unnecessary files that could make the final structure messy.
>
> I'll send Problem 1 next.

---

## Problem 1 — Vibe Coder Prompts

**Prompt:**

> I'm now on Problem 1: Vibe coder prompts.
>
> Create AI_prompts.md at the start of the project and keep updating it as I work through the assignment.
>
> I want one section for each problem. Each problem section should include:
> - the problem number and title
> - at least one prompt I actually gave you, kept in my own words as much as possible
> - if I needed a follow-up prompt, include that too and add one short sentence explaining what was missing after the first attempt
>
> This file should reflect the actual prompts I give you as we work, not something reconstructed at the end.
>
> Create the Problem 1 section now and log this prompt there. Keep maintaining AI_prompts.md automatically when I give you the later problems.

---

## Problem 2 — Study the Campus Customs Database

**Prompt:**

> I'm now on Problem 2: Study the Campus Customs database.
>
> Open data/campus_customs.db and actually inspect the database. I want you to look through every table and the real fields in each table rather than guessing the schema.
>
> The tables I expect you to cover are: desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, invoices
>
> Also study the three open tickets in the database and understand how each ticket connects to the other tables it will need.
>
> Before we make any changes to the shop data, copy the original database to: data/campus_customs_new.db
>
> The original data/campus_customs.db should stay untouched. The working copy is what the later MCP server and backend will use.
>
> Start: output/harness.md
>
> For every table, include:
> - the table name
> - its actual fields from the database
> - one short, specific explanation of why that table matters to the agent team
>
> Please make sure all nine tables are covered and that the fields come from the actual database. Do not invent fields or leave tables out.
>
> Also make sure data/campus_customs_new.db actually exists before finishing this problem.

---

## Problem 3 — Build the MCP Server

**Prompt:**

> I'm now on Problem 3: Build the MCP server.
>
> Create an MCP server inside: mcp_server/
>
> Use FastMCP and have it work with: data/campus_customs_new.db
>
> I do not need to connect or run the MCP server yet. That comes in the next problem.
>
> Every agent later in the assignment will use this MCP server for shop information and actions, so start with three tools that we clearly need to work on the three open tickets already in the database.
>
> Choose the tools based on the actual tickets and database rather than making generic tools just to fill space. Give them clear names and make sure they only return real information from the database. Do not invent shop data.
>
> Add these three tools to output/harness.md. For each tool, explicitly document:
> - the tool name
> - which database table or tables it reads
> - which open ticket it helps unlock, specifically ticket 101, 102, or 103
> - one specific sentence explaining why that tool is the right tool for that ticket
>
> Do not just write vague descriptions like "reads inventory." I want the explanation tied to what that particular ticket actually needs.
>
> Also create: mcp_server/README.md
>
> Keep it short, but explain:
> - what this MCP server is for
> - that it uses data/campus_customs_new.db
> - the three tools currently available and what they do
>
> Build the server and files for this problem, but do not move ahead to connecting it to Claude Code yet.

---

## Problem 4 — Add the MCP Server to My Vibe Coder and Test Each Tool

**Prompt:**

> I'm now on Problem 4: Add the MCP server to my vibe coder and test each tool.
>
> Connect the local MCP server we just built to this Claude Code project so you can actually call its tools.
>
> Save the project MCP connection configuration at the project root as: .mcp.json
>
> Make sure the configuration points to our real MCP server rather than creating a fake or separate implementation.
>
> Once the connection is working, test all three MCP tools individually through Claude Code.
>
> Save the evidence from those tests to: output/mcp_smoke.json
>
> For each of the three tools, include:
> - the prompt I used to ask Claude Code to use the tool
> - the exact MCP tool name
> - a short version of the tool output
>
> The returned values must match the actual values in data/campus_customs_new.db. Please verify them against the database rather than fabricating example outputs.
>
> Make sure all three tools are tested and that .mcp.json and output/mcp_smoke.json both exist before finishing.

**Tool-test prompts (sent in a new Claude Code session opened in the `HW 5` folder):**

> Use the campus-customs MCP tool check_stock to check whether we have 1 CC-TEE-WHITE in size S for ticket 101.

> Use the campus-customs MCP tool get_rent_status to look up lease 1 for ticket 102.

> Use the campus-customs MCP tool quote_bulk_order to price 20 CC-HOOD-NAVY hoodies at a 15% discount for ticket 103.

**Follow-up prompt:**

> We are continuing Problem 4. Now that all three MCP tools have been called successfully, create output/mcp_smoke.json using the real results from those calls.
>
> For each tool include:
> - the prompt I used
> - the exact MCP tool name
> - a short version of the actual tool output
>
> Use the real outputs you just received. Do not make up or reconstruct test results.
>
> Also verify those returned values against data/campus_customs_new.db before finishing. If anything does not match the database, flag it and fix the underlying issue rather than changing the evidence.
>
> Make sure output/mcp_smoke.json contains all three successful tool tests and is valid JSON.

*What was missing after the first attempt:* the MCP tools weren't available in the original session because it had been opened in the course folder, so `output/mcp_smoke.json` couldn't be written until the tools were called from a session opened in `HW 5`.

---

## Problem 5 — Build the Agent Team and Grow the MCP Tools

**Prompt:**

> I'm now on Problem 5: Build the agent team and grow the MCP tools.
>
> Build the Campus Customs multi-agent team using PydanticAI.
>
> I need five clearly separate agents: Boss, Inventory, Accounting, Facilities, Customer Service
>
> They should have full connectivity, meaning an agent can delegate work to another agent when that makes sense. Build the agent loops and delegation structure needed for this to work.
>
> Keep the backend organized under backend/. Put the shared structured data types in: backend/models.py
>
> Put the system prompts in: backend/prompts/
>
> I need one prompt file for each agent: backend/prompts/boss.md, backend/prompts/inventory.md, backend/prompts/accounting.md, backend/prompts/facilities.md, backend/prompts/customer_service.md
>
> Make each agent prompt detailed and specific to that agent's actual job. Do not use generic one-paragraph role descriptions. Include the shop rules that matter to each role in natural language.
>
> The Boss should understand the overall ticket, decide who should work first, coordinate handoffs, and make final calls.
>
> Inventory should understand inventory by SKU and size, shortages, vendor lead times from the vendors table, and that a vendor cannot ship new product while an invoice with that vendor is still open and unpaid.
>
> Accounting should understand cash, invoices, margins, payments and purchase orders. Any payment must require human approval before money moves. It must refuse a payment if there is not enough cash and must never allow a negative cash balance. Cash only goes out in this assignment, so do not invent revenue.
>
> Facilities should handle leases, rent, and other physical shop issues. When something depends on whether it is overdue, use desk.date_today as the shop's definition of today.
>
> Customer Service should draft messages for customers when needed, but must never actually email or contact them.
>
> Also keep the general rule that we do not contact real vendors. Any vendor communication should stay as a draft.
>
> For every AI call across all five agents, use my PORTKEY_API_KEY through Portkey and use only: gpt-6-luna
>
> Do not put any other model in the code, configuration, fallbacks, or test runs.
>
> Add any additional tools these agents need to the existing MCP server so they can actually work on the open tickets.
>
> Very important: shop facts and shop database actions should continue to come through the MCP server using data/campus_customs_new.db. Do not create a second set of local database helper tools inside the backend that bypasses MCP.
>
> Also wire the agent team to append its activity to: output/audit_trail.json
>
> I want real auditability of the agent loops. Each agent-loop step should record enough to understand later what happened, such as the ticket, agent, step or time, what it decided or said, delegations, any MCP tool used and its arguments, a short result, and how that step ended. Append new entries as the agents run. Do not wipe the file on each run.
>
> Update output/harness.md with:
> - all five agents and what each one does
> - every MCP tool currently available, including tools added in this problem
> - which database table or tables each tool uses
> - a safety section with the guardrails a real business would need when agents can interact with customers and money
> - practical limits that control token usage and prevent runaway agent loops
>
> Also update mcp_server/README.md so its tool list matches the MCP server we actually have after this problem.
>
> Implement the full Problem 5 setup and check that the five agents, five prompt files, MCP tools, audit mechanism, model restriction, and harness documentation all line up.

---

## Problem 6 — Plan the Three Tickets

**Prompt:**

> I'm now on Problem 6: Plan the three tickets.
>
> Before running the full backend, I want to write down what I expect the multi-agent team to do on each of the three open tickets.
>
> Create: output/desk_tickets.html
>
> This should be a standalone page that I can double-click and open in a browser.
>
> Give it separate tabs for: Ticket 101, Ticket 102, Ticket 103, Cash, Reflection
>
> For now, leave the Cash and Reflection tabs blank or with a simple "coming later" note because later problems will fill those in.
>
> For each of the three ticket tabs, create an Expected section. Also leave a clear place for an Actual section that we will fill after we run the agents, but do not fill Actual yet.
>
> Base the Expected plan on the actual ticket and database information we already studied.
>
> For each ticket, explain:
> - which agent the Boss should call first and why that agent is the logical starting point
> - the agent-to-agent delegations I expect after that
> - which MCP tools I expect the team to use
>
> I want purposeful delegation. Do not write "Boss calls everyone" or send all five specialists into every ticket. The plan should reflect what that particular ticket actually needs.
>
> Make the page clean and readable because later we will use the same file to compare Expected versus Actual behavior.

---

## Problem 7 — Backend Routes

**Prompt:**

> I'm now on Problem 7: Backend routes.
>
> Build the FastAPI backend that the React dashboard will call.
>
> Use: backend/main.py
>
> Add clear routes that let the frontend do all of the following:
>
> - get the three tickets and whether each one is currently open or resolved
> - send a ticket id and start the multi-agent team on that ticket
> - get recent agent events so the dashboard can refresh and show what each agent is saying, doing, delegating, and which MCP tools are being used
> - approve a payment or purchase after a human explicitly clicks approve
> - get the current checking balance from cash_accounts
> - reset the working database back to the original database values for a clean run
>
> Keep the payment approval rule strict. Agents can prepare a payment or purchase request, but they must not silently execute it. The approval endpoint is where a human approval allows the actual cash-changing action to happen.
>
> The backend should continue using the architecture we already built rather than creating a separate shop-data layer that bypasses the MCP setup.
>
> For a reset, restore data/campus_customs_new.db from the untouched original data/campus_customs.db so we can repeat the exercise from a clean starting point.
>
> I should be able to start the backend from inside backend/ with:
>
> uvicorn main:app --reload --port 8000
>
> That should expose it at:
>
> http://localhost:8000
>
> Also update output/harness.md with one short line for every API route, including the route or URL and what it does.
>
> Implement the routes and make sure the approval route is the only path that actually executes a prepared payment or purchase.

---

## Problem 8 — Agent Dashboard

**Prompt:**

> I'm now on Problem 8: Agent dashboard.
>
> Build the frontend inside: frontend/
>
> Use React + Vite + TypeScript and connect it to the FastAPI backend from Problem 7 at: http://localhost:8000
>
> The dashboard needs to actually function as the human operations desk, not just be a static mockup.
>
> At minimum, I need it to:
> - list all three tickets
> - let me choose a ticket and start the agent team on it
> - show each agent and what they are saying or doing while the ticket is running
> - make the different agents easy to distinguish
> - mark the ticket resolved when the run finishes
> - show a short summary of what each agent did on that ticket
> - clearly surface a payment or purchase that needs human approval and give me an approve action
> - show the current checking balance
> - refresh the checking balance after an approved payment so I can see the cash actually drop
>
> On the backend, configure CORS so the Vite frontend can call it. The normal Vite origin will be: http://localhost:5173
>
> I should be able to start the frontend using: npm run dev
>
> Put real effort into the visual design. I do not want a stock Vite screen, a generic admin dashboard, or something that looks like a default AI-generated SaaS template.
>
> Make the visual identity feel like me: Afro, sporty, nerdy, polished, and a little playful. I like interfaces that feel smart and data-driven but still have personality and energy.
>
> For the dashboard, aim for:
> - a clean and information-dense operations desk that still feels easy to scan
> - strong visual hierarchy so I can immediately tell what is open, resolved, waiting on approval, or actively being worked on
> - distinct visual identities for the five agents so I can quickly tell who is speaking or acting
> - some athletic energy in the layout and typography without making it look like a sports website
> - subtle Afro-inspired personality or geometric detail where it fits, but keep it tasteful and modern rather than using obvious stereotypes, flags, or generic "African" decoration
> - nerdy details that make the system feel intelligent, like useful status indicators, timelines, activity traces, tool-call chips, or compact data displays
> - a polished Campus Customs/Yale feel without simply copying Yale branding
>
> The payment approval should feel especially important and visually different from normal agent activity because it is a human decision point.
>
> The cash balance should also be easy to notice, especially before and after an approved payment.
>
> Use motion, icons, badges, or small interaction details if they genuinely improve the experience, but do not over-design it or make the dashboard harder to use.
>
> I want the final product to feel like a real operations control room I would enjoy using, not a class project template.
>
> Also create: output/design.md
>
> Explain the design choices, including:
> - the overall layout
> - how the five agents look or read differently
> - how open versus resolved tickets are shown
> - how cash and approval requests are surfaced
> - any creative details that make this feel like a distinctive human operations desk rather than a default dashboard
> - why you made those choices
>
> Run the frontend and backend together and make sure the dashboard is actually calling the real routes rather than showing hardcoded demo data.

---

## Problem 9 — Resolve the Tickets

**Prompt:**

> I'm now on Problem 9: Resolve the tickets.
>
> This is the full run, so before doing anything else, reset: data/campus_customs_new.db back to the original values from: data/campus_customs.db
>
> I want this run to start completely clean.
>
> After the reset, record the starting checking balance from the working database.
>
> Then run tickets 101, 102 and 103 through the actual dashboard and agent team until all three are resolved.
>
> Keep the human approval rule real. If a payment or purchase needs approval, do not silently approve it or simulate my approval. Pause at that point and surface the approval clearly so I can approve it through the dashboard before the money moves.
>
> As the three tickets run, make sure the real activity continues appending to: output/audit_trail.json
>
> Then update the existing: output/desk_tickets.html
>
> For each Ticket 101, 102 and 103 tab, keep the Expected section from Problem 6 and fill in the Actual section using what really happened in this full run.
>
> For each Actual section, include:
> - which agents actually worked on the ticket
> - what agent-to-agent delegations actually happened
> - which MCP tools were actually used
> - the outcome
>
> This should make it easy to compare Expected versus Actual.
>
> Now fill the Cash tab in the same HTML file. I need exact cash accounting:
> - starting checking balance immediately after the reset
> - for Ticket 101, how cash changed and exactly why, including the payment or purchase and dollar amount
> - the same for Ticket 102
> - the same for Ticket 103
> - ending checking balance
>
> The ending balance must exactly match cash_accounts in data/campus_customs_new.db. Please calculate and verify the math directly rather than trusting what the UI displays.
>
> Also create: output/resolved_tickets.json
>
> For each of the three tickets include:
> - ticket id
> - final status
> - a short outcome
> - what each agent contributed
> - any human approvals involved
>
> Also create: output/resolved_board.html
>
> This should be a standalone page I can double-click. Include an actual screenshot of the React board showing the resolved state for each ticket, so I need three real resolved-board screenshots, one each for tickets 101, 102 and 103. Do not use fake placeholder screenshots.
>
> Finally, finish output/harness.md so it now fully covers:
> - all database tables
> - all MCP tools
> - all five agents
> - all FastAPI routes
> - the React dashboard
> - the safety and approval rules
> - relevant limits and implementation constraints
>
> Before finishing, verify that all three tickets are resolved, the actual database reflects what happened, the cash math is exact, the audit file contains real runs, and every required output exists.

**Approval replies during the run.** I approved each payment myself in the dashboard, then replied so the run could continue:

> Approved, A

*Context:* after ticket 101's first run I approved invoice 501 ($840) in the dashboard and chose option A, re-running 101 so the team would order the tee once the vendor was unblocked.

> approved

*Context:* I approved the $8 tee purchase order in the dashboard. The re-run before it had missed ordering the tee, so the assistant clarified the Boss and Accounting prompts before the run that produced this order.

> approved

*Context:* I approved ticket 102's $2,400 rent payment in the dashboard. Ticket 103 then ran and needed no approval.

---

## Problem 10 — Reflection

**Prompt:**

> I'm now on Problem 10: Reflection.
>
> Go back to: output/desk_tickets.html
>
> and fill the existing Reflection tab. Do not create a separate reflection markdown file.
>
> I want this to sound like me thinking through what actually happened, not like a generic AI essay. Keep it thoughtful, specific, analytical and natural. I'm happy for it to have a little personality, but the substance matters more than polished prose.
>
> Use the actual Ticket 101, 102 and 103 tabs, the Expected versus Actual sections, the Cash tab, resolved outputs and audit trail as evidence.
>
> Be detailed and thorough and cover all of these:
>
> 1. Evaluate how the agents performed on Ticket 101, Ticket 102 and Ticket 103 separately. Explain what worked, what did not, and why.
>
> 2. For each ticket, compare the Actual delegation and workflow against the Expected plan I wrote before the run. Call out where the team behaved as expected and where it differed.
>
> 3. For each ticket, mention any human approval that was required or explain if none was required, and how that approval affected the workflow.
>
> 4. Looking at the system as a whole, explain what parts would actually have been simpler to solve with one agent plus tools rather than a multi-agent team, and why.
>
> 5. Describe three realistic new problems Campus Customs could face that the current agent team could solve using the agents and MCP tools we already built. Be specific about which agents and tools would handle each one.
>
> 6. Describe three realistic new Campus Customs problems that the current system could not solve with the tools we have. For each one, explain what additional MCP tool or tools would be needed and whether we would need a new agent or could extend one of the existing agents.
>
> Tie the reflection back to the actual app and the real tickets throughout. Use ticket IDs, agent names, tools, approvals and cash outcomes where relevant. Avoid generic statements about the benefits of multi-agent AI that could have been written without running this project.
>
> Keep the writing in my natural style: sharp, curious, analytical, and conversational. I tend to notice both the operational logic and the little things that make a system feel smart or clunky. Avoid corporate filler, generic AI language, and overly polished prose. No em dashes.
