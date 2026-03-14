# Upload File Action Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `upload_file` action to `execute_action_tool` that sets files on `<input type="file">` elements via CDP `DOM.setFileInputFiles`.

**Architecture:** Leverages botasaurus-driver's existing `BrowserTab.upload_file(selector, path)` method, which is inherited by `Driver`, `IframeTab`, and `IframeElement`. Under the hood, it calls `wait_for_element` + `Element.upload_file()` + `cdp.dom.set_file_input_files()`. The new action follows the same pattern as `click`/`type`/`select` — resolve target, call `target.upload_file(selector, path)`. File path validation is added to `validation.py` for defense-in-depth (fail fast with a clean error before the browser round-trip).

**Tech Stack:** Python, botasaurus-driver CDP bindings, Pydantic, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/scout/validation.py` | Modify | Add `validate_file_path()` — existence + regular-file check |
| `src/scout/actions.py:78-199` | Modify | Add `case "upload_file"` branch in `match` statement |
| `src/scout/server.py:320` | Modify | Add `"upload_file"` to the `Literal` type constraint |
| `src/scout/workflow.py:43-47` | Modify | Add `"upload_file"` to `WorkflowStep.action` Literal |
| `tests/test_validation.py` | Modify | Add tests for `validate_file_path()` |
| `tests/test_upload_file.py` | Create | Unit tests for `upload_file` action (mocked driver) |
| `tests/fixtures/actions.html` | Modify | Add `<input type="file">` element for integration tests |
| `tests/test_actions.py` | Modify | Add integration test for `upload_file` |

---

## Chunk 1: File Path Validation

### Task 1: Add `validate_file_path()` to validation.py

**Files:**
- Modify: `src/scout/validation.py` (append after line 128)
- Test: `tests/test_validation.py` (append new test class)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_validation.py`:

```python
from scout.validation import validate_file_path


class TestValidateFilePath:
    def test_accepts_existing_file(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_text("fake pdf")
        validate_file_path(str(f))  # should not raise

    def test_rejects_nonexistent_file(self):
        with pytest.raises(ValueError, match="File not found"):
            validate_file_path("/nonexistent/path/file.txt")

    def test_rejects_directory(self, tmp_path):
        with pytest.raises(ValueError, match="not a regular file"):
            validate_file_path(str(tmp_path))

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="File path required"):
            validate_file_path("")

    def test_rejects_none_path(self):
        with pytest.raises(ValueError, match="File path required"):
            validate_file_path(None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_validation.py::TestValidateFilePath -v`
