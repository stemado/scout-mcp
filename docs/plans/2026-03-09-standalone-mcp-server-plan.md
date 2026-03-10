# Scout → scout-mcp-server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Scout from a Claude Code plugin into a standalone MCP server published to PyPI and npm as `scout-mcp-server` v1.0.0.

**Architecture:** In-place refactor. Remove all Claude Code plugin components (commands, skills, hooks, plugin manifest, CLAUDE.md). Remove engine integration. Keep all 17 MCP tools and the scheduler. Add a thin npm launcher package. Update pyproject.toml for PyPI publishing.

**Tech Stack:** Python 3.11+ (FastMCP, botasaurus-driver, Pydantic), Node.js (npm launcher), Hatchling (build system)

**Design doc:** `docs/plans/2026-03-09-standalone-mcp-server-design.md`

---

### Task 1: Remove Claude Code Plugin Components

**Files:**
- Delete: `commands/benchmark.md`
- Delete: `commands/connect.md`
- Delete: `commands/demo.md`
- Delete: `commands/export-workflow.md`
- Delete: `commands/landscape.md`
- Delete: `commands/landscape-template.md`
- Delete: `commands/report.md`
- Delete: `commands/run.md`
- Delete: `commands/schedule.md`
- Delete: `commands/scout.md`
- Delete: `commands/status.md`
- Delete: `commands/sync.md`
- Delete: `skills/` (entire directory, 2 skills: `release/`, `scout/`)
- Delete: `hooks/check-deps.sh`
- Delete: `hooks/hooks.json`
- Delete: `.claude-plugin/plugin.json`
- Delete: `.claude-plugin/marketplace.json`
- Delete: `.mcp.json`
- Delete: `CLAUDE.md`

**Step 1: Remove all plugin directories and files**

```bash
cd D:/Projects/scout
rm -rf commands/ skills/ hooks/ .claude-plugin/ .mcp.json CLAUDE.md
```

**Step 2: Verify removal**

```bash
# These should all return "No such file or directory"
ls commands/ 2>&1
ls skills/ 2>&1
ls hooks/ 2>&1
ls .claude-plugin/ 2>&1
ls .mcp.json 2>&1
ls CLAUDE.md 2>&1
```

**Step 3: Commit**

```bash
git add -A && git commit -m "chore: remove Claude Code plugin components

Remove commands/, skills/, hooks/, .claude-plugin/, .mcp.json, and
CLAUDE.md. Scout is now a standalone MCP server, no longer a plugin."
```

---

### Task 2: Remove Engine Integration

**Files:**
- Delete: `src/scout/engine.py`
- Delete: `tests/test_engine.py`

**Step 1: Verify no other files import engine**

```bash
cd D:/Projects/scout
grep -r "from.*engine" src/scout/ --include="*.py" | grep -v "engine.py"
grep -r "import.*engine" src/scout/ --include="*.py" | grep -v "engine.py"
```

Expected: No matches (engine.py is only imported by the deleted slash commands, not by server.py or any other module).

**Step 2: Delete engine files**

```bash
rm src/scout/engine.py tests/test_engine.py
```

**Step 3: Run tests to confirm nothing breaks**

```bash
uv run pytest tests/ -m "not integration" -v
```

Expected: All tests pass. No imports of engine should exist.

**Step 4: Commit**

```bash
git add -A && git commit -m "chore: remove engine integration

Delete engine.py and its tests. The standalone MCP server focuses
on local browser automation. Engine integration can be a separate
package if needed later."
```

---

### Task 3: Update pyproject.toml for PyPI Publishing

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update pyproject.toml**

Replace the entire `[project]` section and scripts:

