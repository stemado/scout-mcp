"""Integration tests for actions.py — browser action execution, JS, screenshots, inspect.

Requires a real browser (botasaurus-driver), so skip in CI.
Run manually: uv run pytest tests/test_actions.py -v -s
"""

import pytest

from scout.actions import (
    execute_action,
    inspect_element,
    run_javascript,
    take_screenshot,
)
from scout.session import BrowserSession

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def session(base_url):
    """Launch a real browser session for action testing."""
    s = BrowserSession(headless=True)
    s.launch(base_url + "/actions.html")
    yield s
    s.close()


@pytest.fixture(autouse=True)
def reset_page(request, session, base_url):
    """Reset to actions.html before each test to prevent state leakage."""
    if "form_session" not in request.fixturenames:
        session.driver.get(base_url + "/actions.html")


# ---------------------------------------------------------------------------
# execute_action — click
# ---------------------------------------------------------------------------


def test_click_updates_dom(session):
    """Click a button and verify the DOM changed."""
    result, record = execute_action(session.driver, "click", "#click-btn", wait_after=0)
    assert result.success is True
    assert record.action == "click"

    # Verify the onclick handler fired
    js_result, _ = run_javascript(session.driver, "return document.getElementById('click-result').textContent")
    assert js_result.result == "clicked"


def test_click_missing_selector(session):
    """Click without a selector returns an error."""
    result, record = execute_action(session.driver, "click", selector=None, wait_after=0)
    assert result.success is False
    assert "selector required" in result.error.lower()


def test_click_nonexistent_element(session):
    """Click on a nonexistent element returns an error."""
    result, _ = execute_action(session.driver, "click", "#nope", wait_after=0)
    assert result.success is False
    assert result.error is not None


def test_click_dom_changing_has_no_warning(session):
    """Click that causes a real DOM change does not produce a warning."""
    result, _ = execute_action(session.driver, "click", "#click-btn", wait_after=0)
    assert result.success is True
    # The onclick handler modifies the DOM, so no "no effect" warning
    assert result.warning is None


# ---------------------------------------------------------------------------
# execute_action — type
# ---------------------------------------------------------------------------


