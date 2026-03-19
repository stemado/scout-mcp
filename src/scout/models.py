"""Data models for Scout MCP server."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConnectionMode(str, Enum):
    """How Scout connects to Chrome."""

    LAUNCH = "launch"
    EXTENSION = "extension"


class IframeInfo(BaseModel):
    """Information about an iframe element on the page."""

    selector: str = Field(description="CSS selector path to this iframe")
    src: str = Field(default="", description="Iframe source URL")
    depth: int = Field(description="Nesting level (0 = top-level iframe)")
    cross_origin: bool = Field(default=False, description="Whether this iframe is cross-origin")
    accessible: bool = Field(default=True, description="Whether DOM inspection is possible")
    children: list[str] = Field(default_factory=list, description="Selectors of nested iframes")


class ShadowDomBoundary(BaseModel):
    """A shadow DOM boundary discovered on the page."""

    host_selector: str = Field(description="CSS selector of the shadow host element")
    mode: str = Field(description="Shadow root mode: 'open' or 'closed'")
    frame_context: str = Field(default="main", description="Iframe selector path or 'main'")
    child_interactive_count: int = Field(default=0, description="Interactive elements inside this shadow root")


class InteractiveElement(BaseModel):
    """An interactive element discovered during scouting."""

    tag: str = Field(description="Element tag name")
    type: str = Field(default="", description="Input type, button, link, select, etc.")
    selector: str = Field(description="Most reliable CSS selector")
    text: str = Field(default="", description="Visible text content")
    frame_context: str = Field(default="main", description="Iframe selector path or 'main'")
    in_shadow_dom: bool = Field(default=False)
    shadow_host: str | None = Field(default=None, description="Host selector if in shadow DOM")
    attributes: dict[str, str] = Field(default_factory=dict, description="Key attributes: id, name, class, href")
    visible: bool = Field(default=True)
    enabled: bool = Field(default=True)


class ElementSummary(BaseModel):
    """Aggregated summary of interactive elements on a page."""

    total: int = Field(description="Total interactive elements found")
    visible: int = Field(description="Number of visible interactive elements")
    by_type: dict[str, int] = Field(default_factory=dict, description="Count by element type")
    by_frame: dict[str, int] = Field(default_factory=dict, description="Count by frame context")


class FindElementsResult(BaseModel):
    """Result from targeted element search."""

    matched: int = Field(description="Number of elements matching the query")
    total_on_page: int = Field(description="Total interactive elements on the page")
    elements: list[InteractiveElement] = Field(default_factory=list)


class NetworkEvent(BaseModel):
    """A captured network request/response event."""

    url: str
    method: str = Field(default="GET")
    type: str = Field(default="other", description="xhr, fetch, document, etc.")
    status: int | None = Field(default=None, description="HTTP status code")
    response_type: str | None = Field(default=None, description="json, blob, text, etc.")
    timestamp: str = Field(description="ISO format timestamp")
    triggered_download: bool = Field(default=False)
    response_body: str | None = Field(default=None, description="Response body if captured, capped at 1MB")
    request_headers: dict[str, str] = Field(default_factory=dict)
    download_filename: str | None = Field(default=None)
    download_size_bytes: int | None = Field(default=None)


class DownloadEvent(BaseModel):
    """A tracked download from the CDP Browser.DownloadWillBegin/DownloadProgress events."""

    guid: str = Field(description="Chrome's unique download identifier")
    suggested_filename: str = Field(default="", description="Server-suggested filename")
    url: str = Field(default="", description="URL that triggered the download")
    file_path: str = Field(default="", description="Absolute path to GUID-named file on disk")
    total_bytes: float = Field(default=0)
    received_bytes: float = Field(default=0)
    state: str = Field(default="pending", description="pending | in_progress | completed | canceled")
    timestamp: str = Field(description="ISO format timestamp")


class ProcessResult(BaseModel):
    """Result of processing a downloaded file (convert + rename + move)."""

    success: bool
    source_path: str = Field(default="", description="Original GUID file path")
    converted_path: str | None = Field(default=None, description="Path after conversion (in temp dir)")
    final_path: str | None = Field(default=None, description="Path after rename + move to target directory")
    source_format: str = Field(default="", description="Detected or specified source format")
    target_format: str = Field(default="", description="Target format for conversion")
    error: str | None = Field(default=None, description="On failure, includes temp file path for recovery")


class PageMetadata(BaseModel):
    """Basic page state information."""

    url: str
    title: str
    load_state: str = Field(default="complete", description="domcontentloaded | load | networkidle")


class ScoutReport(BaseModel):
    """Comprehensive intelligence report from page scouting."""

    page_metadata: PageMetadata
    iframe_map: list[IframeInfo] = Field(default_factory=list)
    shadow_dom_boundaries: list[ShadowDomBoundary] = Field(default_factory=list)
    interactive_elements: list[InteractiveElement] = Field(default_factory=list)
    page_summary: str = Field(default="", description="Human-readable summary of page structure")


class ActionResult(BaseModel):
    """Result of executing a browser action."""

    success: bool
    action_performed: str = Field(description="Description of what was executed")
    url_changed: bool = Field(default=False)
    current_url: str = Field(default="")
    error: str | None = Field(default=None)
    warning: str | None = Field(default=None, description="Post-action verification warning")
    elapsed_ms: int = Field(default=0)


class ActionRecord(BaseModel):
    """Historical record of an action taken during the session."""

    action: str
    selector: str | None = None
    value: str | None = None
    frame_context: str | None = None
    success: bool = True
    url_before: str = ""
    url_after: str = ""
    timestamp: str = ""
    error: str | None = None


class SessionInfo(BaseModel):
    """Information returned when a session is launched."""

    session_id: str
    browser_info: dict = Field(default_factory=dict)
    current_url: str = Field(default="about:blank")
    status: str = Field(default="active")
    connection_mode: str = Field(default="launch", description="'launch' or 'extension'")
    profile: str | None = Field(default=None, description="Profile name or path, or None for temp profile")
    profile_cloned: bool = Field(default=False, description="True if profile was cloned due to lock")
    clone_warnings: list[str] | None = Field(default=None, description="Warnings from partial clone")


class ScoutSummaryRecord(BaseModel):
    """Compact scout record for session history (no element list)."""

    page_metadata: PageMetadata
    iframe_count: int = 0
    shadow_dom_count: int = 0
    element_summary: ElementSummary | None = None
    page_summary: str = ""


class FindElementsRecord(BaseModel):
    """Compact record of a find_elements call for session history."""

    query: str | None = None
    element_types: list[str] | None = None
    matched: int = 0
    timestamp: str = ""


class JavaScriptResult(BaseModel):
    """Result of executing arbitrary JavaScript in the page context."""

    success: bool
    result: Any = Field(default=None, description="Return value from the script")
    result_type: str = Field(default="undefined", description="JS typeof the result: string, number, object, array, boolean, null, undefined")
    error: str | None = Field(default=None)
    warning: str | None = Field(default=None, description="Hint when result is empty but script suggests computation occurred")
    elapsed_ms: int = Field(default=0)


class JavaScriptRecord(BaseModel):
    """Compact record of a JavaScript execution for session history."""

    script_preview: str = Field(default="", description="First 200 chars of the script")
    frame_context: str | None = None
    success: bool = True
    result_preview: str = Field(default="", description="First 500 chars of the result")
    timestamp: str = ""


class ScreenshotResult(BaseModel):
    """Result metadata from taking a screenshot (image bytes sent separately)."""

    success: bool
    format: str = Field(default="png", description="Image format: png or jpeg")
    byte_size: int = Field(default=0, description="Size of the screenshot in bytes")
    clipped: bool = Field(default=False, description="Whether a clip region was applied")
    file_path: str | None = Field(default=None, description="Path to saved screenshot file")
    error: str | None = Field(default=None)


class ScreenshotRecord(BaseModel):
    """Compact record of a screenshot for session history."""

    format: str = "png"
    clipped: bool = False
    full_page: bool = False
    timestamp: str = ""


class RecordingResult(BaseModel):
    """Result from video recording operations."""

    recording_active: bool = Field(default=False)
    video_path: str | None = Field(default=None, description="Path to encoded MP4 file")
    gif_path: str | None = Field(default=None, description="Path to encoded GIF file")
    frames_dir: str | None = Field(default=None, description="Path to raw frames if encoding unavailable")
    frame_count: int = Field(default=0)
    duration_seconds: float = Field(default=0.0)
    encoded: bool = Field(default=False, description="Whether frames were encoded to video/gif")
    output_format: str = Field(default="mp4", description="Output format: mp4 or gif")
    started_at: str | None = Field(default=None)
    elapsed_seconds: float = Field(default=0.0)
    target_fps: int = Field(default=15)
    resolution: str = Field(default="1920x1080")
    error: str | None = Field(default=None)
    encode_warning: str | None = Field(default=None)


class RecordingRecord(BaseModel):
    """Compact record of a recording for session history."""

    started_at: str = ""
    stopped_at: str = ""
    duration_seconds: float = 0.0
    frame_count: int = 0
    video_path: str | None = None
    gif_path: str | None = None
    output_format: str = "mp4"
    encoded: bool = False
    timestamp: str = ""


class MonitorResult(BaseModel):
    """Result from network monitoring operations."""

    events: list[NetworkEvent] = Field(default_factory=list)
    total_captured: int = 0
    total_matched: int = Field(default=0, description="Total matching events before pagination")
    monitoring_active: bool = False


class ElementInspection(BaseModel):
    """Detailed inspection of a single DOM element."""

    found: bool = Field(description="Whether the element was found")
    selector: str = Field(default="", description="The selector that was queried")
    tag: str = Field(default="")
    bounding_rect: dict[str, float] = Field(default_factory=dict, description="x, y, width, height, top, right, bottom, left")
    computed_visibility: dict[str, str] = Field(default_factory=dict, description="display, visibility, opacity, overflow, pointer-events")
    is_visible: bool = Field(default=False)
    is_obscured: bool = Field(default=False, description="Whether another element covers it at its center point")
    obscured_by: str | None = Field(default=None, description="Selector of the element covering it")
    in_shadow_dom: bool = Field(default=False)
    shadow_host: str | None = Field(default=None)
    parent_chain: list[str] = Field(default_factory=list, description="Tag#id.class chain from element to body")
    attributes: dict[str, str] = Field(default_factory=dict)
    aria: dict[str, str] = Field(default_factory=dict, description="ARIA attributes")
    input_state: dict[str, Any] = Field(default_factory=dict, description="value, checked, selected, disabled, readOnly for form elements")
    children_summary: dict[str, int] = Field(default_factory=dict, description="Count of child elements by tag")
    event_listeners: list[str] = Field(default_factory=list, description="Event types registered on the element")
    error: str | None = Field(default=None)


class SessionHistory(BaseModel):
    """Complete structured history of a browser session."""

    session_id: str
    started_at: str
    connection_mode: str = Field(default="launch", description="'launch' or 'extension'")
    actions: list[ActionRecord] = Field(default_factory=list)
    scouts: list[ScoutSummaryRecord] = Field(default_factory=list)
    find_elements_calls: list[FindElementsRecord] = Field(default_factory=list)
    javascript_calls: list[JavaScriptRecord] = Field(default_factory=list)
    screenshots: list[ScreenshotRecord] = Field(default_factory=list)
    recordings: list[RecordingRecord] = Field(default_factory=list)
    network_events: list[NetworkEvent] = Field(default_factory=list)
    navigations: list[dict] = Field(default_factory=list, description="List of {url, timestamp}")


class SessionCloseResult(BaseModel):
    """Result of closing a session."""

    closed: bool = True
    session_duration_seconds: float = 0
    total_actions_performed: int = 0
    total_scouts_performed: int = 0


class ExtensionStatus(BaseModel):
    """Status of the Chrome extension connection."""

    status: str = Field(description="'connected', 'waiting', or 'not_running'")
    message: str = Field(description="Human-readable status message")
    install_instructions: str | None = Field(
        default=None,
        description="Installation instructions (present when not_running)",
    )


class FillSecretResult(BaseModel):
    """Result of filling a secret value into a form field."""

    success: bool
    env_var: str = Field(description="Name of the .env variable used")
    selector: str = Field(description="CSS selector of the target field")
    chars_typed: int = Field(default=0, description="Number of characters typed")
    url_changed: bool = Field(default=False)
    current_url: str = Field(default="")
    error: str | None = Field(default=None)
    warning: str | None = Field(default=None, description="Scrubbing limitation warning for short credentials")
    elapsed_ms: int = Field(default=0)
