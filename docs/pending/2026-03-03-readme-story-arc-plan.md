# README Story Arc — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Scout's README demo content with a three-chapter story arc ("See the page" → "Do something with it" → "Make it run itself") powered by purpose-built stage pages and new capture scripts.

**Architecture:** Four self-contained HTML stage pages share a CSS design token file and live in `assets/stages/`. Five botasaurus-driver capture scripts (one per GIF) live in `scripts/`. The README is rewritten around the narrative arc, with reference sections preserved at the bottom.

**Tech Stack:** HTML/CSS (stage pages via `/frontend-design`), Python + botasaurus-driver (capture scripts), ffmpeg (frame → GIF encoding)

**Design doc:** `docs/plans/2026-03-03-readme-story-arc-design.md`

---

### Task 1: Create shared design tokens

**Files:**
- Create: `assets/stages/stage-tokens.css`

**Step 1: Create the stages directory**

```bash
mkdir -p assets/stages
```

**Step 2: Write the shared design tokens CSS**

Use `/frontend-design` to create `stage-tokens.css` with these requirements:
- CSS custom properties only (~50 lines)
- Neutral palette (near-white backgrounds, subtle gray borders, dark text)
- One accent color derived from Scout's brand for interactive elements (buttons, focus states)
- System font stack: `Inter, system-ui, -apple-system, 'Segoe UI', sans-serif`
- Spacing scale: 4px base (4, 8, 12, 16, 24, 32, 48)
- Border radius: 6px for inputs, 8px for cards, 12px for containers
- No shadows, no gradients — thin 1px borders only
- Color tokens for: background, surface, border, text-primary, text-secondary, text-muted, accent, accent-hover, success, error

**Step 3: Verify the file exists and is well-formed**

```bash
cat assets/stages/stage-tokens.css
```

Verify: CSS variables defined under `:root`, no syntax errors, ~50 lines.

**Step 4: Commit**

```bash
git add assets/stages/stage-tokens.css
git commit -m "feat(demo): add shared design tokens for stage pages"
```

---

### Task 2: Build portal stage page

**Files:**
- Create: `assets/stages/portal.html`
- Reference: `assets/stages/stage-tokens.css` (from Task 1)
- Reference: `assets/demo-form.html` (existing dark-themed form — for structural inspiration, NOT style)

**Step 1: Design and build the portal page**

Use `/frontend-design` to create `portal.html` with these requirements:

**Layout:**
- Imports `stage-tokens.css` via `<link>` (relative path: `stage-tokens.css`)
- Top nav bar: logo placeholder (styled text, not an image), 3-4 nav links (Dashboard, Reports, Settings, Help)
- Left sidebar: 5-6 menu items (Overview, Employees, Payroll, Benefits, Time Off, Documents) — non-interactive, just visual structure
- Main content area: centered login card
- Login card: "Sign In" heading, username input, password input, "Sign In" button, "Forgot password?" link
- All inputs have `name`, `id`, `aria-label`, `data-testid`, and `placeholder` attributes (Scout surfaces these during scouting — they need to be there)

**Design language:**
- Elevated wireframe — recognizable portal pattern, minimal styling
- Uses only tokens from `stage-tokens.css`
- No JavaScript needed (static page for scouting and form-fill demos)
- No fake company name — page title is just "Portal"

**Viewport:** Design for 800x500 capture viewport

**Step 2: Open in browser and verify**

```bash
start assets/stages/portal.html
```

Verify: Page renders at 800x500 with visible nav, sidebar, and centered login form. All inputs are focusable and have proper attributes.

**Step 3: Commit**

```bash
git add assets/stages/portal.html
git commit -m "feat(demo): add portal stage page for scout and form demos"
```

---

### Task 3: Build dashboard stage page

**Files:**
- Create: `assets/stages/dashboard.html`
- Reference: `assets/stages/stage-tokens.css` (from Task 1)

**Step 1: Design and build the dashboard page**

Use `/frontend-design` to create `dashboard.html` with these requirements:

**Layout:**
- Imports `stage-tokens.css`
- Header with breadcrumb: "Reports > Monthly Summary"
- Page title: "Monthly Report" with a date range subtitle (e.g., "March 2026")
- Data table with 5 rows, 4 columns: Name, Department, Status, Date
  - Sample data: clean, realistic names/departments
  - Status column uses colored badges (Active/Pending/Complete) using token colors
- "Export CSV" button in the top-right of the table section, styled with accent color
- All table cells, rows, and the export button have `data-testid` attributes

**Behavior:**
- Clicking "Export CSV" shows a brief success toast: "Report exported — enrollment_march_2026.csv"
- Toast appears for 3 seconds then fades — this provides visual feedback in the capture
- Minimal JavaScript for the toast only (~15 lines)

