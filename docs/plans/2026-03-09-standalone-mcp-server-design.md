# Scout → scout-mcp-server: Standalone MCP Server Migration

**Date:** 2026-03-09
**Status:** Approved
**Version:** 1.0.0

## Summary

Transform Scout from a Claude Code plugin into a standalone MCP server publishable to both PyPI and npm. Any AI client (Claude Desktop, Cursor, Windsurf, Continue, etc.) can use Scout's browser automation via standard MCP protocol. The Claude Code plugin shell (commands, skills, hooks, plugin manifest) is removed entirely.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Distribution | Both npm + PyPI | Maximum reach across AI ecosystems |
| Package name | `scout-mcp-server` | Follows MCP naming convention, discoverable |
| npm scope | Unscoped | Simpler, most common pattern |
| Plugin components | Remove entirely | Clean break — this is a new product identity |
| Engine integration | Remove | Focus on local browser automation |
| Schedulers | Keep | Cross-platform scheduling is a differentiator |
| Version | 1.0.0 | Fresh major version for new product identity |
| Migration approach | In-place refactor | Preserves git history, fastest to ship |
| Tool count | 17 (all kept) | No redundancy, within MCP norms |

## Architecture

### What Gets Removed

| Path | Reason |
|------|--------|
| `commands/` (12 files) | Claude Code slash commands |
| `skills/` (2 skills) | Claude Code skills |
| `hooks/` | Claude Code hooks |
| `.claude-plugin/plugin.json` | Plugin manifest |
| `.claude-plugin/marketplace.json` | Plugin registry metadata |
| `.claude-plugin/` directory | Entire plugin metadata directory |
| `.mcp.json` | Claude Code MCP config (`${CLAUDE_PLUGIN_ROOT}`) |
| `CLAUDE.md` | Claude Code project instructions |
| `src/scout/engine.py` | Remote engine client |

### What Stays

Everything in `src/scout/` except `engine.py`:

- `server.py` — FastMCP server with 17 tools
- `session.py` — BrowserSession lifecycle
- `scout.py` — Page reconnaissance
- `actions.py` — Browser interactions
- `models.py` — Pydantic data models
- `network.py` — Network monitoring (CDP)
- `download_manager.py` — Download tracking
- `history.py` — Session history tracker
- `screencast.py` — Video recording
- `workflow.py` — Workflow export + converter
- `secrets.py` — .env credential loading
- `sanitize.py` — Response scrubbing
- `validation.py` — URL/path validation
- `otp.py` — 2FA code polling
- `js/scout_page.js` — Client-side page reconnaissance
- `js/inspect_element.js` — Client-side element inspection
- `scheduler/` — Cross-platform scheduling (Windows/macOS/Linux)
- All tests, demos, docs

### Final Directory Structure

```
scout/
├── src/scout/                      # Python MCP server package
│   ├── __init__.py
│   ├── server.py                   # FastMCP server, 17 tools
│   ├── session.py
│   ├── scout.py
│   ├── actions.py
│   ├── models.py
│   ├── network.py
│   ├── download_manager.py
│   ├── history.py
│   ├── screencast.py
│   ├── workflow.py
│   ├── secrets.py
│   ├── sanitize.py
│   ├── validation.py
│   ├── otp.py
│   ├── js/
│   │   ├── scout_page.js
│   │   └── inspect_element.js
│   └── scheduler/
│       ├── base.py
│       ├── windows.py
│       ├── macos.py
│       └── linux.py
├── npm/                            # Thin npm launcher
│   ├── package.json
│   ├── index.js
│   └── README.md
├── tests/
├── demos/
├── docs/
├── pyproject.toml                  # name: scout-mcp-server, v1.0.0
├── uv.lock
├── LICENSE
└── README.md
```

## PyPI Package

**`pyproject.toml` changes:**

```toml
[project]
name = "scout-mcp-server"
version = "1.0.0"
description = "MCP server for browser automation with anti-detection. Scout pages, find elements, interact with websites, and monitor network traffic."
license = "MIT"
requires-python = ">=3.11"
keywords = ["mcp", "browser", "automation", "anti-detection", "botasaurus", "model-context-protocol"]

[project.scripts]
scout-mcp-server = "scout.server:main"

[project.urls]
Homepage = "https://github.com/mtsteinle/scout"
Repository = "https://github.com/mtsteinle/scout"
```

**Installation:**
```bash
pip install scout-mcp-server
# or zero-install:
uvx scout-mcp-server
```

## npm Launcher Package

A thin Node.js package that installs and launches the Python MCP server.

**`npm/package.json`:**
```json
{
  "name": "scout-mcp-server",
  "version": "1.0.0",
  "description": "MCP server for browser automation with anti-detection",
  "bin": {
    "scout-mcp-server": "./index.js"
  },
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/mtsteinle/scout"
  },
  "keywords": ["mcp", "browser", "automation", "model-context-protocol"]
}
```

**`npm/index.js` launcher:**
1. Try `uvx scout-mcp-server` (zero-install Python runner)
2. Fallback: `pipx run scout-mcp-server`
3. Fallback: `python -m scout.server`
4. Pass through all stdio for MCP transport
5. Forward exit codes

## MCP Client Configuration

Any AI client configures Scout the same way:

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

Or via Python directly:

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

## MCP Tools (17 total)

| Category | Tool | Purpose |
|----------|------|---------|
| Session | `launch_session` | Open browser with optional proxy, user-agent, window size |
| Session | `close_session` | Close browser and release resources |
| Session | `get_session_history` | Export structured session log |
| Scouting | `scout_page_tool` | Compact page overview (metadata, iframes, shadow DOM) |
| Scouting | `find_elements` | Search elements by text, type, selector |
| Scouting | `inspect_element_tool` | Deep-inspect single element |
| Actions | `execute_action_tool` | Click, type, select, navigate, scroll, etc. |
| Actions | `execute_javascript` | Run arbitrary JS in page context |
| Actions | `fill_secret` | Type credentials from .env without exposure |
| Capture | `take_screenshot_tool` | Capture page as PNG/JPEG |
| Capture | `record_video` | Record browser to MP4 via CDP screencast |
| Capture | `monitor_network` | Capture HTTP traffic |
| Capture | `process_download` | Convert downloaded files |
| Auth | `get_2fa_code` | Poll Twilio SMS for OTP codes |
| Scheduling | `schedule_create` | Create OS-level scheduled task |
| Scheduling | `schedule_list` | List scheduled tasks |
| Scheduling | `schedule_delete` | Remove scheduled task |

## Server.py Changes

Minimal — engine integration was commands-only (not MCP tools):

1. Update FastMCP server name/description
2. Remove any `${CLAUDE_PLUGIN_ROOT}` references (if any)
3. Remove `engine.py` import (if any — currently none)
4. Verify all 17 tools work standalone

## Dependencies

**Keep:**
- `mcp[cli]>=1.0.0` — MCP framework
- `botasaurus-driver>=4.0.0` — Browser automation
- `pydantic>=2.0.0` — Data models
- `python-dotenv>=1.0.0` — .env loading
- `pyyaml>=6.0` — YAML parsing

**Evaluate for removal:**
- `httpx>=0.27.0` — Was used by `engine.py`. Check if any other module uses it. If not, remove.

## README

New README focused on:
1. What Scout does (one paragraph)
2. Installation (pip, uvx, npx)
3. Configuration for popular AI clients (Claude Desktop, Cursor, Windsurf, Continue)
4. Tool reference (17 tools with brief descriptions)
5. Examples
6. Development setup
