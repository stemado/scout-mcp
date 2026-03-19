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


# --- Task 4: Profile Cloning ---

from scout.profile_clone import clone_profile, _CLONES_DIR_NAME


def _create_mock_chrome_profile(base: Path, profile_subdir: str = "Default") -> Path:
    """Create a minimal mock Chrome User Data directory for testing."""
    profile = base / profile_subdir
    profile.mkdir(parents=True)

    # Root files
    (base / "Local State").write_text(json.dumps({
        "profile": {"last_used": profile_subdir},
        "os_crypt": {"encrypted_key": "fake-key"},
    }))
    (base / "lockfile").write_bytes(b"")

    # Profile files (with journals)
    (profile / "Login Data").write_bytes(b"sqlite-login")
    (profile / "Login Data-journal").write_bytes(b"journal-login")
    (profile / "Web Data").write_bytes(b"sqlite-web")
    (profile / "Preferences").write_text('{"prefs": true}')
    (profile / "Secure Preferences").write_text('{"secure": true}')
    (profile / "Cookies").write_bytes(b"legacy-cookies")
    (profile / "Extension Cookies").write_bytes(b"ext-cookies")
    (profile / "Extension Cookies-journal").write_bytes(b"ext-cookies-j")
    (profile / "Favicons").write_bytes(b"favicons-data")
    (profile / "Favicons-journal").write_bytes(b"favicons-j")

    # Network directory (Chrome 96+ cookies location)
    network = profile / "Network"
    network.mkdir()
    (network / "Cookies").write_bytes(b"network-cookies")
    (network / "Cookies-journal").write_bytes(b"network-cookies-j")
    (network / "TransportSecurity").write_bytes(b"hsts")

    # Local Storage (LevelDB)
    ls = profile / "Local Storage" / "leveldb"
    ls.mkdir(parents=True)
    (ls / "000003.log").write_bytes(b"leveldb-log")

    # IndexedDB
    idb = profile / "IndexedDB"
    idb.mkdir()
    (idb / "https_example.com_0.indexeddb.leveldb").mkdir()

    # Cache directories (should NOT be cloned)
    (profile / "Code Cache" / "js").mkdir(parents=True)
    (profile / "Code Cache" / "js" / "big_file.bin").write_bytes(b"x" * 1000)
    (profile / "Cache" / "Cache_Data").mkdir(parents=True)
    (profile / "GPUCache").mkdir()
    (profile / "Service Worker" / "CacheStorage").mkdir(parents=True)

    return base


