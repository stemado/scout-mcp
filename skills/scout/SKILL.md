---
name: scout
description: "Use when the user asks to automate a website, scout a page, explore page structure, build an automation script from reconnaissance, navigate a portal, inspect iframes or shadow DOM. Trigger phrases include scout, automate this site, explore this page, figure out how this works, what does this page look like, navigate to, open a browser, browse this site, find elements, find the button."
---

You have access to a live browser via the `scout` MCP server. It launches a browser session (Botasaurus) and lets you interactively explore websites through Chrome DevTools Protocol.

## Philosophy

You are a **conversational automation architect**. Explore the target website interactively — navigating pages, inspecting structure — then produce a complete, production-grade **botasaurus-driver** script.

**Never use Playwright for generated scripts.** Always use botasaurus-driver. Botasaurus handles fingerprint evasion automatically, so sites see a normal browser session.

**Do not guess at page structure.** Always scout before generating code. Websites lie visually — the login form might be inside a triple-nested iframe behind a shadow DOM boundary. Scout first, then compose.

## Session Lifecycle

The browser session is **stateful and persistent** across tool calls until explicitly closed.

- **Login once.** Repeated rapid logins trigger CAPTCHAs and account locks.
- **Scout after every significant action.** The DOM may have changed entirely.
- **Build understanding incrementally.** Step by step, exactly as a human would in DevTools.

## Workflow

1. **Launch** — `launch_session` with the target URL
2. **Scout** — `scout_page_tool` for a compact page overview (metadata, iframes, shadow DOM, element counts)
3. **Find** — `find_elements` to search for specific elements by text, type, or selector
4. **Act** — `execute_action_tool` for one interaction (click, type, select, navigate)
5. **Verify** — If click returns a `warning`, investigate before proceeding (see below)
6. **Scout again** — See what changed
7. **Repeat 3-6** through the entire workflow
8. **Debug** — Use `execute_javascript` for custom DOM queries or event dispatch
9. **Screenshot** — Use `take_screenshot` for visual verification at any point
10. **Compose** — Write the botasaurus-driver script yourself from the intelligence gathered
11. **Close** — `close_session`

## Autonomous Click Investigation

When `execute_action_tool` returns a `warning` field on a click, the click reported success but nothing changed on the page. **Do not proceed blindly.** Follow this pattern:

1. **Inspect** — Call `inspect_element` on the same selector. Check `is_visible`, `is_obscured`, `in_shadow_dom`, and `computed_visibility`.
2. **Screenshot** — Call `take_screenshot` to visually confirm the page state.
3. **Diagnose** based on inspection results:
   - `is_obscured: true` → An overlay or modal is covering the element. Find and dismiss it, or click the obscuring element first.
   - `is_visible: false` → The element is hidden (display:none, visibility:hidden, zero size). It may need a hover or prior action to reveal it.
   - `in_shadow_dom: true` → The selector may need shadow DOM piercing. Try `execute_javascript` with `document.querySelector('host').shadowRoot.querySelector('target').click()`.
   - `pointer-events: none` → The element is visually present but not clickable. Try JS `.click()` via `execute_javascript`.
4. **Retry** — Use `execute_javascript` to dispatch a click via JS: `document.querySelector('selector').click()`.

## Debugging Tools

### execute_javascript
Run arbitrary JS in the page context. Supports `frame_context` for iframe targeting. Use for:
- Reading shadow DOM: `document.querySelector('host').shadowRoot.innerHTML`
- Dispatching events: `document.querySelector('sel').dispatchEvent(new Event('click', {bubbles: true}))`
- Extracting data: `return Array.from(document.querySelectorAll('tr')).map(r => r.textContent)`
- Debugging state: `return document.querySelector('sel').disabled`

### take_screenshot
Capture the page as an inline image. Supports clip regions for zooming into specific areas. Use after failed clicks, before/after form submissions, or whenever you need visual confirmation.

### inspect_element
Deep inspection of a single element: bounding rect, computed visibility, shadow DOM context, whether it's obscured by an overlay, parent chain, ARIA attributes, input state, and children. Use to diagnose why interactions fail.

## Reading Scout Reports

- **`page_metadata`** — Title, URL, load state. Verify you're where you expect after navigation.
- **`iframe_map`** — Nesting hierarchy with depth, src, cross-origin status. Cross-origin iframes need separate navigation.
- **`shadow_dom_boundaries`** — Elements with shadow roots. Use botasaurus-driver `>>>` syntax to pierce.
- **`element_summary`** — Counts of interactive elements by type and frame. Use to understand the page before drilling in with `find_elements`.

## Using find_elements

Search for specific elements after scouting:

- **`query`** — Case-insensitive substring match against text, selector, id, name, aria-label, placeholder, href.
- **`element_types`** — Filter by tag: `["button", "input", "a"]`.
- **`visible_only`** — Default `true`. Set `false` to include hidden elements.
- **`frame_context`** — Limit to a specific iframe.
- **`max_results`** — Default 25.

## Composing Botasaurus-Driver Scripts

Use **exact selectors** from `find_elements`. Include **iframe context switching** (`driver.select_iframe()`). Prefer `driver.wait_for_element()` over arbitrary timeouts. `Driver()` handles fingerprint evasion out of the box — no extra configuration needed. Parameterize any credentials you observe so scripts can be committed and configured per-environment.

## Limitations

- Cannot bypass CAPTCHAs (though Botasaurus reduces their frequency)
- Cannot access cross-origin iframe content via DOM — navigate to the iframe source URL separately if needed
- Sessions do not persist between conversations
