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

In Cursor Settings > MCP Servers, add:

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
