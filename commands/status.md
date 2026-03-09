---
description: Check execution status on the remote scout-engine server
argument-hint: "[execution-id]"
---

View execution status from the remote scout-engine server.

## Prerequisites

Check if `.claude/scout.local.md` exists in the current working directory. If not, tell the user: "No engine connection configured. Run `/connect` first."

Read the `engine_url` and `engine_api_key` from the YAML frontmatter.

## Mode A: List recent executions (no argument)

1. Fetch recent executions:
   ```
   GET {engine_url}/api/executions
   Authorization: Bearer {api_key}
   ```
   If the URL is an IP address, skip TLS verification.

2. Display as a table (last 10), showing:
   - **ID** (first 8 chars)
   - **Workflow** name
   - **Status** (pending/running/completed/failed/cancelled)
   - **Started** (relative time, e.g., "2 min ago")
   - **Duration** (e.g., "45s" or "running...")

   If no executions exist: "No executions found. Run a workflow with `/run <name>`."

## Mode B: Execution detail (argument provided)

1. Fetch execution detail:
   ```
   GET {engine_url}/api/executions/{execution_id}
   Authorization: Bearer {api_key}
   ```

   If 404: "Execution '{id}' not found."

2. Display execution header:
   - Workflow name, status, started at, total duration
   - If failed: show the error message

3. Display step-by-step results as a table:
   - **#** (step order)
   - **Step** name
   - **Action** (navigate, click, type, etc.)
   - **Status** (passed/failed/skipped/pending)
   - **Time** (elapsed ms)
   - **Error** (if failed, show error message)

4. If the execution is running or paused, mention: "This execution is still in progress. Use `/attach {id}` to take over the browser."

## Error Handling

- Connection errors: "Cannot reach scout-engine at {url}. Is the server running?"
- 401/403: "API key rejected. Run `/connect` to reconfigure."

Use `httpx` for all HTTP calls.
