# Screenshot Action Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a native `screenshot` action to the JSON workflow schema, replacing the `run_js` placeholder approach.

**Architecture:** Add `"screenshot"` as the 12th action type in `WorkflowStep.action`, with two optional action-specific fields (`screenshot_format`, `full_page`). The `value` field holds an optional label/filename stem. Update the converter, step name generator, export-workflow command mapping, and tests.

**Tech Stack:** Python, Pydantic v2, pytest

---

### Task 1: Add `screenshot` to WorkflowStep schema

**Files:**
- Modify: `src/scout/workflow.py:43-47` (action Literal)
- Modify: `src/scout/workflow.py:56-61` (action-specific fields)

**Step 1: Write the failing test**

Add to `tests/test_workflow.py` after line 101 (after `test_workflow_step_defaults`):

```python
def test_workflow_step_screenshot():
    step = WorkflowStep(
        order=3,
        name="Capture dashboard state",
        action="screenshot",
        value="after-login",
        screenshot_format="png",
        full_page=False,
    )
    assert step.action == "screenshot"
    assert step.value == "after-login"
    assert step.screenshot_format == "png"
    assert step.full_page is False


def test_workflow_step_screenshot_defaults():
    step = WorkflowStep(order=1, name="Take screenshot", action="screenshot")
    assert step.screenshot_format is None
    assert step.full_page is None
    assert step.value is None
    assert step.selector is None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py::test_workflow_step_screenshot tests/test_workflow.py::test_workflow_step_screenshot_defaults -v`
Expected: FAIL — `"screenshot"` is not a valid Literal value, and `screenshot_format`/`full_page` are unknown fields.

**Step 3: Add screenshot to the action Literal and add fields**

In `src/scout/workflow.py`, update the `WorkflowStep` class:

1. Add `"screenshot"` to the `action` Literal (line 43-47):
```python
    action: Literal[
        "navigate", "click", "type", "select", "scroll", "wait",
        "wait_for_download", "wait_for_response",
        "press_key", "hover", "clear", "screenshot",
    ]
```

2. Add action-specific fields after the existing ones (after line 61):
```python
    screenshot_format: Literal["png", "jpeg"] | None = None  # screenshot
    full_page: bool | None = None                             # screenshot
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::test_workflow_step_screenshot tests/test_workflow.py::test_workflow_step_screenshot_defaults -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scout/workflow.py tests/test_workflow.py
git commit -m "feat: add screenshot action type to workflow schema"
```

---

### Task 2: Add screenshot case to step name generator

**Files:**
- Modify: `src/scout/workflow.py:187-219` (`_generate_step_name`)

**Step 1: Write the failing test**

Add to `tests/test_workflow.py` after the converter step name test:

```python
def test_step_name_generator_screenshot():
    from scout.workflow import _generate_step_name

    record = ActionRecord(action="screenshot", value="dashboard", success=True, timestamp="T1")
    name = _generate_step_name(record)
    assert "screenshot" in name.lower() or "capture" in name.lower()
    assert "dashboard" in name.lower()


def test_step_name_generator_screenshot_no_label():
    from scout.workflow import _generate_step_name

    record = ActionRecord(action="screenshot", success=True, timestamp="T1")
    name = _generate_step_name(record)
    assert "screenshot" in name.lower() or "capture" in name.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py::test_step_name_generator_screenshot tests/test_workflow.py::test_step_name_generator_screenshot_no_label -v`
Expected: FAIL — falls through to the default `case _:` branch, producing "Screenshot" (which might accidentally pass). Verify the label isn't included.

**Step 3: Add the screenshot case**

In `src/scout/workflow.py`, add a case before the `case _:` in `_generate_step_name`:

```python
        case "screenshot":
            label = action.value or ""
            return f"Capture screenshot '{label}'" if label else "Capture screenshot"
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::test_step_name_generator_screenshot tests/test_workflow.py::test_step_name_generator_screenshot_no_label -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scout/workflow.py tests/test_workflow.py
git commit -m "feat: add screenshot case to step name generator"
```

---

### Task 3: Add screenshot to the all-actions validation test

**Files:**
- Modify: `tests/test_workflow.py:265-282` (`test_workflow_json_schema_all_action_types_valid`)

**Step 1: Update the test**

Add the screenshot config to the `action_configs` list in `test_workflow_json_schema_all_action_types_valid`:

```python
        {"action": "screenshot", "value": "after-login", "screenshot_format": "png"},
```

This goes after the `"clear"` entry. The test already iterates all configs and asserts they instantiate correctly.

**Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::test_workflow_json_schema_all_action_types_valid -v`
Expected: PASS (schema already updated in Task 1)

**Step 3: Commit**

```bash
git add tests/test_workflow.py
git commit -m "test: add screenshot to all-actions validation test"
```

---

### Task 4: Add screenshot to the full ADP workflow test

**Files:**
- Modify: `tests/test_workflow.py:285-327` (`test_full_adp_workflow_from_design_doc`)

**Step 1: Add a screenshot step to the workflow**

Insert a screenshot step after the login wait (step 6) and before the navigation to Custom Reports. This shifts subsequent step orders by 1.

Replace the steps list in `test_full_adp_workflow_from_design_doc` — add after step 6:

```python
            WorkflowStep(order=7, name="Capture dashboard screenshot", action="screenshot",
                         value="dashboard-loaded", screenshot_format="png", full_page=False),
