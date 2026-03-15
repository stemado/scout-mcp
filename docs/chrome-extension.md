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

### 2. Start the Scout MCP Server

Start (or restart) the Scout MCP server — it auto-registers the Native Messaging host manifest for Chrome. The extension has a pinned `key` in `manifest.json`, so every installation gets the same deterministic extension ID. No manual ID copying or environment variables needed.

### 3. Activate the Extension

1. Click the **Scout MCP Bridge** icon in the Chrome toolbar
2. Toggle the switch to **Active**
3. The status will show "Waiting for Scout..." until you launch a session

### 4. Launch in Extension Mode

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

### "Setup required" error

The extension popup shows "Setup required" when the NM host manifest has not been registered. Fix:

1. Start (or restart) the Scout MCP server so it writes the NM host manifest
2. Reload the extension from `chrome://extensions`

### Native Messaging host not found

Chrome logs `Native host has exited` or the extension cannot open the NM channel. Common causes:

- The NM host manifest (`com.scout.mcp.json`) is missing from Chrome's `NativeMessagingHosts/` directory. Restarting Scout should recreate it.
- You are using a Chromium-based browser (Brave, Edge) that reads NM manifests from a different path. Set `SCOUT_CHROME_NM_PATH` to the correct directory (see [Environment Variables](#environment-variables) below).
- On macOS/Linux, the manifest file or the Scout executable it points to has incorrect permissions.

### Token mismatch

The extension connects but is immediately disconnected with an authentication error. This happens when the token the extension received via NM does not match the token the server expects. Causes:

- Scout was restarted (which generates a new token) but the extension has a stale token. Toggle the extension off and on again, or reload it from `chrome://extensions`.
- Multiple Scout instances are running and wrote different token files. Stop all instances and start a single one.

## Security

Scout extension mode uses a 6-layer security model to protect the WebSocket relay between the MCP server and Chrome.

### Security Model

| Layer | Threat Blocked | Mechanism |
|-------|---------------|-----------|
| 1. Localhost binding | Remote attackers | Server binds to `127.0.0.1` explicitly — not `0.0.0.0`, not a wildcard |
| 2. Path enforcement | Probing / scanning | Server rejects WebSocket connections to any path other than `/scout-extension` with 404 |
| 3. Origin rejection | Malicious websites | WebSocket connections that include an `Origin` header are rejected with 403 (browsers set `Origin` on page-initiated WebSocket connections; extensions do not) |
| 4. Token auth via Native Messaging | Local malicious apps | A one-time token is written to a permission-restricted file and delivered to the extension through Chrome's Native Messaging (NM) channel. Chrome enforces that only the extension with the pinned ID can invoke the NM host |
| 5. Connection limit | Session hijacking | Only 1 concurrent WebSocket connection is accepted. A second connection is refused until the first disconnects |
| 6. File permissions | Other-user processes | The token file is created with `os.open()` using mode `0o600` on Unix. On Windows, the per-user temp directory ACLs restrict access to the current user |

### Native Messaging Setup

Native Messaging (NM) is the mechanism Chrome uses to let extensions communicate with local executables. Scout uses it to deliver the authentication token securely — Chrome guarantees that only the extension with the registered ID can open the NM channel.

**Setup steps:**

1. Load the extension from the `extension/` directory (see [Installation](#installation))
2. Start the Scout MCP server — it automatically writes the NM host manifest (`com.scout.bridge.json`) to Chrome's `NativeMessagingHosts/` directory using the pinned extension ID

The extension uses a `key` field in `manifest.json` that pins its ID to `mjialmenlimilhhjgjjjofneeflihccn` on every machine. No manual ID copying is needed. If you build a custom extension with a different key, set `SCOUT_EXTENSION_ID` to override the default.

### Browser Compatibility

Extension mode supports **Chrome only** in v1. Chromium-based browsers (Brave, Edge, Chromium) can work with the `SCOUT_CHROME_NM_PATH` override described below, but are not officially tested.

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `SCOUT_EXTENSION_ID` | **(Optional)** Override the default extension ID (`mjialmenlimilhhjgjjjofneeflihccn`). Only needed if you build a custom extension with a different `key` in `manifest.json`. |
| `SCOUT_CHROME_NM_PATH` | **(Optional)** Override the directory where Scout writes the NM host manifest. Use this when running a Chromium-based browser that reads NM manifests from a non-default location. |

**Known `SCOUT_CHROME_NM_PATH` values for Chromium-based browsers:**

| Browser | OS | Path |
|---------|----|------|
| Brave | Linux | `~/.config/BraveSoftware/Brave-Browser/NativeMessagingHosts/` |
| Brave | macOS | `~/Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts/` |
| Chromium | Linux | `~/.config/chromium/NativeMessagingHosts/` |
| Edge | Linux | `~/.config/microsoft-edge/NativeMessagingHosts/` |

### What Scout CAN Access Through the Extension

- DOM content of the active tab (same as DevTools)
- Network requests/responses for the active tab
- JavaScript execution in the page context
- Screenshots of the active tab
- Cookies and storage visible to the page

### What Scout CANNOT Access

- Other tabs (only the active tab is debugged)
- Chrome's internal pages (`chrome://`, `chrome-extension://`)
- Browser-level settings or bookmarks
- File system (beyond download directory)
- Other extensions' data

### Infobar Notice

When the debugger attaches, Chrome shows an infobar: *"Scout MCP Bridge started debugging this browser"*. This is a Chrome security feature — it is visible to you (the user) but is **not detectable by websites**. The infobar disappears when the debugger detaches.

### Automation Detection

Extension mode does NOT set any automation flags (`navigator.webdriver`, automation headers, etc.). Your browser fingerprint remains identical to normal browsing. The `chrome.debugger` API uses the same CDP protocol as DevTools — websites cannot distinguish debugger usage from normal browsing.

### Residual Risk

No localhost WebSocket design is immune to every local-machine attack. A process running as the same OS user with the ability to read the token file (layer 6) and connect before the legitimate extension (layer 5) could, in theory, impersonate the extension. The NM channel (layer 4) raises the bar significantly — an attacker would need to register their own NM host or read the token file within the narrow window between server start and extension connection. For most threat models, the combination of all six layers provides defense-in-depth that is appropriate for a development-time tool running on a developer workstation.

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