**Viewport:** 800x500

**Step 2: Open in browser and verify**

```bash
start assets/stages/dashboard.html
```

Verify: Table renders with 5 rows. Export button is prominent. Clicking it shows the toast.

**Step 3: Commit**

```bash
git add assets/stages/dashboard.html
git commit -m "feat(demo): add dashboard stage page for data extraction and export demos"
```

---

### Task 4: Build components stage page

**Files:**
- Create: `assets/stages/components.html`
- Reference: `assets/stages/stage-tokens.css` (from Task 1)

**Step 1: Design and build the components page**

Use `/frontend-design` to create `components.html` with these requirements:

**Layout:**
- Imports `stage-tokens.css`
- Page title: "Components"
- 2x2 grid of component cards, each containing one interactive element:
  1. **Button card** — A primary button labeled "Submit Order" with `data-testid="submit-order"`, `aria-label="Submit your order"`, specific font-size, padding, border-radius (these are the values Scout will reveal during inspection)
  2. **Text input card** — A labeled input "Search products" with placeholder, `aria-label`, `role="searchbox"`
  3. **Dropdown card** — A `<select>` with 4 options (Department: Engineering, Design, Marketing, Sales)
  4. **Checkbox group card** — 3 checkboxes (Notifications: Email, SMS, Push) with `name`, `value`, `aria-label` on each

**Design language:**
- Each card has a subtle label above it describing the component type (muted text)
- Generous spacing between cards
- Components are full-size, not miniaturized — they need to be clearly visible at 800x500

**No JavaScript needed** — static page for inspection demos.

**Step 2: Open in browser and verify**

```bash
start assets/stages/components.html
```

Verify: 4 component cards visible. All elements have proper accessibility attributes. Button, input, select, and checkboxes are all full-size and interactive.

**Step 3: Commit**

```bash
git add assets/stages/components.html
git commit -m "feat(demo): add components stage page for element inspection demos"
```

---

### Task 5: Build scout capture script

**Files:**
- Create: `scripts/capture_scout.py`
- Reference: `scripts/capture_demo_frames.py` (existing pattern for `take_frame`, `hold_frame`, driver setup)
- Target: `assets/stages/portal.html`

**Step 1: Write the capture script**

The script should:
1. Open `portal.html` via `file://` URL (resolve absolute path from script location)
2. Set viewport to 800x500 via CDP `Emulation.setDeviceMetricsOverride`
3. Wait for page load (2s)
4. Capture frames showing the full portal page
5. Use `hold_frame` to pause on the initial view (~1.5s worth of frames at 10fps = 15 frames)
6. Optionally: use JS to add a subtle highlight/outline around major page sections sequentially (nav, sidebar, form) to visually suggest "Scout is reading the page structure" — if this adds too much complexity, skip it and just hold on the static page
7. Final hold (~1s)
8. Close driver

```python
"""Capture scout demo: Scout reads page structure.

Usage:
    python scripts/capture_scout.py
"""
import os
import sys

# Add project root so we can import the shared capture helpers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.capture_demo_frames import take_frame, hold_frame

from botasaurus_driver import Driver

OUTPUT_DIR = os.path.join("assets", "frames_scout_stage")
STAGE_PAGE = os.path.abspath(os.path.join("assets", "stages", "portal.html"))
VIEWPORT = (800, 500)


def capture():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    driver = Driver()

    # Set viewport
    driver.run_cdp_command({
        "method": "Emulation.setDeviceMetricsOverride",
        "params": {
            "width": VIEWPORT[0],
            "height": VIEWPORT[1],
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    })

    driver.get(f"file:///{STAGE_PAGE}")
    import time; time.sleep(2)

    f = 0
    # Hold on initial page view
    f = hold_frame(driver, OUTPUT_DIR, f, 15)

    # Final hold
    f = hold_frame(driver, OUTPUT_DIR, f, 10)

    driver.close()
    print(f"Captured {f} frames in {OUTPUT_DIR}")


if __name__ == "__main__":
    capture()
```

> **Note:** The CDP command for viewport may need adjustment based on botasaurus-driver's API. Check `capture_demo_frames.py` for how the driver is initialized — it may handle viewport sizing differently. The implementer should verify the CDP call works and adjust if needed.

**Step 2: Run the script and verify frames are captured**

```bash
python scripts/capture_scout.py
ls assets/frames_scout_stage/ | head -5
```

Expected: JPEG frames in `assets/frames_scout_stage/`, numbered sequentially.

**Step 3: Encode frames to GIF**

```bash
ffmpeg -y -framerate 10 -i assets/frames_scout_stage/frame_%06d.jpg -vf "fps=10,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" assets/demo-scout.gif
```

Expected: `demo-scout.gif` under 500KB showing the portal page.

