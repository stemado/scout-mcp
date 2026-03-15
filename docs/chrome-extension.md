# Scout Chrome Extension Mode

## Overview

Scout supports two connection modes:

- **`launch` (default)** — Scout launches its own Chromium instance via botasaurus-driver. Best for clean, repeatable automation with anti-detection features.
- **`extension`** — Scout connects to your existing Chrome browser via a WebSocket relay extension. Preserves your logged-in sessions, cookies, and browser state.

## Installation

### 1. Load the Extension

1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `extension/` directory from the Scout repository
5. The Scout MCP Bridge icon appears in your toolbar

### 2. Activate the Extension

1. Click the **Scout MCP Bridge** icon in the Chrome toolbar
2. Toggle the switch to **Active**
3. The status will show "Waiting for Scout..." until you launch a session

### 3. Launch in Extension Mode

```python
# From any MCP client (Claude Desktop, Cursor, etc.)
launch_session(connection_mode="extension")

# Or with an initial URL
launch_session(url="https://example.com", connection_mode="extension")
```

## When to Use Each Mode

| Scenario | Recommended Mode |
|----------|-----------------|
| Automating sites where you're already logged in | `extension` |
| Scraping with anti-detection | `launch` |
| Interacting with sites that require 2FA/SSO | `extension` |
| Headless automation in CI/CD | `launch` |
| Debugging with browser DevTools open | `extension` |
| Parallel sessions | `launch` |

## How It Works

```
Chrome Extension <── WebSocket ──> Scout Server (ws://localhost:9222/scout-extension)
     │
     └── chrome.debugger API ──> CDP commands on active tab
```

1. The extension connects to Scout's WebSocket relay server
2. Scout sends CDP commands over WebSocket
3. The extension relays them via `chrome.debugger.sendCommand()`
4. CDP events (network, page, etc.) are forwarded back to Scout
5. All existing Scout tools work identically in both modes

## Troubleshooting

### "Debugger is already attached"

Another DevTools session or extension is using `chrome.debugger` on the same tab. Close other debugging tools or switch to a different tab.

### Port conflict on 9222

Another process is using port 9222 (often a Chrome remote debugging instance). Either:
- Stop the conflicting process: `lsof -i :9222`
- Or close any Chrome instances launched with `--remote-debugging-port=9222`

### Extension shows "Waiting for Scout..."

The extension is active but can't reach the Scout server. Make sure:
1. Scout MCP server is running
2. You've called `launch_session(connection_mode="extension")`
3. No firewall is blocking localhost:9222

### Extension disconnects frequently

Service workers in Manifest V3 can be suspended by Chrome after ~30 seconds of inactivity. The extension auto-reconnects with exponential backoff. If issues persist, keep the popup open or interact with the extension periodically.

### Tab switching behavior

When you switch tabs in Chrome, the extension automatically:
1. Detaches the debugger from the previous tab
2. Attaches to the new active tab
3. Notifies Scout of the tab change

This means Scout always operates on your currently active tab.

## Security Notes

### What Scout CAN access through the extension

- DOM content of the active tab (same as DevTools)
- Network requests/responses for the active tab
- JavaScript execution in the page context
- Screenshots of the active tab
- Cookies and storage visible to the page

### What Scout CANNOT access

- Other tabs (only the active tab is debugged)
- Chrome's internal pages (chrome://, chrome-extension://)
- Browser-level settings or bookmarks
- File system (beyond download directory)
- Other extensions' data

### Infobar notice

When the debugger attaches, Chrome shows an infobar: *"Scout MCP Bridge started debugging this browser"*. This is a Chrome security feature — it is visible to you (the user) but is **not detectable by websites**. The infobar disappears when the debugger detaches.

### Automation detection

Extension mode does NOT set any automation flags (`navigator.webdriver`, automation headers, etc.). Your browser fingerprint remains identical to normal browsing. The `chrome.debugger` API uses the same CDP protocol as DevTools — websites cannot distinguish debugger usage from normal browsing.

## Architecture

### Extension Components

- **`background.js`** — Service worker: WebSocket client, chrome.debugger relay, tab management
- **`popup.html/js`** — Toggle UI with connection status
- **`manifest.json`** — Manifest V3, permissions: debugger, tabs, activeTab, storage, scripting

### Server Components

- **`extension_relay.py`** — WebSocket server (`ExtensionRelay`) and CDP adapter (`ExtensionDriver`)
- **`session.py`** — `BrowserSession` dispatches to either Driver or ExtensionDriver based on `connection_mode`

### CDP Command Flow

```
Scout tool (e.g., scout_page)
  → asyncio.to_thread(driver.run_cdp_command, cdp.runtime.evaluate(...))
  → ExtensionDriver.run_cdp_command()
    → PyCDP generator: next(cmd) → {method: "Runtime.evaluate", params: {...}}
    → ExtensionRelay.send_cdp_command_sync() → WebSocket → Extension
    → chrome.debugger.sendCommand() → Chrome CDP
    → Response → WebSocket → cmd.send(response) → parsed Python objects
```
