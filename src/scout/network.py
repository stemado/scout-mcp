"""CDP network monitoring — captures requests, responses, and downloads."""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from botasaurus_driver import cdp

from .models import NetworkEvent
from .validation import validate_regex_pattern

if TYPE_CHECKING:
    from botasaurus_driver import Driver

# 1MB cap for response bodies
BODY_CAP_BYTES = 1_048_576

# Internal Chrome URL prefixes to filter out
_INTERNAL_PREFIXES = ("chrome://", "chrome-extension://", "chrome-untrusted://", "devtools://", "data:", "about:")

# Headers that should be redacted from captured network events
_SENSITIVE_HEADERS = frozenset({
    "authorization", "cookie", "set-cookie",
    "x-api-key", "x-auth-token", "proxy-authorization",
})


def _redact_headers(headers: dict) -> dict:
    """Redact sensitive header values."""
    return {
        k: "[REDACTED]" if k.lower() in _SENSITIVE_HEADERS else v
        for k, v in headers.items()
    }


class NetworkMonitor:
    """Monitors network activity via botasaurus-driver's CDP callback system.

    Body capture is deferred to query-time to avoid deadlocking the CDP
    event loop (run_cdp_command blocks the websocket thread if called
    inside a CDP event handler).
    """

    def __init__(self, download_dir: str) -> None:
        self.download_dir = download_dir
        self.events: list[NetworkEvent] = []
        self.monitoring = False
        self._url_pattern: re.Pattern | None = None
        self._capture_bodies = False
        self._driver: Driver | None = None
        self._download_event = threading.Event()
        self._lock = threading.Lock()
        # Track request metadata by request_id so we can correlate with responses
        self._pending_requests: dict[str, dict] = {}
        # Request IDs that need body capture (deferred from callback to query-time)
        self._pending_body_captures: list[tuple[int, str]] = []  # (event_index, request_id)

    def start(self, driver: Driver, url_pattern: str | None = None, capture_bodies: bool = False) -> None:
        """Start network monitoring with optional URL pattern filter."""
        self._driver = driver
        self._url_pattern = validate_regex_pattern(url_pattern) if url_pattern else None
        self._capture_bodies = capture_bodies
        self.monitoring = True
        self._download_event.clear()

        driver.before_request_sent(self._on_request)
        driver.after_response_received(self._on_response)

    def stop(self) -> None:
        """Stop network monitoring."""
        self.monitoring = False

    def query(
        self,
        url_pattern: str | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NetworkEvent]:
        """Return captured events, optionally filtered by URL pattern.

        If capture_bodies was enabled, lazily fetches response bodies
        for events that haven't been fetched yet.

        Args:
            url_pattern: Optional regex to filter by URL.
            limit: Maximum events to return. 0 means no limit. Default: 100.
            offset: Skip this many matching events. Default: 0.
        """
        self._fetch_pending_bodies()

        with self._lock:
            if url_pattern:
                pat = validate_regex_pattern(url_pattern)
                matched = [e for e in self.events if pat.search(e.url)]
            else:
                matched = list(self.events)

        if offset > 0:
            matched = matched[offset:]
        if limit > 0:
            matched = matched[:limit]

        return matched

    def query_all(self, url_pattern: str | None = None) -> list[NetworkEvent]:
        """Return ALL captured events without pagination limits.

        Internal method for history recording — bypasses the default limit
        so that session history captures every event.
        """
        return self.query(url_pattern, limit=0)

    @property
    def total_count(self) -> int:
        """Total number of captured events (not affected by query pagination)."""
        with self._lock:
            return len(self.events)

    def wait_for_download(self, timeout_ms: int = 30000) -> list[NetworkEvent]:
        """Block until a download event is detected or timeout."""
        self._download_event.clear()
        self._download_event.wait(timeout=timeout_ms / 1000)
        with self._lock:
            return [e for e in self.events if e.triggered_download]

    def clear(self) -> None:
        """Clear all captured events."""
        with self._lock:
            self.events.clear()
            self._pending_requests.clear()
            self._pending_body_captures.clear()

    def _fetch_pending_bodies(self) -> None:
        """Fetch response bodies that were deferred from CDP callbacks.

        Called at query-time, outside the CDP event loop, so run_cdp_command
        is safe to call here.
        """
        if not self._driver or not self._pending_body_captures:
            return

        with self._lock:
            pending = list(self._pending_body_captures)
            self._pending_body_captures.clear()

        for event_idx, request_id in pending:
            try:
                body_data, _is_base64 = self._driver.run_cdp_command(
                    cdp.network.get_response_body(request_id=request_id)
                )
                if body_data:
                    body = body_data[:BODY_CAP_BYTES]
                    if len(body_data) > BODY_CAP_BYTES:
                        body += f"\n\n[TRUNCATED — response was {len(body_data)} bytes, cap is {BODY_CAP_BYTES}]"
                    with self._lock:
                        if event_idx < len(self.events):
                            self.events[event_idx] = self.events[event_idx].model_copy(
                                update={"response_body": body}
                            )
            except Exception:
                pass  # Some responses don't have retrievable bodies

    def _on_request(self, request_id: str, request, event) -> None:
        """Callback for Network.requestWillBeSent."""
        if not self.monitoring:
            return

        url = request.url if hasattr(request, "url") else str(request)
        # Filter out internal Chrome URLs
        if any(url.startswith(prefix) for prefix in _INTERNAL_PREFIXES):
            return
        if self._url_pattern and not self._url_pattern.search(url):
            return

        method = request.method if hasattr(request, "method") else "GET"
        headers = {}
        if hasattr(request, "headers") and request.headers:
            headers = dict(request.headers) if not isinstance(request.headers, dict) else request.headers

        # Determine request type from the event
        req_type = "other"
        if hasattr(event, "type_") and event.type_:
            req_type = str(event.type_).lower().replace("resourcetype.", "")
        elif hasattr(event, "type") and event.type:
            req_type = str(event.type).lower()

        with self._lock:
            self._pending_requests[request_id] = {
                "url": url,
                "method": method,
                "type": req_type,
                "request_headers": _redact_headers(headers),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def _on_response(self, request_id: str, response, event) -> None:
        """Callback for Network.responseReceived.

        Never calls run_cdp_command here — body capture is deferred to
        query-time via _pending_body_captures to avoid deadlocking the
        CDP event loop.
        """
        if not self.monitoring:
            return

        url = response.url if hasattr(response, "url") else ""
        # Filter out internal Chrome URLs
        if any(url.startswith(prefix) for prefix in _INTERNAL_PREFIXES):
            return
        if self._url_pattern and not self._url_pattern.search(url):
            return

        # Get request metadata if we captured it
        with self._lock:
            req_meta = self._pending_requests.pop(request_id, {})

        status = response.status if hasattr(response, "status") else None
        mime = response.mime_type if hasattr(response, "mime_type") else None
        headers = {}
        if hasattr(response, "headers") and response.headers:
            headers = dict(response.headers) if not isinstance(response.headers, dict) else response.headers

        # Detect download by content-disposition header
        content_disposition = headers.get("content-disposition", headers.get("Content-Disposition", ""))
        is_download = "attachment" in content_disposition.lower() if content_disposition else False
        download_filename = None
        if is_download and "filename=" in content_disposition:
            download_filename = content_disposition.split("filename=")[-1].strip('" ')

        # Extract content-length for download size
        content_length = headers.get("content-length", headers.get("Content-Length"))
        download_size = int(content_length) if content_length and content_length.isdigit() else None

        # Determine response type from MIME
        response_type = None
        if mime:
            if "json" in mime:
                response_type = "json"
            elif "html" in mime:
                response_type = "html"
            elif "xml" in mime:
                response_type = "xml"
            elif "text" in mime:
                response_type = "text"
            elif "octet-stream" in mime or "pdf" in mime or "zip" in mime:
                response_type = "blob"
            else:
                response_type = mime

        net_event = NetworkEvent(
            url=url or req_meta.get("url", ""),
            method=req_meta.get("method", "GET"),
            type=req_meta.get("type", "other"),
            status=status,
            response_type=response_type,
            timestamp=req_meta.get("timestamp", datetime.now(timezone.utc).isoformat()),
            triggered_download=is_download,
            response_body=None,  # Populated lazily at query-time
            request_headers=req_meta.get("request_headers", {}),
            download_filename=download_filename,
            download_size_bytes=download_size,
        )

        with self._lock:
            event_idx = len(self.events)
            self.events.append(net_event)
            # Defer body capture to query-time
            if self._capture_bodies:
                self._pending_body_captures.append((event_idx, request_id))

        if is_download:
            self._download_event.set()
