# Scout — Expanded Narrative Build Prompt

## Context

You are building a cinematic, single-page product narrative for **Scout**, a tool that turns legacy web portals into programmable APIs. The presentation is a phased animation — one screen, multiple acts — that tells the story of a customer's journey from manual pain to organizational infrastructure.

**You have a companion document called `scout-style-prompt.md`** that defines the complete design system: color tokens, typography, animation principles, spatial grammar, and component patterns. Treat it as your visual bible. Every phase you build must look and feel like it belongs to that system.

The current working file is `universal-api-adapter.html`. It already contains Phase 0 (The Problem) and Phase I (Plugin). You are extending this narrative with new phases that replace or refine the existing Phase I through IV structure.

---

## The New Narrative Arc

The story we're telling is not "here are Scout's capabilities." It's **"here is what happens to you, the customer, from first encounter to organizational transformation."** Each phase is an act in that story.

### Phase 0 — The Problem (already built)

**Headline:** "Your data is trapped behind a login screen."

The stage shows a lone user icon, a single legacy portal, and a dashed red path between them — no Scout present. A stat overlay reads "17 hrs / per year · per report." This is the wound. The audience sits with it for 6.5 seconds.

No changes needed here.

---

### Phase 1 — You Teach Scout (replaces old Phase I — Plugin)

**Core idea:** Demonstrate how absurdly simple it is to teach Scout a workflow. The user speaks in plain language: "Go here. Log in. Select this report. Download it." That's the entire instruction set. No code. No configuration UI. Just natural language.

