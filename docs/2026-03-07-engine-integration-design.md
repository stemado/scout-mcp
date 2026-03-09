# Engine Integration Design

**Date:** 2026-03-07
**Status:** Approved
**Goal:** Connect the Scout plugin to a remote scout-engine server for workflow deployment, execution, and scheduling

## Context

scout-engine is now deployed on a Hetzner VPS with API key auth, PostgreSQL, and TLS. The Scout plugin can author and export workflows locally but has no way to deploy them to the remote server, trigger executions, monitor results, or manage schedules. Two commands (`/attach` and `/resume`) already talk to scout-engine for Hot Takeover, but they use inline httpx calls with no shared infrastructure.

## Architecture

```
┌─ Scout Plugin (Claude Code) ─────────────────────┐
│                                                   │
│  EngineClient (src/scout/engine.py)               │
│  ├── Config: .claude/scout.local.md → env vars    │
│  ├── Auth: Bearer token on every request          │
│  └── Methods: sync, run, status, schedule, ...    │
│                                                   │
│  Commands (use EngineClient):                     │
│  ├── /connect — setup URL + API key               │
│  ├── /sync — upload workflow to engine             │
│  ├── /run — trigger remote execution              │
│  ├── /status — list/detail executions             │
│  ├── /schedule — CRUD + natural language cron     │
│  ├── /attach — (existing, refactored)             │
│  └── /resume — (existing, refactored)             │
│                                                   │
└──────────────────┬────────────────────────────────┘
                   │ HTTPS + Bearer token
┌──────────────────▼────────────────────────────────┐
│  scout-engine (Hetzner VPS)                       │
│  POST /api/workflows — upload                     │
│  POST /api/workflows/{id}/run — execute           │
│  GET  /api/executions — list                      │
│  GET  /api/executions/{id} — detail               │
│  POST /api/schedules — create                     │
│  GET  /api/schedules — list                       │
│  PUT  /api/schedules/{id} — update                │
│  DELETE /api/schedules/{id} — delete              │
└───────────────────────────────────────────────────┘
```

## Component 1: EngineClient (`src/scout/engine.py`)

A thin async wrapper around the scout-engine REST API.

```python
class EngineClient:
    # Config discovery order:
    # 1. .claude/scout.local.md YAML frontmatter
    # 2. SCOUT_ENGINE_URL / SCOUT_ENGINE_API_KEY env vars
    # 3. Default: http://localhost:8000, no key

    async def health() -> dict
    async def sync_workflow(workflow: dict) -> dict
    async def list_workflows() -> list[dict]
    async def run(workflow_id: str) -> dict
    async def list_executions() -> list[dict]
    async def get_execution(exec_id: str) -> dict
    async def create_schedule(workflow_id, cron, tz) -> dict
    async def list_schedules() -> list[dict]
    async def update_schedule(schedule_id, **kwargs) -> dict
    async def delete_schedule(schedule_id) -> dict
```

**Error handling:**
- `httpx.ConnectError` → "Cannot reach scout-engine at {url}. Is the server running?"
- 401/403 → "API key rejected. Run `/connect` to reconfigure."
- Self-signed TLS: disable cert verification when URL is an IP address

**Refactor:** `/attach` and `/resume` commands updated to use EngineClient instead of inline httpx.

## Component 2: Configuration (`/connect`)

**Command flow:**
1. Ask for engine URL (or accept as argument)
2. Ask for API key (or accept as argument)
3. Test connection with health check
4. Save to `.claude/scout.local.md`
5. Confirm: "Connected to scout-engine at https://X.X.X.X (v0.1.0)"

**Config file** (`.claude/scout.local.md`):
```yaml
---
engine_url: https://178.104.0.194
engine_api_key: <key>
---
```

**Auto-gate:** All remote commands check for saved config. If missing, tell the user to run `/connect` first.

**Overwrite semantics:** `/connect` always replaces existing config. No merge.

## Component 3: Commands

### `/sync [name]`

Two modes:
- **`/sync <name>`** — Reads `workflows/<name>/<name>.json`, uploads to engine
- **`/sync`** (active session) — Converts session history → workflow JSON, uploads directly. Asks for a name.

Output: "Synced workflow '<name>' to engine (id: abc-123). Run it with `/run <name>`."

### `/run <name>`

1. Fuzzy-match workflow name against `client.list_workflows()`
2. Call `client.run(workflow_id)`
3. Report: "Execution started (id: xyz-789). Check progress with `/status xyz-789`."

### `/status [execution_id]`

- **No arg:** Table of last 10 executions — short ID, workflow name, status, started, duration
- **With ID:** Step-by-step detail — step name, action, status, elapsed, error if failed

### `/schedule`

Subcommands with natural language support:

- **`/schedule <workflow> <when>`** — Create. `<when>` is natural language ("every weekday at 9am") or cron (`"0 9 * * MON-FRI"`). Claude parses to cron.
- **`/schedule list`** — All schedules: workflow name, cron, next run, enabled/disabled
- **`/schedule update <id> <changes>`** — Update cron or enabled state
- **`/schedule delete <id>`** — Delete with confirmation

## Error Handling Summary

| Scenario | Behavior |
|---|---|
| No config saved | "Run `/connect` to set up your engine connection." |
| Connection refused | "Cannot reach scout-engine at {url}. Is the server running?" |
| 401/403 | "API key rejected. Run `/connect` to reconfigure." |
| Workflow name not found | List available workflows, ask which one |
| Self-signed cert (IP URL) | Skip TLS verification automatically |
| Stale config | `/connect` overwrites, no merge |

## What Already Exists vs. What Needs Building

### Already exists:
- scout-engine API (all endpoints deployed and working)
- `/attach` and `/resume` commands (inline httpx, to be refactored)
- `SCOUT_ENGINE_URL` env var convention
- Workflow JSON schema shared between both repos
- `WorkflowConverter.from_history()` for session → JSON conversion

### Needs building:
1. `src/scout/engine.py` — EngineClient class
2. `commands/connect.md` — Connection setup command
3. `commands/sync.md` — Workflow upload command
4. `commands/run.md` — Remote execution trigger
5. `commands/status.md` — Execution monitoring
6. `commands/schedule.md` — Schedule management
7. Refactor `commands/attach.md` and `commands/resume.md` to use EngineClient
