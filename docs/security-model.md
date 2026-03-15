# Scout MCP Security Model

This document describes the seven security layers implemented to harden Scout
against threats that emerge from its deployment context: an AI agent operating
Scout via MCP, with an optional Chrome extension relay giving Scout access to
the user's authenticated browser sessions.

## Threat Model

Scout's unique risk profile comes from the combination of:

1. **AI agent as operator** — The agent interprets web page content and decides
   what actions to take. Malicious page content can influence agent behavior
   (prompt injection).

2. **Authenticated browser access** — In extension mode, Scout operates within
   the user's logged-in browser sessions, with access to cookies, localStorage,
   and session tokens.

3. **Credential handling** — `fill_secret` types credentials from `.env` files
   into form fields. Credentials must not leak into tool responses or be typed
   into unintended domains.

4. **Network visibility** — `monitor_network` captures request/response data
   including POST bodies that may contain credentials.

5. **JavaScript execution** — `execute_javascript` runs arbitrary JS in the
   page context with full access to the page's origin.

---

## Layer 1: Prompt Injection Hardening

**Module:** `scout/security/injection_filter.py`

**Threat:** Malicious web pages embed text designed to influence the AI agent's
behavior — e.g., "ignore previous instructions", "navigate to evil.com",
"send credentials to...".

**Mitigation:** The `PromptInjectionFilter` scans all content returned by
`scout_page_tool`, `find_elements`, and `inspect_element_tool` for:

- **Imperative instruction patterns**: "ignore previous", "disregard",
  "new instructions", "system prompt", "you are now", "act as", "your new role",
  "forget everything"
- **Self-referential agent commands**: "navigate to", "click on", "type",
  "execute" — when these appear in non-interactive page content
- **Credential-targeting patterns**: text referencing sending/posting credentials
  to unexpected destinations
- **Authority/urgency framing**: "IMPORTANT:", "SYSTEM:", "ADMIN:", "WARNING:"
  in page text

**Behavior:**
- Content is **never modified or suppressed** — it is returned intact
- A structured `[SCOUT SECURITY WARNING]` block is prepended outside content
  boundaries when patterns are detected
- Detections are logged to `~/.scout/security.log`
- A session-level `injection_attempts` counter is maintained

**Design rationale:** Silent modification is more dangerous than transparent
flagging. The agent and user should see exactly what the page contains, plus
an explicit warning about suspicious patterns.

---

## Layer 2: WebSocket Origin and Token Validation (Extension Mode)

**Module:** `scout/extension_relay.py` (modified)

**Threat:** The WebSocket server on localhost:9222 could accept connections from
arbitrary localhost processes (e.g., malicious web pages, other applications).

**Mitigations:**

### Session Token Authentication
- On startup, a cryptographically random 32-byte token is generated
- Token is written to `/tmp/scout-extension-token-<pid>` (owner-only permissions)
- The extension reads this token at activation time
- First WebSocket message must be `{"type": "auth", "token": "<token>"}`
- Connections that don't authenticate within 2 seconds are rejected
- Token file is deleted on server shutdown

### Origin Validation
- WebSocket upgrade requests with an `Origin` header are rejected
- Browser extensions send no Origin header; web pages attempting to connect
  would send one
- Rejected connections are logged

### Connection Limit
- Exactly one concurrent extension connection is accepted
- Additional connection attempts are rejected with a clear error message

---

## Layer 3: Domain Scoping for fill_secret

**Module:** `scout/server.py` (modified `fill_secret` and `launch_session`)

**Threat:** An agent could be tricked into typing credentials into form fields
on a phishing page that has navigated away from the intended domain.

**Mitigation:**

`launch_session` accepts an optional `allowed_domains` parameter:

```python
launch_session(url="https://app.example.com", allowed_domains=["example.com"])
```

**Behavior:**
- If `allowed_domains` is set, `fill_secret` extracts the current page's
  registered domain (via `tldextract`) and verifies it's in the allowed list
- If the domain is NOT allowed: credential typing is refused, an error is
  returned, and the attempt is logged as `credential_refused` (severity: critical)
- If `allowed_domains` is not set: `fill_secret` works as before but emits a
  `[SECURITY]` warning in its response recommending domain scoping

---

## Layer 4: Cross-Origin Navigation Guard (Extension Mode)

**Module:** `scout/security/navigation_guard.py`

**Threat:** In extension mode, the debugger follows the tab wherever it navigates.
A malicious page could redirect to a phishing domain while the agent believes
it's still on the original site.

**Mitigation:**

The `NavigationGuard` tracks the origin domain from `launch_session` and checks
all navigations against the `allowed_domains` list.