```

Renumber steps 7-9 to 8-10. Update the assertions at the bottom:

```python
    assert len(restored.steps) == 10
    assert restored.steps[6].action == "screenshot"
    assert restored.steps[6].value == "dashboard-loaded"
    assert restored.steps[8].frame_context == "iframe#adprIframe"
    assert restored.steps[9].action == "wait_for_download"
```

**Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::test_full_adp_workflow_from_design_doc -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_workflow.py
git commit -m "test: add screenshot step to full ADP workflow test"
```

---

### Task 5: Handle screenshot in WorkflowConverter

**Files:**
- Modify: `src/scout/workflow.py:153-176` (converter second pass)

The converter's second pass builds `WorkflowStep` objects from `ActionRecord` entries. If an `ActionRecord` has `action="screenshot"`, the current code would fail Pydantic validation because `screenshot_format` and `full_page` aren't on `ActionRecord` — they'd just be `None` (which is fine, those fields are optional).

Actually, the converter already works correctly because:
- `action.action` = `"screenshot"` is now in the Literal
- `selector`, `value`, `frame_context` are passed through
- Action-specific fields default to `None`

The only thing to verify is that it works end-to-end.

**Step 1: Write the test**

Add to `tests/test_workflow.py`:

```python
def test_converter_screenshot_action():
    history = _make_history([
        ActionRecord(action="navigate", value="https://example.com", success=True, timestamp="T1"),
        ActionRecord(action="screenshot", value="homepage", success=True, timestamp="T2"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert len(workflow.steps) == 2
    assert workflow.steps[1].action == "screenshot"
    assert workflow.steps[1].value == "homepage"
    assert workflow.steps[1].name == "Capture screenshot 'homepage'"
    assert workflow.steps[1].order == 2
```

**Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::test_converter_screenshot_action -v`
Expected: PASS (converter + schema already handle this)

**Step 3: Write test for screenshot without label**

```python
def test_converter_screenshot_action_no_label():
    history = _make_history([
        ActionRecord(action="screenshot", success=True, timestamp="T1"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.steps[0].action == "screenshot"
    assert workflow.steps[0].value is None
    assert workflow.steps[0].name == "Capture screenshot"
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::test_converter_screenshot_action_no_label -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_workflow.py
git commit -m "test: add converter tests for screenshot action"
```

---

### Task 6: Update export-workflow command with screenshot mapping

**Files:**
- Modify: `commands/export-workflow.md:23-38` (action mapping table)

**Step 1: Add screenshot row to the mapping table**

In `commands/export-workflow.md`, add this row to the action-to-code mapping table (after the `clear` row):

```markdown
| `screenshot` | `driver.save_screenshot(f"screenshots/step_{N}_{value or 'capture'}.png")` |
```

**Step 2: Add a note about the screenshots directory**

After the mapping table, add a brief note:

```markdown
For `screenshot` actions, the generated script creates a `screenshots/` subdirectory at the start of the workflow. The `value` field provides the filename label (e.g., `step_3_after-login.png`). If `full_page` is set, use `driver.run_js("return document.body.scrollHeight")` to capture the full scrollable area via CDP.
```

**Step 3: Commit**

```bash
git add commands/export-workflow.md
git commit -m "docs: add screenshot action mapping to export-workflow command"
```

---

### Task 7: Run full test suite and verify

**Step 1: Run all workflow tests**

Run: `python -m pytest tests/test_workflow.py -v`
Expected: ALL PASS

**Step 2: Run full test suite to check for regressions**

Run: `python -m pytest --tb=short`
Expected: ALL PASS — no regressions

**Step 3: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix: address any test regressions from screenshot action"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `src/scout/workflow.py:43-47` | Add `"screenshot"` to `WorkflowStep.action` Literal |
| `src/scout/workflow.py:56-61` | Add `screenshot_format` and `full_page` optional fields |
| `src/scout/workflow.py:187-219` | Add `"screenshot"` case to `_generate_step_name` |
| `tests/test_workflow.py` | 6 new tests: schema, defaults, name gen (x2), converter (x2) |
| `tests/test_workflow.py:265-282` | Add screenshot to all-actions validation test |
| `tests/test_workflow.py:285-327` | Add screenshot step to full ADP workflow test |
| `commands/export-workflow.md:23-38` | Add screenshot row to action mapping table |

## What This Does NOT Change

- **Engine executor** — the remote scout-engine server handles its own step execution. It already captures screenshots per-step via StepResult. This schema change lets workflows *request* explicit screenshots at specific points.
- **Session history model** — `ScreenshotRecord` and `SessionHistory.screenshots` are unchanged. Interactive screenshots during scouting remain a separate tracking concern.
- **MCP tools** — `take_screenshot_tool` is unchanged. The screenshot action is for *workflow replay*, not interactive sessions.
