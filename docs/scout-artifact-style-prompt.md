# Scout — Visual Style & Design System Prompt

Use this as context when building any new phase or screen for the Scout product narrative. Every screen should feel like it belongs to the same cinematic presentation — dark, deliberate, and quietly confident.

---

## Design Philosophy

Scout's visual identity draws from **keynote-grade product storytelling** — think Linear, Vercel, or Stripe's product pages. The aesthetic is restrained luxury: deep dark backgrounds, surgical typography, and motion that serves narrative rather than decoration. Nothing moves unless it means something. Color is scarce and therefore powerful when it appears.

The tone is **authoritative without being aggressive**. Scout is positioned as an obedient instrument, not an autonomous agent. The visuals should reinforce that the *user* is in control — Scout is capable, but deferential. This matters because the audience includes IT directors and engineering leads who are wary of tools that operate outside their authority.

---

## Color System

```css
:root {
  /* Foundations */
  --bg: #080b14;              /* Near-black with cool blue undertone */
  --surface: #111827;         /* Card/node background — barely lighter */
  --border: #1e293b;          /* Default borders — visible but quiet */
  --text: #e2e8f0;            /* Primary text — warm off-white */
  --muted: #64748b;           /* Secondary text, labels, descriptions */
  --dim: #334155;             /* Inactive/dormant element borders */

  /* Semantic Colors */
  --scout: #f97316;            /* Scout's brand color — warm amber/orange */
  --scout-glow: rgba(249, 115, 22, 0.15);  /* Soft halo behind Scout elements */
  --legacy: #64748b;          /* Legacy systems at rest — neutral slate */
  --legacy-active: #94a3b8;   /* Legacy systems when active — brighter slate */
  --modern: #38bdf8;          /* Modern/consuming systems — cool sky blue */
  --modern-glow: rgba(56, 189, 248, 0.12);
  --green: #34d399;           /* Success, completion, repaired states */
  --red: #f87171;             /* Problems, errors, manual/broken workflows */
  --yellow: #fbbf24;          /* Warnings, caution (used sparingly) */
  --connector: #475569;       /* Connector lines at rest */
}
```

### Color Usage Rules