**Step 4: Commit**

```bash
git add scripts/capture_scout.py
git commit -m "feat(demo): add scout capture script for portal stage"
```

---

### Task 6: Build form-fill capture script

**Files:**
- Create: `scripts/capture_form.py`
- Reference: `scripts/capture_demo_frames.py` (for `type_into_field`, `hold_frame`, `take_frame`)
- Target: `assets/stages/portal.html`

**Step 1: Write the capture script**

The script should:
1. Open `portal.html` via `file://`
2. Set viewport to 800x500
3. Hold on empty form (~1s)
4. Click username field, type "admin@company.com" char by char (capturing frame per char)
5. Hold briefly (~0.5s)
6. Click password field, type "••••••••" (8 bullet chars) to simulate `fill_secret` behavior
7. Hold briefly (~0.5s)
8. Click "Sign In" button
9. Hold on result (~1s)
10. Close driver

Use the same `type_into_field` pattern from `capture_demo_frames.py`. For the password field, type actual bullet characters (`\u2022`) to visually convey that the real password is never visible.

**Step 2: Run and verify**

```bash
python scripts/capture_form.py
ls assets/frames_form_stage/ | wc -l
```

Expected: ~80-120 frames (typing is frame-per-char).

**Step 3: Encode to GIF**

```bash
ffmpeg -y -framerate 10 -i assets/frames_form_stage/frame_%06d.jpg -vf "fps=10,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" assets/demo-form.gif
```

**Step 4: Commit**

```bash
git add scripts/capture_form.py
git commit -m "feat(demo): add form-fill capture script for portal stage"
```

---

### Task 7: Build data extraction capture script

**Files:**
- Create: `scripts/capture_data.py`
- Reference: `scripts/capture_demo_frames.py`
- Target: `assets/stages/dashboard.html`

**Step 1: Write the capture script**

The script should:
1. Open `dashboard.html` via `file://`
2. Set viewport to 800x500
3. Hold on dashboard view (~1.5s)
4. Optionally: use JS to highlight table rows one by one (add/remove a CSS class with a subtle background color) to suggest "Scout is reading the data" — 5 rows, ~0.3s per row
5. Hold briefly
6. Click "Export CSV" button
7. Capture the toast notification appearing
8. Hold on toast (~1.5s)
9. Close driver

**Step 2: Run and verify**

```bash
python scripts/capture_data.py
```

**Step 3: Encode to GIF**

```bash
ffmpeg -y -framerate 10 -i assets/frames_data_stage/frame_%06d.jpg -vf "fps=10,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" assets/demo-data.gif
```

**Step 4: Commit**

```bash
git add scripts/capture_data.py
git commit -m "feat(demo): add data extraction capture script for dashboard stage"
```

---

### Task 8: Build element inspection capture script

**Files:**
- Create: `scripts/capture_inspect.py`
- Reference: `scripts/capture_demo_frames.py`
- Target: `assets/stages/components.html`

**Step 1: Write the capture script**

The script should:
1. Open `components.html` via `file://`
2. Set viewport to 800x500
3. Hold on components grid (~1s)
4. Use JS to simulate an inspection overlay on the "Submit Order" button:
   - Add a dashed outline (2px dashed accent color) around the button
   - Display a small tooltip-like box below the button showing computed properties:
     ```
     font: 14px/1.5 Inter
     padding: 12px 24px
     border-radius: 8px
     aria-label: "Submit your order"
     ```
   - This tooltip is injected via JS (`document.createElement`) — it's part of the capture choreography, not the static page
5. Hold on the inspection view (~2s)
6. Close driver

**Step 2: Run and verify**

```bash
python scripts/capture_inspect.py
```

**Step 3: Encode to GIF**

```bash
ffmpeg -y -framerate 10 -i assets/frames_inspect_stage/frame_%06d.jpg -vf "fps=10,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" assets/demo-inspect.gif
```

**Step 4: Commit**

```bash
git add scripts/capture_inspect.py
git commit -m "feat(demo): add element inspection capture script for components stage"
```

---

### Task 9: Build automate capture script

**Files:**
- Create: `scripts/capture_automate.py`
- Reference: `scripts/capture_demo_frames.py`
- Target: `assets/stages/dashboard.html`

**Step 1: Write the capture script**

The script should:
1. Open `dashboard.html` via `file://`
2. Set viewport to 800x500
3. Hold on dashboard (~1s)
4. Click "Export CSV"
5. Capture toast
6. Use JS to replace the toast content with a schedule confirmation:
   - Inject or modify the toast to read: "Scheduled: Every Monday at 6:00 AM"
   - Add a small calendar/clock icon (CSS-only or Unicode: `📅`) if it fits the elevated wireframe aesthetic — otherwise just text
