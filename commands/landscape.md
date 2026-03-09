---
description: "Run a structured landscape analysis of a product or website"
argument-hint: "<url> --depth <light|standard|deep> [--output <path>] [--states \"...\"] [--flows \"...\"]"
allowed-tools:
  - "mcp__plugin_scout_scout__*"
  - "Read"
  - "Write"
  - "Bash"
  - "Glob"
  - "AskUserQuestion"
---

Run a structured landscape analysis on a product or website. Produces a four-pillar report (Language & Terminology, Product & Feature Profile, Design & UX Context, Behavioral Flows) combining text extraction and screenshots. The report becomes a reference artifact for downstream design work.

**Design doc:** `docs/plans/2026-03-04-landscape-command-design.md`
**Brief:** `docs/features/LANDSCAPE_PLUGIN_BRIEF.md`

## Argument Parsing

Parse the user's argument string. Extract:

- **url** (required) — the starting URL. If missing, ask the user with AskUserQuestion: "What URL should I analyze?"
- **--depth** (required) — `light`, `standard`, or `deep`. If missing, ask the user with AskUserQuestion:
  - "What depth level for this analysis?"
  - Options: "Light — content websites, blogs (fastest)" / "Standard — established products, 1-2 flows" / "Deep — complex products, 2-3 flows, full observations (slowest)"
- **--output** (optional) — overrides default output path
- **--states** (optional) — natural language hints for Pillar 3 screenshot states. These are navigation targets interpreted by you, not structured identifiers. Example: `"board populated, card detail open, inline creation"`
- **--flows** (optional) — natural language hints for Pillar 4 user flows. Same interpretation model. Example: `"create work item, move item between stages"`

### Product Name Derivation

Extract the product name from the URL domain:
1. Parse the hostname from the URL
2. Strip common subdomain prefixes: `www.`, `app.`, `workspace.`, `board.`, `portal.`, `my.`
3. Take the primary domain name (before the TLD): `trello.com` → `trello`, `stmichael-orthodox.org` → `stmichael-orthodox`
4. If `--output` is provided, use that instead for the directory path (but still derive the product name for the report title)

### Depth Level Reference

The depth level determines scope across all phases:

| Depth | Pillar 1 | Pillar 2 | Pillar 3 | Pillar 4 |
|-------|----------|----------|----------|----------|
| **Light** | Full | Light (content types, navigation only) | Light (layout model + screenshots, no observation table) | Skip entirely |
| **Standard** | Full | Full | Standard (full observation table) | 1-2 flows |
| **Deep** | Full | Full with behavioral depth | Deep (full table + responsive + accessibility) | 2-3 flows with screenshot sequences |

### Screenshot Matrix

Which screenshots to capture at each depth level:

| Screenshot | Light | Standard | Deep |
|-----------|-------|----------|------|
| Primary view (populated) | Required | Required | Required |
| Navigation / sidebar | Required | Required | Required |
| Detail view | — | Required | Required |
| Creation flow | — | Required | Required |
| Empty state | — | — | Attempt |
| Alternative views | — | — | Attempt |
| Mobile view | — | — | Attempt |
| Settings / config | — | — | Attempt |

"Attempt" means try to navigate there; if the state can't be reached, skip it and note why.

## Failure Resilience — Global Rule

**At every step in every phase:** if a tool call fails, a page doesn't load, a state can't be reached, or data can't be extracted — **skip and document**. Insert a `[SKIPPED: brief reason]` marker in the relevant report section and continue to the next step. A partial report with documented gaps is always more useful than an aborted run with no output. Never abort the entire analysis due to a single step failure.

---

## Phase 0: Setup

**Step 1.** Set the output directory:
- Default: `./landscape/{product-name}/`
- If `--output` is provided, use that path instead
- Check if the directory already exists using Glob for `landscape/{product-name}/*`. If files exist, warn the user: "Existing landscape report for {product-name} will be overwritten."

**Step 2.** Create the output directory structure via Bash:
```bash
mkdir -p landscape/{product-name}/screenshots
```

**Step 3.** Read the report template using the Read tool:
- Path: Use the `${CLAUDE_PLUGIN_ROOT}` variable to locate the plugin directory
- File: `commands/landscape-template.md` relative to the plugin root
- Store the template content in memory for Phase 5

**Step 4.** Initialize a running log of pages visited (for the metadata section).

---

## Phase 1: Initial Reconnaissance

**Step 5.** Call `launch_session` with `url` set to the target URL and `headless=false`.

**Step 6.** Call `scout_page_tool` with the session_id to get the structural overview.

