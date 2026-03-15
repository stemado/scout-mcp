/**
 * Scout MCP Bridge — Popup UI
 */

const toggle = document.getElementById("active-toggle");
const toggleText = document.getElementById("toggle-text");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const tabUrl = document.getElementById("tab-url");

const STATUS_MESSAGES = {
  connected: "Connected to Scout",
  waiting: "Waiting for Scout...",
  inactive: "Inactive",
};

function updateUI(data) {
  const isActive = data.active || false;
  const status = data.status || "inactive";

  toggle.checked = isActive;
  toggleText.textContent = isActive ? "Active" : "Inactive";

  // Status dot
  statusDot.className = "status-dot " + status;

  // Status text
  statusText.textContent = STATUS_MESSAGES[status] || status;

  // Tab URL
  if (isActive && data.tabUrl) {
    tabUrl.textContent = data.tabUrl;
    tabUrl.style.display = "block";
  } else {
    tabUrl.style.display = "none";
  }
}

// Load initial state
chrome.runtime.sendMessage({ action: "getStatus" }, (response) => {
  if (response) {
    // Also get current tab URL
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        response.tabUrl = tabs[0].url;
      }
      updateUI(response);
    });
  }
});

// Toggle handler
toggle.addEventListener("change", () => {
  const action = toggle.checked ? "activate" : "deactivate";
  chrome.runtime.sendMessage({ action }, () => {
    // Refresh status after a brief delay
    setTimeout(() => {
      chrome.runtime.sendMessage({ action: "getStatus" }, (response) => {
        if (response) {
          chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
              response.tabUrl = tabs[0].url;
            }
            updateUI(response);
          });
        }
      });
    }, 500);
  });
});

// Auto-refresh status every 2 seconds while popup is open
setInterval(() => {
  chrome.runtime.sendMessage({ action: "getStatus" }, (response) => {
    if (response) {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          response.tabUrl = tabs[0].url;
        }
        updateUI(response);
      });
    }
  });
}, 2000);