Expected: FAIL with `ImportError` (validate_file_path doesn't exist yet)

- [ ] **Step 3: Implement validate_file_path**

Add to `src/scout/validation.py` at the end of the file:

```python
# --- File path validation ---


def validate_file_path(path: str | None) -> None:
    """Validate that a file path points to an existing regular file.

    Raises ValueError if the path is empty, doesn't exist, or is not a regular file.
    """
    if not path:
        raise ValueError("File path required for upload_file action")

    from pathlib import Path
    p = Path(path)
    if not p.exists():
        raise ValueError(f"File not found: {path}")
    if not p.is_file():
        raise ValueError(f"Path is not a regular file: {path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_validation.py::TestValidateFilePath -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/scout/validation.py tests/test_validation.py
git commit -m "feat: add validate_file_path for upload_file action"
```

---

## Chunk 2: Core Action Implementation

### Task 2: Add upload_file action to actions.py

**Files:**
- Create: `tests/test_upload_file.py`
- Modify: `src/scout/actions.py:193-199` (insert new case before the default `case _`)

- [ ] **Step 1: Write the failing unit tests**

Create `tests/test_upload_file.py`:

```python
"""Unit tests for upload_file action (no browser required)."""

from unittest.mock import MagicMock

from scout.actions import execute_action


class TestUploadFileAction:
    """Tests for the upload_file action branch."""

    def test_upload_file_calls_target_upload(self, tmp_path):
        """upload_file calls target.upload_file(selector, resolved_path)."""
        test_file = tmp_path / "report.pdf"
        test_file.write_text("fake pdf content")

        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value=str(test_file), wait_after=0,
        )

        assert result.success is True
        assert "report.pdf" in result.action_performed
        assert record.action == "upload_file"
        driver.upload_file.assert_called_once_with(
            "input[type=file]", str(test_file.resolve()),
        )

    def test_upload_file_requires_selector(self):
        """upload_file without a selector returns error."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector=None,
            value="/some/file.pdf", wait_after=0,
        )

        assert result.success is False
        assert "selector required" in result.error.lower()

    def test_upload_file_requires_value(self):
        """upload_file without a value (file path) returns error."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value=None, wait_after=0,
        )

        assert result.success is False
        assert "file path required" in result.error.lower()

    def test_upload_file_rejects_nonexistent_file(self):
        """upload_file with nonexistent file returns error."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value="/nonexistent/file.pdf", wait_after=0,
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_upload_file_rejects_directory(self, tmp_path):
        """upload_file with a directory path returns error."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value=str(tmp_path), wait_after=0,
        )

        assert result.success is False
        assert "not a regular file" in result.error.lower()

    def test_upload_file_does_not_call_driver_before_validation(self):
        """upload_file fails fast on bad path without hitting the browser."""
        driver = MagicMock()
        driver.current_url = "http://example.com"

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value="/nonexistent/file.pdf", wait_after=0,
        )

        assert result.success is False
        driver.upload_file.assert_not_called()

    def test_upload_file_handles_driver_error(self, tmp_path):
        """upload_file returns error when target.upload_file raises."""
        test_file = tmp_path / "report.pdf"
        test_file.write_text("content")

        driver = MagicMock()
        driver.current_url = "http://example.com"
        driver.upload_file.side_effect = Exception("Element not found: input[type=file]")

        result, record = execute_action(
            driver, "upload_file", selector="input[type=file]",
            value=str(test_file), wait_after=0,
        )

        assert result.success is False
        assert "Element not found" in result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_upload_file.py -v`
Expected: FAIL — `execute_action` raises `ValueError("Unknown action: upload_file")`

- [ ] **Step 3: Implement the upload_file case in actions.py**

In `src/scout/actions.py`, add the import at the top (after the existing `from .validation import validate_url` on line 23):

```python
from .validation import validate_file_path, validate_url
```

Then update the docstring on line 53 to include `upload_file`:

Change:
```python
        action: One of: click, type, select, navigate, scroll, wait, press_key, hover, clear.
```
To:
```python
        action: One of: click, type, select, navigate, scroll, wait, press_key, hover, clear, upload_file.
```

Then insert a new case **before** the `case _:` default (between lines 196 and 198):

```python
            case "upload_file":
                _require(selector, "selector required for upload_file")
                _require(value, "file path required for upload_file")
                validate_file_path(value)
                from pathlib import Path
                resolved = str(Path(value).resolve())
                target.upload_file(selector, resolved)
                action_desc = f"Uploaded file: {Path(value).name}"
```

> **Note:** `target.upload_file(selector, path)` is a `BrowserTab` method inherited by
> `Driver`, `IframeTab`, and `IframeElement`. It calls `wait_for_element(selector)` +
> `Element.upload_file(path)`, which internally validates the element is `<input type="file">`
> and calls `cdp.dom.set_file_input_files()`. Our `validate_file_path()` provides
> defense-in-depth — failing fast with a clean error before the browser round-trip.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_upload_file.py -v`
Expected: All 7 tests PASS (including the new `test_upload_file_does_not_call_driver_before_validation` which verifies fail-fast behavior)

- [ ] **Step 5: Run full unit test suite to check for regressions**

Run: `uv run pytest tests/ -m "not integration" -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/scout/actions.py tests/test_upload_file.py
git commit -m "feat: add upload_file action to execute_action"
```

---

### Task 3: Update server.py Literal type

**Files:**
- Modify: `src/scout/server.py:320`

- [ ] **Step 1: Update the Literal type on line 320**

Change:
```python
    action: Literal["click", "type", "select", "navigate", "scroll", "wait", "press_key", "hover", "clear"],
```
To:
```python
    action: Literal["click", "type", "select", "navigate", "scroll", "wait", "press_key", "hover", "clear", "upload_file"],
```

- [ ] **Step 2: Update the docstring on line 336**

Change:
```python
        value: Text to type, option to select, URL to navigate to, key to press, or wait duration.
```
To:
```python
        value: Text to type, option to select, URL to navigate to, key to press, wait duration, or file path to upload.
```

- [ ] **Step 3: Run tests to verify nothing is broken**

Run: `uv run pytest tests/ -m "not integration" -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/scout/server.py
git commit -m "feat: expose upload_file action in MCP tool definition"
```

---

### Task 4: Update workflow.py Literal type

**Files:**
- Modify: `src/scout/workflow.py:43-47`

- [ ] **Step 1: Add upload_file to WorkflowStep.action Literal**

Change:
```python
    action: Literal[
        "navigate", "click", "type", "select", "scroll", "wait",
        "wait_for_download", "wait_for_response",
        "press_key", "hover", "clear",
    ]
```
To:
```python
    action: Literal[
        "navigate", "click", "type", "select", "scroll", "wait",
        "wait_for_download", "wait_for_response",
        "press_key", "hover", "clear", "upload_file",
    ]
```

- [ ] **Step 2: Add explicit case to `_generate_step_name` (around line 217)**

Insert before the `case _:` default in the `_generate_step_name` function:

```python
            case "upload_file":
                return f"Upload file to '{action.selector}'"
```

- [ ] **Step 3: Run tests to verify nothing is broken**

Run: `uv run pytest tests/ -m "not integration" -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/scout/workflow.py
git commit -m "feat: add upload_file to WorkflowStep action types"
```

---

## Chunk 3: Integration Test

### Task 5: Add file input to test fixture and integration test

**Files:**
- Modify: `tests/fixtures/actions.html` (add file input element)
- Modify: `tests/test_actions.py` (add integration test)

- [ ] **Step 1: Add file input HTML to actions.html**

Add before the closing `</body>` tag (before the `<script>` block at line 59):

```html
  <!-- File upload testing -->
  <input id="file-input" type="file" />
  <input id="multi-file-input" type="file" multiple />
  <span id="file-result"></span>
  <script>
    document.getElementById('file-input').addEventListener('change', function(e) {
      document.getElementById('file-result').textContent = e.target.files[0]?.name || '';
    });
  </script>
```

- [ ] **Step 2: Add integration test to test_actions.py**

Add at the end of `tests/test_actions.py`:

```python
# ---------------------------------------------------------------------------
# execute_action — upload_file
# ---------------------------------------------------------------------------


def test_upload_file_sets_file(session, tmp_path):
    """Upload a file to an <input type='file'> and verify via JS."""
    # Create a temporary test file
    test_file = tmp_path / "test-upload.txt"
    test_file.write_text("test file content")

    result, record = execute_action(
        session.driver, "upload_file",
        selector="#file-input",
        value=str(test_file),
        wait_after=100,
    )

    assert result.success is True
    assert record.action == "upload_file"
    assert "test-upload.txt" in result.action_performed

    # Verify the file was actually set on the input element
    js_result, _ = run_javascript(
        session.driver,
        "return document.getElementById('file-input').files[0]?.name"
    )
    assert js_result.result == "test-upload.txt"


def test_upload_file_nonexistent_file(session):
    """Upload a nonexistent file returns error."""
    result, record = execute_action(
        session.driver, "upload_file",
        selector="#file-input",
        value="/nonexistent/file.pdf",
        wait_after=0,
    )

    assert result.success is False
    assert "not found" in result.error.lower()
```

- [ ] **Step 3: Run integration tests (requires Chrome)**

Run: `uv run pytest tests/test_actions.py::test_upload_file_sets_file tests/test_actions.py::test_upload_file_nonexistent_file -v`
Expected: Both PASS (file input receives the file, change event fires)

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/actions.html tests/test_actions.py
git commit -m "test: add integration tests for upload_file action"
```

---

## Chunk 4: OTO/Otto Parity (Follow-up)

> This chunk is for tracking only. OTO and Otto share the same codebase pattern (`execute_action_tool` with `Literal` constraint + `actions.py` match/case). The identical changes should be applied to their repositories:
>
> 1. Add `validate_file_path` to their `validation.py` (or import from shared code)
> 2. Add `case "upload_file"` to their `actions.py`
> 3. Add `"upload_file"` to their `server.py` Literal
> 4. Add `"upload_file"` to their `workflow.py` Literal (if applicable)
>
> This is deferred to a separate PR per repo.

---

## Summary

| Task | Files Changed | Tests Added |
|------|--------------|-------------|
| 1. File path validation | `validation.py` | 5 unit tests |
| 2. Core action logic | `actions.py`, `test_upload_file.py` | 7 unit tests |
| 3. MCP tool exposure | `server.py` | — (covered by task 2) |
| 4. Workflow type | `workflow.py` | — |
| 5. Integration test | `actions.html`, `test_actions.py` | 2 integration tests |

**Total:** ~25 lines of production code, 14 tests.
