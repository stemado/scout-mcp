# Scout

Browser automation for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Describe what you need done on a website — Scout opens a browser, reads the DOM, and acts.

-----

## Install

**Prerequisites:** Claude Code, Python 3.11+, [uv](https://docs.astral.sh/uv/), Google Chrome, Node.js

```sh
/plugin marketplace add stemado/Scout
/plugin install Scout@Scout
```

Restart Claude Code.

**To update:**

```sh
/plugin marketplace update Scout
/plugin install Scout@Scout
```

-----

## Tools

|Tool                 |Description                                                       |
|---------------------|------------------------------------------------------------------|
|`launch_session`     |Open a browser (headed or headless, optional proxy)               |
|`scout_page_tool`    |Structural page overview: iframes, shadow DOM, element counts     |
|`find_elements`      |Search for elements by text, type, or CSS selector                |
|`execute_action_tool`|Click, type, select, navigate, scroll, hover, wait                |
|`fill_secret`        |Type credentials from `.env` without exposing them in conversation|
|`get_2fa_code`       |Retrieve a 2FA OTP code from Twilio SMS                           |
|`execute_javascript` |Run arbitrary JS in the page context                              |
|`take_screenshot`    |Capture the page                                                  |
|`inspect_element`    |Deep-inspect visibility, overlays, shadow DOM, ARIA               |
|`process_download`   |Convert and move downloaded files                                 |
|`get_session_history`|Export the full session as a structured workflow log              |
|`monitor_network`    |Watch HTTP traffic to discover API endpoints under the UI         |
|`record_video`       |Record the browser session as MP4                                 |
|`close_session`      |Close the browser and release resources                           |

-----

## Slash Commands

|Command                               |Description                                                |
|--------------------------------------|-----------------------------------------------------------|
|`/Scout:demo`                         |Run a full capabilities demo                               |
|`/Scout:scout <url>`                  |Launch a browser and scout any page                        |
|`/Scout:export [name]`                |Export the current session as a replayable workflow        |
|`/Scout:schedule [list/name/delete]`  |Schedule an exported workflow                              |
|`/Scout:landscape <url>`              |Run a structured landscape analysis of a product or website|
|`/Scout:benchmark`                    |Run performance benchmarks                                 |
|`/Scout:report [bug/feature/friction]`|File a GitHub issue with diagnostics                       |

-----

## Export and Schedule

Walk through a workflow conversationally, then capture it:

```sh
/export enrollment
```

Produces `workflows/enrollment/` containing a standalone Python script, portable workflow JSON, `requirements.txt`, and `.env.example`.

Schedule it with:

```sh
/schedule enrollment
```

Detects your OS and creates the appropriate task — Windows Task Scheduler, macOS launchd, or Linux cron.

-----

## Security

- **Credential isolation** — `fill_secret` reads from `.env` server-side; passwords never enter the conversation
- **Header redaction** — Authorization, Cookie, and API key headers scrubbed from network logs
- **URL validation** — blocks `file://`, `javascript://`, cloud metadata endpoints, and localhost (opt-in via `Scout_ALLOW_LOCALHOST`)
- **Path traversal protection** — all file paths validated
- **Invisible character stripping** — removes zero-width Unicode to prevent prompt injection

-----

## License

MIT
