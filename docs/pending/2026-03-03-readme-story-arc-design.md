# README Story Arc — Design Doc

**Date:** 2026-03-03
**Status:** Approved
**Approach:** Self-Contained Demo Kit (Approach A)

## Problem

Scout's README GIFs don't match the sections they demo. Real websites are messy, uncontrolled, and change between captures. The example prompts lack short headers. There's no narrative thread — the reader sees isolated features, not a story.

## Decision: Story Arc

The README is restructured around a three-chapter progressive disclosure arc that mirrors Scout's actual workflow: Scout → Interact → Automate. Casual users stop at Chapter 1; power users follow the full arc. Same README, two audiences, self-selecting.

## Audience Strategy

Scout's audience installs Claude Code plugins — they're already technical. Leading with specs alienates the broader audience. Leading with "easy mode" makes Scout look like a toy. The story arc lets the reader discover depth by following along.

## Stage Pages: Elevated Wireframes

Purpose-built HTML pages that Scout performs against. Design language sits between a wireframe and a polished app:

- Recognizable web patterns (login form, data table, export dialog)
- Clean, minimal styling — no fake company branding
- Shared design tokens via `stage-tokens.css` (palette, font, spacing, border-radius)
- Built using `/frontend-design` skill for distinctive, production-grade output

Not pretending to be Workday. A wireframe that graduated to a real design.

### Page Inventory (4 pages)

**`portal.html`** — Chapters 1 and 2 (Scout, Form Fill)
- Top nav bar with nav links
- Centered login form: username, password, Sign In button
- Sidebar with menu items (non-interactive, gives scout report depth)

**`dashboard.html`** — Chapters 2 and 3 (Data Extraction, Export, Automate)
- Header with "Reports" breadcrumb
- Data table with ~5 rows of sample data (dates, names, statuses)
- "Export CSV" button top-right

**`components.html`** — Chapter 2 (Element Inspection)
- Grid of UI components: button, text input, dropdown, checkbox group
- Realistic attributes: `data-testid`, `aria-label` — details Scout surfaces during inspection

**`scheduled.html`** — Chapter 3 (Schedule) — optional
- Confirmation view: "Workflow exported. Scheduled: Every Monday at 6:00 AM."
- Could be a modal overlay on `dashboard.html` instead

### Shared Design Tokens (`stage-tokens.css`)

~50 lines of CSS variables. Neutral palette with one Scout accent color for interactive elements. System font stack (Inter or OS default). Generous whitespace. Subtle grid — thin borders, light backgrounds, no shadows or gradients.

## GIF Map (5-6 total)

### Chapter 1: "See the page" (1 GIF)

| GIF | Stage Page | What It Shows |
|-----|-----------|---------------|
| `demo-scout.gif` | `portal.html` | Browser opens page, Scout returns compact structural overview |

### Chapter 2: "Do something with it" (3 GIFs)

| GIF | Stage Page | What It Shows |
|-----|-----------|---------------|
| `demo-form.gif` | `portal.html` | Finds inputs, types credentials, submits |
| `demo-data.gif` | `dashboard.html` | Scouts table, highlights rows, clicks Export CSV |
| `demo-inspect.gif` | `components.html` | Hovers button, reveals computed styles / a11y attributes |

### Chapter 3: "Make it run itself" (1-2 GIFs)

| GIF | Stage Page | What It Shows |
|-----|-----------|---------------|
| `demo-automate.gif` | `dashboard.html` | Export flow + "Scheduled" confirmation |

## Capture Pipeline

### Method

Botasaurus-driver capture scripts (proven pattern from existing `capture_demo_frames.py`):

1. Script opens stage page via `file://` — no network dependency
2. Captures numbered JPEG frames at key moments with controlled timing
3. `ffmpeg` composites frames into optimized GIFs
4. Output to `assets/`

### Scripts

| Script | Target | GIF Output |
|--------|--------|-----------|
| `capture_scout.py` | `portal.html` | `demo-scout.gif` |
| `capture_form.py` | `portal.html` | `demo-form.gif` |
| `capture_data.py` | `dashboard.html` | `demo-data.gif` |
| `capture_inspect.py` | `components.html` | `demo-inspect.gif` |
| `capture_automate.py` | `dashboard.html` | `demo-automate.gif` |

### Quality Targets

- **Viewport:** Consistent across all captures (e.g., 800x500)
- **Duration:** 5-10 seconds per GIF
- **File size:** Under 500KB per GIF

## README Redesign

### New Structure

```
Logo + tagline ("Stop clicking.")
One-liner description

── Chapter 1: See the page ──────────────────
[scout GIF]
Brief explanation — 200 tokens to understand a page

── Chapter 2: Do something with it ──────────
[form-fill GIF]   [data GIF]   [inspect GIF]
Brief explanation per demo

── Chapter 3: Make it run itself ─────────────
[automate GIF]
Brief explanation — export once, schedule forever

── Example Prompts ───────────────────────────
Short header (1-3 words) + prompt pairs:
  "Report pull" — "Go to the portal, pull this month's report..."
  "API recon" — "Watch the network traffic..."
  "Scrape" — "Scout news.ycombinator.com..."
  "Accessibility" — "Find every button missing an aria-label..."
  "Localhost" — "Open localhost:3000 and test the login form..."
  "Screenshot" — "Walk through Stripe's onboarding and screenshot every step..."
  "Design QA" — "Inspect the submit button — what font, color, padding..."
  "Full auto" — "Walk through payroll export, schedule every Monday at 6 AM..."

── Reference ─────────────────────────────────
Install instructions
Tools table (14 tools)
Slash commands (6 commands)
Benchmarks / comparison table
Security
```

### What Changes vs. Today

- **How It Works** and **Export & Schedule** sections → replaced by three-chapter arc
- **Example prompts** → get short headers, move below the arc (supporting evidence, not the lead)
- **Reference sections** (tools, install, benchmarks, security) → stay at bottom, mostly unchanged
- **Comparison table** → stays (factual differentiation)

## File Layout

```
assets/
  stages/
    stage-tokens.css        # shared design tokens
    portal.html             # login portal page
    dashboard.html          # data table + export page
    components.html         # inspectable UI components
    scheduled.html          # (optional) schedule confirmation
scripts/
  capture_scout.py          # botasaurus-driver capture script
  capture_form.py
  capture_data.py
  capture_inspect.py
  capture_automate.py
assets/
  demo-scout.gif            # output GIFs (replace existing)
  demo-form.gif
  demo-data.gif
  demo-inspect.gif
  demo-automate.gif
README.md                   # redesigned around story arc
```

## What's Out of Scope

- **plugin-demo CLI tool** — shelved. The design exists but won't be built.
- **scout-marketplace expansion** — Scout remains self-contained.
- **Scout recording itself** — capture uses botasaurus scripts, not Scout's own record_video.