7. Hold on schedule confirmation (~2s)
8. Close driver

> **Note:** This script reuses the dashboard page but adds a second act (the scheduling confirmation). The implementer may want to add a CSS transition between the export toast and the schedule toast to make the sequence feel smooth.

**Step 2: Run and verify**

```bash
python scripts/capture_automate.py
```

**Step 3: Encode to GIF**

```bash
ffmpeg -y -framerate 10 -i assets/frames_automate_stage/frame_%06d.jpg -vf "fps=10,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" assets/demo-automate.gif
```

**Step 4: Commit**

```bash
git add scripts/capture_automate.py
git commit -m "feat(demo): add automation capture script for export+schedule demo"
```

---

### Task 10: Rewrite README.md around story arc

**Files:**
- Modify: `README.md`
- Reference: `docs/plans/2026-03-03-readme-story-arc-design.md` (design doc — README structure section)

**Step 1: Back up the current README**

```bash
cp README.md README.md.bak
```

**Step 2: Rewrite README.md**

Follow the structure from the design doc exactly:

```markdown
<p align="center">
  <img src="assets/logo.png" alt="Scout" width="200">
</p>

<h1 align="center">Scout</h1>

<p align="center">
  <em>Stop clicking.</em>
</p>

---

Scout ("auto") is browser automation for Claude Code. You describe what you need
done on a website and Claude opens a browser, figures out the page, and does it.

No scripts. No selectors. You talk, Claude browses.

## See the page

[scout GIF + brief explanation — 200 tokens to understand a page]

## Do something with it

[form-fill GIF]   [data GIF]   [inspect GIF]
[Brief explanation per demo — interact with natural language]

## Make it run itself

[automate GIF]
[Brief explanation — export once, schedule forever]

## What can you say?

[Short header + prompt pairs — 8 example prompts with 1-3 word headers]

## Your Passwords Stay Out of It
[Preserved from current README]

## 2FA Doesn't Break It
[Preserved from current README]

## Sites Can't Tell It's Not You
[Preserved from current README — keep anti-detection GIF]

## Why Scout
[Comparison table — preserved]

## Benchmarks
[Preserved]

## Security
[Preserved]

## Install
[Preserved]

## What You Get
[Tools table, slash commands — preserved]

## License
MIT
```

**Key changes from current README:**
- "How It Works" → replaced by "See the page" chapter
- "Export and Schedule" → replaced by "Make it run itself" chapter
- Example prompts → moved under "What can you say?" with short headers
- All demo GIFs point to new stage-captured versions
- Reference sections (Security, Install, What You Get) → unchanged, moved to bottom

**Step 3: Verify all image references resolve**

```bash
grep -o 'src="[^"]*"' README.md
```

Verify: All `src=` paths point to files that exist in `assets/`.

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: redesign README around three-chapter story arc"
```

---

### Task 11: Clean up old assets

**Files:**
- Delete: `assets/frames_scout/` (old scout frames)
- Delete: `assets/frames_form/` (old form frames)
- Delete: `assets/frames_replay/` (old replay frames)
- Keep: `assets/demo-antidetection.gif` (still used in README)
- Keep: `assets/demo-form.html` (local form page, may be useful for other demos)
- Delete: `README.md.bak` (backup from Task 10)

**Step 1: Remove old frame directories**

```bash
rm -rf assets/frames_scout assets/frames_form assets/frames_replay
rm -f README.md.bak
```

**Step 2: Remove new frame directories (no longer needed after GIF encoding)**

```bash
rm -rf assets/frames_scout_stage assets/frames_form_stage assets/frames_data_stage assets/frames_inspect_stage assets/frames_automate_stage
```

**Step 3: Verify asset directory is clean**

```bash
ls assets/
```

Expected: GIF files, stage pages directory, icons, logos. No stale frame directories.

**Step 4: Commit**

```bash
git add -A assets/ README.md.bak
git commit -m "chore: clean up old demo frame directories"
```

---

### Task 12: Final review and verification

**Step 1: Verify all GIFs are under 500KB**

```bash
ls -la assets/demo-*.gif
```

Any GIF over 500KB needs re-encoding with lower quality or fewer frames.

**Step 2: Verify README renders correctly**

Open `README.md` in a markdown previewer (VS Code or GitHub) and check:
- All GIFs load and animate
- Story arc flows naturally: See → Do → Automate
- Example prompts have short headers
- Reference sections are intact
- No broken links or image references

**Step 3: Verify stage pages render correctly**

Open each stage page in a browser at 800x500 and check:
- Consistent visual language across all 4 pages
- All interactive elements have proper attributes (`data-testid`, `aria-label`, etc.)
- Dashboard toast works on Export CSV click

**Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: final polish on story arc demos"
```
