---
description: "Run a full Scout capabilities demo — scouts, scrapes, records, and exports"
allowed-tools:
  - "mcp__plugin_scout_scout__*"
  - "Write"
  - "Bash"
  - "TodoWrite"
---

Run a comprehensive demo of Scout's browser automation capabilities against Reddit. Launch a session, scout the page, extract data, capture artifacts, and produce a timestamped folder of outputs including a replayable script.

## Setup

### Detect model name

Look in the injected system prompt context for a phrase like "You are powered by the model named..." or "The model named..." and extract the model name (e.g., "Claude Opus 4.6"). Store it for the demo report. If not detectable, use "Unknown".

### Create output directory

Run via Bash:
```bash
mkdir -p scout-demo/$(date +%Y-%m-%d_%H-%M-%S)
```

Store the full path as `OUTPUT_DIR` — all artifacts will be written here.

### Create progress checklist

Use TodoWrite to create a checklist matching the five execution phases:
1. Launch & Record — open browser, start video and network capture
2. Scout & Discover — scout page, handle bot detection, find elements, scroll
3. Extract Data — JavaScript extraction of posts, deep element inspection
4. Capture Artifacts — screenshot, network log, session history, stop recording, close session
5. Generate Outputs — write all 8 artifact files to output directory

## Phase 1: Launch & Record

1. Call `launch_session` with `url="https://www.google.com"` and `headless=false`.

   **Why Google first:** Navigating directly to a complex site like Reddit with a fresh browser session triggers bot detection — the fingerprint looks like a just-spawned automation tool. Visiting Google first warms the browser fingerprint: cookies get set, TLS sessions establish, and the browsing pattern looks natural by the time we reach the target site.

2. Call `record_video` with `command="start"` using the session_id.

3. Call `monitor_network` with `command="start"` using the session_id.

4. Call `execute_action_tool` with `action="navigate"` and `value="https://old.reddit.com"` to warm Reddit's cookie domain.

   **Why old.reddit.com first:** Google warms the TLS/fingerprint layer, but Reddit's bot detection (PerimeterX/HUMAN) also checks for existing `.reddit.com` cookies. `old.reddit.com` sets tracking cookies (`loid`, `session_tracker`, `csv`) on the shared `.reddit.com` domain. When we then navigate to `www.reddit.com`, those cookies signal "returning visitor" and the CAPTCHA gate is bypassed. Two warm-up layers: Google for the browser fingerprint, old.reddit.com for the application-layer identity.

5. Call `execute_action_tool` with `action="navigate"` and `value="https://www.reddit.com"` to navigate to the target site.

## Phase 2: Scout & Discover

6. Call `scout_page_tool` with the session_id to get the structural overview.

7. **Assess the page state.** Check whether Reddit loaded correctly or if bot detection triggered (CAPTCHA, interstitial, challenge page, blank content, or a "verify you're human" prompt).

   If bot detection triggered:
   - You are NOT a bot — you browse on behalf of the user with their authorization.
   - Problem-solve: diagnose what triggered detection from the scout report.
   - If there is a "click to verify" button or human-check element, click it with `execute_action_tool`.
   - After any recovery action, scout again and re-assess.
   - Note the incident and resolution — include it in the demo report.
   - Continue the demo with whatever state was recovered.

   If the page loaded normally, note that anti-detection succeeded.

**General error handling:** If any tool call fails during the demo, note the failure in the demo report and continue with the remaining steps. The demo should produce as many artifacts as possible even if individual steps encounter issues.

8. Call `find_elements` to search for post-like elements. Use what the scout report revealed about the page structure — do NOT hardcode selectors. Try queries like "post", "article", or look for repeated content containers from the element summary.

9. Call `execute_action_tool` with `action="scroll"` to scroll down and trigger lazy-loaded content. Use a reasonable scroll distance based on the viewport.

10. Call `scout_page_tool` again after scrolling. Note any changes in element counts or new content that loaded.

## Phase 3: Extract Data

11. Call `execute_javascript` to extract the top 10 posts visible on the page. The script should collect whatever fields are available based on what scouting revealed — prioritize: title, URL, score, author, subreddit, and comment count. Return as a JSON array.

    Do NOT hardcode selectors in the script — use what you discovered during scouting. If the page structure makes certain fields unavailable, extract what you can and note the gaps.

12. Call `inspect_element_tool` on one interesting element from the page (e.g., the first post container, a navigation element, or a shadow DOM boundary if one exists). Choose something that demonstrates the depth of DOM inspection.

## Phase 4: Capture Artifacts

13. Call `take_screenshot_tool` with the session_id to capture the final page state.

14. Call `monitor_network` with `command="stop"`, then call `monitor_network` with `command="query"` and `limit=100` to retrieve captured network events.

15. Call `get_session_history` to retrieve the complete session log. Count the total number of tool calls in the history.