**Step 7.** Assess the page state from the scout report. Look for **absence of product content** — not login page detection. Indicators of a login wall:
- Page has very few interactive elements (just 1-2 form inputs and a button)
- No navigation structure (no sidebar, no menu, no tabs)
- No product objects visible (no cards, messages, posts, content items)
- Page title contains "login", "sign in", or "authenticate"

If the page appears to be a login wall: inform the user — "This page appears to require authentication. Please log in first using Scout's browser, then re-run `/landscape` with the authenticated page URL." Close the session and stop.

If the page has meaningful content, continue.

**Step 8.** Call `find_elements` with broad queries to get an initial vocabulary pass:
- Query for navigation elements: `find_elements` with `element_types=["nav", "a"]` and `max_results=50`
- Query for headings: `find_elements` with `element_types=["h1", "h2", "h3"]`
- Query for buttons and inputs: `find_elements` with `element_types=["button", "input"]`

Record all element text, labels, placeholders, and aria-labels. These are raw material for Pillar 1.

**Step 9.** Call `take_screenshot_tool` to capture the **Primary View (populated)** — the single most important screenshot. Use Bash to copy the screenshot file to `{output-dir}/screenshots/pillar-3-primary-view-populated.png` using the `file_path` from the response.

Add the starting URL to the pages-visited log.

---

## Phase 2: Text Extraction (Pillars 1 & 2)

### From the Live UI

**Step 10.** Run additional `find_elements` queries with varied search terms to extract vocabulary:
- Navigation labels, menu items, tab names
- Button labels and form field labels
- Status indicators, badge text, category names
- Tooltip text (if discoverable via element attributes)

Combine with Step 8 results. Deduplicate. Organize into:
- **Domain nouns** — the objects/entities in this product's world
- **Domain verbs** — action words, what users can do
- **User-facing labels** — exact text users see on buttons, menus, forms

**Step 11.** Enhancement pass (not required): Call `execute_javascript` with a **read-only** DOM query script to systematically extract visible text content. Example approach:

```javascript
// Read-only — no mutations, no event dispatching
Array.from(document.querySelectorAll('button, a, label, [aria-label], [placeholder], h1, h2, h3, h4, [role="tab"], [role="menuitem"]'))
  .map(el => ({
    tag: el.tagName,
    text: el.textContent?.trim()?.substring(0, 100),
    ariaLabel: el.getAttribute('aria-label'),
    placeholder: el.getAttribute('placeholder')
  }))
  .filter(e => e.text || e.ariaLabel || e.placeholder)
```

If JS execution fails (CSP violation, error, empty result), fall back to Step 10's `find_elements` results. This is an enhancement, not a requirement — do not treat failure as an error.

**Step 12.** If there are navigable sub-sections visible (tabs, sidebar items, secondary pages), navigate to 1-2 of them and call `scout_page_tool` + `find_elements` on each to capture vocabulary from different product areas. Add each visited URL to the pages-visited log.

### From Docs / Help Center

**Step 13.** Attempt to navigate to the product's supplementary pages to fill in Pillar 2 data. Try these paths in order (stop after 2-3 successful hits):
- `{domain}/help` or `{domain}/support`
- `{domain}/docs` or `{domain}/documentation`
- `{domain}/features`
- `{domain}/about`

For each page that loads successfully (not 404, not redirect to login):
- Call `scout_page_tool` + `find_elements` to extract feature names, product descriptions, terminology
- Record findings for Pillar 2: product snapshot, feature names, "what's unique"
- Add URL to pages-visited log

If all docs pages fail (404, login redirect, empty content), note `[SKIPPED: docs/help pages not publicly accessible — Pillar 2 populated from UI observation only]` and continue.

**Step 14.** Navigate back to the original starting URL. This is a **mandatory state reset** before Phase 3.

### Source-per-element reference

Use this mapping to decide where each Pillar 1/2 element comes from:

| Report element | Primary source | Fallback |
|---------------|---------------|----------|
| Domain nouns/verbs | Live UI (Steps 10-11) | — |
| User-facing labels | Live UI (Steps 10-11) | — |
| Feature names | Docs/help (Step 13) | Infer from UI navigation structure |
| Terminology patterns | Both — UI shows usage, docs explain metaphors | UI-only observation if docs unavailable |
| Product snapshot | Marketing/about page (Step 13) | Compose from UI observations |
| How it works | Both — conceptual model from UI, articulated in docs | Infer from navigation + scout structure |
| Core features | Docs/help (Step 13) | Infer from UI navigation + element discovery |
| Domain conventions | Live UI — observed behaviors | — |
| What's unique | Marketing page (Step 13) | Note as needing manual input |

---

## Phase 3: Visual Capture (Pillar 3)

Capture screenshots at UI states determined by the depth level and the screenshot matrix above.

**The primary view screenshot was already captured in Step 9.** Do not re-capture it.

