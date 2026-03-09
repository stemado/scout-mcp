# Landscape Analysis — Plugin Brief

> What we need a landscape analysis to produce, why we need it, and what the output artifact looks like.
> Date: 2026-03-03
> Author: Matthew Steinle (requirements), Claude (brief)

---

## The Problem

We're designing a digital product (a church website with embedded tools — messaging, project management boards, member features). Before we design anything, we need to understand the ecosystem our users already live in. What does Trello look like? How does Telegram work? What do Orthodox church websites typically contain?

This matters because of **Jakob's Law**: users spend most of their time on *other* products, so they bring expectations from those products into yours. A user who's used Trello a thousand times has internalized what a Kanban board looks and feels like — the columns, the cards, the drag-and-drop. When they encounter our project management board, that's their baseline. We need to capture that baseline.

We've already done a text-only landscape analysis using Claude Code that captured **language and terminology** extremely well — comprehensive noun/verb maps, feature names, terminology divergences. What we're missing is the **visual and experiential layer**: what these products actually look like, how they're laid out, what interaction patterns they use, and how key user flows work. We need both text and screenshots in a single artifact.

---

## What We Need: The Four Pillars

A landscape analysis report should capture four dimensions of an external product. Together they produce an artifact that serves us across the entire design pipeline — from domain modeling through UX patterns through final design.

Each pillar answers a different question. The boundaries are sharp:

| Pillar | Question It Answers | Medium Emphasis |
|--------|-------------------|-----------------|
| **1. Language & Terminology** | What does this product *call* things? | Text-heavy |
| **2. Product & Feature Profile** | What does this product *do*? | Text-heavy |
| **3. Design & UX Context** | What does this product *look like*? | Screenshot-heavy |
| **4. Behavioral Flows** | How does this product *move*? | Text + screenshot sequences |

Pillars 1-3 are always required. Pillar 4 is required for products (Standard and Deep depth) but not applicable to content websites (Light depth) where there are no meaningful interaction flows to capture.

---

### Pillar 1: Language & Terminology

**Goal:** Capture the product's vocabulary so we can use it as reference when building our domain model (DDD), object map (OOUX), and content model (content strategy).

**What to capture (text):**

| Element | Description | Example |
|---------|-------------|---------|
| **Domain nouns** | Every significant noun — the "objects" in this product's world. People, places, things. | Card, Board, List, Member, Label, Checklist, Workspace |
| **Domain verbs** | Action words. What users can do. How actions are described. | Create, Assign, Move, Archive, Watch, Filter |
| **User-facing labels** | Exact text users see: button labels, menu items, form labels, page titles. | "Add a card", "Mark complete", "Filter cards", "Board menu" |
| **Feature names** | What the product calls its capabilities, using the product's own naming. | "Butler" (Trello's automation), "WorkForms" (Monday.com's intake) |
| **Terminology patterns** | Jargon vs. plain language. Metaphors used. Domain-specific terms. | Trello uses a physical card metaphor (front/back). FMX uses facility management jargon (Work Order, Technician). |
| **Naming divergences** | Where this product names something differently than competitors. | Trello: "Card". Asana: "Task". Monday.com: "Item". Same concept, different names. |

**What to capture (screenshots):**
- Navigation structure showing menu labels and hierarchy
- Screens with prominent labeling or terminology choices

**Why this feeds the pipeline:** These nouns become candidate objects in OOUX. These verbs become candidate CTAs. These labels feed content strategy. When multiple products disagree on a term, that's a signal that the right name must come from our own users. When they all agree, that's a strong signal to align with ecosystem conventions.

---

### Pillar 2: Product & Feature Profile

**Goal:** Produce a concise reference of what this product *is* and what it *does* — enough that a designer can recall the product months later without revisiting it. This pillar is the **product sheet**: identity, purpose, and capabilities. It does not cover how the product looks (Pillar 3) or how interactions flow (Pillar 4).

**What to capture (text):**

| Element | Description | Example |
|---------|-------------|---------|
| **Product snapshot** | 2-3 sentences: what it is, who it's for, what problem it solves. | "Trello is a visual project management tool built around the metaphor of physical cards on a board. It's used by individuals and teams to organize work into customizable workflows. It solves the problem of tracking work items across stages of completion." |
| **How it works** | 1 paragraph narrative of the product's conceptual model — how its pieces fit together. Not how users interact with the UI (that's Pillar 4), but how the product organizes its domain. | "Boards contain Lists (representing stages). Lists contain Cards (individual work items). Each Card has a front (summary) and back (full detail). Status is determined by which List a Card belongs to." |
| **Core features** | Table of main capabilities: name, what it does, how prominent it is. | Board views, Card assignment, Checklists, Labels, Automation, Attachments, Templates, Filtering... |
| **Domain conventions** | How this product models its domain in ways that differ from obvious defaults. Conceptual rules, not interaction patterns. | "Status is positional — a Card's List IS its status. No separate status field. Completion and archiving are independent concepts — a card can be complete but still visible." |
| **What's unique** | What distinguishes this product from peers. | "Email-to-board creates cards from email. Butler automation uses natural-language rule definitions." |