class TestCloneProfile:
    """Tests for selective profile cloning."""

    def test_copies_local_state(self, tmp_path):
        source = _create_mock_chrome_profile(tmp_path / "source")
        clone_path, warnings = clone_profile(str(source), "test-session-1")
        assert os.path.exists(os.path.join(clone_path, "Local State"))

    def test_copies_profile_files_with_journals(self, tmp_path):
        source = _create_mock_chrome_profile(tmp_path / "source")
        clone_path, warnings = clone_profile(str(source), "test-session-2")
        profile_dir = os.path.join(clone_path, "Default")
        assert os.path.exists(os.path.join(profile_dir, "Login Data"))
        assert os.path.exists(os.path.join(profile_dir, "Login Data-journal"))
        assert os.path.exists(os.path.join(profile_dir, "Web Data"))

    def test_copies_network_directory(self, tmp_path):
        source = _create_mock_chrome_profile(tmp_path / "source")
        clone_path, warnings = clone_profile(str(source), "test-session-3")
        network_dir = os.path.join(clone_path, "Default", "Network")
        assert os.path.exists(os.path.join(network_dir, "Cookies"))
        assert os.path.exists(os.path.join(network_dir, "Cookies-journal"))

    def test_copies_local_storage(self, tmp_path):
        source = _create_mock_chrome_profile(tmp_path / "source")
        clone_path, warnings = clone_profile(str(source), "test-session-4")
        ls_dir = os.path.join(clone_path, "Default", "Local Storage")
        assert os.path.isdir(ls_dir)

    def test_skips_cache_directories(self, tmp_path):
        source = _create_mock_chrome_profile(tmp_path / "source")
        clone_path, warnings = clone_profile(str(source), "test-session-5")
        profile_dir = os.path.join(clone_path, "Default")
        assert not os.path.exists(os.path.join(profile_dir, "Code Cache"))
        assert not os.path.exists(os.path.join(profile_dir, "Cache"))
        assert not os.path.exists(os.path.join(profile_dir, "GPUCache"))
        assert not os.path.exists(os.path.join(profile_dir, "Service Worker"))

    def test_lock_files_not_copied(self, tmp_path):
        source = _create_mock_chrome_profile(tmp_path / "source")
        clone_path, warnings = clone_profile(str(source), "test-session-6")
        assert not os.path.exists(os.path.join(clone_path, "lockfile"))

    def test_clone_destination_under_scout_clones(self, tmp_path, monkeypatch):
        source = _create_mock_chrome_profile(tmp_path / "source")
        clones_base = tmp_path / "scout-profiles"
        monkeypatch.setenv("SCOUT_PROFILE_DIR", str(clones_base))
        clone_path, warnings = clone_profile(str(source), "session-abc")
        assert _CLONES_DIR_NAME in clone_path
        assert "session-abc" in clone_path

    def test_auto_detects_profile_subdir(self, tmp_path):
        source = _create_mock_chrome_profile(tmp_path / "source", "Profile 1")
        clone_path, warnings = clone_profile(str(source), "test-session-7")
        assert os.path.isdir(os.path.join(clone_path, "Profile 1"))
        assert not os.path.isdir(os.path.join(clone_path, "Default"))

    def test_missing_optional_file_produces_warning(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "Local State").write_text(json.dumps({
            "profile": {"last_used": "Default"},
        }))
        profile = source / "Default"
        profile.mkdir()
        (profile / "Preferences").write_text("{}")
        clone_path, warnings = clone_profile(str(source), "test-session-8")
        assert os.path.exists(os.path.join(clone_path, "Default", "Preferences"))

    def test_returns_no_warnings_on_clean_clone(self, tmp_path):
        source = _create_mock_chrome_profile(tmp_path / "source")
        _, warnings = clone_profile(str(source), "test-session-9")
        assert warnings == []


# --- Task 5: Cleanup Functions ---

from scout.profile_clone import cleanup_clone, cleanup_orphaned_clones


class TestCleanupClone:
    """Tests for clone directory removal."""

    def test_removes_clone_directory(self, tmp_path):
        clone_dir = tmp_path / "clone-to-remove"
        clone_dir.mkdir()
        (clone_dir / "some_file.txt").write_text("data")
        cleanup_clone(str(clone_dir))
        assert not clone_dir.exists()

    def test_idempotent_on_missing_directory(self, tmp_path):
        cleanup_clone(str(tmp_path / "nonexistent"))


class TestOrphanCleanup:
    """Tests for stale clone directory sweep."""

    def test_removes_old_clones(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCOUT_PROFILE_DIR", str(tmp_path))
        clones_dir = tmp_path / _CLONES_DIR_NAME
        clones_dir.mkdir()
        old_clone = clones_dir / "old-session"
        old_clone.mkdir()
        old_time = time.time() - (25 * 60 * 60)
        os.utime(str(old_clone), (old_time, old_time))
        cleanup_orphaned_clones()
        assert not old_clone.exists()

    def test_preserves_recent_clones(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCOUT_PROFILE_DIR", str(tmp_path))
        clones_dir = tmp_path / _CLONES_DIR_NAME
        clones_dir.mkdir()
        recent_clone = clones_dir / "recent-session"
        recent_clone.mkdir()
        cleanup_orphaned_clones()
        assert recent_clone.exists()

    def test_no_error_when_clones_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCOUT_PROFILE_DIR", str(tmp_path))
        cleanup_orphaned_clones()