```toml
[project]
name = "scout-mcp-server"
version = "1.0.0"
description = "MCP server for browser automation with anti-detection. Scout pages, find elements, interact with websites, and monitor network traffic."
requires-python = ">=3.11"
authors = [{name = "sdoherty"}]
license = {text = "MIT"}
readme = "README.md"
keywords = ["mcp", "browser", "automation", "anti-detection", "stealth", "botasaurus", "model-context-protocol"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Internet :: WWW/HTTP :: Browsers",
    "Topic :: Software Development :: Testing",
]
dependencies = [
    "mcp[cli]>=1.0.0",
    "botasaurus-driver>=4.0.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",  # retained — used by otp.py for Twilio SMS polling
    "pyyaml>=6.0",
]

[project.scripts]
scout-mcp-server = "scout.server:main"

[project.urls]
Homepage = "https://github.com/stemado/scout-mcp"
Repository = "https://github.com/stemado/scout-mcp"
Issues = "https://github.com/stemado/scout-mcp/issues"
```

**Step 2: Update `src/scout/__init__.py`**

```python
"""Scout MCP Server — Browser automation with anti-detection."""

__version__ = "1.0.0"
```

**Step 3: Update server.py docstring and FastMCP name**

In `src/scout/server.py`, line 1:
```python
"""Scout MCP Server — Browser automation with anti-detection."""
```

Line 92 — update the FastMCP constructor:
```python
mcp = FastMCP("scout-mcp-server", lifespan=app_lifespan)
```

**Step 4: Regenerate lockfile**

```bash
uv lock
```

**Step 5: Verify the entry point works**

```bash
uv run scout-mcp-server --help 2>&1 || echo "Entry point registered"
# The server runs on stdio, so it will hang waiting for input.
# Just verify it starts without import errors:
timeout 3 uv run python -c "from scout.server import main; print('OK')" || true
```

**Step 6: Run tests**

```bash
uv run pytest tests/ -m "not integration" -v
```

Expected: All tests pass.

**Step 7: Commit**

```bash
git add -A && git commit -m "feat: rename package to scout-mcp-server v1.0.0

Update pyproject.toml with new package name, version, description,
classifiers, and entry point. This is now a standalone MCP server
publishable to PyPI."
```

---

### Task 4: Create npm Launcher Package

**Files:**
- Create: `npm/package.json`
- Create: `npm/index.js`
- Create: `npm/README.md`

**Step 1: Create npm directory**

```bash
mkdir -p npm
```

**Step 2: Write `npm/package.json`**

```json
{
  "name": "scout-mcp-server",
  "version": "1.0.0",
  "description": "MCP server for browser automation with anti-detection. Scout pages, find elements, interact with websites, and monitor network traffic.",
  "license": "MIT",
  "author": "sdoherty",
  "repository": {
    "type": "git",
    "url": "https://github.com/stemado/scout-mcp"
  },
  "keywords": [
    "mcp",
    "browser",
    "automation",
    "anti-detection",
    "model-context-protocol",
    "botasaurus"
  ],
  "bin": {
    "scout-mcp-server": "./index.js"
  },
  "files": [
    "index.js",
    "README.md"
  ],
  "engines": {
    "node": ">=18"
  }
}
```

**Step 3: Write `npm/index.js`**

```javascript
#!/usr/bin/env node

/**
 * scout-mcp-server npm launcher
 *
 * Thin wrapper that launches the Python MCP server.
 * Tries uvx first (zero-install), then pipx fallback.
 * All stdio is passed through for MCP transport.
 *
 * Windows compatibility: uses shell:true so Node can execute .cmd/.ps1
 * shims (uvx.cmd, pipx.cmd) that package managers install on Windows.
 *
 * Signal forwarding: SIGTERM/SIGINT are forwarded to the child process
 * so the Python server (and Chrome) shut down cleanly when the MCP
 * client disconnects.
 */

const { spawn, execSync } = require("child_process");

const IS_WIN = process.platform === "win32";

function commandExists(cmd) {
  try {
    execSync(`${cmd} --version`, { stdio: "ignore", shell: true });
    return true;
  } catch {
    return false;
  }
}

function launch(command, args) {
  const child = spawn(command, args, {
    stdio: "inherit",
    shell: IS_WIN,
    windowsHide: true,
  });

  // Forward termination signals so the Python server shuts down cleanly.
  // Without this, killing the npm process orphans the Python process
  // (and any Chrome instances it launched).
  function forwardSignal(signal) {
    process.on(signal, () => {
      child.kill(signal);
    });
  }
  forwardSignal("SIGTERM");
  forwardSignal("SIGINT");

  child.on("error", (err) => {
    if (err.code === "ENOENT") {
      process.stderr.write(
        `Error: '${command}' not found. Install uv (https://docs.astral.sh/uv/) and Python 3.11+.\n`
      );
      process.exit(1);
    }
    process.stderr.write(`Error: ${err.message}\n`);
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code ?? 1);
  });
}

