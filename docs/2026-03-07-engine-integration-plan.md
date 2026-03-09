# Engine Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect the Scout plugin to a remote scout-engine server for workflow deployment, execution, monitoring, and scheduling.

**Architecture:** Add an `EngineClient` class (`src/scout/engine.py`) that wraps the scout-engine REST API with config discovery, auth, and error handling. Five new slash commands (`/connect`, `/sync`, `/run`, `/status`, `/schedule`) use the client. Existing `/attach` and `/resume` are refactored to use it too.

**Tech Stack:** httpx (already in deps), pydantic for config, YAML frontmatter in `.claude/scout.local.md` for saved credentials.

**Design doc:** `docs/plans/2026-03-07-engine-integration-design.md`

---

### Task 1: EngineClient — config discovery and health check

**Files:**
- Create: `src/scout/engine.py`
- Create: `tests/test_engine.py`
- Modify: `pyproject.toml` — add `pyyaml>=6.0` to dependencies (used by `_parse_frontmatter`)

**Step 1: Write failing tests for config discovery and health check**

```python
"""Tests for EngineClient."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, mock_open

from scout.engine import EngineClient


# --- Config discovery ---

def test_config_from_local_md(tmp_path):
    """Reads engine_url and engine_api_key from .claude/scout.local.md frontmatter."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://example.com\nengine_api_key: secret-key\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client.base_url == "https://example.com"
    assert client.api_key == "secret-key"


def test_config_from_env_vars(tmp_path, monkeypatch):
    """Falls back to env vars when no .local.md exists."""
    monkeypatch.setenv("SCOUT_ENGINE_URL", "https://env.example.com")
    monkeypatch.setenv("SCOUT_ENGINE_API_KEY", "env-key")
    client = EngineClient(config_dir=tmp_path)
    assert client.base_url == "https://env.example.com"
    assert client.api_key == "env-key"


def test_config_local_md_overrides_env(tmp_path, monkeypatch):
    """local.md takes precedence over env vars."""
    monkeypatch.setenv("SCOUT_ENGINE_URL", "https://env.example.com")
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://file.example.com\nengine_api_key: file-key\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client.base_url == "https://file.example.com"


def test_config_defaults(tmp_path):
    """Defaults to localhost:8000 with no key."""
    client = EngineClient(config_dir=tmp_path)
    assert client.base_url == "http://localhost:8000"
    assert client.api_key == ""


def test_is_configured_true(tmp_path):
    """is_configured returns True when API key is set."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://x.com\nengine_api_key: key\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client.is_configured is True


def test_is_configured_false(tmp_path):
    """is_configured returns False when no API key."""
    client = EngineClient(config_dir=tmp_path)
    assert client.is_configured is False


# --- TLS verification ---

def test_tls_verify_disabled_for_ip(tmp_path):
    """Skip TLS verification when URL is an IP address."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://178.104.0.194\nengine_api_key: k\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client._verify_tls is False


def test_tls_verify_enabled_for_domain(tmp_path):
    """Verify TLS normally when URL is a domain."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://scout.example.com\nengine_api_key: k\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client._verify_tls is True
```

**Step 2: Run tests to verify they fail**

Run: `cd D:/Projects/scout && uv run pytest tests/test_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scout.engine'`

**Step 3: Implement EngineClient with config discovery**