**Step 15.** Capture the **Navigation / sidebar** screenshot:
- Look for sidebar, top navigation, hamburger menu, or tab bar
- If a sidebar needs to be opened (hamburger/toggle), click to open it first
- Call `take_screenshot_tool`, copy to `{output-dir}/screenshots/pillar-3-navigation-sidebar.png`

**Step 16.** (Standard and Deep only) Capture the **Detail view** screenshot:
- When `--states` includes a detail state hint, navigate to it
- When `--states` is absent, use heuristic: look for list/grid items in the scout report. Click the first substantive item (a card, post, message, list entry) to open its detail view.
- Call `scout_page_tool` to verify the detail state was reached (look for modal overlay, new content area, URL change)
- Call `take_screenshot_tool`, copy to `{output-dir}/screenshots/pillar-3-detail-view.png`
- Record observations: Is this a modal overlay or full page navigation? Did the URL change? What information is shown at the detail level vs. the list level?

**Step 17.** (Standard and Deep only) Capture the **Creation flow** screenshot:
- When `--states` includes a creation hint, navigate to it
- When `--states` is absent, use heuristic: look for elements with text matching "New", "Create", "Add", "+" or similar creation triggers
- Click to trigger the creation UI
- Call `scout_page_tool` to verify creation state (form, modal, inline input)
- Call `take_screenshot_tool`, copy to `{output-dir}/screenshots/pillar-3-creation-flow.png`
- Record observations: Is creation inline, modal, or full-page? Progressive disclosure? What fields are required?

**Step 18.** (Deep only) Attempt additional screenshots — each wrapped in try-or-skip:

For each of: empty state, alternative views, mobile view, settings/configuration:
- Use the navigation heuristic checklist:
  1. Look for view switcher elements (list/grid/table/calendar toggles) for alternative views
  2. Look for settings/gear icons for configuration
  3. Empty state may not be reachable in a populated product — skip if no obvious path
  4. Mobile view: if the product is web-based, attempt viewport resize via `execute_javascript`:
     ```javascript
     // Read-only observation of responsive behavior
     document.documentElement.style.width = '375px';
     ```
     Take screenshot, then restore: `document.documentElement.style.width = '';`
- If a state can't be reached, note `[SKIPPED: {state} — {reason}]` and move on
- Save each with naming: `pillar-3-{state-name}.png`

**Step 19.** Throughout Phase 3, record observations for the Pillar 3 text content from each scout report:
- **Layout model** — spatial organization of the primary interface
- **Visual hierarchy** — what gets prominence, what's secondary
- **Interaction vocabulary** — named interaction patterns present (drag-and-drop, click-to-open modal, inline editing, etc.)
- **Information density** — how much is shown at once, dense vs. sparse
- **UX patterns observed** — named or recognizable UX patterns (Kanban, card/modal detail, progressive disclosure, etc.)
- (Deep only) **Responsive behavior** — how the product adapts
- (Deep only) **Accessibility observations** — notable a11y features or concerns

**Step 20.** Navigate back to the original starting URL. **Mandatory state reset** before Phase 4.

---

## Phase 4: Behavioral Flows (Pillar 4)

**If depth is Light, skip this entire phase.** Light depth targets content websites where there are no meaningful interaction flows.

**Step 21.** Determine which flows to capture:
- If `--flows` is provided, use those descriptions as the flow list
- If not provided, infer flows capped at the depth-level maximum:
  - **Standard:** 1-2 flows
  - **Deep:** 2-3 flows
