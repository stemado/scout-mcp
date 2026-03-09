---
description: Export the current browser session as a replayable workflow (Python script + portable JSON)
argument-hint: "[workflow-name]"
allowed-tools:
  - "mcp__plugin_scout_scout__*"
---

Generate both a self-contained Python script and a portable workflow JSON file from the current browser session. Follow these steps precisely:

## Step 1: Get the session history

Call `get_session_history` with the active session_id. If no session is active, tell the user they need to run a workflow first using `/scout`.

## Step 2: Extract the workflow steps

From the history, use ONLY these fields to build the script:
- **`navigations`** — the first entry's `url` becomes the initial `driver.get()` call
- **`actions`** — each successful action becomes a step in the script

**Ignore** `scouts` and `find_elements_calls` entirely — those were reconnaissance, not replay steps. Only include actions where `success` is `true`.

## Step 3: Map actions to botasaurus-driver code

Use this exact mapping for each action record:

| action | Code |
|--------|------|
| `navigate` | `driver.get(value)` |
| `click` | `driver.click(selector)` |
| `type` | `human_type(driver, selector, value)` |
| `select` | `driver.select_option(selector, value=value)` |
| `scroll` | `driver.run_js(f"window.scrollBy(0, {amount})")` |
| `wait` (with selector) | `driver.wait_for_element(selector, wait=timeout_seconds)` |
| `wait` (no selector) | `time.sleep(seconds)` |
| `press_key` | Use CDP dispatch pattern from botasaurus_driver.cdp |
| `hover` | Use JS getBoundingClientRect + CDP mouseMoved |
| `clear` | `driver.clear(selector)` |

If `frame_context` is present and not "main", wrap the action with `driver.select_iframe(frame_context)` to get the iframe handle, then call the method on that handle instead of the driver.

## Step 4: Parameterize credentials — MANDATORY

Scan all `type` actions for sensitive fields:
- If the **selector** contains "password" (case-insensitive) OR the action's value was typed into a password-type field: extract the value to a `PASSWORD` variable at the top of the script. Replace the inline value with the variable name.
- If a `type` action targets a selector containing "username", "user", "email", or "login" (case-insensitive): extract the value to a `USERNAME` variable.
- For any other potentially sensitive values (API keys, tokens), extract them to named variables.

**NEVER hardcode credentials in the script body.** Use placeholder values like `"your_username"` and `"your_password"` in the variable declarations.

## Step 5: Compose the script

Structure the script exactly like this:

**When credentials ARE detected** (from Step 4 or pre-parameterized `${VAR}` from `fill_secret`):

```python
"""Workflow: <workflow-name>
Generated from Scout session on <date>.
Session: <session_id> | Actions: <count> | Duration: <if available>

Setup:
    cd workflows/<workflow-name>
    pip install -r requirements.txt
    cp .env.example .env   # fill in your credentials
    python <workflow-name>.py
"""
import os
import random
import time
from dotenv import load_dotenv
from botasaurus_driver import Driver

load_dotenv()

# --- Configuration (update .env or override these) ---
USERNAME = os.getenv("USERNAME", "your_username")
PASSWORD = os.getenv("PASSWORD", "your_password")
BASE_URL = "<first navigation URL>"
```

For pre-parameterized `${VAR}` variables from `fill_secret` (e.g., `BC_USERNAME`, `BC_PASSWORD`), use the actual env var names:
```python
BC_USERNAME = os.getenv("BC_USERNAME", "your_username")
BC_PASSWORD = os.getenv("BC_PASSWORD", "your_password")
```

**When NO credentials are detected:**

```python
"""Workflow: <workflow-name>
Generated from Scout session on <date>.
Session: <session_id> | Actions: <count> | Duration: <if available>

Setup:
    cd workflows/<workflow-name>
    pip install -r requirements.txt
    python <workflow-name>.py
"""
import random
import time
from botasaurus_driver import Driver

# --- Configuration ---
BASE_URL = "<first navigation URL>"
```

Note: When no credentials are detected, omit `os`, `dotenv`, `load_dotenv()`, and all credential variables. Do NOT include the `cp .env.example .env` line in the docstring. Always include `import random` in both variants — it's used by `human_type()` and randomized delays.

**Common script body (used by both variants):**

