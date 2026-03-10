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
