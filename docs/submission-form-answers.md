# Scout — Claude Plugin Directory Submission

Copy-pasteable answers for the Anthropic Plugin Directory submission form.

---

## Plugin Name

Scout

## Plugin Description

Scout turns any web portal into a programmable API. Enterprise teams use it to automate vendor dashboards, HR portals, and internal tools that were never designed to be automated — systems locked behind logins with no API in sight. Claude scouts the page structure through collaborative navigation, drives the workflow step by step, and exports a standalone Python script that runs unattended. Includes runtime secret scrubbing, network interception, and video recording. No web development knowledge required.

## Is this plugin for Claude Code or Cowork?

Claude Code

## Link to GitHub

https://github.com/stemado/scout

## Company/Organization URL

https://github.com/stemado

## Primary Contact Email

frankdoherty1921@gmail.com

## Plugin Examples

**1. Enterprise Report Automation**

"Log into our vendor portal, navigate to Reports > Monthly Summary, export the CSV, and convert it to our standard format." Scout scouts the login page (discovering the form inside nested iframes), handles credential injection securely, navigates the report interface, captures the download via network monitoring, and exports a replayable script you can run on a schedule.

**2. HR/Benefits Portal Workflow**

"Check our benefits platform for open enrollment status and pull the current plan summary." Scout navigates the authentication flow, discovers the SPA navigation structure, extracts the relevant data, and produces a standalone automation — turning a 15-minute manual process into a one-command operation.

**3. SaaS Data Extraction**

"Pull the last 30 days of activity data from our project management dashboard — there's no export button." Scout scouts the page to find the data table, monitors the XHR calls that populate it, discovers the underlying API endpoint, and produces a script that hits the API directly with the session cookies — faster and more reliable than browser-based scraping.
