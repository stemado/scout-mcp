# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Scout is an MCP (Model Context Protocol) server for browser automation with anti-detection. It exposes 17 tools over MCP stdio transport that AI clients (Claude Desktop, Cursor, Claude Code) invoke to scout pages, find elements, interact with websites, and monitor network traffic. Built on botasaurus-driver for stealth browsing.

## Commands

```bash
# Install dependencies
uv sync

# Run unit tests (no browser needed)
uv run pytest tests/ -m "not integration" -v

# Run all tests including integration (needs Chrome)
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_validation.py -v

# Run a single test by name
uv run pytest tests/test_sanitize.py::TestStripInvisible::test_strips_zero_width_space -v

# Run the MCP server locally
uv run scout-mcp-server
```

No linter or formatter is configured. `.ruff_cache/` and `.mypy_cache/` are gitignored but have no config files.

## Architecture

```
AI Client <── MCP stdio ──> server.py (FastMCP) ──> session.py (BrowserSession) ──> botasaurus-driver (Chrome CDP)
```

### Core Flow

The Scout/Find/Act cycle: scout the page structure (~200 tokens), find specific elements, execute actions (click/type/navigate), scout again to see what changed. This replaces screenshot-based approaches that cost ~124K tokens per capture.

### Key Modules (src/scout/)

- **server.py** — All 17 `@mcp.tool()` definitions, FastMCP server, AppContext lifespan. This is the largest file (~1200 lines) and the only MCP entry point.
- **session.py** — `BrowserSession` owns the Driver lifecycle, element cache, and secret registry.
- **scout.py** — Page reconnaissance: injects `js/scout_page.js` into the browser, parses the result into a `ScoutReport`.
- **actions.py** — Action execution (click, type, select, navigate, scroll, wait, press_key, hover, clear) + JS evaluation via CDP.
- **models.py** — 25+ Pydantic models for all data structures. Every tool input/output is typed.
- **sanitize.py** — 3-layer pipeline: zero-width char stripping, secret scrubbing, content boundary markers.
- **validation.py** — URL validation (SSRF protection with IPv6 normalization), directory path validation, regex validation.
- **network.py** — CDP network monitoring with deferred body fetch.
- **workflow.py** — Converts SessionHistory to portable Workflow JSON + standalone Python scripts.
- **scheduler/** — Cross-platform OS scheduling: Windows (schtasks), macOS (launchd), Linux (cron) via `BaseScheduler` ABC.
- **converters/** — Pluggable format converter registry (e.g., SpreadsheetML 2003 XML → CSV) using `@register()` decorator.

### Critical Patterns

**Sync-in-async wrapping** — botasaurus-driver is synchronous. All driver calls are wrapped in `asyncio.to_thread()` so they don't block the async MCP server. Never call driver methods directly from async code.

**Element cache invalidation** — Scout results are cached in BrowserSession. The cache is invalidated after any action or navigation. Code that changes page state must ensure cache invalidation happens.

**Secret isolation** — `fill_secret` reads credentials from `.env` server-side and types them via the driver. The MCP response only reports character count. All registered secret values are scrubbed from any text returned to the AI client. Exported workflows use `${ENV_VAR}` references.

**CDP-direct JS evaluation** — `actions.py` bypasses botasaurus's JS eval wrapper and uses CDP directly (`Runtime.evaluate`) for natural return value semantics.

**Pydantic everywhere** — All tool inputs, outputs, and intermediate data structures use Pydantic models. Add new data structures to `models.py`.

## Test Organization

- **pytest** with **pytest-asyncio** (`asyncio_mode = "auto"`)
- Unit tests mock the browser driver; no Chrome needed
- Integration tests in `test_integration.py` are marked `@pytest.mark.integration` and require Chrome
- Test fixtures (HTML pages) in `tests/fixtures/`, served by a local HTTP server fixture from `conftest.py`
- `conftest.py` sets `SCOUT_ALLOW_LOCALHOST=1` for all tests

## npm Wrapper

`npm/` contains a thin Node.js package (`@stemado/scout-mcp`) that spawns the Python server via `uvx` or `pipx`. It has zero Python logic — it's purely a distribution convenience for `npx -y scout-mcp-server`.

## Environment Variables

- `SCOUT_ALLOW_LOCALHOST` — Enable localhost navigation (blocked by default for SSRF protection)
- `SCOUT_ENV_FILE` — Explicit path to `.env` file for secrets
- `TWILIO_*` — Twilio credentials for 2FA OTP retrieval