```python
def human_type(driver, selector, text):
    """Type text with randomized inter-keystroke delays to mimic human typing."""
    elem = driver.wait_for_element(selector, wait=10)
    elem.click()
    for char in text:
        elem.type(char)
        time.sleep(random.uniform(0.03, 0.12))


def run_workflow():
    """Replay the recorded browser workflow."""
    driver = Driver(headless=False)
    driver.enable_human_mode()
    try:
        # Step 1: Navigate to starting page
        driver.get(BASE_URL)

        # Step 2: <human-readable description of what this action does>
        driver.<method>(selector, value)

        # ... one step per action, numbered sequentially ...

    finally:
        driver.close()


if __name__ == "__main__":
    run_workflow()
```

Rules for the script:
- Every step gets a **comment** explaining what it does in human terms (e.g., "Click the Login button", "Enter username")
- Steps are **numbered sequentially** starting from 1
- The `try/finally` block ensures the browser is always closed
- Only include the `USERNAME`/`PASSWORD` variables if credentials were actually detected
- The script must be **self-contained** — runnable with `pip install -r requirements.txt && python <name>.py` from the workflow directory

**Anti-detection timing — MANDATORY:**

Never use fixed `time.sleep(N)` in generated scripts. All inter-step delays must be randomized:

| Scenario | Delay | Why |
|----------|-------|-----|
| After page navigation (`url_changed` is true) | `driver.short_random_sleep()` (2-4s) | Page loads vary; fixed waits after navigation are a strong bot signal |
| After login form submission | `driver.long_random_sleep()` (6-9s) | Login pages are the most heavily monitored for automation |
| Between same-page interactions (clicks, typing, selects) | `time.sleep(random.uniform(0.3, 0.8))` | Humans don't click at machine speed; small jitter breaks timing fingerprints |
| After form submission (non-login) | `driver.short_random_sleep()` (2-4s) | Server processing time varies; immediate follow-up is unnatural |

The `human_type()` helper already includes per-keystroke jitter (30-120ms) so no additional delay is needed after typing steps that are immediately followed by another type action on the same form.

## Step 5b: Generate workflow JSON

In addition to the Python script, generate a portable workflow JSON file using the `WorkflowConverter` from `src/scout/workflow.py`:

1. Build a `Workflow` model by calling `WorkflowConverter.from_history(history, name=workflow_name, description=description)`
   - `history` is the `SessionHistory` from Step 1
   - `workflow_name` is the slugified name from Step 6
   - `description` is a short summary derived from the key actions (e.g., "Log into ADP WFN and download report")
2. The converter automatically handles credential parameterization (same logic as Step 4) and step name generation
3. Serialize with `workflow.model_dump_json(exclude_none=True, indent=2)`

The JSON file is the portable, machine-parseable workflow definition. It can be consumed by any executor (Python, C#, etc.) without requiring Claude in the loop.

## Step 6: Determine the workflow name

- If the user provided a name as an argument, use it (slugified: lowercase, hyphens for spaces)
- If no name was provided, derive one from the workflow: e.g., "login-to-reports" based on the navigations and key actions
- Use the name for both the filename and the docstring

## Step 7: Write the workflow package

Write a self-contained directory package to `workflows/<name>/`. Create the directory if it doesn't exist.

### 7a: Write the Python script

Write to `workflows/<name>/<name>.py`.

### 7b: Write the workflow JSON

Write to `workflows/<name>/<name>.json`.

### 7c: Write requirements.txt

Write to `workflows/<name>/requirements.txt`:

**When credentials were detected:**
```
botasaurus-driver>=4.0.0
python-dotenv>=1.0.0
```

**When NO credentials were detected** (script doesn't import dotenv):
```
botasaurus-driver>=4.0.0
```

### 7d: Write .env.example (conditional)

**Only create this file if credential variables were detected in Step 4.**

Write to `workflows/<name>/.env.example`. Generate from the variables detected:

```
# Credentials for <workflow-name>
# Copy this file to .env and fill in your values:
#   cp .env.example .env

# Login username
USERNAME=
# Login password
PASSWORD=
```

For pre-parameterized vars (from `fill_secret`), use their original names:
```
# Username for <site>
BC_USERNAME=
# Password for <site>
BC_PASSWORD=
```

### 7e: Present quick-start instructions

Tell the user the directory path and show a quick-start block:

**When credentials exist:**
```
cd workflows/<name>
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
python <name>.py
```

**When NO credentials:**
```
cd workflows/<name>
pip install -r requirements.txt
python <name>.py
```

Also mention:
- That the JSON file is the portable workflow definition for use with any executor
- What they need to update (BASE_URL if targeting a different environment)
