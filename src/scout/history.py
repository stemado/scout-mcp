"""Session history tracking — append-only log of all Scout session activity."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    ActionRecord,
    FindElementsRecord,
    JavaScriptRecord,
    NetworkEvent,
    RecordingRecord,
    ScoutReport,
    ScoutSummaryRecord,
    ScreenshotRecord,
    SessionHistory,
    TokenUsageRecord,
    TokenUsageSummary,
)
from .scout import build_element_summary
from .tokencount import count_tokens

# Maximum list sizes before FIFO eviction
MAX_ACTIONS = 10_000
MAX_SCOUTS = 1_000
MAX_JS_CALLS = 5_000
MAX_SCREENSHOTS = 500
MAX_FIND_ELEMENTS = 5_000
MAX_NAVIGATIONS = 5_000
MAX_NETWORK_EVENTS = 5_000
MAX_RECORDINGS = 100
MAX_TOKEN_RECORDS = 10_000


class SessionHistoryTracker:
    """Tracks all actions, scout reports, network events, and navigations for a session."""

    def __init__(self, session_id: str, connection_mode: str = "launch") -> None:
        self.session_id = session_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.connection_mode = connection_mode
        self.actions: list[ActionRecord] = []
        self.scouts: list[ScoutSummaryRecord] = []
        self.find_elements_calls: list[FindElementsRecord] = []
        self.javascript_calls: list[JavaScriptRecord] = []
        self.screenshots: list[ScreenshotRecord] = []
        self.recordings: list[RecordingRecord] = []
        self.network_events: list[NetworkEvent] = []
        self.navigations: list[dict] = []
        self.token_usage: list[TokenUsageRecord] = []
        self._token_totals: dict[str, int] = {}  # tool -> cumulative tokens
        self._total_tokens: int = 0
        # Monotonic cursor for syncing from NetworkMonitor — independent of FIFO eviction.
        # len(network_events) plateaus at MAX_NETWORK_EVENTS, but this counter never decreases.
        self._network_sync_cursor: int = 0

    def record_scout(self, report: ScoutReport) -> None:
        """Record a compact summary of a scout (no element list)."""
        if len(self.scouts) >= MAX_SCOUTS:
            self.scouts.pop(0)
        summary = build_element_summary(report.interactive_elements)
        self.scouts.append(ScoutSummaryRecord(
            page_metadata=report.page_metadata,
            iframe_count=len(report.iframe_map),
            shadow_dom_count=len(report.shadow_dom_boundaries),
            element_summary=summary,
            page_summary=report.page_summary,
        ))

    def record_find_elements(
        self, query: str | None, element_types: list[str] | None, matched: int
    ) -> None:
        """Record a compact find_elements call."""
        if len(self.find_elements_calls) >= MAX_FIND_ELEMENTS:
            self.find_elements_calls.pop(0)
        self.find_elements_calls.append(FindElementsRecord(
            query=query,
            element_types=element_types,
            matched=matched,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))

    def record_action(self, record: ActionRecord) -> None:
        if len(self.actions) >= MAX_ACTIONS:
            self.actions.pop(0)
        self.actions.append(record)

    def record_navigation(self, url: str) -> None:
        if len(self.navigations) >= MAX_NAVIGATIONS:
            self.navigations.pop(0)
        self.navigations.append({
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_javascript(self, record: JavaScriptRecord) -> None:
        if len(self.javascript_calls) >= MAX_JS_CALLS:
            self.javascript_calls.pop(0)
        self.javascript_calls.append(record)

    def record_screenshot(self, record: ScreenshotRecord) -> None:
        if len(self.screenshots) >= MAX_SCREENSHOTS:
            self.screenshots.pop(0)
        self.screenshots.append(record)

    def record_network_event(self, event: NetworkEvent) -> None:
        if len(self.network_events) >= MAX_NETWORK_EVENTS:
            self.network_events.pop(0)
        self.network_events.append(event)

    def record_recording(self, record: RecordingRecord) -> None:
        if len(self.recordings) >= MAX_RECORDINGS:
            self.recordings.pop(0)
        self.recordings.append(record)

    def record_response_tokens(self, tool: str, response_text: str) -> int:
        """Count tokens in a response string and record it. Returns the token count."""
        tokens = count_tokens(response_text)
        chars = len(response_text)
        if len(self.token_usage) >= MAX_TOKEN_RECORDS:
            self.token_usage.pop(0)
        self.token_usage.append(TokenUsageRecord(
            tool=tool,
            tokens=tokens,
            chars=chars,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        self._total_tokens += tokens
        self._token_totals[tool] = self._token_totals.get(tool, 0) + tokens
        return tokens

    def record_image_tokens(self, tool: str, tokens: int, byte_size: int) -> None:
        """Record estimated image token cost (e.g. for screenshots sent inline)."""
        if len(self.token_usage) >= MAX_TOKEN_RECORDS:
            self.token_usage.pop(0)
        self.token_usage.append(TokenUsageRecord(
            tool=tool,
            tokens=tokens,
            chars=byte_size,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
        self._total_tokens += tokens
        self._token_totals[tool] = self._token_totals.get(tool, 0) + tokens

    def get_token_summary(self) -> TokenUsageSummary:
        """Return aggregate token usage for this session."""
        return TokenUsageSummary(
            total_tokens=self._total_tokens,
            total_responses=len(self.token_usage),
            by_tool=dict(self._token_totals),
        )

    def get_full_history(self) -> SessionHistory:
        return SessionHistory(
            session_id=self.session_id,
            started_at=self.started_at,
            connection_mode=self.connection_mode,
            actions=self.actions,
            scouts=self.scouts,
            find_elements_calls=self.find_elements_calls,
            javascript_calls=self.javascript_calls,
            screenshots=self.screenshots,
            recordings=self.recordings,
            network_events=self.network_events,
            navigations=self.navigations,
            token_usage=self.token_usage,
            token_summary=self.get_token_summary(),
        )
