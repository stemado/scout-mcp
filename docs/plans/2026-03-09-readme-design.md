# Scout MCP Server — README Design Spec

**Date:** 2026-03-09
**Approach:** Engine-First Technical README (Approach A)

## Context

Scout is a standalone MCP server for browser automation with anti-detection. It is published to PyPI (`scout-mcp-server`) and npm (`scout-mcp-server`). It is NOT a Claude Code plugin — it is the engine that any MCP-compatible AI client connects to.

The OTO project (`D:\Projects\oto\README.md`) is a Claude Code plugin that wraps Scout. OTO's README contains strong technical content (How It Works, Credential Safety, 2FA, Anti-Detection, Comparison table, Benchmarks) that should be adapted for Scout's README, with all plugin-specific references removed.

## Audience

Developers configuring MCP servers for AI clients (Claude Desktop, Claude Code, Cursor, Windsurf, etc.). They are technical, understand what MCP is, and want to know what makes Scout different from other browser automation MCP servers.

## Structure

The README follows an engine-first structure: explain what Scout does and why it's different, then show how to install it.

```
1. Header + tagline
2. One-liner description
3. How It Works (scout→find→act→scout cycle + token efficiency claim)
4. Credential Safety (fill_secret flow, never in conversation)
5. 2FA Support (Twilio SMS polling)
6. Anti-Detection (Botasaurus, fingerprint evasion)
7. Comparison table (Scout vs Playwright MCP vs Chrome Extension MCP vs Selenium)
8. Benchmarks (token reduction data)
9. Install (Prerequisites, PyPI, npm, uvx)
10. Configure Your AI Client (Claude Desktop/Code, Cursor, Windsurf)
11. Environment Variables (.env file, SCOUT_ALLOW_LOCALHOST, Twilio vars)
12. Security (updated for hardening: allowlist, ipaddress normalization, defusedxml, etc.)
13. Tools (17-tool reference table)
14. Workflow Export (export + schedule flow)
15. Development (clone, test, run)
16. License (MIT)
```

## Content Sources

### Carry over from OTO README (adapt, remove plugin references)

| Section | OTO Source | Scout Adaptation |
|---------|-----------|-----------------|
| How It Works | Lines 29-38 | Same content. Remove "OTO" → "Scout". Keep the 200-token vs 124,000-token comparison. |
| Credential Safety | Lines 79-81 | Same content. Reference `fill_secret` tool. |
| 2FA Support | Lines 83-85 | Same content. Reference `get_2fa_code` tool. |
| Anti-Detection | Lines 87-89 | Same content. Reference Botasaurus. |
| Comparison table | Lines 93-101 | Replace "OTO" column header with "Scout". Drop "Export to script" and "Cross-platform scheduling" rows (these are now tools, not slash commands). Actually keep them — they're still Scout capabilities via tools. |
| Benchmarks | Lines 103-110 | Same data. Update tool name references if needed. |
| Security | Lines 112-121 | **Update significantly** — reflect the hardening just shipped: scheme allowlist (not blocklist), `ipaddress` normalization for SSRF, `defusedxml` for XML parsing, JS execution timeout, scheduler name validation. Update env var name `OTO_ALLOW_LOCALHOST` → `SCOUT_ALLOW_LOCALHOST`. |
| Tools table | Lines 148-165 | Add 3 scheduler tools (`schedule_create`, `schedule_list`, `schedule_delete`). These exist in Scout but were missing from OTO's table. |

### Carry over from current Scout README

| Section | Source | Notes |
|---------|--------|-------|
| Install | Lines 9-29 | Already correct for MCP server (PyPI, npm, uvx). |
| Client Configuration | Lines 33-68 | Claude Desktop, Cursor, Windsurf configs. Already correct. |
| Workflow Export | Lines 95-108 | Directory structure, schedule_create reference. |
| Development | Lines 121-137 | Clone, uv sync, pytest commands. |

### New content to write

| Section | Notes |
|---------|-------|
| Environment Variables | Document `.env` file search order (explicit path → `SCOUT_ENV_FILE` → CWD `.env`). List key variables: `SCOUT_ALLOW_LOCALHOST`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`. |
| Header/tagline | `scout-mcp-server` as H1. One-liner from pyproject.toml description. No logo (we don't have one for Scout specifically). |

### Drop (plugin-only, not applicable)

- GIF demos (no assets, and this is a technical README)
- Slash commands table (plugin feature)
- Landscape Analysis (plugin skill)
- Plugin install instructions (`/plugin marketplace add`)
- "Stop clicking." tagline (that's OTO's brand)
- Logo image reference

## Tone

Technical, concise, factual. No marketing language. Let the comparison table and benchmarks speak for themselves. Use the same direct style as the current Scout README.

## Length Target

~200-250 lines of markdown. The current Scout README is 144 lines. The OTO README is 181 lines. The combined content with new sections (env vars, updated security) should land around 220 lines.
