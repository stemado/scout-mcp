"""Tests for Chrome profile cloning."""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scout.models import SessionInfo
from scout.session import BrowserSession


class TestSessionInfoCloneFields:
    """Verify SessionInfo includes clone fields."""

    def test_profile_cloned_defaults_to_false(self):
        info = SessionInfo(session_id="abc123")
        assert info.profile_cloned is False

    def test_clone_warnings_defaults_to_none(self):
        info = SessionInfo(session_id="abc123")
        assert info.clone_warnings is None

    def test_profile_cloned_true_appears_in_dump(self):
        info = SessionInfo(session_id="abc123", profile_cloned=True)
        dumped = info.model_dump(exclude_none=True)
        assert dumped["profile_cloned"] is True

    def test_clone_warnings_none_excluded_from_dump(self):
        info = SessionInfo(session_id="abc123")
        dumped = info.model_dump(exclude_none=True)
        assert "clone_warnings" not in dumped

    def test_clone_warnings_list_appears_in_dump(self):
        info = SessionInfo(
            session_id="abc123",
            clone_warnings=["Could not copy Login Data"],
        )
        dumped = info.model_dump(exclude_none=True)
        assert dumped["clone_warnings"] == ["Could not copy Login Data"]


import platform
import sys

from scout.profile_clone import is_profile_locked


class TestIsProfileLocked:
    """Tests for Chrome profile lock detection."""

    def test_not_locked_when_no_lockfile(self, tmp_path):
        """No lockfile/SingletonLock means profile is not locked."""
        assert is_profile_locked(str(tmp_path)) is False

    def test_not_locked_when_directory_missing(self, tmp_path):
        """Non-existent directory is not locked."""
        assert is_profile_locked(str(tmp_path / "nonexistent")) is False

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only lock mechanism")
    def test_locked_when_lockfile_held_windows(self, tmp_path):
        """On Windows, a lockfile with an exclusive lock means locked."""
        lockfile = tmp_path / "lockfile"
        lockfile.write_bytes(b"\x00")  # msvcrt.locking needs ≥1 byte
        # Hold an exclusive lock on the file
        import msvcrt
        fh = open(lockfile, "r+b")
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            assert is_profile_locked(str(tmp_path)) is True
        finally:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            fh.close()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only lock mechanism")
    def test_not_locked_stale_lockfile_windows(self, tmp_path):
        """On Windows, a lockfile without an active lock means NOT locked."""
        lockfile = tmp_path / "lockfile"
        lockfile.write_bytes(b"")
        assert is_profile_locked(str(tmp_path)) is False

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only lock mechanism")
    def test_locked_when_singleton_lock_points_to_live_pid(self, tmp_path):
        """On Unix, SingletonLock symlink pointing to current PID = locked."""
        import socket
        hostname = socket.gethostname()
        singleton = tmp_path / "SingletonLock"
        singleton.symlink_to(f"{hostname}-{os.getpid()}")
        assert is_profile_locked(str(tmp_path)) is True

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only lock mechanism")
    def test_not_locked_when_singleton_lock_points_to_dead_pid(self, tmp_path):
        """On Unix, SingletonLock pointing to a dead PID = not locked."""
        import socket
        hostname = socket.gethostname()
        singleton = tmp_path / "SingletonLock"
        singleton.symlink_to(f"{hostname}-99999999")
        assert is_profile_locked(str(tmp_path)) is False


from scout.profile_clone import _detect_active_profile


class TestDetectActiveProfile:
    """Tests for auto-detecting the active Chrome profile subdirectory."""

    def test_reads_last_used_from_local_state(self, tmp_path):
        local_state = tmp_path / "Local State"
        local_state.write_text(json.dumps({
            "profile": {"last_used": "Profile 1"}
        }))
        assert _detect_active_profile(str(tmp_path)) == "Profile 1"

    def test_defaults_to_default_when_key_missing(self, tmp_path):
        local_state = tmp_path / "Local State"
        local_state.write_text(json.dumps({"other": "data"}))
        assert _detect_active_profile(str(tmp_path)) == "Default"

    def test_defaults_to_default_when_file_missing(self, tmp_path):
        assert _detect_active_profile(str(tmp_path)) == "Default"

    def test_defaults_to_default_when_file_corrupt(self, tmp_path):
        local_state = tmp_path / "Local State"
        local_state.write_text("not json {{{")
        assert _detect_active_profile(str(tmp_path)) == "Default"
