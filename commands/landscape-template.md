# Landscape Analysis — {PRODUCT_NAME}

**Source:** {URL}
**Date:** {DATE}
**Depth:** {DEPTH_LEVEL}
**Provenance tag:** `[landscape]`

---

## Pillar 1: Language & Terminology

| Element | Captured |
|---------|----------|
| **Domain nouns** | {DOMAIN_NOUNS} |
| **Domain verbs** | {DOMAIN_VERBS} |
| **User-facing labels** | {USER_FACING_LABELS} |
| **Feature names** | {FEATURE_NAMES} |

### Terminology patterns

{TERMINOLOGY_PATTERNS_PROSE}

### Naming divergences

{NAMING_DIVERGENCES_PROSE_OR_TBD}

{PILLAR_1_SCREENSHOTS}

---

<!-- DEPTH: light -->
## Pillar 2: Product & Feature Profile

**Product snapshot:** {PRODUCT_SNAPSHOT}

**Content types and navigation:** {CONTENT_TYPES_AND_NAVIGATION}

![Primary view]({PRIMARY_VIEW_SCREENSHOT_PATH})
*{PRIMARY_VIEW_CAPTION}*
<!-- /DEPTH -->

<!-- DEPTH: standard,deep -->
## Pillar 2: Product & Feature Profile

**Product snapshot:** {PRODUCT_SNAPSHOT}

**How it works:** {HOW_IT_WORKS}

**Core features:**

| Feature | What it does | Prominence |
|---------|-------------|-----------|
{CORE_FEATURES_ROWS}

**Domain conventions:**
{DOMAIN_CONVENTIONS}

**What's unique:**
{WHATS_UNIQUE}

![Primary view — populated]({PRIMARY_VIEW_SCREENSHOT_PATH})
*{PRIMARY_VIEW_CAPTION}*
<!-- /DEPTH -->

---

<!-- DEPTH: light -->
## Pillar 3: Design & UX Context

**Layout model:** {LAYOUT_MODEL}

{PILLAR_3_SCREENSHOT_GALLERY}
<!-- /DEPTH -->

<!-- DEPTH: standard,deep -->
## Pillar 3: Design & UX Context

| Element | Observation |
|---------|-------------|
| **Layout model** | {LAYOUT_MODEL} |
| **Visual hierarchy** | {VISUAL_HIERARCHY} |
| **Interaction vocabulary** | {INTERACTION_VOCABULARY} |
| **Information density** | {INFORMATION_DENSITY} |
| **UX patterns observed** | {UX_PATTERNS} |
<!-- DEPTH: deep -->
| **Responsive behavior** | {RESPONSIVE_BEHAVIOR} |
| **Accessibility observations** | {ACCESSIBILITY} |
<!-- /DEPTH -->

### Screenshots

{PILLAR_3_SCREENSHOT_GALLERY}
<!-- /DEPTH -->

---

<!-- DEPTH: standard,deep -->
## Pillar 4: Behavioral Flows

<!-- INSTRUCTION: For each flow captured in Phase 4, duplicate the
     following subsection and fill it in. Remove this comment from
     the final report. -->

### Flow: {FLOW_NAME}

{NUMBERED_STEP_NARRATIVE}

#### Key moments

{FLOW_SCREENSHOT_SEQUENCE}

<!-- /DEPTH -->

---

## Analysis Metadata

| Field | Value |
|-------|-------|
| **Tool** | Scout {SCOUT_VERSION} |
| **Session duration** | {SESSION_DURATION} |
| **Starting URL** | {STARTING_URL} |
| **Pages visited** | {PAGES_VISITED_LIST} |
| **Screenshots captured** | {SCREENSHOT_COUNT} |
| **Skipped items** | {SKIPPED_ITEMS_OR_NONE} |

### Pipeline cross-reference

| Pipeline Stage | References |
|---------------|-----------|
| Domain Modeling (DDD) | Pillar 1 — nouns → entities, verbs → events/commands |
| Object Mapping (OOUX) | Pillar 1 — nouns → objects, verbs → CTAs |
| Content Strategy | Pillar 1 — vocabulary, labeling, naming patterns |
| UX Patterns & Representation | Pillars 2, 3, 4 — design baseline and flow expectations |