**What to capture (screenshots):**
- The primary/default view with realistic data (e.g., a populated Kanban board) — **the single most important screenshot in the entire report** (shared with Pillar 3 — one screenshot, two purposes)

**Why this feeds the pipeline:** This section rebuilds mental context. When a designer reaches the UX Patterns stage and is working on the project management board section, they need to quickly recall "what does a Kanban product actually do?" without leaving their workflow. The product snapshot and "how it works" narrative are the most-referenced elements.

---

### Pillar 3: Design & UX Context

**Goal:** Capture what the product *looks like* — visual design patterns, layout conventions, spatial organization, and named UX patterns. This pillar is the **design reference**: what a user would see if they took a screenshot and annotated it. It does not cover what the product does (Pillar 2) or how interactions unfold over time (Pillar 4).

**What to capture (text):**

| Element | Description | Example |
|---------|-------------|---------|
| **Layout model** | Spatial organization of the primary interface. | "Horizontal columns fill viewport width. Cards stack vertically within columns. Board scrolls horizontally when columns exceed viewport." |
| **Visual hierarchy** | What gets prominence? What's large, bold, first? What's secondary? | "Card titles most prominent. Labels as colored chips below title. Assignee avatars and due date badges at card bottom." |
| **Interaction vocabulary** | Named interaction patterns present in the UI — the pattern names, not the step-by-step sequences (that's Pillar 4). | "Drag-and-drop. Click-to-open modal. Inline editing. Keyboard shortcuts." |
| **Information density** | How much is shown at once? Dense or sparse? | "Board view: many cards at low detail. Card detail: one card at high detail. Trades item detail for overview-level awareness." |
| **UX patterns observed** | Named or recognizable patterns in use. | "Kanban board. Card/modal detail (click card opens modal overlay). Inline creation. Progressive disclosure (card front = summary, card back = full detail)." |
| **Responsive behavior** | How the product adapts to different screen sizes. | "Board becomes horizontally scrollable on narrow viewports. Mobile app converts board to a list of lists." |
| **Accessibility observations** | Notable accessibility features or concerns. | "Color-coded labels have optional text labels. Keyboard navigation supported for major actions." |

**What to capture (screenshots):**

This is the pillar where screenshots carry the most weight — text descriptions of visual design are inherently lossy. A screenshot communicates layout, hierarchy, density, and convention instantly.

| Screenshot | What It Shows | Priority |
|-----------|---------------|----------|
| **Primary view — populated** | Main interface with realistic data. Layout, density, visual hierarchy. | Required |
| **Primary view — empty state** | What users see before content exists. Onboarding pattern. | Nice to have |
| **Detail view** | Full detail of one item. Information architecture at item level. | Required |
| **Creation flow** | Creating a new item. Progressive disclosure, form patterns. | Required |
| **Navigation / sidebar** | Main navigation structure. Application-level information architecture. | Required |
| **Alternative views** | Different presentations of the same data. | Nice to have |
| **Mobile view** | Responsive or mobile adaptation. | Nice to have |
| **Settings / configuration** | Settings that reveal product concepts (notification, permissions). | Nice to have |

**Why this feeds the pipeline:** There's a reason Telegram, Signal, and WhatsApp all look similar. There's a reason every LLM chat interface looks similar. Users have expectations about what these products look like, and they bring those expectations to your product. The screenshots and UX observations create the design reference library. Not to copy — but to establish the baseline from which we can then apply better UX patterns, accessibility standards, and domain-specific improvements.

---

### Pillar 4: Behavioral Flows

**Goal:** Capture how the product *moves* — key interaction sequences that users internalize through repetition. Where Pillar 2 says what the product does, Pillar 3 shows what it looks like, and Pillar 4 captures what it feels like to *use*. These are the step-by-step sequences that form the Jakob's Law expectations users bring to your product.

**What to capture (text):**

For 2-3 key user flows per product, a narrated step sequence:

```
Flow: Create and track a work item
1. User sees Board with Lists (columns)
2. Clicks "Add a card" at bottom of a List → inline text input appears
3. Types card title, presses Enter → Card appears in the List
4. Clicks card → Modal overlay shows card detail (back of card)
5. Adds description, assigns member, sets due date
6. Closes modal → Returns to Board view
7. Drags card from "To Do" to "In Progress" → Status changes visually
```

**What to capture (screenshots):**
- Screenshot sequence showing 3-5 key steps in the flow, anchoring the narrative

**Why this feeds the pipeline:** This is where Jakob's Law actually lives. A user hasn't internalized "Trello has drag-and-drop" as an abstract feature. They've internalized the *flow* — see board, click card, edit detail, close, drag to new column. That sequence is the expectation they bring. Capturing flows gives us the experiential baseline that feature lists alone miss.

---

## Depth Levels

Not every analysis target needs the same depth across all four pillars.

### Light — Content Websites

For content-heavy, non-product sites (church websites, blogs, documentation):

- **Pillar 1 (Language):** Full. This is the primary value.
- **Pillar 2 (Product):** Light. Content types and navigation, not product features.
- **Pillar 3 (Design):** Light. Homepage, navigation, a content page. General layout observations.
- **Pillar 4 (Flows):** N/A. Content sites don't have interaction flows to capture.

### Standard — Established Products

For products with established, well-known patterns (messaging apps, email, social):

- **Pillar 1 (Language):** Full.
- **Pillar 2 (Product):** Full. Feature inventory and unique differentiators.
- **Pillar 3 (Design):** Standard. Layout model, interaction patterns, key observations.
- **Pillar 4 (Flows):** 1-2 key flows.

### Deep — Complex / Novel Products

For products with complex interaction models users will bring strong expectations from (Kanban boards, design tools, spreadsheet-like tools):

- **Pillar 1 (Language):** Full.
- **Pillar 2 (Product):** Full with behavioral depth.
- **Pillar 3 (Design):** Deep. All observations. Multiple views. Responsive behavior.
- **Pillar 4 (Flows):** 2-3 key flows with screenshot sequences.

---

## The Artifact

The output is a **single report per source** combining text and screenshots. This report becomes a reference artifact in our design pipeline — consulted during domain modeling, content strategy, object mapping, UX pattern selection, and representation design. It sits alongside (not inside) those activities.

### How the artifact gets used downstream

| Pipeline Stage | What It References |
|---------------|-------------------|
| **Domain Modeling (DDD)** | Pillar 1 — nouns map to domain entities, verbs map to domain events and commands, terminology divergences inform ubiquitous language decisions |
| **Object Mapping (OOUX)** | Pillar 1 — nouns become candidate objects, verbs become candidate CTAs, relationships between concepts become candidate object relationships |
| **Content Strategy** | Pillar 1 — vocabulary, labeling patterns, and communication approaches inform content models, voice/tone, and naming decisions |
| **UX Patterns & Representation** | Pillars 2, 3, 4 — the design baseline. When designing a Kanban board, the team references these screenshots, layout observations, and flow sequences to understand what users expect, then applies their own UX patterns, accessibility standards, and domain-specific improvements |

### Provenance

All findings from landscape analysis are tagged with `[landscape]` provenance when referenced downstream. This keeps a clean separation between what was learned from external observation vs. primary user research vs. internal domain knowledge.

### Qualities of the artifact

- **Dense but skimmable.** Tables over paragraphs. Captions on screenshots. Scannable headings. A designer should find what they need in under 60 seconds.
- **Descriptive, not prescriptive.** The report describes what exists. It doesn't say what to build. Language like "the system should..." or "best practice is..." doesn't belong. Language like "this product provides..." and "the interface is organized as..." does.
- **Durable.** The report captures what *is*, not what should be. It stays useful months later because products don't change their fundamental patterns quickly.

---

## Success Criteria

A successful landscape analysis report enables someone who has never used the product to:

1. **Understand what it is and does** without visiting it (Pillar 2)
2. **Use the product's own vocabulary** accurately when discussing the domain (Pillar 1)
3. **Visualize the product's interface** from screenshots and descriptions (Pillar 3)
4. **Recall how key interactions feel** from flow narratives and screenshot sequences (Pillar 4)
5. **Reference it during design work months later** and still find it useful

---

## Appendix: Worked Example — Trello (Partial)

To calibrate the level of detail and tone, here's what a filled-in report would look like for Trello across all four pillars. This is abbreviated — a real report would be more complete.

---

### Pillar 1 (Language) — Excerpt

| Element | Captured |
|---------|---------|
| **Domain nouns** | Board, List, Card, Member, Label, Checklist, Checklist Item, Attachment, Comment, Activity, Power-Up, Workspace, Template, Custom Field, Due Date, Cover |
| **Domain verbs** | Create, Add, Move, Drag, Assign, Watch, Archive, Filter, Automate, Mark Complete, Copy, Share |
| **User-facing labels** | "Add a card", "Add a list", "Mark complete", "Filter cards", "Watch", "Join", "Board menu", "Card covers", "Archived items" |
| **Terminology patterns** | Physical card metaphor throughout — "card front" / "card back", "cover image". Lists are never called "columns" or "stages" in official docs. Casual, imperative tone ("Add a card" not "Create new card"). |
| **Naming divergences** | "Card" where Asana says "Task" and Monday.com says "Item". "List" where Asana says "Section" and Monday.com says "Group". "Power-Up" for integrations (unique branded term). |

### Pillar 2 (Product) — Excerpt

**Product snapshot:** Trello is a visual project management tool built around the metaphor of physical cards on a board. It's used by individuals and teams to organize work into customizable workflows. It solves the problem of tracking work items across stages of completion.

**How it works:** Boards contain Lists. Lists contain Cards. Each Board represents a project or workflow. Each List represents a stage (e.g., "To Do", "In Progress", "Done"). Each Card represents a unit of work. Status is determined by which List a Card belongs to — there is no separate status field. Cards have a front (title, labels, assignee badges, due date) and a back (description, checklist, attachments, comments, activity log).

**Domain conventions:**
- Status is positional. A Card's List IS its status. No separate status field exists.
- Completion and archiving are independent. A Card can be marked complete but remain visible on the board. Archiving removes it from view but retains it.
- Lists are user-defined. Trello imposes no default List names — the user defines stages entirely.
- Self-assignment via keyboard shortcut (SPACE bar) is a first-class interaction.

[Screenshot: Populated Trello board showing three Lists with Cards]

### Pillar 3 (Design) — Excerpt

**Layout model:** Horizontal columns (Lists) arranged left to right across the full viewport width. Cards stack vertically within each column. Board scrolls horizontally when columns exceed viewport. A fixed header bar sits above with board name, starred status, view switcher, and member avatars.

**Visual hierarchy:** Card titles are the most prominent per-card element. Colored Label chips appear below the title. Assignee avatar thumbnails and due date badges cluster at the bottom-right of the card face. List headers are bold but secondary to the overall board pattern. The board background (customizable image or color) provides ambient context.

**Interaction vocabulary:** Drag-and-drop. Click-to-open modal. Inline editing. Inline creation. Keyboard shortcuts.

**Information density:** Board view optimizes for many-items-at-low-detail. A typical board shows 15-30 cards simultaneously across 3-5 columns, each showing title + 2-3 metadata indicators. Card detail modal shows one card at high detail with full description, checklist progress, file attachments, and threaded comments.

**UX patterns observed:** Kanban board. Card/modal detail (click card opens full-screen-width modal overlay with dimmed board behind). Inline creation (click "Add a card" at bottom of list, text input appears in-place). Progressive disclosure (card front = summary, card back = everything).

[Screenshot: Card detail modal open over dimmed board]
[Screenshot: Board view showing label colors, avatars, due date badges]
[Screenshot: Navigation sidebar with Workspace and Board list]

### Pillar 4 (Flows) — Excerpt

**Flow: Create and track a work item**
1. User sees Board with 3 Lists: "To Do", "Doing", "Done"
2. Clicks "+ Add a card" link at bottom of "To Do" list
3. Inline text input appears in-place within the list
4. Types card title, presses Enter — Card appears as the bottom card in the list
5. Clicks the new Card — Modal overlay slides in, showing card detail (back)
6. Types description, clicks "Members" to assign, clicks "Dates" to set due date
7. Closes modal (click X or click dimmed background) — Returns to Board view
8. Drags Card from "To Do" to "Doing" — Card animates to the new column. Status is now "Doing".
9. Later, drags Card to "Done" — Card animates again. Optionally clicks "Mark complete" for the green checkmark.

[Screenshot sequence: Steps 2-3 (inline creation), Step 5 (modal open), Step 8 (mid-drag)]
