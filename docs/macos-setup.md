# macOS Setup Guide

This guide covers installing Scout and its prerequisites on macOS. If you already have Claude Code running, this should take about 5 minutes.

## Prerequisites

### 1. Homebrew

Most of the dependencies install easiest through Homebrew. If you don't have it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After installing, follow the instructions it prints to add Homebrew to your PATH (the commands differ between Intel and Apple Silicon Macs).

### 2. Python 3.11+

Check your current version:

```bash
python3 --version
```

If you need to install or upgrade:

```bash
brew install python@3.11
```

Verify it worked:

```bash
python3 --version  # Should show 3.11.x or higher
```

### 3. uv (Python package manager)

Scout uses `uv` to auto-install its Python dependencies in an isolated environment. No manual `pip install` needed -- `uv` handles everything on first launch.

```bash
brew install uv
```

Or via the official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:

```bash
uv --version
```

### 4. Google Chrome

Scout drives Chrome via the DevTools Protocol. It expects Chrome at the standard macOS path:

```
/Applications/Google Chrome.app
```

If you don't have Chrome installed, download it from [google.com/chrome](https://www.google.com/chrome/) or:

```bash
brew install --cask google-chrome
```

### 5. Node.js

Botasaurus (the browser engine under Scout) requires Node.js at runtime.

```bash
brew install node
```

Verify:

```bash
node --version
```

### 6. Claude Code

Scout is a Claude Code plugin. Install Claude Code if you haven't:

```bash
npm install -g @anthropic-ai/claude-code
```

## Install Scout

With all prerequisites in place, open Claude Code and run these two commands:

```
/plugin marketplace add stemado/scout-marketplace
```

Then:

```
/plugin install scout@scout-marketplace
```

Restart Claude Code to load the MCP server.

## Verify It Works

After restarting, ask Claude:

```
/scout https://example.com
```

You should see a Chrome window open, navigate to the page, and Claude will return a structural overview of the page. If the browser opens and the scout report comes back, you're all set.

## Troubleshooting

### "Chrome not found" or browser fails to launch

Make sure Chrome is at `/Applications/Google Chrome.app`. Botasaurus looks for Chrome at the standard macOS installation path. If you installed Chromium instead, you may need to create a symlink or set the Chrome path explicitly.

### "uv: command not found"

Your shell hasn't picked up the `uv` binary yet. Either:
- Open a new terminal window, or
- Run `source ~/.zshrc` (or `~/.bashrc` if using bash)

### "node: command not found"

Same as above -- open a new terminal or source your shell profile after installing Node.js via Homebrew.

### MCP server fails to start

Check that `uv` can resolve dependencies:

```bash
cd ~/.claude/plugins/scout   # or wherever Claude Code installed the plugin
uv run python -c "import botasaurus_driver; print('OK')"
```

If this fails, try clearing the virtual environment and letting `uv` recreate it:

```bash
rm -rf .venv
uv run python -c "import botasaurus_driver; print('OK')"
```

### Permission denied errors

macOS may prompt you to allow Chrome to be controlled by another application. Click "Allow" when prompted. If you previously denied it, go to **System Settings > Privacy & Security > Automation** and enable the relevant permissions.

## Quick Reference

| Prerequisite | Install command | Verify command |
|---|---|---|
| Homebrew | See above | `brew --version` |
| Python 3.11+ | `brew install python@3.11` | `python3 --version` |
| uv | `brew install uv` | `uv --version` |
| Google Chrome | `brew install --cask google-chrome` | `ls "/Applications/Google Chrome.app"` |
| Node.js | `brew install node` | `node --version` |
| Claude Code | `npm install -g @anthropic-ai/claude-code` | `claude --version` |

## Next Steps

- Read the [Getting Started guide](getting-started.md) for a walkthrough of your first session
- Try `/scout` on a site you want to automate
- Set up a `.env` file for credential handling (see Getting Started)
