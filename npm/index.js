#!/usr/bin/env node

/**
 * scout-mcp-server npm launcher
 *
 * Thin wrapper that launches the Python MCP server.
 * Tries uvx first (zero-install), then pipx fallback.
 * All stdio is passed through for MCP transport.
 *
 * Windows compatibility: uses shell:true so Node can execute .cmd/.ps1
 * shims (uvx.cmd, pipx.cmd) that package managers install on Windows.
 *
 * Signal forwarding: SIGTERM/SIGINT are forwarded to the child process
 * so the Python server (and Chrome) shut down cleanly when the MCP
 * client disconnects.
 */

const { spawn, execSync } = require("child_process");

const IS_WIN = process.platform === "win32";

function commandExists(cmd) {
  try {
    execSync(`${cmd} --version`, { stdio: "ignore", shell: true });
    return true;
  } catch {
    return false;
  }
}

function launch(command, args) {
  const child = spawn(command, args, {
    stdio: "inherit",
    shell: IS_WIN,
    windowsHide: true,
  });

  // Forward termination signals so the Python server shuts down cleanly.
  // Without this, killing the npm process orphans the Python process
  // (and any Chrome instances it launched).
  function forwardSignal(signal) {
    process.on(signal, () => {
      child.kill(signal);
    });
  }
  forwardSignal("SIGTERM");
  forwardSignal("SIGINT");

  child.on("error", (err) => {
    if (err.code === "ENOENT") {
      process.stderr.write(
        `Error: '${command}' not found. Install uv (https://docs.astral.sh/uv/) and Python 3.11+.\n`
      );
      process.exit(1);
    }
    process.stderr.write(`Error: ${err.message}\n`);
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code ?? 1);
  });
}

// Strategy 1: uvx (zero-install Python runner — preferred)
if (commandExists("uvx")) {
  launch("uvx", ["scout-mcp-server"]);
}
// Strategy 2: pipx
else if (commandExists("pipx")) {
  launch("pipx", ["run", "scout-mcp-server"]);
}
// No supported launcher found
else {
  process.stderr.write(
    "Error: Neither uvx nor pipx found.\n" +
      "Install uv (recommended): https://docs.astral.sh/uv/\n" +
      "Or install pipx: https://pipx.pypa.io/\n"
  );
  process.exit(1);
}
