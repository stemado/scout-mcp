#!/usr/bin/env bash
# Scout dependency pre-check — runs at SessionStart via Claude Code hook.
# Always exits 0 (informational, never blocking).
#
# POSIX-compatible: no bash arrays, works on macOS default bash 3.2.
#
# Note: We do NOT check for 'uv' here. The MCP server is started via
# 'uv run ...' in .mcp.json, so if uv is missing the server never starts
# and this hook never fires. Claude Code itself reports the MCP startup
# failure in that case.

set -u

# --- OS detection ---
detect_os() {
  case "${OSTYPE:-}" in
    darwin*)  echo "macos" ;;
    msys*|cygwin*|mingw*) echo "windows" ;;
    linux*)   echo "linux" ;;
    *)
      case "$(uname -s 2>/dev/null)" in
        Darwin)  echo "macos" ;;
        Linux)   echo "linux" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)       echo "unknown" ;;
      esac
      ;;
  esac
}

OS="$(detect_os)"

# String-based tracking (no arrays — POSIX compatible)
MISSING=""
FOUND=""

add_found() {
  if [ -n "$FOUND" ]; then
    FOUND="$FOUND, $1"
  else
    FOUND="$1"
  fi
}

add_missing() {
  if [ -n "$MISSING" ]; then
    MISSING="$MISSING $1"
  else
    MISSING="$1"
  fi
}

# --- Check Python 3.11+ ---
check_python() {
  for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
      py_version=$("$cmd" --version 2>&1 | sed -n 's/.*\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -1)
      if [ -n "$py_version" ]; then
        major=$(echo "$py_version" | cut -d. -f1)
        minor=$(echo "$py_version" | cut -d. -f2)
        # Correct comparison: major > 3, OR major == 3 AND minor >= 11
        if [ "$major" -gt 3 ] 2>/dev/null || { [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; } 2>/dev/null; then
          add_found "Python $py_version"
          return
        fi
      fi
    fi
  done
  add_missing "python"
}

# --- Check Node.js ---
check_node() {
  if command -v node >/dev/null 2>&1; then
    node_version=$(node --version 2>&1 | sed -n 's/.*\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -1)
    add_found "Node.js ${node_version:-unknown}"
  else
    add_missing "node"
  fi
}

# --- Check Chrome ---
check_chrome() {
  case "$OS" in
    macos)
      if [ -d "/Applications/Google Chrome.app" ]; then
        add_found "Chrome (macOS)"
        return
      fi
      ;;
    windows)
      # Git Bash / MSYS uses /c/ prefix for Windows drive paths
      for chrome_path in \
        "/c/Program Files/Google/Chrome/Application/chrome.exe" \
        "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"; do
        if [ -f "$chrome_path" ]; then
          add_found "Chrome (Windows)"
          return
        fi
      done
      # Also check via user profile path
      if [ -n "${USERPROFILE:-}" ]; then
        # Convert backslashes to forward slashes for bash
        user_local=$(echo "$USERPROFILE" | sed 's|\\|/|g' | sed 's|^\([A-Za-z]\):|/\L\1|')
        if [ -f "$user_local/AppData/Local/Google/Chrome/Application/chrome.exe" ]; then
          add_found "Chrome (Windows)"
          return
        fi
      fi
      ;;
    linux)
      for cmd in google-chrome google-chrome-stable chromium chromium-browser; do
        if command -v "$cmd" >/dev/null 2>&1; then
          add_found "Chrome/Chromium (Linux)"
          return
        fi
      done
      ;;
  esac
  add_missing "chrome"
}

# --- Install instructions per OS ---
install_instructions() {
  dep="$1"
  case "$dep" in
    python)
      case "$OS" in
        macos)   echo "    brew install python@3.11" ;;
        windows) echo "    Download from https://python.org or let uv manage it" ;;
        linux)   echo "    sudo apt install python3.11  (or equivalent for your distro)" ;;
        *)       echo "    Install Python 3.11+ from https://python.org" ;;
      esac
      ;;
    node)
      case "$OS" in
        macos)   echo "    brew install node" ;;
        windows) echo "    winget install OpenJS.NodeJS" ;;
        linux)   echo "    sudo apt install nodejs  (or see https://nodejs.org)" ;;
        *)       echo "    Install Node.js from https://nodejs.org" ;;
      esac
      ;;
    chrome)
      case "$OS" in
        macos)   echo "    brew install --cask google-chrome" ;;
        linux)   echo "    sudo apt install google-chrome-stable  (or download from https://www.google.com/chrome/)" ;;
        *)       echo "    Download from https://www.google.com/chrome/" ;;
      esac
      ;;
  esac
}

# --- Self-test mode ---
if [ "${1:-}" = "--self-test" ]; then
  echo "OS detected: $OS"
  echo ""
  echo "Testing Python version comparison:"
  for test_ver in "3.10.5" "3.11.0" "3.12.1" "4.0.0" "2.7.18"; do
    major=$(echo "$test_ver" | cut -d. -f1)
    minor=$(echo "$test_ver" | cut -d. -f2)
    if [ "$major" -gt 3 ] 2>/dev/null || { [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; } 2>/dev/null; then
      echo "  Python $test_ver -> PASS (meets 3.11+)"
    else
      echo "  Python $test_ver -> FAIL (below 3.11)"
    fi
  done
  echo ""
  echo "Running full dependency check:"
  echo ""
  # Fall through to normal execution
fi

# --- Run all checks ---
check_python
check_node
check_chrome

# --- Output report ---
if [ -z "$MISSING" ]; then
  echo "Scout: All dependencies OK ($FOUND)."
else
  # Count missing
  missing_count=0
  for dep in $MISSING; do
    missing_count=$((missing_count + 1))
  done

  echo "Scout dependency check: $missing_count missing dependency(ies) detected."
  echo ""
  if [ -n "$FOUND" ]; then
    echo "Found: $FOUND"
    echo ""
  fi
  echo "Missing:"
  for dep in $MISSING; do
    echo "  - $dep"
    install_instructions "$dep"
  done
  echo ""
  echo "Please install the missing dependencies above. If you'd like, I can run the install commands for you."
fi

exit 0
