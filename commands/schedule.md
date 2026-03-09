---
description: Schedule an exported workflow to run automatically
argument-hint: "[list | workflow-name <when> | update <id> <changes> | delete <name-or-id>] [--local]"
allowed-tools:
  - "mcp__plugin_scout_scout__schedule_create"
  - "mcp__plugin_scout_scout__schedule_list"
  - "mcp__plugin_scout_scout__schedule_delete"
  - "Read"
  - "AskUserQuestion"
---

Manage scheduled tasks for Scout workflows. Automatically routes to the best scheduler:

- **Engine connected** (`.claude/scout.local.md` exists) → schedules on the remote scout-engine server (persistent, runs even when your machine is off)
- **No engine** → schedules locally via OS task manager (Windows Task Scheduler / macOS launchd / Linux cron)

Use `--local` to force local scheduling even when an engine is connected.

## Step 0: Determine the scheduling backend

1. Check if the argument contains `--local`. If so, strip it from the argument and use **local mode**.
2. Otherwise, check if `.claude/scout.local.md` exists in the current working directory.
   - If it exists, read `engine_url` and `engine_api_key` from the YAML frontmatter. Use **remote mode**.
   - If it does not exist, use **local mode**.

## Parse the argument

Determine the operation from the remaining argument (after stripping `--local`):

- **No argument or `list`**: Go to List
- **`delete <name-or-id>`**: Go to Delete
- **`update <id> <changes>`**: Go to Update (remote mode only)
- **`<workflow-name>` or `<workflow-name> <when>`**: Go to Create

---

## Create a schedule

### Remote mode

1. **Resolve the workflow.** List workflows from the engine:
   ```
   GET {engine_url}/api/workflows
   Authorization: Bearer {api_key}
   ```
   If the URL is an IP address, skip TLS verification.

   Match the argument by name (case-insensitive) or ID. If no match, list available workflows and suggest `/sync` if the list is empty.

2. **Parse the schedule.**
   `<when>` can be either:
   - **Natural language**: "every weekday at 9am", "daily at midnight", "every hour", "every Monday at 3pm"
     → Parse to a standard cron expression. Examples:
     - "every weekday at 9am" → `0 9 * * MON-FRI`
     - "daily at midnight" → `0 0 * * *`
     - "every hour" → `0 * * * *`
     - "every Monday at 3pm" → `0 15 * * MON`
   - **Cron syntax**: Starts with a digit or `*`, e.g., `"0 9 * * MON-FRI"` — use as-is.
   - **No `<when>` provided**: Ask the user using AskUserQuestion (same flow as local mode).

3. **Confirm** before creating: "Create schedule for '{workflow_name}' running `{cron_expression}` ({human_readable})?"

4. **Create the schedule:**
   ```
   POST {engine_url}/api/schedules
   Authorization: Bearer {api_key}
   Content-Type: application/json

   {"workflow_id": "{id}", "cron_expression": "{cron}", "timezone": "UTC"}
   ```

5. **Report:**
   ```
   Scheduled "enrollment" to run daily at 6:45 AM
   Platform: scout-engine (remote)
   Next run: 2026-03-07 06:45 UTC

   To view all schedules: /schedule list
   To remove this schedule: /schedule delete <id>
   ```

### Local mode

1. **Find the workflow.** Check that `workflows/<name>/<name>.py` exists using Read. If not: "No exported workflow found at `workflows/<name>/`. Run `/export <name>` first."

2. **Ask for schedule details** using AskUserQuestion:
   - "How often should this run?" — Daily / Weekly / Weekdays (Mon-Fri) / One-time
   - "What time should it run?" — Accept flexible formats (6:45am, 06:45, 6:45 AM), convert to HH:MM 24-hour.
   - If Weekly: "Which days?" — MON, TUE, WED, THU, FRI, SAT, SUN (multi-select)

3. **Create the scheduled task.** Map answers to MCP tool parameters:
   - Daily → `schedule="DAILY"`
   - Weekly → `schedule="WEEKLY"`, `days="MON,WED,FRI"`
   - Weekdays → `schedule="WEEKLY"`, `days="MON,TUE,WED,THU,FRI"`
   - One-time → `schedule="ONCE"`

   Call `schedule_create` with `name`, `workflow_dir` (absolute path), `schedule`, `time`, and `days`.

4. **Report:**
   ```
   Scheduled "enrollment" to run daily at 6:45 AM
   Platform: Windows (Task Scheduler)
   Script: workflows/enrollment/enrollment.py

   To view all schedules: /schedule list
   To remove this schedule: /schedule delete enrollment
   ```

---

## List schedules

### Remote mode

1. Fetch schedules:
   ```
   GET {engine_url}/api/schedules
   Authorization: Bearer {api_key}
   ```

2. Display as a table:
   - **ID** (first 8 chars)
   - **Workflow** name
   - **Cron** expression
   - **Next Run** (datetime or "disabled")
   - **Enabled** (yes/no)

   If no schedules: "No schedules found. Create one with `/schedule <workflow> <when>`."

### Local mode

Call the `schedule_list` MCP tool. Display as a table:

| Workflow | Schedule | Time | Days | Status | Next Run |
|----------|----------|------|------|--------|----------|
| enrollment | Daily | 6:45 AM | | Ready | 2/28/2026 |

If no tasks: "No scheduled tasks found. Export a workflow with `/export` first, then schedule it with `/schedule <name>`."

---

## Update a schedule (remote mode only)

If in local mode: "Schedule updates are only supported with a remote engine. Delete and recreate the schedule, or run `/connect` to set up an engine."

1. Parse changes from the argument. Supported:
   - `enabled=true` or `enabled=false`
   - A new cron expression or natural language schedule
   - `timezone=America/New_York`

2. Send the update:
   ```
   PUT {engine_url}/api/schedules/{id}
   Authorization: Bearer {api_key}
   Content-Type: application/json

   {<changed fields>}
   ```

3. **Report:** "Schedule {short_id} updated. {summary of changes}."

---

## Delete a schedule

### Remote mode

1. **Confirm:** "Delete schedule {short_id} for '{workflow_name}'? This cannot be undone."
2. If confirmed:
   ```
   DELETE {engine_url}/api/schedules/{id}
   Authorization: Bearer {api_key}
   ```
3. **Report:** "Schedule {short_id} deleted."

### Local mode

1. **Confirm:** "Delete the scheduled task for **<name>**? This removes it from the system scheduler."
2. Call the `schedule_delete` MCP tool with the task name.
3. Confirm deletion.

---

## Error Handling

**Remote mode:**
- Connection errors: "Cannot reach scout-engine at {url}. Is the server running?"
- 401/403: "API key rejected. Run `/connect` to reconfigure."
- 422 (invalid cron): Show the engine's validation error.
- Schedule not found: "Schedule '{id}' not found."

**Local mode:**
- Workflow not found: "No exported workflow found at `workflows/<name>/`. Run `/export <name>` first."
- MCP tool errors: Surface the error message from the tool.

Use `httpx` for remote HTTP calls.
