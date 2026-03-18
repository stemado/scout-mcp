"""Tests for workflow JSON schema models."""

import json

from scout.models import ActionRecord, SessionHistory
from scout.workflow import (
    Workflow,
    WorkflowConverter,
    WorkflowSettings,
    WorkflowSource,
    WorkflowStep,
    WorkflowVariable,
)


def test_workflow_variable_credential():
    var = WorkflowVariable(type="credential", default="your_password", description="Login password")
    assert var.type == "credential"
    assert var.default == "your_password"


def test_workflow_variable_defaults():
    var = WorkflowVariable()
    assert var.type == "string"
    assert var.default == ""
    assert var.description == ""


def test_workflow_settings_defaults():
    settings = WorkflowSettings()
    assert settings.headless is False
    assert settings.default_timeout_ms == 30000
    assert settings.step_delay_ms == 500
    assert settings.on_error == "stop"


def test_workflow_step_navigate():
    step = WorkflowStep(order=1, name="Go to login", action="navigate", value="https://example.com")
    assert step.order == 1
    assert step.action == "navigate"
    assert step.value == "https://example.com"
    assert step.selector is None
    assert step.frame_context is None


def test_workflow_step_click_with_iframe():
    step = WorkflowStep(
        order=5,
        name="Click export button",
        action="click",
        selector="#exportBtn",
        frame_context="iframe#adprIframe",
    )
    assert step.frame_context == "iframe#adprIframe"


def test_workflow_step_type_with_variable_ref():
    step = WorkflowStep(
        order=2,
        name="Enter username",
        action="type",
        selector="#username",
        value="${USERNAME}",
        clear_first=True,
    )
    assert step.value == "${USERNAME}"
    assert step.clear_first is True


def test_workflow_step_wait_for_download():
    step = WorkflowStep(
        order=9,
        name="Wait for CSV download",
        action="wait_for_download",
        timeout_ms=60000,
        filename_pattern="*.csv",
    )
    assert step.action == "wait_for_download"
    assert step.filename_pattern == "*.csv"


def test_workflow_step_wait_for_response():
    step = WorkflowStep(
        order=7,
        name="Wait for report API response",
        action="wait_for_response",
        url_pattern=r"/api/reports/\d+",
        timeout_ms=15000,
    )
    assert step.action == "wait_for_response"
    assert step.url_pattern == r"/api/reports/\d+"


def test_workflow_step_defaults():
    step = WorkflowStep(order=1, name="test", action="click", selector="#btn")
    assert step.on_error is None
    assert step.timeout_ms is None
    assert step.clear_first is None
    assert step.filename_pattern is None
    assert step.url_pattern is None
    assert step.method is None
    assert step.download_dir is None


def test_full_workflow():
    workflow = Workflow(
        name="test-workflow",
        description="A test workflow",
        variables={
            "USERNAME": WorkflowVariable(type="credential", default="your_user"),
        },
        steps=[
            WorkflowStep(order=1, name="Navigate", action="navigate", value="https://example.com"),
            WorkflowStep(order=2, name="Type user", action="type", selector="#user", value="${USERNAME}"),
        ],
    )
    assert workflow.schema_version == "1.0"
    assert workflow.name == "test-workflow"
    assert len(workflow.steps) == 2
    assert "USERNAME" in workflow.variables


def test_workflow_to_json_roundtrip():
    workflow = Workflow(
        name="roundtrip-test",
        description="Tests JSON serialization roundtrip",
        steps=[
            WorkflowStep(order=1, name="Navigate", action="navigate", value="https://example.com"),
        ],
    )
    json_str = workflow.model_dump_json(exclude_none=True, indent=2)
    restored = Workflow.model_validate_json(json_str)
    assert restored.name == "roundtrip-test"
    assert restored.steps[0].value == "https://example.com"


# --- Converter tests ---


def _make_history(actions: list[ActionRecord], session_id: str = "test-session") -> SessionHistory:
    """Helper to build a minimal SessionHistory for testing."""
    return SessionHistory(
        session_id=session_id,
        started_at="2026-02-19T14:00:00Z",
        actions=actions,
    )