def test_type_fills_input(session):
    """Type text into an input and verify the value."""
    result, _ = execute_action(session.driver, "type", "#text-input", "hello world", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(session.driver, "return document.getElementById('text-input').value")
    assert js_result.result == "hello world"


# ---------------------------------------------------------------------------
# execute_action — type (constrained HTML5 inputs)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def form_session(base_url):
    """Browser session pointed at the form test fixture."""
    s = BrowserSession(headless=True)
    s.launch(base_url + "/form_test.html")
    yield s
    s.close()


@pytest.fixture(autouse=False)
def reset_form_page(form_session, base_url):
    """Reset to form_test.html before each form test."""
    form_session.driver.get(base_url + "/form_test.html")


def test_type_date_input(form_session, reset_form_page):
    """Type action on input[type=date] sets value via JS injection."""
    result, _ = execute_action(form_session.driver, "type", "#date", "2026-03-15", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(form_session.driver, "return document.getElementById('date').value")
    assert js_result.result == "2026-03-15"


def test_type_time_input(form_session, reset_form_page):
    """Type action on input[type=time] sets value via JS injection."""
    result, _ = execute_action(form_session.driver, "type", "#time", "11:45", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(form_session.driver, "return document.getElementById('time').value")
    assert js_result.result == "11:45"


def test_type_datetime_local_input(form_session, reset_form_page):
    """Type action on input[type=datetime-local] sets value via JS injection."""
    result, _ = execute_action(
        form_session.driver, "type", "#datetime", "2026-03-15T11:45", wait_after=0
    )
    assert result.success is True

    js_result, _ = run_javascript(
        form_session.driver, "return document.getElementById('datetime').value"
    )
    assert js_result.result == "2026-03-15T11:45"


def test_type_month_input(form_session, reset_form_page):
    """Type action on input[type=month] sets value via JS injection."""
    result, _ = execute_action(form_session.driver, "type", "#month", "2026-03", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(form_session.driver, "return document.getElementById('month').value")
    assert js_result.result == "2026-03"


def test_type_week_input(form_session, reset_form_page):
    """Type action on input[type=week] sets value via JS injection."""
    result, _ = execute_action(form_session.driver, "type", "#week", "2026-W12", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(form_session.driver, "return document.getElementById('week').value")
    assert js_result.result == "2026-W12"


def test_type_text_still_uses_keystrokes(form_session, reset_form_page):
    """Type on a regular text input still uses keystroke simulation (no regression)."""
    result, _ = execute_action(form_session.driver, "type", "#name", "Scout", wait_after=0)
    assert result.success is True
    # action_performed should say "Typed into" (keystrokes), not "Set value on" (injection)
    assert "Typed into" in result.action_performed

    js_result, _ = run_javascript(form_session.driver, "return document.getElementById('name').value")
    assert js_result.result == "Scout"


def test_type_constrained_reports_injection(form_session, reset_form_page):
    """Constrained input type action reports it used value injection."""
    result, _ = execute_action(form_session.driver, "type", "#time", "14:30", wait_after=0)
    assert result.success is True
    assert "value injection" in result.action_performed.lower()


def test_type_constrained_dispatches_events(form_session, reset_form_page):
    """Constrained input injection dispatches input and change events."""
    execute_action(form_session.driver, "type", "#time", "09:00", wait_after=0)

    js_result, _ = run_javascript(form_session.driver, "return document.getElementById('events').textContent")
    assert "time:input" in js_result.result
    assert "time:change" in js_result.result


# ---------------------------------------------------------------------------
# execute_action — click (enhanced submit warning)
# ---------------------------------------------------------------------------


def test_click_submit_no_effect_mentions_requestsubmit(form_session, reset_form_page):
    """Click on submit button with no DOM effect gives submit-specific warning."""
    # Clone the form to strip all event listeners, then prevent default on submit
    run_javascript(
        form_session.driver,
        "var form = document.getElementById('test-form');"
        "var clone = form.cloneNode(true);"
        "form.parentNode.replaceChild(clone, form);"
        "clone.addEventListener('submit', function(e) { e.preventDefault(); });",
    )
    result, _ = execute_action(form_session.driver, "click", "#submit-btn", wait_after=300)
    # The click should succeed but the warning should mention requestSubmit
    assert result.warning is not None, "Expected a no-effect warning for submit click"
    assert "requestSubmit" in result.warning


def test_click_noop_button_no_submit_mention(form_session, reset_form_page):
    """Click on a non-submit button with no DOM effect gives generic warning, not submit-specific."""
    result, _ = execute_action(form_session.driver, "click", "#noop-btn", wait_after=300)
    # Warning should fire (no DOM change) but should NOT mention requestSubmit
    assert result.warning is not None, "Expected a no-effect warning for noop click"
    assert "requestSubmit" not in result.warning


# ---------------------------------------------------------------------------
# execute_action — select
# ---------------------------------------------------------------------------


def test_select_by_value(session):
    """Select a dropdown option by value string."""
    result, _ = execute_action(session.driver, "select", "#color-select", "green", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(session.driver, "return document.getElementById('color-select').value")
    assert js_result.result == "green"


def test_select_by_index(session):
    """Select a dropdown option by numeric index (triggers the isdigit path)."""
    result, _ = execute_action(session.driver, "select", "#color-select", "2", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(session.driver, "return document.getElementById('color-select').value")
    assert js_result.result == "blue"


# ---------------------------------------------------------------------------
# execute_action — navigate
# ---------------------------------------------------------------------------


def test_navigate_changes_url(session, base_url):
    """Navigate to a different page and verify URL changed."""
    result, _ = execute_action(session.driver, "navigate", value=base_url + "/navigate.html", wait_after=0)
    assert result.success is True
    assert result.url_changed is True
    assert "navigate.html" in result.current_url


# ---------------------------------------------------------------------------
# execute_action — scroll
# ---------------------------------------------------------------------------


def test_scroll_moves_viewport(session):
    """Scroll default amount and verify viewport position changed."""
    # Reset scroll position
    run_javascript(session.driver, "window.scrollTo(0, 0)")

    result, _ = execute_action(session.driver, "scroll", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(session.driver, "return window.scrollY")
    assert js_result.result > 0


# ---------------------------------------------------------------------------
# execute_action — wait
# ---------------------------------------------------------------------------


def test_wait_timed(session):
    """Timed wait completes successfully."""
    result, _ = execute_action(session.driver, "wait", value="100", wait_after=0)
    assert result.success is True
    assert result.elapsed_ms >= 100


def test_wait_for_element(session):
    """Wait for a dynamically injected element (appears after 1s)."""
    result, _ = execute_action(session.driver, "wait", selector="#delayed-element", value="5000", wait_after=0)
    assert result.success is True


# ---------------------------------------------------------------------------
# execute_action — press_key
# ---------------------------------------------------------------------------


def test_press_key_dispatches_event(session):
    """Press Enter key and verify the keydown event fired."""
    # Use JS to focus the input — botasaurus click doesn't trigger native focus
    run_javascript(session.driver, "document.getElementById('key-input').focus()")
    result, _ = execute_action(session.driver, "press_key", value="Enter", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(session.driver, "return document.getElementById('key-result').textContent")
    assert js_result.result == "Enter"


# ---------------------------------------------------------------------------
# execute_action — hover
# ---------------------------------------------------------------------------


def test_hover_triggers_event(session):
    """Hover over an element and verify the mouseover event fired."""
    result, _ = execute_action(session.driver, "hover", "#hover-target", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(
        session.driver,
        "return document.getElementById('hover-target').dataset.hovered",
    )
    assert js_result.result == "true"


# ---------------------------------------------------------------------------
# execute_action — clear
# ---------------------------------------------------------------------------


def test_clear_empties_input(session):
    """Type then clear an input field."""
    execute_action(session.driver, "type", "#text-input", "temporary", wait_after=0)
    result, _ = execute_action(session.driver, "clear", "#text-input", wait_after=0)
    assert result.success is True

    js_result, _ = run_javascript(session.driver, "return document.getElementById('text-input').value")
    assert js_result.result == ""


# ---------------------------------------------------------------------------
# execute_action — error / edge cases
# ---------------------------------------------------------------------------


def test_unknown_action(session):
    """Unknown action name returns an error."""
    result, _ = execute_action(session.driver, "destroy", wait_after=0)
    assert result.success is False
    assert "Unknown action" in result.error


def test_action_returns_record(session):
    """Verify ActionRecord fields are properly populated."""
    _, record = execute_action(session.driver, "click", "#click-btn", wait_after=0)
    assert record.action == "click"
    assert record.selector == "#click-btn"
    assert record.success is True
    assert record.url_before != ""
    assert record.url_after != ""
    assert record.timestamp != ""


def test_wait_after_adds_delay(session):
    """wait_after parameter adds measurable delay to elapsed time."""
    result_fast, _ = execute_action(session.driver, "click", "#click-btn", wait_after=0)
    result_slow, _ = execute_action(session.driver, "click", "#click-btn", wait_after=300)
    # The slow action should take at least 200ms more (allowing some tolerance)
    assert result_slow.elapsed_ms > result_fast.elapsed_ms + 200


# ---------------------------------------------------------------------------
# run_javascript
# ---------------------------------------------------------------------------


def test_js_returns_string(session):
    """JavaScript returning a string is classified correctly."""
    result, _ = run_javascript(session.driver, "return document.title")
    assert result.success is True
    assert result.result_type == "string"
    assert result.result == "Actions Test Page"


def test_js_returns_number(session):
    """JavaScript returning a number is classified correctly."""
    result, _ = run_javascript(session.driver, "return 42")
    assert result.success is True
    assert result.result_type == "number"
    assert result.result == 42


def test_js_returns_object(session):
    """JavaScript returning an object is classified correctly."""
    result, _ = run_javascript(session.driver, "return {a: 1, b: 'two'}")
    assert result.success is True
    assert result.result_type == "object"
    assert result.result["a"] == 1


def test_js_error(session):
    """JavaScript that throws returns an error."""
    result, _ = run_javascript(session.driver, "throw new Error('boom')")
    assert result.success is False
    assert result.error is not None


def test_js_record_preview(session):
    """Long scripts are truncated in the history record."""
    long_script = "return " + "'x' + " * 100 + "'x'"
    _, record = run_javascript(session.driver, long_script)
    assert len(record.script_preview) <= 200


# CDP-direct evaluation — expressions without 'return' (the bug fix)


def test_js_expression_returns_value(session):
    """JavaScript expressions without 'return' return their value (the bug fix)."""
    result, _ = run_javascript(session.driver, "document.title")
    assert result.success is True
    assert result.result_type == "string"
    assert result.result == "Actions Test Page"


def test_js_expression_arithmetic(session):
    """Arithmetic expressions return their computed value."""
    result, _ = run_javascript(session.driver, "2 + 2")
    assert result.success is True
    assert result.result_type == "number"
    assert result.result == 4


def test_js_expression_null(session):
    """null expression returns null type."""
    result, _ = run_javascript(session.driver, "null")
    assert result.success is True
    assert result.result_type == "null"
    assert result.result is None


def test_js_expression_undefined(session):
    """undefined expression returns undefined type."""
    result, _ = run_javascript(session.driver, "undefined")
    assert result.success is True
    assert result.result_type == "undefined"
    assert result.result is None


def test_js_expression_object(session):
    """Object literal expressions return correctly (must use parens)."""
    result, _ = run_javascript(session.driver, "({a: 1, b: 'two'})")
    assert result.success is True
    assert result.result_type == "object"
    assert result.result["a"] == 1


def test_js_expression_array(session):
    """Array expressions return correctly."""
    result, _ = run_javascript(session.driver, "[1, 2, 3]")
    assert result.success is True
    assert result.result_type == "array"
    assert result.result == [1, 2, 3]


def test_js_multistatement(session):
    """Multi-statement script returns last expression value."""
    result, _ = run_javascript(session.driver, "let x = 5; x * 2")
    assert result.success is True
    assert result.result == 10


def test_js_return_backward_compat(session):
    """Scripts with explicit 'return' still work."""
    result, _ = run_javascript(session.driver, "return document.title")
    assert result.success is True
    assert result.result == "Actions Test Page"


def test_js_await_promise(session):
    """Async expressions with Promises resolve correctly."""
    result, _ = run_javascript(
        session.driver,
        "await new Promise(resolve => setTimeout(() => resolve('done'), 50))",
    )
    assert result.success is True
    assert result.result == "done"


def test_js_empty_result_guard_warns_on_loop(session):
    """A for...of loop as the last statement triggers a warning when result is undefined."""
    # This is structurally identical to benchmark Run 2's failing script.
    # The for...of loop's completion value is undefined in CDP repl_mode.
    script = """
    const links = document.querySelectorAll('a');
    let result = '';
    for (const a of links) {
        const text = a.textContent.trim();
        if (text.length > 0) {
            result = text;
            break;
        }
    }
    """
    r, _ = run_javascript(session.driver, script)
    # The loop's completion value is undefined — result should be None
    # and warning should be present because the script clearly does computation
    if r.result is None:
        assert r.warning is not None
        assert "non-trivial computation" in r.warning
    else:
        # If CDP happens to return the value, no warning needed — still a pass
        assert r.warning is None


def test_js_empty_result_guard_no_warning_on_success(session):
    """A script that successfully returns a value should never have a warning."""
    result, _ = run_javascript(session.driver, "document.title")
    assert result.success is True
    assert result.result is not None
    assert result.warning is None


def test_js_empty_result_guard_no_warning_on_bare_expression(session):
    """A bare expression returning undefined should not warn if no computation patterns."""
    result, _ = run_javascript(session.driver, "undefined")
    assert result.result is None
    assert result.warning is None


# ---------------------------------------------------------------------------
# take_screenshot
# ---------------------------------------------------------------------------


def test_screenshot_png(session):
    """Default PNG screenshot succeeds with valid PNG bytes."""
    result, record, raw_bytes = take_screenshot(session.driver)
    assert result.success is True
    assert result.format == "png"
    assert result.byte_size > 0
    assert raw_bytes[:4] == b"\x89PNG"


def test_screenshot_jpeg(session):
    """JPEG screenshot succeeds with valid JPEG bytes."""
    result, _, raw_bytes = take_screenshot(session.driver, image_format="jpeg", quality=80)
    assert result.success is True
    assert result.format == "jpeg"
    assert raw_bytes[:2] == b"\xff\xd8"


def test_screenshot_invalid_format(session):
    """Invalid format returns an error without touching the browser."""
    result, _, raw_bytes = take_screenshot(session.driver, image_format="gif")
    assert result.success is False
    assert "Invalid format" in result.error
    assert raw_bytes is None


# ---------------------------------------------------------------------------
# inspect_element
# ---------------------------------------------------------------------------


def test_inspect_visible_button(session):
    """Inspect a visible button returns correct metadata."""
    inspection = inspect_element(session.driver, "#click-btn")
    assert inspection.found is True
    assert inspection.tag == "button"
    assert inspection.is_visible is True
    assert inspection.bounding_rect.get("width", 0) > 0


def test_inspect_hidden_element(session):
    """Inspect a display:none element reports it as not visible."""
    inspection = inspect_element(session.driver, "#hidden-el")
    assert inspection.found is True
    assert inspection.is_visible is False


def test_inspect_nonexistent(session):
    """Inspect a nonexistent element returns found=False."""
    inspection = inspect_element(session.driver, "#nope")
    assert inspection.found is False