```python
"""HTTP client for the scout-engine remote API."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml


_CONFIG_FILENAME = ".claude/scout.local.md"


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def _is_ip_address(url: str) -> bool:
    """Check if the URL's host is an IP address (not a domain)."""
    try:
        host = urlparse(url).hostname or ""
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


class EngineClient:
    """Async wrapper around the scout-engine REST API."""

    def __init__(self, config_dir: Path | None = None):
        config = self._load_config(config_dir or Path.cwd())
        self.base_url: str = config.get("engine_url", "http://localhost:8000")
        self.api_key: str = config.get("engine_api_key", "")
        self._verify_tls: bool = not _is_ip_address(self.base_url)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _load_config(self, config_dir: Path) -> dict:
        """Load config from .claude/scout.local.md, falling back to env vars."""
        config: dict = {}

        # Priority 1: .claude/scout.local.md
        config_file = config_dir / _CONFIG_FILENAME
        if config_file.exists():
            config = _parse_frontmatter(config_file.read_text())

        # Priority 2: env vars (only fill gaps)
        if "engine_url" not in config:
            env_url = os.environ.get("SCOUT_ENGINE_URL")
            if env_url:
                config["engine_url"] = env_url
        if "engine_api_key" not in config:
            env_key = os.environ.get("SCOUT_ENGINE_API_KEY")
            if env_key:
                config["engine_api_key"] = env_key

        return config

    def _headers(self) -> dict:
        """Build request headers with auth if configured."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request to the engine."""
        url = f"{self.base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(verify=self._verify_tls) as http:
            resp = await http.request(method, url, headers=self._headers(), **kwargs)
        if resp.status_code == 401:
            raise EngineAuthError("API key rejected. Run `/connect` to reconfigure.")
        if resp.status_code == 403:
            raise EngineAuthError("API key rejected. Run `/connect` to reconfigure.")
        return resp

    async def health(self) -> dict:
        """Check engine health."""
        try:
            resp = await self._request("GET", "/api/health")
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise EngineConnectionError(
                f"Cannot reach scout-engine at {self.base_url}. Is the server running?"
            )

    @staticmethod
    def save_config(config_dir: Path, url: str, api_key: str) -> Path:
        """Save engine config to .claude/scout.local.md."""
        config_file = config_dir / _CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            f"---\nengine_url: {url}\nengine_api_key: {api_key}\n---\n"
        )
        return config_file


class EngineConnectionError(Exception):
    pass


class EngineAuthError(Exception):
    pass
```

**Step 4: Run tests to verify they pass**

Run: `cd D:/Projects/scout && uv run pytest tests/test_engine.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
cd D:/Projects/scout
git add src/scout/engine.py tests/test_engine.py
git commit -m "feat: add EngineClient with config discovery and health check"
```

---

### Task 2: EngineClient — API methods (workflows, executions, schedules)

**Files:**
- Modify: `src/scout/engine.py`
- Modify: `tests/test_engine.py`

**Step 1: Write failing tests for API methods**

Add these tests to `tests/test_engine.py`:

```python
# --- API methods (mocked HTTP) ---

@pytest.fixture
def client(tmp_path):
    """Client with config pointing to a fake server."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://test.example.com\nengine_api_key: test-key\n---\n")
    return EngineClient(config_dir=tmp_path)


async def test_sync_workflow(client):
    """sync_workflow POSTs workflow JSON to /api/workflows."""
    workflow = {"name": "test-wf", "steps": []}
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(200, json={"id": "abc-123", "name": "test-wf"})
        result = await client.sync_workflow(workflow)
    mock.assert_called_once_with("POST", "/api/workflows", json={"workflow": workflow})
    assert result["id"] == "abc-123"


async def test_list_workflows(client):
    """list_workflows GETs /api/workflows."""
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(200, json=[{"id": "1", "name": "wf1"}])
        result = await client.list_workflows()
    mock.assert_called_once_with("GET", "/api/workflows")
    assert len(result) == 1


async def test_run(client):
    """run POSTs to /api/workflows/{id}/run."""
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(202, json={"id": "exec-1", "status": "pending"})
        result = await client.run("wf-id-123")
    mock.assert_called_once_with("POST", "/api/workflows/wf-id-123/run")
    assert result["status"] == "pending"


async def test_list_executions(client):
    """list_executions GETs /api/executions."""
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(200, json=[{"id": "e1", "status": "completed"}])
        result = await client.list_executions()
    mock.assert_called_once_with("GET", "/api/executions")
    assert result[0]["status"] == "completed"


async def test_get_execution(client):
    """get_execution GETs /api/executions/{id}."""
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(200, json={"id": "e1", "steps": []})
        result = await client.get_execution("e1")
    mock.assert_called_once_with("GET", "/api/executions/e1")
    assert result["id"] == "e1"


async def test_create_schedule(client):
    """create_schedule POSTs to /api/schedules."""
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(200, json={"id": "s1"})
        result = await client.create_schedule("wf-id", "0 9 * * MON-FRI", "UTC")
    mock.assert_called_once_with("POST", "/api/schedules", json={
        "workflow_id": "wf-id", "cron_expression": "0 9 * * MON-FRI", "timezone": "UTC"
    })
    assert result["id"] == "s1"


async def test_list_schedules(client):
    """list_schedules GETs /api/schedules."""
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(200, json=[{"id": "s1"}])
        result = await client.list_schedules()
    mock.assert_called_once_with("GET", "/api/schedules")


async def test_update_schedule(client):
    """update_schedule PUTs to /api/schedules/{id}."""
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(200, json={"id": "s1", "enabled": False})
        result = await client.update_schedule("s1", enabled=False)
    mock.assert_called_once_with("PUT", "/api/schedules/s1", json={"enabled": False})


async def test_delete_schedule(client):
    """delete_schedule DELETEs /api/schedules/{id}."""
    with patch.object(client, "_request") as mock:
        mock.return_value = httpx.Response(200, json={"ok": True})
        result = await client.delete_schedule("s1")
    mock.assert_called_once_with("DELETE", "/api/schedules/s1")
```