def test_converter_navigate_action():
    history = _make_history([
        ActionRecord(action="navigate", value="https://example.com", success=True, timestamp="2026-02-19T14:00:01Z"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert len(workflow.steps) == 1
    assert workflow.steps[0].action == "navigate"
    assert workflow.steps[0].value == "https://example.com"
    assert workflow.steps[0].order == 1


def test_converter_skips_failed_actions():
    history = _make_history([
        ActionRecord(action="click", selector="#btn", success=True, timestamp="T1"),
        ActionRecord(action="click", selector="#missing", success=False, error="not found", timestamp="T2"),
        ActionRecord(action="type", selector="#input", value="hello", success=True, timestamp="T3"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert len(workflow.steps) == 2
    assert workflow.steps[0].action == "click"
    assert workflow.steps[1].action == "type"
    assert workflow.steps[1].order == 2


def test_converter_preserves_frame_context():
    history = _make_history([
        ActionRecord(
            action="click", selector="#btn", frame_context="iframe#content",
            success=True, timestamp="T1",
        ),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.steps[0].frame_context == "iframe#content"


def test_converter_strips_main_frame_context():
    history = _make_history([
        ActionRecord(
            action="click", selector="#btn", frame_context="main",
            success=True, timestamp="T1",
        ),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.steps[0].frame_context is None


def test_converter_parameterizes_password():
    history = _make_history([
        ActionRecord(action="type", selector="#login-form_password", value="s3cret!", success=True, timestamp="T1"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.steps[0].value == "${PASSWORD}"
    assert "PASSWORD" in workflow.variables
    assert workflow.variables["PASSWORD"].type == "credential"


def test_converter_parameterizes_username_before_password():
    history = _make_history([
        ActionRecord(action="type", selector="#login-form_username", value="admin", success=True, timestamp="T1"),
        ActionRecord(action="click", selector="#next", success=True, timestamp="T2"),
        ActionRecord(action="type", selector="#login-form_password", value="s3cret!", success=True, timestamp="T3"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.steps[0].value == "${USERNAME}"
    assert "USERNAME" in workflow.variables
    assert workflow.variables["USERNAME"].type == "credential"
    # Step 2 (click) is preserved between username and password
    assert workflow.steps[2].value == "${PASSWORD}"


def test_converter_auto_generates_step_names():
    history = _make_history([
        ActionRecord(action="navigate", value="https://example.com/login", success=True, timestamp="T1"),
        ActionRecord(action="click", selector="#submit-btn", success=True, timestamp="T2"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert "Navigate" in workflow.steps[0].name or "navigate" in workflow.steps[0].name.lower()
    assert workflow.steps[1].name  # Non-empty name generated


def test_converter_sets_source():
    history = _make_history([], session_id="sess-abc")
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.source.tool == "scout"
    assert workflow.source.session_id == "sess-abc"


def test_converter_json_output_excludes_none():
    history = _make_history([
        ActionRecord(action="click", selector="#btn", success=True, timestamp="T1"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    json_str = workflow.model_dump_json(exclude_none=True, indent=2)
    # None fields like frame_context should not appear
    assert "frame_context" not in json_str
    assert "url_pattern" not in json_str


# --- Schema validation tests ---


def test_workflow_json_schema_has_required_envelope_fields():
    """Verify the JSON schema matches the design doc envelope."""
    workflow = Workflow(name="schema-test", description="Testing schema compliance")
    data = json.loads(workflow.model_dump_json(exclude_none=True))

    assert "schema_version" in data
    assert "name" in data
    assert "description" in data
    assert "created" in data
    assert "source" in data
    assert "variables" in data
    assert "settings" in data
    assert "steps" in data


def test_workflow_json_schema_all_action_types_valid():
    """Every action type from the design doc can be instantiated."""
    action_configs = [
        {"action": "navigate", "value": "https://example.com"},
        {"action": "click", "selector": "#btn"},
        {"action": "type", "selector": "#input", "value": "hello"},
        {"action": "select", "selector": "#dropdown", "value": "option1"},
        {"action": "scroll", "value": "500"},
        {"action": "wait", "value": "2000"},
        {"action": "wait_for_download", "filename_pattern": "*.csv"},
        {"action": "wait_for_response", "url_pattern": "/api/data"},
        {"action": "press_key", "value": "Enter"},
        {"action": "hover", "selector": "#menu"},
        {"action": "clear", "selector": "#input"},
        {"action": "upload_file", "selector": "#file", "value": "/path/to/file"},
    ]
    for i, config in enumerate(action_configs):
        step = WorkflowStep(order=i + 1, name=f"Step {i + 1}", **config)
        assert step.action == config["action"]


def test_full_adp_workflow_from_design_doc():
    """Instantiate the complete ADP example from the design doc."""
    workflow = Workflow(
        name="adp-report-download",
        description="Log into ADP WFN and download the Unum LTD FMLA report",
        source=WorkflowSource(tool="scout", session_id="abc123"),
        variables={
            "USERNAME": WorkflowVariable(type="credential", default="your_username"),
            "PASSWORD": WorkflowVariable(type="credential", default="your_password"),
            "REPORT_NAME": WorkflowVariable(type="string", default="Unum_LTD_FMLA_Report"),
        },
        settings=WorkflowSettings(headless=False, default_timeout_ms=30000, step_delay_ms=500, on_error="stop"),
        steps=[
            WorkflowStep(order=1, name="Navigate to ADP sign-in", action="navigate",
                         value="https://online.adp.com/signin/v1/?APPID=WFNPortal"),
            WorkflowStep(order=2, name="Enter username", action="type",
                         selector="#login-form_username", value="${USERNAME}", clear_first=True),
            WorkflowStep(order=3, name="Click Next button", action="click",
                         selector="[data-testid='verifUseridBtn']"),
            WorkflowStep(order=4, name="Enter password", action="type",
                         selector="#login-form_password", value="${PASSWORD}", clear_first=True),
            WorkflowStep(order=5, name="Click Sign In", action="click", selector="#signBtn"),
            WorkflowStep(order=6, name="Wait for WFN dashboard", action="wait",
                         selector="#shellNavComponent", timeout_ms=15000),
            WorkflowStep(order=7, name="Navigate to Custom Reports", action="navigate",
                         value="https://workforcenow.adp.com/theme/admin.html#/Reports/ReportsTabCustomReportsCategoryAllReports"),
            WorkflowStep(order=8, name="Click report link", action="click",
                         selector="[aria-label='${REPORT_NAME}']",
                         frame_context="iframe#adprIframe", timeout_ms=15000),
            WorkflowStep(order=9, name="Wait for report download", action="wait_for_download",
                         timeout_ms=60000, filename_pattern="*.csv"),
        ],
    )

    # Roundtrip through JSON
    json_str = workflow.model_dump_json(exclude_none=True, indent=2)
    restored = Workflow.model_validate_json(json_str)

    assert restored.name == "adp-report-download"
    assert len(restored.steps) == 9
    assert restored.variables["USERNAME"].type == "credential"
    assert restored.steps[7].frame_context == "iframe#adprIframe"
    assert restored.steps[8].action == "wait_for_download"


# --- Pre-parameterized value tests ---


def test_converter_preserves_pre_parameterized_value():
    """fill_secret records ${VAR} in history — converter should pass it through."""
    history = _make_history([
        ActionRecord(action="type", selector="input#txtPassword", value="${APP_PASSWORD}", success=True, timestamp="T1"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.steps[0].value == "${APP_PASSWORD}"
    assert "APP_PASSWORD" in workflow.variables
    assert workflow.variables["APP_PASSWORD"].type == "credential"


def test_converter_preserves_multiple_pre_parameterized():
    """Multiple pre-parameterized vars from fill_secret."""
    history = _make_history([
        ActionRecord(action="type", selector="#client_code", value="${APP_CLIENT_CODE}", success=True, timestamp="T1"),
        ActionRecord(action="type", selector="#username", value="${APP_USERNAME}", success=True, timestamp="T2"),
        ActionRecord(action="type", selector="#password", value="${APP_PASSWORD}", success=True, timestamp="T3"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.steps[0].value == "${APP_CLIENT_CODE}"
    assert workflow.steps[1].value == "${APP_USERNAME}"
    assert workflow.steps[2].value == "${APP_PASSWORD}"
    assert len(workflow.variables) == 3
    for var in workflow.variables.values():
        assert var.type == "credential"


def test_converter_mixed_pre_parameterized_and_auto_detected():
    """Pre-parameterized fill_secret values coexist with auto-detected ones."""
    history = _make_history([
        ActionRecord(action="type", selector="#username", value="${APP_USERNAME}", success=True, timestamp="T1"),
        ActionRecord(action="type", selector="#other_password_field", value="raw_secret", success=True, timestamp="T2"),
    ])
    workflow = WorkflowConverter.from_history(history, name="test")
    assert workflow.steps[0].value == "${APP_USERNAME}"
    assert "APP_USERNAME" in workflow.variables
    assert workflow.steps[1].value == "${PASSWORD}"
    assert "PASSWORD" in workflow.variables


def test_workflow_settings_profile_default():
    settings = WorkflowSettings()
    assert settings.profile is None


def test_workflow_settings_profile_set():
    settings = WorkflowSettings(profile="work-portal")
    assert settings.profile == "work-portal"


def test_workflow_settings_profile_excluded_when_none():
    settings = WorkflowSettings()
    dumped = settings.model_dump(exclude_none=True)
    assert "profile" not in dumped


def test_converter_propagates_profile():
    """WorkflowConverter.from_history passes profile into WorkflowSettings."""
    history = SessionHistory(
        session_id="abc123",
        started_at="2026-01-01T00:00:00Z",
        actions=[
            ActionRecord(action="navigate", value="https://example.com", success=True),
        ],
    )
    wf = WorkflowConverter.from_history(history, name="test", profile="work-portal")
    assert wf.settings.profile == "work-portal"


def test_converter_no_profile_default():
    """WorkflowConverter.from_history with no profile leaves settings.profile as None."""
    history = SessionHistory(
        session_id="abc123",
        started_at="2026-01-01T00:00:00Z",
        actions=[
            ActionRecord(action="navigate", value="https://example.com", success=True),
        ],
    )
    wf = WorkflowConverter.from_history(history, name="test")
    assert wf.settings.profile is None
