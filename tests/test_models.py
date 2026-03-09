"""Tests for scout Pydantic models."""

from scout.models import (
    ActionResult,
    ElementInspection,
    ElementSummary,
    FindElementsResult,
    InteractiveElement,
    JavaScriptRecord,
    JavaScriptResult,
    ScreenshotRecord,
    ScreenshotResult,
    SessionHistory,
)


def test_element_summary_creation():
    summary = ElementSummary(
        total=100,
        visible=80,
        by_type={"button": 10, "input": 5, "a": 65},
        by_frame={"main": 90, "iframe#content": 10},
    )
    assert summary.total == 100
    assert summary.visible == 80
    assert summary.by_type["button"] == 10
    assert summary.by_frame["main"] == 90


def test_element_summary_defaults():
    summary = ElementSummary(total=0, visible=0)
    assert summary.by_type == {}
    assert summary.by_frame == {}


def test_find_elements_result():
    result = FindElementsResult(
        matched=2,
        total_on_page=50,
        elements=[
            InteractiveElement(
                tag="button",
                type="submit",
                selector="#login",
                text="Log In",
            ),
        ],
    )
    assert result.matched == 2
    assert len(result.elements) == 1
    assert result.elements[0].selector == "#login"


def test_find_elements_result_defaults():
    result = FindElementsResult(matched=0, total_on_page=0)
    assert result.elements == []


# --- ActionResult with warning field ---


def test_action_result_warning_none_by_default():
    result = ActionResult(success=True, action_performed="Clicked '#btn'")
    assert result.warning is None
    dumped = result.model_dump(exclude_none=True)
    assert "warning" not in dumped


def test_action_result_warning_set():
    result = ActionResult(
        success=True,
        action_performed="Clicked '#btn'",
        warning="Click may not have had an effect",
    )
    assert result.warning == "Click may not have had an effect"
    dumped = result.model_dump(exclude_none=True)
    assert "warning" in dumped


# --- JavaScriptResult ---


def test_javascript_result_success():
    result = JavaScriptResult(
        success=True,
        result={"title": "My Page"},
        result_type="object",
        elapsed_ms=15,
    )
    assert result.success is True
    assert result.result == {"title": "My Page"}
    assert result.result_type == "object"
    assert result.error is None


def test_javascript_result_error():
    result = JavaScriptResult(
        success=False,
        error="ReferenceError: foo is not defined",
        elapsed_ms=5,
    )
    assert result.success is False
    assert result.result is None
    assert result.result_type == "undefined"


def test_javascript_result_undefined():
    result = JavaScriptResult(success=True, result_type="undefined")
    assert result.result is None


def test_javascript_result_primitive_types():
    for val, expected_type in [
        ("hello", "string"),
        (42, "number"),
        (3.14, "number"),
        (True, "boolean"),
        ([1, 2, 3], "array"),
    ]:
        result = JavaScriptResult(success=True, result=val, result_type=expected_type)
        assert result.result == val


def test_javascript_result_warning_none_by_default():
    result = JavaScriptResult(success=True, result="hello", result_type="string")
    assert result.warning is None
    dumped = result.model_dump(exclude_none=True)
    assert "warning" not in dumped


def test_javascript_result_warning_present():
    result = JavaScriptResult(
        success=True,
        result=None,
        result_type="undefined",
        warning="Warning: result is undefined but script appears to perform non-trivial computation.",
    )
    assert result.warning is not None
    assert "non-trivial" in result.warning
    dumped = result.model_dump()
    assert dumped["warning"] == result.warning


# --- JavaScriptRecord ---


def test_javascript_record():
    record = JavaScriptRecord(
        script_preview="return document.title",
        frame_context=None,
        success=True,
        result_preview='"My Page"',
        timestamp="2026-02-19T10:00:00Z",
    )
    assert record.script_preview == "return document.title"
    assert record.frame_context is None
    assert record.success is True


def test_javascript_record_defaults():
    record = JavaScriptRecord()
    assert record.script_preview == ""
    assert record.success is True
    assert record.result_preview == ""
    assert record.timestamp == ""


# --- ScreenshotResult ---


def test_screenshot_result_success():
    result = ScreenshotResult(
        success=True,
        format="png",
        byte_size=123456,
        clipped=False,
    )
    assert result.success is True
    assert result.byte_size == 123456
    assert result.error is None


def test_screenshot_result_clipped():
    result = ScreenshotResult(
        success=True,
        format="jpeg",
        byte_size=45000,
        clipped=True,
    )
    assert result.clipped is True
    assert result.format == "jpeg"