// Strategy 1: uvx (zero-install Python runner — preferred)
if (commandExists("uvx")) {
  launch("uvx", ["scout-mcp-server"]);
}
// Strategy 2: pipx
else if (commandExists("pipx")) {
  launch("pipx", ["run", "scout-mcp-server"]);
}
// No supported launcher found
else {
  process.stderr.write(
    "Error: Neither uvx nor pipx found.\n" +
    "Install uv (recommended): https://docs.astral.sh/uv/\n" +
    "Or install pipx: https://pipx.pypa.io/\n"
  );
  process.exit(1);
}
```

**Step 3b: Write `npm/README.md`**

This is what renders on the npm registry page. Keep it focused on npm users.

```markdown
# scout-mcp-server

MCP server for browser automation with anti-detection. Scout pages, find elements, interact with websites, and monitor network traffic — from any AI client that supports the [Model Context Protocol](https://modelcontextprotocol.io/).

Built on [botasaurus-driver](https://github.com/omkarcloud/botasaurus) for automatic fingerprint evasion and stealth browsing.

## Quick Start

```bash
npx -y scout-mcp-server
```

## Configure Your AI Client

Add to your MCP server configuration:

```json
{
  "mcpServers": {
    "scout": {
      "command": "npx",
      "args": ["-y", "scout-mcp-server"]
    }
  }
}
```

Works with Claude Desktop, Cursor, Windsurf, Continue, and any MCP-compatible client.

**Prerequisites:** Python 3.11+, Google Chrome, and either [uv](https://docs.astral.sh/uv/) (recommended) or [pipx](https://pipx.pypa.io/).

For full documentation, see the [GitHub repository](https://github.com/stemado/scout-mcp).
```

> **Why no direct `python -m scout.server` fallback?** That strategy only works if
> the user already ran `pip install scout-mcp-server` — but if they did that, they
> can run `scout-mcp-server` directly without the npm launcher. Including it as a
> fallback produces a confusing `ModuleNotFoundError` when the package isn't
> installed, misleading users into thinking Python itself is broken.

**Step 4: Test the launcher locally**

```bash
cd npm && node index.js &
# Should start the MCP server on stdio (or show the uvx launch)
# Kill it after confirming it starts:
kill %1 2>/dev/null || true
cd ..
```

**Step 5: Commit**

```bash
git add npm/ && git commit -m "feat: add npm launcher package

Thin Node.js wrapper that finds and launches the Python MCP server.
Tries uvx (preferred), then pipx fallback. Forwards termination
signals so Chrome shuts down cleanly when the MCP client disconnects.
Enables 'npx -y scout-mcp-server' for any AI client."
```

---

### Task 5: Write New README

**Files:**
- Modify: `README.md`

**Step 1: Replace README.md entirely**

```markdown
# scout-mcp-server

MCP server for browser automation with anti-detection. Scout pages, find elements, interact with websites, and monitor network traffic — from any AI client that supports the [Model Context Protocol](https://modelcontextprotocol.io/).

Built on [botasaurus-driver](https://github.com/omkarcloud/botasaurus) for automatic fingerprint evasion and stealth browsing. Sites that block Playwright and Selenium see a normal browser session.

---

## Install

**Prerequisites:** Python 3.11+, Google Chrome

### Via PyPI (recommended)

```bash
pip install scout-mcp-server
```

Or run without installing:

```bash
uvx scout-mcp-server
```

### Via npm

```bash
npx -y scout-mcp-server
```

---

## Configure Your AI Client

Add Scout to your client's MCP server configuration:

### Claude Desktop / Claude Code

```json
{
  "mcpServers": {
    "scout": {
      "command": "uvx",
      "args": ["scout-mcp-server"]
    }
  }
}
```

### Cursor

In Cursor Settings → MCP Servers, add:

```json
{
  "mcpServers": {
    "scout": {
      "command": "npx",
      "args": ["-y", "scout-mcp-server"]
    }
  }
}
```

### Windsurf / Continue / Other MCP Clients

Use either the `uvx` or `npx` configuration above — both work with any MCP-compatible client.

---

## Tools

| Tool | Description |
|------|-------------|
| `launch_session` | Open a browser (headed or headless, optional proxy) |
| `scout_page_tool` | Structural page overview: iframes, shadow DOM, element counts |
| `find_elements` | Search for elements by text, type, or CSS selector |
| `execute_action_tool` | Click, type, select, navigate, scroll, hover, wait |
| `fill_secret` | Type credentials from `.env` without exposing them in conversation |
| `get_2fa_code` | Retrieve a 2FA OTP code from Twilio SMS |
| `execute_javascript` | Run arbitrary JS in the page context |
| `take_screenshot_tool` | Capture the page as PNG or JPEG |
| `inspect_element_tool` | Deep-inspect visibility, overlays, shadow DOM, ARIA |
| `process_download` | Convert and move downloaded files |
| `get_session_history` | Export the full session as a structured workflow log |
| `monitor_network` | Watch HTTP traffic to discover API endpoints under the UI |
| `record_video` | Record the browser session as MP4 |
| `close_session` | Close the browser and release resources |
| `schedule_create` | Create an OS-level scheduled task |
| `schedule_list` | List scheduled tasks |
| `schedule_delete` | Remove a scheduled task |

---

## Workflow Export

Walk through a workflow conversationally, then export it as a standalone Python script:

```
workflows/<name>/
├── <name>.py              # Standalone replay script
├── <name>.json            # Portable workflow definition
├── requirements.txt
└── .env.example           # Credential template
```

Schedule exported workflows with the `schedule_create` tool — works on Windows (Task Scheduler), macOS (launchd), and Linux (cron).

---

## Security

- **Credential isolation** — `fill_secret` reads from `.env` server-side; passwords never enter the conversation
- **Header redaction** — Authorization, Cookie, and API key headers scrubbed from network logs
- **URL validation** — Blocks `file://`, `javascript://`, cloud metadata endpoints, and localhost
- **Path traversal protection** — All file paths validated
- **Invisible character stripping** — Removes zero-width Unicode to prevent prompt injection

---

## Development

```bash
# Clone and install
git clone https://github.com/stemado/scout-mcp.git
cd scout
uv sync

# Run tests (no browser needed)
uv run pytest tests/ -m "not integration" -v

# Run integration tests (needs Chrome)
uv run pytest tests/ -v

# Run the MCP server locally
uv run scout-mcp-server
```

---

## License

MIT
```

**Step 2: Commit**

```bash
git add README.md && git commit -m "docs: rewrite README for standalone MCP server

New README focused on MCP server consumers: installation via pip/uvx/npx,
configuration for Claude Desktop, Cursor, Windsurf, and other MCP clients.
Removes all Claude Code plugin references."
```

---

### Task 6: Clean Up Tests and Verify

**Files:**
- Delete: `tests/test_engine.py` (already deleted in Task 2, verify)
- Verify: all remaining tests pass

**Step 1: Verify test_engine.py is gone**

```bash
ls tests/test_engine.py 2>&1
```

Expected: "No such file or directory"

**Step 2: Run full non-integration test suite**

```bash
uv run pytest tests/ -m "not integration" -v
```

Expected: All tests pass. No import errors for engine.

**Step 3: Check for any remaining references to "Claude Code" or plugin in source and docs**

```bash
# Source code
grep -r "Claude Code" src/scout/ --include="*.py"
grep -r "CLAUDE_PLUGIN_ROOT" src/scout/ --include="*.py"
grep -r "plugin" src/scout/ --include="*.py"

# Documentation, scripts, demos, benchmarks
grep -r "Claude Code" docs/ scripts/ demos/ benchmarks/ --include="*.md" --include="*.py" --include="*.json"
grep -r "CLAUDE_PLUGIN_ROOT" docs/ scripts/ demos/ benchmarks/
grep -r "plugin" docs/ --include="*.md" | grep -v "browser plugin" | grep -v "plans/"
```

Expected: No matches in source (or only incidental uses of "plugin" in unrelated context like comments about browser plugins). Documentation hits outside `docs/plans/` should be updated or removed.

**Step 4: Fix any stale references found in Step 3**

Update docstrings, comments, and documentation that reference "Claude Code" to say "MCP server" instead. Remove or archive engine integration docs (`docs/2026-03-07-engine-integration-*.md`) if they are no longer relevant.

**Step 5: Run tests again after fixes**

```bash
uv run pytest tests/ -m "not integration" -v
```

**Step 6: Commit if any fixes were needed**

```bash
git add -A && git commit -m "chore: clean up stale Claude Code references in source"
```

---

### Task 7: Build and Verify Distribution

**Files:**
- Verify: `pyproject.toml` builds correctly
- Verify: `npm/package.json` is publishable

**Step 1: Build Python distribution**

```bash
cd D:/Projects/scout
uv build
```

Expected: Creates `dist/scout_mcp_server-1.0.0.tar.gz` and `dist/scout_mcp_server-1.0.0-py3-none-any.whl`

**Step 2: Verify the wheel contents**

```bash
python -m zipfile -l dist/scout_mcp_server-1.0.0-py3-none-any.whl | head -30
```

Expected: Contains `scout/server.py`, `scout/session.py`, `scout/actions.py`, etc. No `commands/`, `skills/`, `hooks/`, `engine.py`.

**Step 3: Verify npm package contents**

```bash
cd npm && npm pack --dry-run
```

Expected: Shows `package.json` and `index.js` only.

**Step 4: Commit build artifacts cleanup**

```bash
cd D:/Projects/scout
rm -rf dist/
# No commit needed — dist/ should be in .gitignore
```

**Step 5: Final commit — tag the release**

```bash
git tag -a v1.0.0 -m "v1.0.0: Standalone MCP server release

Scout is now a standalone MCP server publishable to PyPI and npm.
Any AI client supporting MCP can use Scout for browser automation."
```

---

### Task 8: Publish to PyPI and npm

**Files:** None (publishing commands only)

**Step 1: Publish to PyPI**

```bash
cd D:/Projects/scout
uv build
uv publish
# Or: twine upload dist/*
```

**Step 2: Publish to npm**

```bash
cd npm
npm publish
```

**Step 3: Verify installation from registries**

```bash
# Test PyPI
pip install scout-mcp-server --dry-run

# Test npm
npx -y scout-mcp-server --help 2>&1 || echo "Launched OK"
```

---

## Summary

| Task | What | Files touched |
|------|------|--------------|
| 1 | Remove plugin components | Delete 20+ files across commands/, skills/, hooks/, .claude-plugin/ |
| 2 | Remove engine integration | Delete engine.py + test_engine.py |
| 3 | Update pyproject.toml | pyproject.toml, __init__.py, server.py |
| 4 | Create npm launcher | npm/package.json, npm/index.js |
| 5 | Rewrite README | README.md |
| 6 | Clean up tests & references | tests/, src/scout/*.py |
| 7 | Build & verify distribution | pyproject.toml, npm/package.json |
| 8 | Publish to PyPI and npm | Publishing commands only |