- **Scout orange (#f97316)** is the only "warm" color on the canvas. It represents Scout's presence, activity, and data flow. Use it for Scout's border, label accents, phase indicators, active flow lines, and the pulsing glow ring.
- **Red (#f87171)** is reserved for problems — manual workflows, broken connections, the "before" state. It signals cost and pain.
- **Green (#34d399)** is reserved for resolution — successful repairs, completed states. It appears *after* red, never alone.
- **Blue (#38bdf8)** represents modern systems that consume Scout's output — ERP, payroll, custom apps. It's the "demand side."
- **Slate tones** (--muted, --dim, --legacy) are the default. Most of the canvas should be in this range. Color is *earned* through state changes.

---

## Typography

```css
--serif: 'Instrument Serif', Georgia, serif;
--sans: 'DM Sans', -apple-system, sans-serif;
```

### Typographic Hierarchy

| Element | Font | Weight | Size | Color | Traits |
|---|---|---|---|---|---|
| Page title | Instrument Serif | 400 | 2rem | --text | Italic on key word via `<em>` in --scout |
| Phase headline | Instrument Serif | 400 | 1.8rem | --text | The "statement" — one sentence, punchy |
| Phase label | DM Sans | 600 | 0.65rem | --scout | UPPERCASE, letter-spacing: 2px |
| Subcaption | DM Sans | 300 | 0.9rem | --muted | Max-width 560px, line-height 1.6 |
| Node labels | DM Sans | 500 | 0.7rem | --muted (default), inherits state color when active |
| Scout sub-label | DM Sans | 500 | 0.65rem | --muted → --scout when expanded | UPPERCASE, letter-spacing: 1.5px |
| Stat numbers | DM Sans | 600 | 2.8rem | --red | Tight letter-spacing: -1px |
| Stat units | DM Sans | 500 | 0.7rem | --muted | UPPERCASE, letter-spacing: 2px |

### Writing Style for Copy

- **Headlines** are short declarative sentences. Subject-verb-object. "Scout learns your portal." / "Your data is trapped behind a login screen." / "Every system gets an API." Never a question. Never more than ~8 words.
- **Subcaptions** are 2-3 sentences max. They expand the headline with concrete detail. Tone is conversational but precise — no jargon, no exclamation marks, no filler. The reader should feel like they're being spoken to by someone who respects their time.
- **Phase labels** follow the format: `Phase I — [Name]` or `The Problem` for Phase 0.

---

## Layout & Spatial Rules

- Full-viewport, single-screen presentation. No scrolling. `overflow: hidden` on html and body.
- Content is vertically centered in a flex column: `max-width: 1200px; margin: 0 auto;`
- The **stage** is the central diagram area: `max-width: 960px; height: 340px; position: relative;`
- Below the stage: **caption area** (phase label → headline → subcaption), then **phase dots** for navigation.
- The background has a subtle atmospheric gradient overlay (`body::before`) using three radial gradients at very low opacity (0.02–0.03) in scout-orange, modern-blue, and slate.

### Stage Topology

The stage uses absolute positioning within a relative container. The spatial grammar is:

```
LEFT SIDE          CENTER          RIGHT SIDE
(Demand/Trigger)   (Scout)          (Legacy Portals)

  Modern System ─── ╲
  Modern System ──── Scout ──── Legacy Portal
  Modern System ─── ╱          Legacy Portal
                               Legacy Portal
```

- **Left side (~80px from left)**: Modern consuming systems or context icons (user/schedule). These represent *who or what* triggers the workflow.
- **Center (50%, 50%)**: Scout hub — the adapter/engine/API.
- **Right side (~80px from right)**: Legacy portal nodes — the target websites being automated.
- Nodes are positioned using `calc()` percentages: top node at `14%`, middle at `50%`, bottom at `86%`.

---

## Component Patterns

### Nodes (Systems)

```css
.node-icon {
  width: 64px; height: 64px;
  border-radius: 14px;
  border: 1.5px solid var(--border);
  background: var(--surface);
}
```

- Legacy portals use inline SVGs that depict miniature browser windows (title bar with colored dots, content lines).
- Modern systems use emoji icons (⚙️ ERP, 💰 Payroll, 💻 Custom App).
- Nodes enter via `translateX(±20px)` slide and `opacity: 0 → 1` when activated.
- State classes: `.active` (visible, colored border), `.glitch` (shaking, red), `.repaired` (green, calm).

### Scout Hub

```css
.scout-icon {
  width: 80px; height: 80px;
  border-radius: 20px;
  border: 2px solid var(--scout);
  background: var(--surface);
  box-shadow: 0 0 40px var(--scout-glow);
}
```

- Always centered. Has a pulsing ring animation (`::before` pseudo-element at `inset: -8px`).
- Grows to 90×90 in later phases when Scout becomes the full API layer.
- Sub-label beneath transitions through: `adapter` → `engine` → `api` → `intelligence`.
- Can be dimmed (`.dimmed` class: `opacity: 0.06; filter: grayscale(1)`) when Scout is narratively absent.

### SVG Connectors

- Drawn as `<path>` elements in an SVG overlay (`viewBox="0 0 960 340"`).
- Use cubic bezier curves for organic arcs between nodes and Scout center.
- States: default (invisible) → `.active` (0.5 opacity, slate) → `.flowing` (scout-orange, stroke-width 2, glow filter) → `.glitch` (red) → `.repaired` (green).
- Animated flow dots (`<circle>` with `<animateMotion>`) travel along connector paths when active.

### Manual Path (Problem Phase)

- Dashed red line (`stroke-dasharray: 6 4`) that arcs directly from user to portal, bypassing Scout's position.
- Pulses slowly via keyframe animation between 0.3 and 0.6 opacity.
- Represents the tedious, unautomated workflow.

---

## Animation Principles

### Timing

- **Easing**: `cubic-bezier(0.4, 0, 0.2, 1)` for structural movements (nodes, Scout). `ease` for fades.
- **Entrance stagger**: Elements within a phase appear sequentially with 100-200ms gaps. Captions first (label → headline → subcaption at 100ms intervals), then connectors, then nodes.
- **Phase transitions**: `clearPhaseVisuals()` resets all state instantly, then the new phase animates in.
- **Phase dwell time**: 5.5s default. Problem phase gets 6.5s. Glitch phases need extra time for the animation sequence.

### Keyframes Used

- `fadeUp`: `opacity 0 → 1, translateY(12px → 0)` — standard entrance for all initial elements.
- `scoutPulse`: Pulsing ring at 3s interval — subtle breathing effect on Scout's halo.
- `glitchShake`: Rapid X-axis jitter + slight rotation — used when a portal "breaks."
- `dotTravel`: `offset-distance 0% → 100%` with fade in/out at edges — for data flow particles.
- `manualPulse`: Slow opacity oscillation (0.3–0.6) — for the dashed problem-phase path.

### Motion Rules

- Nothing auto-loops except Scout's pulse ring and active flow dots. Everything else is triggered by phase transitions.
- When a node activates, its connector lights up *first*, then the node slides in. Data flows toward the destination.
- Glitch sequences: node shakes (0.6s × 3 iterations) → pause (2s) → repair transition (class swap, no animation needed — the border color shift is enough).

---

## Phase Navigation

- **Phase dots** at the bottom: small circles (10px), clickable, with Roman numeral labels beneath.
- Active dot: scout-orange fill + glow. Completed dots: green fill. Inactive: dim border only.
- **Replay button**: Fixed bottom-right, appears after auto-play completes. Minimal styling — surface background, border, small text.
- Auto-play starts 1.2s after page load and runs through all phases sequentially.

---

## Responsive Behavior

At `max-width: 768px`:
- Container padding reduces, font sizes scale down ~75%.
- Node icons shrink to 50×50, Scout to 64×64.
- Stage height reduces to 280px.

---

## File Structure

Each phase is a single self-contained HTML file with inline `<style>` and `<script>`. No external dependencies beyond Google Fonts. SVG is inline for full animation control. The files are designed to be viewed standalone or eventually composed into a unified presentation.

---

## Voice & Positioning Reminders

- Scout is positioned as **"the API that legacy systems never built"** — it synthesizes APIs from browser interactions.
- The user is always the authority. "You teach Scout" not "Scout learns." "You describe the task" not "Scout figures it out."
- The target audience is IT directors, engineering leads, and operations managers at mid-market companies stuck with portal-based vendor systems.
- The analogy is a **universal travel adapter** — one tool that fits any outlet. Not a power converter, not a rewiring of the building. It adapts to what's already there.