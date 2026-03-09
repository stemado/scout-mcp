"""Scout browser session management — owns the botasaurus Driver lifecycle."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from botasaurus_driver import Driver

from .download_manager import DownloadManager
from .history import SessionHistoryTracker
from .models import InteractiveElement, SessionCloseResult, SessionInfo
from .network import NetworkMonitor
from .screencast import ScreencastMonitor
from .validation import validate_directory_path, validate_url


class BrowserSession:
    """Manages a single browser session via botasaurus-driver.

    All methods are synchronous (botasaurus-driver is sync).
    The server.py layer wraps calls in asyncio.to_thread().
    """

    def __init__(
        self,
        headless: bool = False,
        proxy: str | None = None,
        download_dir: str = "./downloads",
        user_agent: str | None = None,
        window_size: tuple[int, int] | None = None,
    ) -> None:
        self.session_id = uuid.uuid4().hex[:12]
        self.created_at = datetime.now(timezone.utc)
        validate_directory_path(download_dir)
        self.download_dir = os.path.realpath(download_dir)
        self._headless = headless
        self._proxy = proxy
        self._user_agent = user_agent
        self._window_size = window_size

        self.driver: Driver | None = None
        self.history = SessionHistoryTracker(self.session_id)
        self.download_manager = DownloadManager(self.download_dir, self.session_id)
        self.network_monitor = NetworkMonitor(self.download_dir)
        self.screencast_monitor = ScreencastMonitor(self.download_dir)

        # Cached elements from the most recent scout (invalidated on action/navigation)
        self._cached_elements: list[InteractiveElement] | None = None

        # Secret values registered by fill_secret — used to scrub tool responses.
        self._secret_values: set[str] = set()

    def launch(self, url: str | None = None) -> SessionInfo:
        """Launch the browser and optionally navigate to an initial URL."""
        os.makedirs(self.download_dir, exist_ok=True)

        driver_kwargs: dict = {
            "headless": self._headless,
        }
        if self._proxy:
            driver_kwargs["proxy"] = self._proxy
        if self._user_agent:
            driver_kwargs["user_agent"] = self._user_agent
        if self._window_size:
            driver_kwargs["window_size"] = self._window_size

        try:
            self.driver = Driver(**driver_kwargs)

            # Initialize download management (session-scoped dir + CDP config)
            self.download_manager.start(self.driver)

            current_url = "about:blank"
            if url:
                validate_url(url, allow_localhost=bool(os.environ.get("SCOUT_ALLOW_LOCALHOST")))
                self.driver.get(url)
                current_url = self.driver.current_url
                self.history.record_navigation(current_url)
        except Exception:
            # Clean up partially-initialized browser to prevent process leaks
            self.close()
            raise

        # Extract browser info
        browser_info = {}
        try:
            info = self.driver._browser.info
            browser_info = {
                "user_agent": info.get("User-Agent", ""),
                "browser_version": info.get("Browser", ""),
                "protocol_version": info.get("Protocol-Version", ""),
            }
        except Exception:
            pass

        return SessionInfo(
            session_id=self.session_id,
            browser_info=browser_info,
            current_url=current_url,
            status="active",
        )

    def close(self) -> SessionCloseResult:
        """Close the browser and release all resources."""
        self.network_monitor.stop()
        if self.screencast_monitor.recording:
            self.screencast_monitor.stop()
        self.screencast_monitor.cleanup()
        self.download_manager.cleanup()

        total_actions = len(self.history.actions)
        total_scouts = len(self.history.scouts)
        duration = (datetime.now(timezone.utc) - self.created_at).total_seconds()

        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver = None

        return SessionCloseResult(
            closed=True,
            session_duration_seconds=round(duration, 1),
            total_actions_performed=total_actions,
            total_scouts_performed=total_scouts,
        )

    def cache_elements(self, elements: list[InteractiveElement]) -> None:
        """Cache elements from a scout for use by find_elements."""
        self._cached_elements = elements

    def get_cached_elements(self) -> list[InteractiveElement] | None:
        """Return cached elements, or None if cache is empty/invalidated."""
        return self._cached_elements

    def invalidate_element_cache(self) -> None:
        """Invalidate the element cache (call after actions/navigations)."""
        self._cached_elements = None

    def register_secret(self, value: str) -> str | None:
        """Register a secret value for response scrubbing.

        Returns a warning message if the value is too short to scrub safely,
        or None if registration succeeded.
        """
        if value and len(value) >= 4:
            self._secret_values.add(value)
            return None
        return (
            "Warning: credential is shorter than 4 characters and cannot be "
            "scrubbed from tool responses without excessive false positives."
        )

    def scrub_secrets(self, text: str) -> str:
        """Best-effort replacement of known secret values with [REDACTED]."""
        if not self._secret_values:
            return text
        result = text
        for secret in sorted(self._secret_values, key=len, reverse=True):
            if secret in result:
                result = result.replace(secret, "[REDACTED]")
        return result

    @property
    def is_active(self) -> bool:
        return self.driver is not None
