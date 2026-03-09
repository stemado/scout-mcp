# Getting Started with Scout

This guide walks you through installation, your first session, credential handling, and exporting replayable workflows. If you've never used the plugin before, start here.

## What Is It?

Scout gives Claude Code a browser it can drive interactively. You tell Claude to go to a website, and it launches a real Chrome window (via Botasaurus). Claude can then click around, fill forms, inspect page structure, capture network traffic, and ultimately generate a replayable automation script — all through conversation.

Think of it as giving Claude its own browser DevTools session.

## Prerequisites

You need three things installed before the plugin will work:

1. **Python 3.11+** — the MCP server is written in Python
2. **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — a fast Python package manager. The plugin uses `uv run` to auto-install dependencies on first launch (no manual `pip install` needed)
3. **Google Chrome** — Botasaurus drives Chrome via the DevTools Protocol

`uv` creates an isolated virtual environment and installs all dependencies (`botasaurus-driver`, `mcp`, `pydantic`, `python-dotenv`) automatically the first time the server starts. Zero manual dependency management.

> **Auto-checked:** Scout runs a SessionStart hook that verifies Python, Node.js, and Chrome are available every time you start a session. If anything is missing, you'll see a clear error message before the server starts.

## Installation

Two commands in Claude Code:

```
/plugin marketplace add stemado/scout-marketplace
```

This registers the marketplace (a pointer to the GitHub repo — not a centralized store). Then install the plugin:

```
/plugin install scout@scout-marketplace
```

That's it. Claude Code snapshots the plugin into its cache, registers the MCP server, and makes the skills and commands available. Restart Claude Code after installing.

To update to the latest version later:

```
/plugin update scout@scout-marketplace
```

Then restart Claude Code again to pick up the changes.

## Your First Session

### Quick Start with `/scout`

The fastest way to try it:

```
/scout https://example.com
```

This launches a visible Chrome window (headed mode), navigates to the URL, and returns a structural overview: page title, iframe hierarchy, shadow DOM boundaries, and counts of interactive elements. The browser stays open so you can keep interacting.

### Conversational Workflow

After scouting, just talk to Claude naturally:

- **"Click the Login button"** — Claude finds the button and clicks it
- **"Type admin@example.com in the email field"** — Claude locates the input and types into it
- **"What changed on the page?"** — Claude re-scouts and tells you what's different
- **"Monitor network traffic, then click Export"** — Claude captures the XHR/fetch calls triggered by the click
- **"Take a screenshot"** — Claude captures and shows you the current browser state

Claude builds up a complete understanding of the site step by step, exactly like you would in DevTools.

## Handling Credentials

If a form needs a password or API key, you don't paste it into chat. Instead:

1. Create a `.env` file in your project directory:

```
MY_PASSWORD=supersecret123
MY_USERNAME=admin@example.com
```

2. Tell Claude: **"Fill the password field using MY_PASSWORD from .env"**

Claude uses the `fill_secret` tool — the actual value is read server-side, typed into the field, and never appears in your conversation. The session history records `${MY_PASSWORD}` instead of the real value.

This is a deliberate security design. The `.env` file should be gitignored, and credentials are parameterized in both conversation history and exported scripts. You can safely share scripts and session logs without leaking secrets.

The `.env` search order is: explicit path > `SCOUT_ENV_FILE` env var > `.env` in the current working directory.

## Exporting a Replayable Script

Once you've walked through a complete workflow (login, navigate, click export, etc.), run:

```
/export-workflow acme-export
```

This generates a self-contained directory package in `workflows/acme-export/`:

```
workflows/acme-export/
├── acme-export.py           # Standalone replay script (loads creds from .env)
├── acme-export.json         # Portable workflow JSON
├── requirements.txt         # pip install -r requirements.txt
└── .env.example             # Credential template (only if credentials detected)
```

Quick start:
```
cd workflows/acme-export
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
python acme-export.py
```

## Replaying Workflows Without Claude

The JSON workflow can be replayed from the command line without Claude in the loop:

```
workflow-run workflows/acme-export/acme-export.json \
  --var USERNAME=admin --var PASSWORD=secret
```

Useful flags:

- `--dry-run` — validate and print the plan without executing
- `--headless` — run without a visible browser window
- `--timeout 60000` — set step timeout in milliseconds
- `--download-dir ./downloads` — where to save downloaded files
- `--screenshot-dir ./screenshots` — where to save failure screenshots

Variables are resolved in this order: `--var` CLI args > environment variables > workflow defaults. If a variable can't be resolved, the executor exits with code 2 before launching a browser.

## The 12 MCP Tools

These are the tools Claude uses behind the scenes. You don't call them directly — Claude picks the right one based on what you ask — but knowing what's available helps you understand what's possible.

| Tool | What it does |
|------|-------------|
| `launch_session` | Open a Chrome browser |
| `scout_page_tool` | Compact page overview (~200 tokens) |
| `find_elements` | Search for specific elements by text/type/selector |
| `execute_action_tool` | Click, type, select, scroll, navigate, hover |
| `fill_secret` | Inject credentials from `.env` without exposing them |
| `execute_javascript` | Run arbitrary JS in page context |
| `take_screenshot` | Capture the current browser state as an image |
| `inspect_element` | Deep-inspect a single element (visibility, overlays, shadow DOM) |
| `monitor_network` | Capture/query network traffic and downloads |
| `record_video` | Record browser screen to MP4 via CDP screencast |
| `get_session_history` | Get the full structured record of everything you did |
| `close_session` | Close the browser and clean up |

## Common Gotchas

- **One session at a time** — the server limits to 1 concurrent browser session. Close the current one before starting another.
- **Sessions don't persist between conversations** — each Claude Code conversation starts fresh. If you need to repeat a workflow, export it first.
- **CAPTCHAs** — Botasaurus reduces how often they appear, but can't solve them. If you hit one, you'll need to handle it manually in the browser window.
- **The browser window is real** — it opens a visible Chrome window on your screen (unless you pass `headless: true`). You can watch Claude drive it in real time.
- **Don't repeat logins** — the session is stateful. Once you're logged in, stay logged in. Repeated rapid login attempts trigger security detection and CAPTCHAs.
- **Found a bug?** -- Run `/report bug` and Claude will gather diagnostics, check for duplicates, and file a GitHub issue for you.

### "Blocked URL host: localhost"

If you try to automate a locally running application (`http://localhost:3000`, `http://127.0.0.1:8080`, etc.), you'll get this error:

```text
Error: Blocked URL host: localhost
```

Scout blocks loopback addresses by default as an SSRF (Server-Side Request Forgery) safety measure — since Scout takes URLs from the AI conversation, this prevents prompt injection attacks from redirecting the browser to internal services.

To allow localhost access, set the `SCOUT_ALLOW_LOCALHOST` environment variable in your MCP configuration. Add an `env` block to the Scout server entry in your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "scout": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/scout", "scout"],
      "env": {
        "SCOUT_ALLOW_LOCALHOST": "1"
      }
    }
  }
}
```

Then restart Claude Code. Cloud metadata endpoints (`169.254.169.254`, etc.) remain blocked regardless of this setting.