**Visual concept:** The user icon is on the left. Scout appears in the center (fading in from its dimmed/absent state in Phase 0 — this is Scout's *entrance*). A speech-bubble or text-cascade effect shows the natural language instructions appearing one line at a time, flowing from the user toward Scout:

```
→ "Go to portal.benefitsco.com"
→ "Log in with my credentials"  
→ "Navigate to Reports → Weekly Census"
→ "Download the CSV"
```

These should appear as minimal, monospaced text fragments — not literal speech bubbles. Think terminal output or a quiet typewriter effect. They cascade vertically or arc along the connector path from user to Scout. As each instruction arrives, Scout's border brightens incrementally, as if it's absorbing the knowledge.

The legacy portal on the right should be visible but inactive — Scout hasn't acted yet. This phase is about *teaching*, not executing.

**Headline:** "You teach Scout your portal."
**Subcaption:** "No code. No configuration. Describe the task in plain language — where to go, what to click, what to bring back. Scout handles the rest."
**Scout sub-label:** `learning`

---

### Phase 2 — The Transformation (new)

**Core idea:** The plain-language instructions from Phase 1 transform into a structured workflow. This is the "magic moment" — the raw description becomes an executable, repeatable artifact. That workflow then uploads to a cloud-hosted environment where it lives and runs.

**Visual concept:** The text fragments from Phase 1 (or a representation of them) visually compress/collapse into a compact object — a small card or document icon that represents the workflow artifact. This object then animates upward or along a path toward a **cloud node** that appears above or near Scout's position. The cloud represents Scout's hosted infrastructure — where the workflow is stored and scheduled.

The cloud node should be a simple, elegant shape (not a cartoonish cloud) — perhaps a rounded rectangle with a subtle cloud icon or the word "hosted" beneath it. It uses --surface background with --scout border, glowing softly once the workflow arrives.

A **schedule indicator** (clock icon or cron-like label "Every Monday, 6:00 AM") should appear near or within the cloud, signaling that this workflow now runs autonomously.

**Headline:** "Your words become a workflow."
**Subcaption:** "Scout transforms your description into a repeatable, scheduled workflow — hosted, monitored, and ready to run without you."
**Scout sub-label:** `engine`

---

### Phase 3 — Delivery (new)

**Core idea:** The workflow executes, and the output lands where the user actually needs it — their email inbox, an SFTP folder, a shared drive. The user doesn't have to go get it. The data comes to them.

**Visual concept:** The cloud/Scout engine activates. A connector flows from Scout rightward to the legacy portal (the portal briefly glows as Scout interacts with it), then data flows *back* through Scout and out the left side toward **delivery destination nodes**. These replace the "modern system" nodes from the old design and represent concrete delivery targets:

- 📧 Email Inbox
- 📁 SFTP Folder  
- ☁️ Cloud Storage (or a third destination of your choice)

The key visual beat is the **direction reversal**: data flows right (Scout → portal) to fetch, then left (Scout → delivery) to deliver. This could be shown as a two-phase connector animation — right-side connectors light up first, then left-side connectors light up with a brief pause between.

The portal node should show a subtle "download" animation (a small arrow or pulse) when Scout extracts data from it.

**Headline:** "The report finds you."
**Subcaption:** "Every Monday morning. In your inbox. On your SFTP server. Wherever you need it — without opening a browser."
**Scout sub-label:** `delivery`

---

### Phase 4 — Internal Discovery (new)

**Core idea:** Someone on the engineering or IT team notices what's happening and realizes this automation could serve the whole organization. This is the moment of internal evangelism — one person's workflow becomes a team's opportunity.

**Visual concept:** This is the most narratively ambitious phase. The stage should shift to show a **new persona** appearing on the left side — not the original user, but a developer or IT figure (use a different icon: perhaps a code brackets symbol `</>` or a terminal icon `▸_` inside a node). This figure "observes" the existing Scout + portal + delivery flow that's already running.

A **discovery indicator** should appear — perhaps a subtle highlight or spotlight effect that draws attention to the Scout hub, as if this new persona is seeing it for the first time. A small annotation or label could appear near the new persona: something like `"We could use this."` in italic, muted text — a nod to the discovery moment without the meme. Keep it restrained and typographic, not visual-gag.

The existing flow (cloud → Scout → portal → delivery) should be running in the background in a subdued/steady state, showing that automation is already operational.

**Headline:** "Your team sees the opportunity."
**Subcaption:** "What started as one person's workflow becomes an engineering conversation. If Scout can fetch this data on a schedule — could it serve it as an API?"
**Scout sub-label:** `catalyst`

---

### Phase 5 — The API Switch (new)

**Core idea:** The IT team flips a switch and Scout exposes the workflow as a proper API endpoint. The browser-based automation is now indistinguishable from a native integration. This is Scout's thesis statement made tangible.

**Visual concept:** The developer/IT persona from Phase 4 interacts with Scout — a visual "switch" or "toggle" element appears on or near Scout's hub. When activated (with a satisfying visual beat — border color intensifying, maybe a brief expansion), a new element appears: an **API endpoint label** that materializes below or beside Scout. Something like:

```
GET /api/v1/census-report
```

rendered in monospaced type, --scout colored, with a subtle glow. This is the "product shot" — the artifact that represents everything Scout has built.

Scout's hub should grow slightly (as in the old Phase III) to visually represent its expanded role. The sub-label transitions to `api`.

**Headline:** "One toggle. A new API."
**Subcaption:** "No backend to build. No integration to maintain. Scout serves the data as a clean API endpoint — the one the legacy system never offered."
**Scout sub-label:** `api`

---

### Phase 6 — Integration at Scale (new)

**Core idea:** Multiple systems now call Scout's API endpoints. Data flows bidirectionally across the organization. This is the "zoom out" moment — what was one person's workflow is now infrastructure.

**Visual concept:** This is the full-expansion phase. Multiple modern system nodes appear on the left (ERP, Payroll, Custom App — reuse the existing node designs). Multiple legacy portals are visible on the right. All connectors are active and flowing in --scout orange. Flow dots animate along every path.

Scout is at full size in the center, with the sub-label `infrastructure`. The API endpoint label from Phase 5 is still visible, possibly joined by 1-2 additional endpoints stacked beneath it:

```
GET /api/v1/census-report
GET /api/v1/benefits-elections
POST /api/v1/employee-sync
```

The visual should feel like a **living nervous system** — quiet, constant data flow between all nodes through Scout as the central hub. No single path is highlighted; the emphasis is on the totality of the connected ecosystem.

**Headline:** "Every system gets an API."
**Subcaption:** "Payroll pulls census data. The ERP syncs benefits elections. Your custom app pushes employee records. None of them know a browser is involved."
**Scout sub-label:** `infrastructure`

---

## Build Instructions

Each phase should be built as a **self-contained addition** to the existing `universal-api-adapter.html` file. That means:

1. **CSS**: Add new styles scoped to the phase (new classes, keyframes) without modifying existing styles. Use the established CSS variable system.
2. **HTML**: Add any new DOM elements needed (new nodes, overlays, text elements) to the existing `.stage` container.
3. **JavaScript**: Add the new phase object to the `phaseData` array and update `showPhase()` to handle any new visual behaviors (text cascades, directional flow, persona swaps, API labels, etc.).
4. **Phase dots**: Update the navigation dots to reflect the total phase count.

The phases should be built **one at a time** so we can review and refine each before moving to the next. Start with Phase 1 (You Teach Scout), since it's the immediate successor to the existing Phase 0.

When building animations, favor **CSS transitions triggered by class addition** over JavaScript-driven animation. Use `await wait(ms)` patterns for sequencing within `showPhase()`, consistent with the existing controller pattern.

---

## Headline & Copy Reference

| Phase | Label | Headline | Scout Sub-Label |
|---|---|---|---|
| 0 | The Problem | Your data is trapped behind a login screen. | *(hidden)* |
| 1 | You Teach Scout | You teach Scout your portal. | learning |
| 2 | The Transformation | Your words become a workflow. | engine |
| 3 | Delivery | The report finds you. | delivery |
| 4 | Internal Discovery | Your team sees the opportunity. | catalyst |
| 5 | The API Switch | One toggle. A new API. | api |
| 6 | Integration at Scale | Every system gets an API. | infrastructure |