16. Call `record_video` with `command="stop"` to finalize the recording. Note the video file path from the response.

17. Call `close_session`. Record `session_duration_seconds` from the response.

## Phase 5: Generate Outputs

Write all artifacts to `OUTPUT_DIR`:

### 18. scraped-items.json

Write the extracted posts array from Phase 3, pretty-printed with 2-space indent.

### 19. element-inspection.json

Write the full inspection result from step 12, pretty-printed.

### 20. network-log.json

Write the network events from step 14. For each event include: URL, method, status code, and content-type (where available). Pretty-print with 2-space indent.

### 21. session-history.json

Write the complete session history from step 15, pretty-printed.

### 22. screenshot.png

The `take_screenshot_tool` auto-saves the image to disk and returns its `file_path` in the response JSON. Use Bash `cp` to copy it into `OUTPUT_DIR/screenshot.png` using that path.

### 23. recording.mp4

The `record_video` stop response includes a `video_path` field. Use Bash `cp` to copy the MP4 into `OUTPUT_DIR/recording.mp4` using that path.

### 24. replay.py

Write a self-contained botasaurus-driver script that replays the browsing session. Structure it as:

```python
"""Scout Demo Replay — Reddit Homepage Scrape
Generated from Scout demo session on <date>.
Session: <session_id> | Duration: <session_duration>s

Setup:
    pip install botasaurus-driver
    python replay.py
"""
import random
import time
from botasaurus_driver import Driver

# --- Configuration ---
BASE_URL = "https://www.reddit.com"
```

Include:
- The exact selectors discovered during scouting — not guesses
- Randomized delays between actions: `time.sleep(random.uniform(0.3, 0.8))` for interactions, `driver.short_random_sleep()` after navigation
- Comments explaining each step
- A `try/finally` block to ensure `driver.close()` is always called
- No credentials (this is a read-only scraping demo — no dotenv, no `human_type()` helper needed)

### 25. demo-report.md

Write a human-readable summary report:

```markdown
# Scout Demo Report

**Date:** <YYYY-MM-DD HH:MM:SS>
**Model:** <detected model name>
**Target:** https://www.reddit.com
**Session Duration:** <session_duration_seconds>s
**Total Tool Calls:** <count from session history>

---

## Capabilities Exercised

| # | Tool | Purpose | Result |
|---|------|---------|--------|
| 1 | launch_session | Open browser to Google (warm fingerprint) | <success/fail + note> |
| 2 | record_video (start) | Begin screen recording | <success/fail> |
| 3 | monitor_network (start) | Begin network capture | <success/fail> |
| 4 | execute_action_tool (navigate) | Navigate to old.reddit.com (warm cookies) | <success/fail> |
| 5 | execute_action_tool (navigate) | Navigate to www.reddit.com | <success/fail> |
| 6 | scout_page_tool | Structural overview | <element counts summary> |
| 7 | find_elements | Discover post selectors | <N elements found> |
| 8 | execute_action_tool | Scroll for lazy content | <success/fail> |
| 9 | scout_page_tool | Post-scroll re-scout | <delta in element counts> |
| 10 | execute_javascript | Extract top 10 posts | <N posts extracted> |
| 11 | inspect_element_tool | Deep DOM analysis | <element inspected> |
| 12 | take_screenshot_tool | Capture page state | <screenshot path> |
| 13 | monitor_network (stop+query) | Retrieve network log | <N requests captured> |
| 14 | get_session_history | Full session log | <N actions recorded> |
| 15 | record_video (stop) | Finalize recording | <video path> |
| 16 | close_session | Release browser | <duration>s |

## Anti-Detection Outcome

<Was full content served? Did any challenges appear? How were they resolved?>

## Scraped Data

<Numbered list of extracted posts: title, subreddit, score — whatever was available>

## Network Activity

- **Total requests captured:** <N>
- **Domains contacted:** <list of unique domains>
- **Content types:** <breakdown of response types>

## Artifacts

| File | Description |
|------|-------------|
| scraped-items.json | <N> extracted posts |
| element-inspection.json | Deep DOM inspection of <element> |
| network-log.json | <N> network events |
| session-history.json | Complete session history |
| screenshot.png | Final page state |
| recording.mp4 | Full session video |
| replay.py | Replayable botasaurus-driver script |
| demo-report.md | This report |
```

Adapt the table rows and details to reflect what actually happened during the demo — do not fabricate results.

## Completion

Present a concise summary to the user:

```
Scout Demo Complete
─────────────────
Output:    <OUTPUT_DIR absolute path>
Duration:  <session_duration_seconds>s
Tools:     <N> tool calls across <N> unique tools
Posts:     <N> extracted
Detection: <full content served / challenge encountered + resolution>

Artifacts (8 files):
  scraped-items.json      network-log.json       screenshot.png
  element-inspection.json session-history.json    recording.mp4
  replay.py               demo-report.md
```