**Step 2: Run tests to verify they fail**

Run: `cd D:/Projects/scout && uv run pytest tests/test_engine.py -v`
Expected: FAIL — `AttributeError: 'EngineClient' object has no attribute 'sync_workflow'`

**Step 3: Add API methods to EngineClient**

Add to `src/scout/engine.py`, inside the `EngineClient` class:

```python
    async def sync_workflow(self, workflow: dict) -> dict:
        """Upload a workflow JSON to the engine."""
        resp = await self._request("POST", "/api/workflows", json={"workflow": workflow})
        resp.raise_for_status()
        return resp.json()

    async def list_workflows(self) -> list[dict]:
        """List all workflows on the engine."""
        resp = await self._request("GET", "/api/workflows")
        resp.raise_for_status()
        return resp.json()

    async def run(self, workflow_id: str) -> dict:
        """Trigger a workflow execution."""
        resp = await self._request("POST", f"/api/workflows/{workflow_id}/run")
        resp.raise_for_status()
        return resp.json()

    async def list_executions(self) -> list[dict]:
        """List recent executions."""
        resp = await self._request("GET", "/api/executions")
        resp.raise_for_status()
        return resp.json()

    async def get_execution(self, execution_id: str) -> dict:
        """Get execution detail with step results."""
        resp = await self._request("GET", f"/api/executions/{execution_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_schedule(self, workflow_id: str, cron_expression: str, timezone: str = "UTC") -> dict:
        """Create a cron schedule for a workflow."""
        resp = await self._request("POST", "/api/schedules", json={
            "workflow_id": workflow_id,
            "cron_expression": cron_expression,
            "timezone": timezone,
        })
        resp.raise_for_status()
        return resp.json()

    async def list_schedules(self) -> list[dict]:
        """List all schedules."""
        resp = await self._request("GET", "/api/schedules")
        resp.raise_for_status()
        return resp.json()

    async def update_schedule(self, schedule_id: str, **kwargs) -> dict:
        """Update a schedule (cron, enabled, etc.)."""
        resp = await self._request("PUT", f"/api/schedules/{schedule_id}", json=kwargs)
        resp.raise_for_status()
        return resp.json()

    async def delete_schedule(self, schedule_id: str) -> dict:
        """Delete a schedule."""
        resp = await self._request("DELETE", f"/api/schedules/{schedule_id}")
        resp.raise_for_status()
        return resp.json()
```

**Step 4: Run tests to verify they pass**

Run: `cd D:/Projects/scout && uv run pytest tests/test_engine.py -v`
Expected: All 18 tests PASS

**Step 5: Commit**

```bash
cd D:/Projects/scout
git add src/scout/engine.py tests/test_engine.py
git commit -m "feat: add EngineClient API methods for workflows, executions, schedules"
```

---

### Task 3: `/connect` command

**Files:**
- Create: `commands/connect.md`

**Step 1: Write the command file**

