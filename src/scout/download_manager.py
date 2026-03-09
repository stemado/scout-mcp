"""CDP-based download lifecycle management.

Uses Browser.setDownloadBehavior with 'allowAndName' mode so Chrome writes
downloaded files using their GUID as the filename, preventing all naming
collisions across concurrent sessions. Tracks downloads via
Browser.DownloadWillBegin and Browser.DownloadProgress CDP events.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from botasaurus_driver import cdp

from .converters import convert, detect_format
from .models import DownloadEvent, ProcessResult

if TYPE_CHECKING:
    from botasaurus_driver import Driver

logger = logging.getLogger(__name__)

# Orphaned session dirs older than this are cleaned up on launch
_ORPHAN_MAX_AGE_SECONDS = 2 * 60 * 60  # 2 hours

# Filename pattern tokens
_TOKEN_PATTERN = re.compile(r"\{(MM|dd|yyyy|HH|mm|suggested)\}")


class DownloadManager:
    """Manages download lifecycle via CDP events.

    Each session gets an isolated temp directory under download_dir.
    Chrome writes files with GUID filenames. The manager tracks download
    state and provides process_download() for convert + rename + move.
    """

    def __init__(self, download_dir: str, session_id: str) -> None:
        self._base_download_dir = download_dir
        self._session_id = session_id
        self._session_dir = os.path.join(download_dir, session_id)
        self._driver: Driver | None = None
        self._lock = threading.Lock()
        self._download_complete = threading.Event()

        # Download tracking: guid -> DownloadEvent
        self._pending: dict[str, DownloadEvent] = {}
        self._completed: dict[str, DownloadEvent] = {}
        self._canceled: dict[str, DownloadEvent] = {}

        # Ordered list of completed guids for "most recent" resolution
        self._completed_order: list[str] = []

    def start(self, driver: Driver) -> None:
        """Initialize download management for a browser session.

        Creates session-scoped temp directory, cleans orphans, configures
        Chrome's download behavior, and registers CDP event handlers.
        """
        self._driver = driver

        # Create session-scoped download directory
        os.makedirs(self._session_dir, exist_ok=True)

        # Clean orphaned session dirs from crashed sessions
        self._cleanup_orphans()

        # Configure Chrome to use GUID-based filenames and emit download events
        try:
            driver.run_cdp_command(
                cdp.browser.set_download_behavior(
                    behavior="allowAndName",
                    download_path=self._session_dir,
                    events_enabled=True,
                )
            )
        except Exception as e:
            logger.warning("Failed to set download behavior: %s", e)

        # Register CDP event handlers (same pattern as screencast.py)
        def on_will_begin(event: cdp.browser.DownloadWillBegin):
            self._on_download_will_begin(event)

        def on_progress(event: cdp.browser.DownloadProgress):
            self._on_download_progress(event)

        driver._tab.add_handler(cdp.browser.DownloadWillBegin, on_will_begin)
        driver._tab.add_handler(cdp.browser.DownloadProgress, on_progress)

    def wait_for_download(self, timeout_ms: int = 30000) -> DownloadEvent | None:
        """Block until a download completes or times out.

        Returns the DownloadEvent for the completed download, or None on timeout.
        The returned guid can be passed to process_download().
        """
        self._download_complete.clear()
        completed = self._download_complete.wait(timeout=timeout_ms / 1000)

        if not completed:
            return None

        with self._lock:
            if self._completed_order:
                guid = self._completed_order[-1]
                return self._completed.get(guid)
        return None

    def process_download(
        self,
        guid: str | None = None,
        source_format: str = "auto",
        target_format: str = "csv",
        target_filename: str | None = None,
        target_directory: str | None = None,
    ) -> ProcessResult:
        """Convert, rename, and move a downloaded file.

        Args:
            guid: Download GUID to process. If None, uses most recently completed.
            source_format: Source format. "auto" sniffs magic bytes.
            target_format: Target format for conversion (e.g., "csv").
            target_filename: Filename pattern with tokens: {MM}, {dd}, {yyyy}, {HH}, {mm}, {suggested}.
            target_directory: Destination directory. UNC paths supported.

        Returns:
            ProcessResult with paths and status.
        """
        # Resolve which download to process
        download = self._resolve_download(guid)
        if download is None:
            return ProcessResult(
                success=False,
                error=f"No completed download found{f' for guid {guid}' if guid else ''}",
                source_format=source_format,
                target_format=target_format,
            )

        source_path = download.file_path
        if not os.path.exists(source_path):
            return ProcessResult(
                success=False,
                source_path=source_path,
                error=f"Downloaded file not found at {source_path}",
                source_format=source_format,
                target_format=target_format,
            )

        # Detect format if auto
        if source_format == "auto":
            source_format = detect_format(source_path)
            if source_format == "unknown":
                return ProcessResult(
                    success=False,
                    source_path=source_path,
                    error=f"Could not auto-detect format of {source_path}. File remains in temp dir.",
                    source_format="unknown",
                    target_format=target_format,
                )

        # Convert if source != target
        converted_path = source_path
        if source_format != target_format:
            try:
                converted_path = convert(source_path, source_format, target_format)
            except (ValueError, Exception) as e:
                return ProcessResult(
                    success=False,
                    source_path=source_path,
                    error=f"Conversion failed: {e}. Original file preserved at {source_path}",
                    source_format=source_format,
                    target_format=target_format,
                )

        # Apply filename pattern
        if target_filename:
            final_name = self._apply_filename_tokens(target_filename, download.suggested_filename)
        else:
            # Use suggested filename with new extension
            base = os.path.splitext(download.suggested_filename or "download")[0]
            ext = f".{target_format}" if target_format else ""
            final_name = base + ext

        # Move to target directory or keep in session dir
        if target_directory:
            final_path = os.path.join(target_directory, final_name)
            try:
                os.makedirs(target_directory, exist_ok=True)
                shutil.copy2(converted_path, final_path)

                # Verify copy
                src_size = os.path.getsize(converted_path)
                dst_size = os.path.getsize(final_path)
                if src_size != dst_size:
                    # Size mismatch — delete partial copy, keep temp
                    try:
                        os.remove(final_path)
                    except OSError:
                        pass
                    return ProcessResult(
                        success=False,
                        source_path=source_path,
                        converted_path=converted_path,
                        error=f"Copy size mismatch ({src_size} vs {dst_size}). "
                              f"Converted file preserved at {converted_path}",
                        source_format=source_format,
                        target_format=target_format,
                    )

                # Success — clean up temp files
                self._cleanup_temp_files(source_path, converted_path)

                return ProcessResult(
                    success=True,
                    source_path=source_path,
                    converted_path=converted_path,
                    final_path=final_path,
                    source_format=source_format,
                    target_format=target_format,
                )

            except OSError as e:
                return ProcessResult(
                    success=False,
                    source_path=source_path,
                    converted_path=converted_path,
                    error=f"Failed to copy to {target_directory}: {e}. "
                          f"Converted file preserved at {converted_path}",
                    source_format=source_format,
                    target_format=target_format,
                )
        else:
            # No target directory — rename in place
            final_path = os.path.join(self._session_dir, final_name)
            try:
                if converted_path != final_path:
                    shutil.move(converted_path, final_path)
                # Clean up GUID file if different from converted
                if source_path != converted_path and os.path.exists(source_path):
                    os.remove(source_path)
            except OSError as e:
                return ProcessResult(
                    success=False,
                    source_path=source_path,
                    converted_path=converted_path,
                    error=f"Failed to rename: {e}",
                    source_format=source_format,
                    target_format=target_format,
                )

            return ProcessResult(
                success=True,
                source_path=source_path,
                converted_path=converted_path,
                final_path=final_path,
                source_format=source_format,
                target_format=target_format,
            )

    def get_downloads(self) -> list[DownloadEvent]:
        """Return all tracked downloads (pending + completed + canceled)."""
        with self._lock:
            return (
                list(self._pending.values())
                + list(self._completed.values())
                + list(self._canceled.values())
            )

    def cleanup(self) -> None:
        """Remove the session download directory and all contents."""
        if os.path.isdir(self._session_dir):
            try:
                shutil.rmtree(self._session_dir)
            except OSError as e:
                logger.warning("Failed to clean up session dir %s: %s", self._session_dir, e)

    # --- CDP event handlers (run on websocket thread) ---

    def _on_download_will_begin(self, event: cdp.browser.DownloadWillBegin) -> None:
        """Handle Browser.DownloadWillBegin — fires before file is written."""
        download = DownloadEvent(
            guid=event.guid,
            suggested_filename=event.suggested_filename,
            url=event.url,
            file_path=os.path.join(self._session_dir, event.guid),
            state="pending",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._pending[event.guid] = download

    def _on_download_progress(self, event: cdp.browser.DownloadProgress) -> None:
        """Handle Browser.DownloadProgress — tracks bytes and completion."""
        with self._lock:
            download = self._pending.get(event.guid)
            if download is None:
                return

            download = download.model_copy(update={
                "total_bytes": event.total_bytes,
                "received_bytes": event.received_bytes,
                "state": event.state,
            })

            if event.state == "completed":
                self._pending.pop(event.guid, None)
                self._completed[event.guid] = download
                self._completed_order.append(event.guid)
                self._download_complete.set()
            elif event.state == "canceled":
                self._pending.pop(event.guid, None)
                self._canceled[event.guid] = download
                # Clean up partial file
                file_path = os.path.join(self._session_dir, event.guid)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                self._download_complete.set()
            else:
                # in_progress — update in pending
                self._pending[event.guid] = download

    # --- Internal helpers ---

    def _resolve_download(self, guid: str | None) -> DownloadEvent | None:
        """Resolve a download by guid or return most recently completed."""
        with self._lock:
            if guid:
                return self._completed.get(guid)
            if self._completed_order:
                return self._completed.get(self._completed_order[-1])
        return None

    def _apply_filename_tokens(self, pattern: str, suggested_filename: str) -> str:
        """Replace filename tokens with actual values."""
        now = datetime.now()
        suggested_base = os.path.splitext(suggested_filename or "download")[0]

        replacements = {
            "MM": now.strftime("%m"),
            "dd": now.strftime("%d"),
            "yyyy": now.strftime("%Y"),
            "HH": now.strftime("%H"),
            "mm": now.strftime("%M"),
            "suggested": suggested_base,
        }

        def replace_token(match):
            return replacements.get(match.group(1), match.group(0))

        return _TOKEN_PATTERN.sub(replace_token, pattern)

    def _cleanup_temp_files(self, source_path: str, converted_path: str) -> None:
        """Remove temp files after successful copy to target."""
        for path in {source_path, converted_path}:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _cleanup_orphans(self) -> None:
        """Remove orphaned session directories older than the max age."""
        if not os.path.isdir(self._base_download_dir):
            return

        now = time.time()
        try:
            for entry in os.scandir(self._base_download_dir):
                if not entry.is_dir():
                    continue
                # Skip our own session dir
                if entry.name == self._session_id:
                    continue
                # Check age
                try:
                    age = now - entry.stat().st_mtime
                    if age > _ORPHAN_MAX_AGE_SECONDS:
                        shutil.rmtree(entry.path)
                        logger.info("Cleaned orphaned session dir: %s (age: %.0fs)", entry.name, age)
                except OSError:
                    pass
        except OSError:
            pass