def test_screenshot_result_error():
    result = ScreenshotResult(
        success=False,
        error="CDP command failed",
    )
    assert result.success is False
    assert result.byte_size == 0


def test_screenshot_result_file_path():
    result = ScreenshotResult(
        success=True, format="png", byte_size=1024, file_path="/tmp/screenshot_120000.png"
    )
    assert result.file_path == "/tmp/screenshot_120000.png"


def test_screenshot_result_file_path_default_none():
    result = ScreenshotResult(success=True, format="png", byte_size=1024)
    assert result.file_path is None


# --- ScreenshotRecord ---


def test_screenshot_record():
    record = ScreenshotRecord(
        format="png",
        clipped=True,
        full_page=False,
        timestamp="2026-02-19T10:00:00Z",
    )
    assert record.format == "png"
    assert record.clipped is True


def test_screenshot_record_defaults():
    record = ScreenshotRecord()
    assert record.format == "png"
    assert record.clipped is False
    assert record.full_page is False


# --- ElementInspection ---


def test_element_inspection_found():
    inspection = ElementInspection(
        found=True,
        selector="#myButton",
        tag="button",
        bounding_rect={"x": 100, "y": 200, "width": 80, "height": 30},
        computed_visibility={"display": "block", "visibility": "visible", "opacity": "1"},
        is_visible=True,
        is_obscured=False,
        parent_chain=["div#container", "form.login-form"],
        attributes={"id": "myButton", "class": "btn primary"},
        aria={"aria-label": "Submit form", "role": "button"},
        children_summary={"span": 1},
    )
    assert inspection.found is True
    assert inspection.tag == "button"
    assert inspection.is_visible is True
    assert inspection.is_obscured is False
    assert len(inspection.parent_chain) == 2


def test_element_inspection_not_found():
    inspection = ElementInspection(
        found=False,
        selector="#nonexistent",
    )
    assert inspection.found is False
    assert inspection.tag == ""
    assert inspection.bounding_rect == {}


def test_element_inspection_obscured():
    inspection = ElementInspection(
        found=True,
        selector="#hiddenBtn",
        tag="button",
        is_visible=True,
        is_obscured=True,
        obscured_by="div.modal-overlay",
    )
    assert inspection.is_obscured is True
    assert inspection.obscured_by == "div.modal-overlay"


def test_element_inspection_shadow_dom():
    inspection = ElementInspection(
        found=True,
        selector="button.inner",
        tag="button",
        in_shadow_dom=True,
        shadow_host="my-component#widget",
    )
    assert inspection.in_shadow_dom is True
    assert inspection.shadow_host == "my-component#widget"


def test_element_inspection_input_state():
    inspection = ElementInspection(
        found=True,
        selector="input#email",
        tag="input",
        input_state={"value": "user@example.com", "disabled": False, "readOnly": False},
    )
    assert inspection.input_state["value"] == "user@example.com"
    assert inspection.input_state["disabled"] is False


def test_element_inspection_error():
    inspection = ElementInspection(
        found=False,
        selector="[invalid",
        error="Invalid selector: SyntaxError",
    )
    assert inspection.found is False
    assert inspection.error is not None


def test_element_inspection_serialization():
    """Verify model_dump(exclude_none=True) strips null fields cleanly."""
    inspection = ElementInspection(
        found=True,
        selector="#btn",
        tag="button",
        is_visible=True,
    )
    dumped = inspection.model_dump(exclude_none=True)
    assert "obscured_by" not in dumped
    assert "shadow_host" not in dumped
    assert "error" not in dumped
    assert dumped["found"] is True


# --- SessionHistory with new fields ---


def test_session_history_includes_new_fields():
    history = SessionHistory(
        session_id="abc123",
        started_at="2026-02-19T10:00:00Z",
        javascript_calls=[
            JavaScriptRecord(
                script_preview="return document.title",
                success=True,
                result_preview='"Test"',
                timestamp="2026-02-19T10:01:00Z",
            ),
        ],
        screenshots=[
            ScreenshotRecord(
                format="png",
                timestamp="2026-02-19T10:02:00Z",
            ),
        ],
    )
    assert len(history.javascript_calls) == 1
    assert len(history.screenshots) == 1
    assert history.javascript_calls[0].script_preview == "return document.title"
    assert history.screenshots[0].format == "png"


def test_session_history_defaults():
    history = SessionHistory(session_id="x", started_at="now")
    assert history.javascript_calls == []
    assert history.screenshots == []
    assert history.actions == []
