/**
 * Scout MCP Bridge — Background Service Worker
 *
 * Relays CDP commands between the Scout MCP server (via WebSocket)
 * and chrome.debugger attached to the active tab.
 */

const WS_URL = "ws://127.0.0.1:9222/scout-extension";
const CDP_VERSION = "1.3";

let ws = null;
let attachedTabId = null;
let active = false;
let reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 30000;

// --- WebSocket Management ---

function connect() {
  if (!active) return;
  if (ws && ws.readyState === WebSocket.OPEN) return;

  // Step 1: Fetch token via Native Messaging before opening WebSocket
  updateStatus("connecting");

  chrome.runtime.sendNativeMessage(
    "com.scout.bridge",
    { type: "get_token" },
    (response) => {
      if (chrome.runtime.lastError) {
        console.error("[Scout] NM host error:", chrome.runtime.lastError.message);
        if (chrome.runtime.lastError.message.includes("not found")) {
          updateStatus("error");
        } else {
          updateStatus("waiting");
          scheduleReconnect();
        }
        return;
      }

      if (response.error) {
        console.log("[Scout] Token not available:", response.error);
        updateStatus("waiting");
        scheduleReconnect();
        return;
      }

      const token = response.token;

      // Step 2: Open WebSocket and send auth token as first message
      try {
        ws = new WebSocket(WS_URL);
      } catch (e) {
        scheduleReconnect();
        return;
      }

      ws.onopen = () => {
        console.log("[Scout] WebSocket connected, sending auth");
        ws.send(JSON.stringify({ type: "auth", token: token }));
      };

      ws.onmessage = (event) => {
        let message;
        try {
          message = JSON.parse(event.data);
        } catch (e) {
          console.error("[Scout] Invalid JSON from server:", e);
          return;
        }

        if (message.type === "auth_ok") {
          console.log("[Scout] Authenticated successfully");
          reconnectDelay = 1000;
          updateStatus("connected");

          // Attach to current tab and send ready
          chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
              attachToTab(tabs[0].id, tabs[0].url);
            }
          });
          return;
        }

        if (message.type === "cdp_command") {
          handleCdpCommand(message);
        } else if (message.type === "detach") {
          detachFromTab();
        }
      };

      ws.onclose = () => {
        console.log("[Scout] WebSocket closed");
        ws = null;
        if (active) {
          updateStatus("waiting");
          scheduleReconnect();
        }
      };

      ws.onerror = (e) => {
        console.warn("[Scout] WebSocket error:", e);
        // onclose will fire after this
      };
    }
  );
}

function scheduleReconnect() {
  if (!active) return;
  setTimeout(() => {
    connect();
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
  }, reconnectDelay);
}

function disconnect() {
  if (ws) {
    ws.close();
    ws = null;
  }
  detachFromTab();
  updateStatus("inactive");
}

// --- Chrome Debugger Management ---

function attachToTab(tabId, url) {
  if (attachedTabId === tabId) {
    // Already attached, just send ready
    sendReady(tabId, url);
    return;
  }

  // Detach from previous tab if needed
  if (attachedTabId !== null) {
    try {
      chrome.debugger.detach({ tabId: attachedTabId });
    } catch (e) {
      // Ignore detach errors
    }
    attachedTabId = null;
  }

  chrome.debugger.attach({ tabId }, CDP_VERSION, () => {
    if (chrome.runtime.lastError) {
      console.error("[Scout] Failed to attach debugger:", chrome.runtime.lastError.message);
      sendError("attach_failed", chrome.runtime.lastError.message);
      return;
    }

    attachedTabId = tabId;
    console.log("[Scout] Debugger attached to tab", tabId);

    // Enable CDP domains that generate events we need to forward
    const domains = ["Page", "Network", "DOM", "Runtime", "Browser"];
    for (const domain of domains) {
      chrome.debugger.sendCommand({ tabId }, `${domain}.enable`, {}, () => {
        if (chrome.runtime.lastError) {
          console.debug(`[Scout] ${domain}.enable:`, chrome.runtime.lastError.message);
        }
      });
    }

    sendReady(tabId, url);
  });
}

function detachFromTab() {
  if (attachedTabId !== null) {
    try {
      chrome.debugger.detach({ tabId: attachedTabId });
    } catch (e) {
      // Ignore
    }
    attachedTabId = null;
  }
}

function sendReady(tabId, url) {
  sendToServer({
    type: "extension_ready",
    tabId: tabId,
    url: url || "about:blank",
  });
}

function sendError(code, message) {
  sendToServer({
    type: "error",
    code: code,
    message: message,
  });
}

function sendToServer(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data));
  }
}

// --- CDP Command Relay ---

function handleCdpCommand(message) {
  const { id, method, params, no_response } = message;

  if (attachedTabId === null) {
    if (!no_response) {
      sendToServer({
        type: "cdp_response",
        id: id,
        error: "No tab attached",
      });
    }
    return;
  }

  chrome.debugger.sendCommand(
    { tabId: attachedTabId },
    method,
    params || {},
    (result) => {
      if (no_response) return;

      if (chrome.runtime.lastError) {
        sendToServer({
          type: "cdp_response",
          id: id,
          error: chrome.runtime.lastError.message,
        });
      } else {
        sendToServer({
          type: "cdp_response",
          id: id,
          result: result || {},
        });
      }
    }
  );
}

// --- CDP Event Forwarding ---

chrome.debugger.onEvent.addListener((source, method, params) => {
  if (source.tabId !== attachedTabId) return;

  sendToServer({
    type: "cdp_event",
    method: method,
    params: params || {},
  });
});

// --- Tab Change Handling ---

chrome.tabs.onActivated.addListener((activeInfo) => {
  if (!active || !ws || ws.readyState !== WebSocket.OPEN) return;

  chrome.tabs.get(activeInfo.tabId, (tab) => {
    if (chrome.runtime.lastError) return;

    // Detach from old tab and attach to new one
    attachToTab(tab.id, tab.url);

    sendToServer({
      type: "tab_changed",
      tabId: tab.id,
      url: tab.url || "about:blank",
    });
  });
});

// --- Debugger Detach Handling ---

chrome.debugger.onDetach.addListener((source, reason) => {
  if (source.tabId === attachedTabId) {
    console.log("[Scout] Debugger detached:", reason);
    attachedTabId = null;

    sendToServer({
      type: "cdp_event",
      method: "Inspector.detached",
      params: { reason },
    });
  }
});

// --- Activation / Deactivation ---

function activate() {
  active = true;
  reconnectDelay = 1000;
  chrome.storage.local.set({ active: true });
  updateStatus("waiting");
  connect();
}

function deactivate() {
  active = false;
  chrome.storage.local.set({ active: false });
  disconnect();
}

function updateStatus(status) {
  chrome.storage.local.set({ status });
}

// --- Message Handling from Popup ---

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "activate") {
    activate();
    sendResponse({ ok: true });
  } else if (message.action === "deactivate") {
    deactivate();
    sendResponse({ ok: true });
  } else if (message.action === "getStatus") {
    chrome.storage.local.get(["active", "status"], (data) => {
      sendResponse({
        active: data.active || false,
        status: data.status || "inactive",
        tabId: attachedTabId,
        tabUrl: attachedTabId ? undefined : null,
      });
    });
    return true; // async response
  }
});

// --- Restore state on service worker startup ---

chrome.storage.local.get(["active"], (data) => {
  if (data.active) {
    activate();
  }
});