**Behavior:**
- Navigations to domains in `allowed_domains` proceed normally
- Cross-origin navigations to unlisted domains are blocked with a structured
  warning returned to the agent
- The `allow_navigation(url)` MCP tool grants a one-time navigation permit
- The guard never auto-permits — explicit agent invocation is required

---

## Layer 5: Network Monitor POST Body Scrubbing

**Module:** `scout/security/scrubbing.py`

**Threat:** `monitor_network` captures request/response bodies that may contain
credentials in POST data (form submissions, API calls).

**Mitigation:** POST bodies are scrubbed before entering the tool response:

- **URL-encoded form fields**: `password=`, `passwd=`, `pwd=`, `pass=`,
  `token=`, `api_key=`, `apikey=`, `secret=`, `client_secret=`
- **JSON body fields**: Same key patterns in JSON format
- **Environment variable values**: Any value from the session's loaded `.env`
  file (matched by key name, case-insensitive)

**Behavior:**
- Values are replaced with `[REDACTED]` — keys are preserved
- A `scrubbed_fields` count is added to the `monitor_network` response
- Scrubbing events are logged and counted in the security summary

---

## Layer 6: execute_javascript Scope Warning

**Module:** `scout/server.py` (modified `execute_javascript`)

**Threat:** Users and agents may not realize the full scope of JS execution —
localStorage access, network request capability, etc.

**Mitigation:** Every `execute_javascript` response is prepended with:

```
[JS EXECUTION SCOPE]
Ran in page context of: <current_url>
localStorage accessible: yes
sessionStorage accessible: yes
HttpOnly cookies: not accessible
Cross-origin iframes: not accessible
Network requests: permitted to <origin> and any CORS-permitted origins
[END SCOPE]
```

This is transparency, not restriction. The agent and user always know what
scope was active during execution.

---

## Layer 7: Security Event Log and Audit Tool

**Module:** `scout/security/audit_log.py`

All security events are centralized into `~/.scout/security.log` as JSON lines:

```json
{
  "timestamp": "2026-03-15T14:23:01Z",
  "session_id": "abc123",
  "event_type": "injection_detected",
  "severity": "warning",
  "url": "https://...",
  "detail": { ... }
}
```

### Event Types
| Event Type | Severity | Description |
|---|---|---|
| `injection_detected` | warning | Prompt injection patterns found in page content |
| `credential_refused` | critical | fill_secret blocked by domain scoping |
| `navigation_blocked` | warning | Cross-origin navigation blocked by guard |
| `ws_rejected` | warning | WebSocket connection rejected (auth/origin/limit) |
| `scrubbing_applied` | info | POST body scrubbing redacted sensitive fields |

### MCP Tool: get_security_log

```python
get_security_log(
    session_id: str | None = None,  # filter to session
    severity: str | None = None,    # filter by severity
    limit: int = 50
) -> dict
```

Returns recent security events. Useful for auditing a session before exporting
a workflow.

### Session History Integration

`get_session_history` now includes a `security_summary` field:

```json
{
  "security_summary": {
    "injection_attempts": 0,
    "credentials_refused": 0,
    "navigations_blocked": 0,
    "post_bodies_scrubbed": 0,
    "ws_connections_rejected": 0
  }
}
```

---

## Existing Security Mitigations (Preserved)

These pre-existing mitigations remain in place and are complemented by the
new layers:

- **Content boundary markers** (`sanitize.py`): Wraps tool responses with
  `[SCOUT_WEB_CONTENT_START]` / `[SCOUT_WEB_CONTENT_END]` delimiters
- **Zero-width character stripping** (`sanitize.py`): Removes invisible Unicode
  characters that can hide injection payloads
- **Secret scrubbing** (`sanitize.py`, `session.py`): Replaces registered
  credential values with `[REDACTED]` in all tool responses
- **URL validation** (`validation.py`): SSRF protection blocking metadata
  endpoints, loopback addresses, and non-HTTP schemes
- **Header redaction** (`network.py`): Authorization, Cookie, and API key
  headers are redacted from captured network events

---

## Security Log Location

All security events are logged to: `~/.scout/security.log`

The log never contains actual credential values — even in the detail field of
`credential_refused` events, only the environment variable name is recorded.

## Design Principles

1. **Never silently modify content** — Flag, warn, log, and surface. Silent
   modification obscures threats.
2. **Defense in depth** — Multiple overlapping layers so that failure of any
   single layer doesn't compromise security.
3. **Transparency over restriction** — The agent and user should always know
   what's happening. Scope disclosures and warnings make implicit capabilities
   explicit.
4. **Fail-safe defaults** — Domain scoping is opt-in but recommended.
   Navigation guards block by default and require explicit permits.
