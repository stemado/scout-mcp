---
description: Open a browser and scout a website's page structure
argument-hint: "<url>"
allowed-tools:
  - "mcp__plugin_scout_scout__*"
---

Open a browser and scout the page structure of the provided URL. Follow these steps:

1. Call `launch_session` with the URL from the user's argument. Use headed mode (headless=false) so the user can observe.

2. Call `scout_page_tool` with the session_id to get a compact page overview (metadata, iframes, shadow DOM, element counts).

3. Present the scout report to the user in a clear summary:
   - Page title and URL
   - Number of iframes (noting any cross-origin)
   - Shadow DOM boundaries found
   - Element counts by type (buttons, inputs, links, etc.)

4. Ask the user what they'd like to do next:
   - Find specific elements (use `find_elements` with a query)
   - Explore further (click, type, navigate)
   - Close the session

Keep the session alive for follow-up interactions. Do NOT close it unless the user asks.

If no URL is provided, ask the user what site they want to scout.
