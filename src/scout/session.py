"""Scout browser session management — owns the botasaurus Driver lifecycle."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from botasaurus_driver import Driver

from .download_manager import DownloadManager
from .history import SessionHistoryTracker
from .models import ConnectionMode, InteractiveElement, SessionCloseResult, SessionInfo
from .network import NetworkMonitor
from .screencast import ScreencastMonitor
from .security import SecurityCounter
from .security.navigation_guard import NavigationGuard
from .validation import validate_url

if TYPE_CHECKING:
    from .extension_relay import ExtensionRelay

_PROFILE_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


class BrowserSession:
    """Manages a single browser session via botasaurus-driver or extension relay.

    All methods are synchronous (botasaurus-driver is sync).
    The server.py layer wraps calls in asyncio.to_thread().
    """

    def __init__(
        self,
        headless: bool = False,
        proxy: str | None = None,
        download_dir: str = os.path.join(os.path.expanduser("~"), ".scout", "downloads"),
        user_agent: str | None = None,
        window_size: tuple[int, int] | None = None,
        connection_mode: ConnectionMode = ConnectionMode.LAUNCH,
        allowed_domains: list[str] | None = None,
        profile: str | None = None,
        allow_localhost_port: int | None = None,
    ) -> None:
        self.session_id = uuid.uuid4().hex[:12]
        self.created_at = datetime.now(timezone.utc)
        self.download_dir = os.path.realpath(download_dir)
        self._headless = headless
        self._proxy = proxy
        self._user_agent = user_agent
        self._window_size = window_size
        self.connection_mode = connection_mode

        self.driver: Driver | None = None
        self._extension_relay: ExtensionRelay | None = None
        self.history = SessionHistoryTracker(self.session_id, connection_mode.value)
        self.download_manager = DownloadManager(self.download_dir, self.session_id)
        self.network_monitor = NetworkMonitor(self.download_dir)
        self.screencast_monitor = ScreencastMonitor(self.download_dir)

        # Cached elements from the most recent scout (invalidated on action/navigation)
        self._cached_elements: list[InteractiveElement] | None = None

        # Secret values registered by fill_secret — used to scrub tool responses.
        self._secret_values: set[str] = set()

        # Security: per-session counters and domain scoping
        self.security_counter = SecurityCounter()
        self._allowed_domains: list[str] | None = allowed_domains

        # Chrome profile: eager validation for fail-fast behavior
        self._resolve_profile_dir(profile)  # validates; raises ValueError on bad input
        self._profile = profile
        self._clone_dir: str | None = None
        self._profile_cloned: bool = False
        self._clone_warnings: list[str] = []
        self._allow_localhost_port = allow_localhost_port

        # Navigation guard (initialized on launch for extension mode)
        self._navigation_guard: NavigationGuard | None = None

    def _resolve_profile_dir(self, profile: str | None) -> str | None:
        """Resolve a profile value to an absolute directory path.

        - None or empty string → None (botasaurus creates a temp profile)
        - Bare name → ~/.scout/profiles/<name>/ (or SCOUT_PROFILE_DIR/<name>/)
        - Absolute path → used as-is (botasaurus detects the path separators
          and returns it unchanged from convert_to_absolute_profile_path)
        - Relative path with separators → rejected
        """
        if not profile:
            return None

        if os.path.isabs(profile):
            return profile

        # Reject relative paths with separators (ambiguous resolution)
        if os.sep in profile or "/" in profile or "\\" in profile:
            raise ValueError(
                f"Profile '{profile}' must be a bare name or an absolute path. "
                f"Relative paths with separators are not allowed."
            )

        # Validate bare name for filesystem safety
        if not _PROFILE_NAME_RE.match(profile):
            raise ValueError(
                f"Profile name '{profile}' contains invalid characters. "
                f"Use only letters, numbers, hyphens, underscores, and dots."
            )

        # Bare name → Scout-managed profile directory
        base = os.environ.get(
            "SCOUT_PROFILE_DIR",
            os.path.join(os.path.expanduser("~"), ".scout", "profiles"),
        )
        return os.path.join(base, profile)

    def launch(self, url: str | None = None) -> SessionInfo:
        """Launch the browser and optionally navigate to an initial URL."""
        if self.connection_mode == ConnectionMode.EXTENSION:
            return self._launch_extension(url)
        return self._launch_browser(url)

    def _launch_browser(self, url: str | None = None) -> SessionInfo:
        """Launch a new browser instance (original behavior)."""
        os.makedirs(self.download_dir, exist_ok=True)

        driver_kwargs: dict = {
            "headless": self._headless,
            # Start on about:blank instead of chrome://newtab to avoid
            # rendering issues when navigating in headed mode (the NTP's
            # renderer process doesn't fully release the viewport).
            "arguments": ["about:blank"],
        }
        if self._proxy:
            driver_kwargs["proxy"] = self._proxy
        if self._user_agent:
            driver_kwargs["user_agent"] = self._user_agent
        if self._window_size:
            driver_kwargs["window_size"] = self._window_size

        # --- Profile lock detection and cloning ---
        resolved_profile = self._resolve_profile_dir(self._profile)
        if resolved_profile and os.path.isdir(resolved_profile):
            from .profile_clone import is_profile_locked, clone_profile, cleanup_orphaned_clones
            cleanup_orphaned_clones()
            if is_profile_locked(resolved_profile):
                clone_path, warnings = clone_profile(resolved_profile, self.session_id)
                resolved_profile = clone_path
                self._clone_dir = clone_path
                self._profile_cloned = True
                self._clone_warnings = warnings
        if resolved_profile:
            driver_kwargs["profile"] = resolved_profile

        try:
            self.driver = Driver(**driver_kwargs)

            # Initialize download management (session-scoped dir + CDP config)
            self.download_manager.start(self.driver)

            current_url = "about:blank"
            if url:
                _env_allow = os.environ.get("SCOUT_ALLOW_LOCALHOST", "").lower() in ("1", "true", "yes")
                validate_url(url, allow_localhost=_env_allow, allow_localhost_port=self._allow_localhost_port)
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
            connection_mode=self.connection_mode.value,
            profile=self._profile or None,
            profile_cloned=self._profile_cloned,
            clone_warnings=self._clone_warnings or None,
        )

    def _launch_extension(self, url: str | None = None) -> SessionInfo:
        """Connect to Chrome via the extension WebSocket relay."""
        from .extension_relay import ExtensionDriver, ExtensionRelay, CONNECT_TIMEOUT

        if self._extension_relay is None:
            raise RuntimeError(
                "Extension relay not initialized. "
                "Call set_extension_relay() before launching in extension mode."
            )

        relay = self._extension_relay

        # Wait for the extension to connect
        if not relay.wait_for_extension(timeout=CONNECT_TIMEOUT):
            raise RuntimeError(
                "Scout extension not detected. Install the extension and set it "
                "to Active before launching in extension mode."
            )

        # Create the adapter driver
        self.driver = ExtensionDriver(relay)

        os.makedirs(self.download_dir, exist_ok=True)

        # Try to initialize download management (may fail if Browser domain
        # isn't fully supported through the extension, which is acceptable)
        try:
            self.download_manager.start(self.driver)
        except Exception:
            pass

        current_url = relay.tab_url or "about:blank"
        if url:
            _env_allow = os.environ.get("SCOUT_ALLOW_LOCALHOST", "").lower() in ("1", "true", "yes")
            validate_url(url, allow_localhost=_env_allow, allow_localhost_port=self._allow_localhost_port)
            self.driver.get(url)
            current_url = self.driver.current_url
            self.history.record_navigation(current_url)

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
            connection_mode=self.connection_mode.value,
        )

    def set_extension_relay(self, relay: ExtensionRelay) -> None:
        """Set the extension relay for extension connection mode."""
        self._extension_relay = relay

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

        # Clean up cloned profile directory
        if self._clone_dir and os.path.isdir(self._clone_dir):
            from .profile_clone import cleanup_clone
            cleanup_clone(self._clone_dir)
            self._clone_dir = None

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
