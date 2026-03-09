---
description: Run a workflow on the remote scout-engine server
argument-hint: "<workflow-name>"
---

Trigger a workflow execution on the remote scout-engine server.

## Prerequisites

Check if `.claude/scout.local.md` exists in the current working directory. If not, tell the user: "No engine connection configured. Run `/connect` first."

Read the `engine_url` and `engine_api_key` from the YAML frontmatter.

## Steps

1. **Resolve the workflow.**
   The argument may be a name (e.g., "login-report") or a UUID. First, list all workflows:
   ```
   GET {engine_url}/api/workflows
   Authorization: Bearer {api_key}
   ```
   If the URL is an IP address, skip TLS verification.

   Search the results for a match:
   - Exact match on `name` field (case-insensitive)
   - Exact match on `id` field
   - Partial/fuzzy match on `name` — if multiple matches, list them and ask the user which one

   If no match found: "Workflow '{arg}' not found on engine. Available workflows:" then list them. Suggest `/sync` if the list is empty.

2. **Trigger execution.**
   ```
   POST {engine_url}/api/workflows/{workflow_id}/run
   Authorization: Bearer {api_key}
   ```

3. **Report.**
   "Execution started for '{workflow_name}' (execution id: {short_id}). Check progress with `/status {short_id}`."

   Show the first 8 characters of the execution ID as the short ID for readability.

## Error Handling

- Connection errors: "Cannot reach scout-engine at {url}. Is the server running?"
- 401/403: "API key rejected. Run `/connect` to reconfigure."
- 404 on run: "Workflow not found on engine. It may have been deleted."

Use `httpx` for all HTTP calls.