- **Default first flow** is always "create and interact with the primary object" — if the product has a primary object (card, message, task, post, article), creating one is the flow users internalize most deeply (strongest Jakob's Law signal)
- Candidate second/third flows: editing an existing item, filtering/searching, changing status/state, navigation between sections

**Step 22.** For each flow, execute the sequence:

1. Navigate to the flow's starting state
2. Perform the first action (click create button, select an item, etc.)
3. Call `take_screenshot_tool` at this first key moment. Copy to `{output-dir}/screenshots/pillar-4-flow-{flow-name}-step-1.png`
4. Continue through the flow, performing each interaction with `execute_action_tool`
5. After each significant transition, call `scout_page_tool` to capture DOM-level details:
   - Is this a modal overlay or page navigation?
   - Did the URL change?
   - Did new iframes mount?
   - What changed in the element structure?
6. Take screenshots at 3-5 key moments total per flow. Name sequentially: `pillar-4-flow-{flow-name}-step-{n}.png`
7. Write a step-by-step narration as you go — what was clicked, what appeared, what changed
8. Note interaction pattern observations: modal vs. page nav, inline editing vs. form, keyboard shortcuts observed, drag-and-drop behavior

**Failure handling for flows:** If a flow step fails (element not clickable, page doesn't transition, unexpected state), document where the flow broke: "Flow stopped at step N — {reason}." Include whatever screenshots were captured up to that point. Move to the next flow.

---

## Phase 5: Report Assembly

**Step 23.** Using the template content loaded in Phase 0, assemble the final report.

### Template interpretation rules:

- **`{PLACEHOLDER}` markers:** Replace each with the data collected during Phases 1-4.
- **`<!-- DEPTH: level -->` sections:** Include only sections matching the current depth level.
  - At Light depth: render `<!-- DEPTH: light -->` sections. Skip `<!-- DEPTH: standard,deep -->` sections.
  - At Standard depth: render `<!-- DEPTH: standard,deep -->` sections. Skip `<!-- DEPTH: light -->` and `<!-- DEPTH: deep -->` sections.
  - At Deep depth: render all `<!-- DEPTH: standard,deep -->` and `<!-- DEPTH: deep -->` sections. Skip `<!-- DEPTH: light -->` sections.
- **Remove all `<!-- DEPTH -->` and `<!-- /DEPTH -->` comment markers** from the final output.
- **Remove the `<!-- INSTRUCTION -->` comment** from the Pillar 4 section.
- **Pillar 3 gallery at Light depth:** Render the screenshot gallery directly after the layout model line — no `### Screenshots` heading.
- **Pillar 3 gallery at Standard/Deep depth:** Render under the `### Screenshots` heading after the observation table.
- **Pillar 4 flow iteration:** For each flow captured in Phase 4, duplicate the Flow subsection from the template (the `### Flow: {FLOW_NAME}` block) and fill in each instance with the flow's narration and screenshot references.

### Screenshot references in the report:

Format each screenshot as:
```markdown
![{description}](screenshots/{filename})
*{caption — one sentence describing what the screenshot shows}*
```

The primary view screenshot is referenced in both Pillar 2 (inline) and Pillar 3 (in the gallery). Same file path, two references.

### Filling Pillar 1:

- **Domain nouns/verbs/labels/feature names** — populate table cells with comma-separated lists from Phase 2 extraction. Include all discovered terms, comprehensive rather than selective. Reference the Trello worked example for calibration: 16 nouns, 12 verbs, 9 labels.
- **Terminology patterns** — write 2-4 sentences analyzing the product's vocabulary: metaphors used, tone (casual/formal/technical), jargon vs. plain language. This is prose, not a list.
- **Naming divergences** — write `TBD — requires cross-report comparison. This product uses: "{key term}" for {concept}, "{key term}" for {concept}.` List the product's own terminology for its key concepts so future cross-report comparison has something to compare.

### Filling Pillar 2:

- Light depth: Fill `{PRODUCT_SNAPSHOT}` and `{CONTENT_TYPES_AND_NAVIGATION}` only.
- Standard/Deep: Fill all Pillar 2 fields. Product snapshot is 2-3 sentences. "How it works" is 1 paragraph. Core features is a table with 5-15 rows depending on product complexity. Domain conventions are behavioral observations (3-5 bullet points). "What's unique" is 2-3 sentences.

### Filling Pillar 3:

- Light: Layout model (1-2 sentences) + screenshot gallery (2-3 images).
- Standard: Full observation table + screenshot gallery (4-5 images).
- Deep: Full observation table with responsive + accessibility rows + screenshot gallery (5-8+ images).

### Filling Pillar 4:

- Standard: 1-2 flow sections with 3-5 step narrations each and 3-5 screenshot references each.
- Deep: 2-3 flow sections.

### Filling Metadata:

- `{SCOUT_VERSION}` — read from plugin.json if accessible, otherwise use "Scout"
- `{SESSION_DURATION}` — from the `close_session` response
- `{STARTING_URL}` — the URL from the command argument
- `{PAGES_VISITED_LIST}` — the running log from all phases, as a bulleted list
- `{SCREENSHOT_COUNT}` — count of .png files in the screenshots directory
- `{SKIPPED_ITEMS_OR_NONE}` — all `[SKIPPED]` markers collected, or "None"

**Step 24.** Write the assembled report to `{output-dir}/{product-name}-landscape.md` using the Write tool.

**Step 25.** Call `close_session` to release the browser. Record `session_duration_seconds` from the response.

**Step 26.** Present a completion summary to the user:

```
Landscape Analysis Complete
────────────────────────────
Product:      {product-name}
Depth:        {depth-level}
Output:       {output-dir absolute path}
Duration:     {session_duration}s
Pages:        {N} pages visited
Screenshots:  {N} captured
Skipped:      {N items or "None"}

Report: {output-dir}/{product-name}-landscape.md
```

If any items were skipped, list them briefly below the summary.