```markdown
---
description: Connect to a remote scout-engine server
argument-hint: "[url]"
---

Set up the connection to a remote scout-engine server. This saves the URL and API key so that `/sync`, `/run`, `/status`, and `/schedule` can talk to the engine.

## Steps

1. **Get the engine URL.**
   If the user provided a URL as an argument, use it. Otherwise, ask: "What is the URL of your scout-engine server? (e.g., https://178.104.0.194)"

2. **Get the API key.**
   Ask: "What is the API key? (find it on the server with `cat /root/scout-credentials.txt`)"

3. **Test the connection.**
   Use `httpx` to call `GET {url}/api/health` with the header `Authorization: Bearer {api_key}`. If the URL is an IP address, skip TLS verification (`verify=False`).

   - If the health check succeeds: continue to step 4.
   - If connection refused: "Cannot reach scout-engine at {url}. Is the server running?"
   - If 401/403: "API key rejected. Double-check the key and try again."

4. **Save the configuration.**
   Write to `.claude/scout.local.md` in the current working directory:
   ```yaml
   ---
   engine_url: {url}
   engine_api_key: {api_key}
   ---
   ```
   Create the `.claude/` directory if it doesn't exist.

5. **Confirm.**
   Report: "Connected to scout-engine at {url} (v{version}). You can now use `/sync`, `/run`, `/status`, and `/schedule`."
   Include the version from the health check response.

Use `httpx` for the HTTP call. Do not use the `EngineClient` class — this command creates the config that `EngineClient` reads.
```

**Step 2: Verify the command is discoverable**

Run: `ls D:/Projects/scout/commands/connect.md`
Expected: File exists

**Step 3: Commit**

```bash
cd D:/Projects/scout
git add commands/connect.md
git commit -m "feat: add /connect command for engine setup"
```

---

### Task 4: `/sync` command

**Files:**
- Create: `commands/sync.md`

**Step 1: Write the command file**

```markdown
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
```

**Step 2: Commit**

```bash
cd D:/Projects/scout
git add commands/sync.md
git commit -m "feat: add /sync command for workflow upload"
```

---

### Task 5: `/run` command

**Files:**
- Create: `commands/run.md`

**Step 1: Write the command file**

```markdown
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
```

**Step 2: Commit**

```bash
cd D:/Projects/scout
git add commands/run.md
git commit -m "feat: add /run command for remote execution"
```

---

### Task 6: `/status` command

**Files:**
- Create: `commands/status.md`

**Step 1: Write the command file**

```markdown
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
```

**Step 2: Commit**

```bash
cd D:/Projects/scout
git add commands/status.md
git commit -m "feat: add /status command for execution monitoring"
```

---

### Task 7: `/schedule` command (smart routing: remote or local)

**Files:**
- Modify: `commands/schedule.md`

**Design:** One `/schedule` command with smart routing. If an engine connection exists (`.claude/scout.local.md`), schedule remotely on the engine. Otherwise, fall back to the existing local OS scheduler. The user doesn't choose — the system picks the right backend based on context. A `--local` flag overrides to force local scheduling when connected to an engine.

**Step 1: Replace the command file**

Replace the contents of `commands/schedule.md` with:

```markdown
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
```

**Step 2: Commit**

```bash
cd D:/Projects/scout
git add commands/schedule.md
git commit -m "feat: unify /schedule with smart routing (remote engine or local OS)"
```

---

### Task 8: Full integration test

**Step 1: Run all tests**

Run: `cd D:/Projects/scout && uv run pytest -v`
Expected: All tests pass (existing + new engine tests)

**Step 2: Manual smoke test against live server**

Test the full loop from a Claude Code session:
1. `/connect https://178.104.0.194` → enter API key → health check passes
2. Verify `.claude/scout.local.md` was created with correct values
3. `/sync` with an active session or existing workflow
4. `/run <workflow-name>` → execution starts
5. `/status` → shows the execution
6. `/status <id>` → shows step detail

**Step 3: Commit any fixes**

```bash
cd D:/Projects/scout
git add -A
git commit -m "fix: integration test fixes"
```
