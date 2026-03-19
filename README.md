# scout-mcp-server

MCP server for browser automation with anti-detection. Scout pages, find elements, interact with websites, and monitor network traffic — from any AI client that supports the [Model Context Protocol](https://modelcontextprotocol.io/).

Built on [botasaurus-driver](https://github.com/omkarcloud/botasaurus) for automatic fingerprint evasion and stealth browsing. Sites that block Playwright and Selenium see a normal browser session.

<video src="https://github.com/user-attachments/assets/00283a6a-73cb-4c9b-986d-b1d9afe040e7" autoplay loop muted playsinline width="100%"></video>

---

## How It Works

Scout reads the page structure, then acts — the same way you'd inspect a page in DevTools before clicking anything:

1. **Scout** — compact structural overview (~200 tokens, not a raw DOM dump)
2. **Find** — search for elements by text, type, or selector
3. **Act** — click, type, select, navigate
4. **Scout again** — see what changed

Most browser-automation tools for AI take full-page screenshots and have the model interpret pixels. A single Playwright MCP screenshot costs ~124,000 tokens and the model still has to guess at selectors from what it sees. Scout reads the DOM directly and returns a compact report (~200 tokens) with exact CSS selectors — 98% less than a screenshot.

## See It In Action

Real-world scenarios demonstrating Claude Code + Scout working together on live websites — checking docs, researching errors, filling forms, downloading files, and more.

**[Scenario Catalog →](docs/scenario-catalog.md)**

## Credential Safety

`fill_secret` reads credentials from `.env` server-side and types them directly into form fields. The AI client only sees `"chars_typed": 22` — never the actual value. Exported scripts use `${ENV_VAR}` references. Authorization and Cookie headers are scrubbed from network logs before they reach the conversation.

## 2FA Support

`get_2fa_code` polls Twilio's SMS API for OTP codes — the AI clicks "Send Code" in the browser, the tool watches for the SMS, extracts the code, and types it in. Requires a Twilio account with an SMS number set as the 2FA recipient.

## Anti-Detection

Scout uses [Botasaurus](https://github.com/omkarcloud/botasaurus) under the hood, which handles browser fingerprinting and detection evasion automatically. Sites that block Selenium and Playwright see a normal browser session.

## Chrome Extension Mode

By default, Scout launches its own browser. **Extension mode** connects to your existing Chrome instead — preserving your logged-in sessions, cookies, and browser state.

```python
launch_session(connection_mode="extension")
```

**Quick setup:**

1. Open `chrome://extensions`, enable Developer mode, click "Load unpacked", select the `extension/` directory from the Scout repo
2. Click the **Scout MCP Bridge** toolbar icon and toggle it **Active**
3. Call `launch_session(connection_mode="extension")` from your AI client

| Scenario | Recommended Mode |
|----------|-----------------|
| Sites where you're already logged in | `extension` |
| Anti-detection scraping or CI/CD | `launch` (default) |
| Sites requiring 2FA/SSO you've already passed | `extension` |
| Parallel sessions or headless automation | `launch` (default) |

Extension mode sets no automation flags — your browser fingerprint stays identical to normal browsing. All 17 Scout tools work the same in both modes.

Full setup guide and troubleshooting: [docs/chrome-extension.md](docs/chrome-extension.md)

---

## Comparison

|   | Scout | Playwright MCP | Chrome Extension MCP | Selenium / scripts |
| --- | --- | --- | --- | --- |
| **Works on sites you don't control** | Yes | Limited — your own app | Limited — your active session | Blocked by detection |
| **Page discovery** | Compact scout (~200 tokens) | Full screenshot (~124,000 tokens) | You provide selectors | You provide selectors |
| **Credential safety** | Never in conversation | Plaintext in context | Plaintext in context | In your script |
| **Anti-detection** | Built-in | None | None | None |
| **2FA** | Built-in | No | No | You build it |
| **Export to script** | One command | No | No | You write it |
| **Cross-platform scheduling** | One command | No | No | You configure it |

## Benchmarks

| Task | Scout tokens | Playwright MCP tokens | Reduction | Wall-clock | Success |
|------|-------------|----------------------|-----------|-----------|---------|
| Fact lookup (Wikipedia) | ~1,264 | ~124,000 | **98% fewer** | 11.0s | 3/3 |
| Form fill + verify (httpbin) | ~3,799 | ~124,000 | **97% fewer** | 25.2s | 3/3 |

<sup>Claude Sonnet 4.6, 3 runs each, wall-clock = browser time only (excludes model reasoning). Playwright MCP baseline is a single full-page screenshot. Full results: <a href="docs/benchmarks/benchmark-results-v0.2.md">v0.2</a></sup>

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
npx -y @stemado/scout-mcp
```

---

## Configure Your AI Client

You configure Scout once. After that, your AI client starts and stops the server automatically — you never run it manually.

### Claude Code

```bash
claude mcp add scout -- npx -y @stemado/scout-mcp
```

Restart Claude Code. Scout's 17 tools are now available in every session.

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "scout": {
      "command": "npx",
      "args": ["-y", "@stemado/scout-mcp"],
      "cwd": "C:\\Users\\YourUsername"
    }
  }
}
```

> **Important:** The `cwd` field sets the working directory for the Scout server. Without it, Claude Desktop may launch Scout from a system directory (e.g. `C:\Windows\System32` on Windows), causing downloads and file operations to fail with permission errors. Set it to your home directory or any folder where Scout should have write access.

### Cursor

In Cursor Settings > MCP Servers, add:

```json
{
  "mcpServers": {
    "scout": {
      "command": "npx",
      "args": ["-y", "@stemado/scout-mcp"]
    }
  }
}
```

### Windsurf / Continue / Other MCP Clients

Use the same JSON configuration above — it works with any MCP-compatible client.

---

## Environment Variables

Scout loads variables from a `.env` file using this search order:

1. Explicit `env_file` path passed to `fill_secret`
2. `SCOUT_ENV_FILE` environment variable
3. `.env` in the current working directory

| Variable | Description |
|----------|-------------|
| `SCOUT_ALLOW_LOCALHOST` | Set to `1`, `true`, or `yes` to allow navigating to localhost URLs (disabled by default) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID for 2FA code retrieval |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Twilio phone number receiving 2FA SMS codes |
| `SCOUT_EXTENSION_ID` | Override the default Chrome extension ID for Native Messaging auth (only needed for custom extension builds) |
| `SCOUT_CHROME_NM_PATH` | Override NM host manifest directory for non-Chrome browsers (Brave, Chromium, Edge) |

---

## Security

- **Credential isolation** — `fill_secret` reads from `.env` server-side; passwords never enter the conversation
- **Header redaction** — Authorization, Cookie, and API key headers scrubbed from network logs
- **Export scrubbing** — credentials parameterized as environment variable references
- **URL scheme allowlist** — only `http` and `https` schemes permitted; all others rejected
- **SSRF protection** — IP addresses normalized via `ipaddress` module to catch IPv6-mapped IPv4 bypasses; blocks cloud metadata endpoints (AWS, GCP, Alibaba), loopback, and link-local addresses
- **Safe XML parsing** — uses `defusedxml` to prevent XXE attacks when processing SpreadsheetML files
- **JS execution timeout** — 2-minute cap on `execute_javascript` with graceful error response
- **Scheduler name validation** — regex pattern prevents path traversal in task scheduler namespaces
- **Path traversal protection** — validates all file paths
- **Invisible character stripping** — removes zero-width Unicode that could hide prompt injection
- **Content boundary markers** — wraps web-sourced data to distinguish data from instructions

Localhost navigation is blocked by default. Set `SCOUT_ALLOW_LOCALHOST=1` to enable it for local development.

---

## Tools

| Tool | Description |
|------|-------------|
| `launch_session` | Open a browser (headed or headless, optional proxy) or connect to an existing Chrome via extension mode |
| `check_extension` | Check Chrome extension connection status |
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
