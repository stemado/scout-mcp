# Docs — Stakeholder Presentation Pages

These HTML files are self-contained stakeholder demos. They have no build system, no external JS, and no framework — just inline `<style>` and `<script>` in a single file each.

## Architecture Pattern (shared across pages)

### Coordinate System Alignment

The stage diagrams use **two independent coordinate systems** that must stay in sync:

1. **CSS positioning** — nodes use `position: absolute` with `left`/`right` (px) and `top` (%). These are real pixel/percentage values within the `.stage` container.
2. **SVG viewBox** — connector paths use a virtual `0 0 960 340` coordinate space that maps onto the stage's `max-width: 960px; height: 340px`.

When the stage is at max-width, 1 SVG unit = 1 CSS pixel. The SVG scales with `preserveAspectRatio="xMidYMid meet"` on narrower viewports.

**Critical rule:** CSS `top: X%` positions the **top edge** of the element, not its center. To align an icon's center to a percentage position, use `top: calc(X% - half_icon_height)`. For 64px icons: `top: calc(50% - 32px)`.

### Node Width and Label Overflow

Nodes have `width: 64px` (matching the icon size) with default `overflow: visible`. Labels wider than 64px (e.g., "Vendor Dashboard") overflow symmetrically because the node uses `flex-direction: column; align-items: center`. This ensures all node icons share the same X position regardless of label width — essential for SVG connector alignment.

At the responsive breakpoint (768px), node width drops to 50px to match the smaller icon.

### SVG Connector Math

When recalculating SVG paths after moving nodes:

- **Left node edge X** = `left` value + icon width (e.g., 80 + 64 = 144). Start lines ~4-6px past this.
- **Right node edge X** = 960 - `right` value - icon width (e.g., 960 - 80 - 64 = 816). End lines ~4-6px before this.
- **Scout edges** = center (480) +/- half icon width. Phase 3/4 icon is 90px, so left=435, right=525. Use ~430/530 for line endpoints.
- **Node icon center Y** = the percentage value of 340px (since `calc()` already offsets by half icon height). E.g., `top: calc(14% - 32px)` puts icon center at 14% of 340 = 47.6 ≈ 48.

Bezier control points follow this pattern:
```
M startX,startY C cp1x,cp1y cp2x,cp2y endX,endY
```
- CP1 keeps the same Y as the start (horizontal departure from node)
- CP2 transitions toward the end Y (smooth arrival at Scout or target node)

**Always update `<animateMotion path="...">` to match the corresponding `<path d="...">`.** They use identical path data.

### Context Icons

The You/Schedule icons use 48px symbols. Their centering offset is `calc(50% - 24px)` (half of 48px).

## universal-adapter.html

Animated 4-phase diagram showing Scout's product evolution. Auto-plays through phases on load; phase dots allow manual navigation.

### Phase System

`phaseData[]` array (4 entries) controls which nodes, connectors, and dots are visible per phase. The `showPhase()` function clears all visuals, then progressively reveals elements with `await wait()` delays for animation sequencing.

Phase 4 has a special glitch→repair sequence on legacy-2 (Vendor Dashboard) to demonstrate adaptive intelligence.

### Node Indexing

- `modern-1` / `legacy-1` = middle row (50%), connector index 0
- `modern-2` / `legacy-2` = top row (14%), connector index 1
- `modern-3` / `legacy-3` = bottom row (86%), connector index 2

The `conn-l1`/`conn-r1` (index 0) are the middle/straight connectors. Index 1 curves up, index 2 curves down.

### Transform Interactions

Node CSS transforms are used for slide-in animations:
```css
.node.legacy        { transform: translateX(20px); }   /* hidden: shifted right */
.node.legacy.active { transform: translateX(0); }       /* visible: in place */
```

The Y centering uses `calc()` in the `top` property (not transforms) specifically to avoid conflicts with these animation transforms and the `glitchShake` keyframes.

## phase-theater.html

Technical deep-dive demo with more granular phase animations. Uses `sleep()` for controller transitions.

## showcase.html

Feature showcase page.
