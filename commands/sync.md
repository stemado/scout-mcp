---
description: Upload a workflow to the remote scout-engine server
argument-hint: "[workflow-name]"
allowed-tools:
  - "mcp__plugin_scout_scout__*"
---

Upload a workflow to the remote scout-engine server for execution and scheduling.

## Prerequisites

Check if `.claude/scout.local.md` exists in the current working directory. If not, tell the user: "No engine connection configured. Run `/connect` first."

Read the `engine_url` and `engine_api_key` from the YAML frontmatter.

## Two Modes

### Mode A: Sync from exported workflow (argument provided)

If the user provided a `workflow-name` argument:

1. Read the workflow JSON from `workflows/{name}/{name}.json`.
   If the file doesn't exist, tell the user: "Workflow '{name}' not found. Export one first with `/export-workflow {name}`." and list available workflows by checking `workflows/*/`.

2. Parse the JSON and POST it to the engine:
   ```
   POST {engine_url}/api/workflows
   Authorization: Bearer {api_key}
   Content-Type: application/json

   {"workflow": <parsed JSON object>}
   ```
   If the URL is an IP address, skip TLS verification.

3. Report: "Synced workflow '{name}' to engine (id: {id}). Run it with `/run {name}`."

### Mode B: Sync from active session (no argument)

If no argument was provided:

1. Call `get_session_history` with the active session_id. If no session is active, tell the user: "No active session and no workflow name provided. Either start a session with `/scout` or specify a workflow name: `/sync my-workflow`."

2. Ask the user for a workflow name: "What should this workflow be called?"

3. Build the workflow JSON using `WorkflowConverter.from_history()` from `src/scout/workflow.py`:
   - Import: `from scout.workflow import WorkflowConverter`
   - Call: `workflow = WorkflowConverter.from_history(history, name=name, description=description)`
   - Serialize: `workflow.model_dump(exclude_none=True)`

4. POST the serialized workflow to the engine (same as Mode A step 2).

5. Report: "Synced workflow '{name}' to engine (id: {id}). Run it with `/run {name}`."

## Error Handling

- Connection errors: "Cannot reach scout-engine at {url}. Is the server running?"
- 401/403: "API key rejected. Run `/connect` to reconfigure."
- 422 (validation error): Show the engine's error message.

Use `httpx` for all HTTP calls.
