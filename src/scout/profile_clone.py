"""Chrome profile cloning for locked User Data directories.

When Chrome is running, it holds an OS-level lock on its User Data directory.
This module detects the lock and creates a selective clone of session-essential
files so Scout can launch a browser with the user's logged-in sessions without
requiring them to close Chrome.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import sqlite3
import time
from glob import glob
from pathlib import Path

logger = logging.getLogger(__name__)

# --- Constants ---

# File prefixes to copy from the profile subdir.
# Glob as <prefix>* to catch SQLite companions (-journal, -wal, -shm).
_PROFILE_FILE_PREFIXES = [
    "Cookies",
    "Login Data",
    "Login Data For Account",
    "Web Data",
    "Preferences",
    "Secure Preferences",
    "Extension Cookies",
    "Favicons",
]

# Subdirectories within the profile to copy recursively.
_PROFILE_DIRS = ["Network", "Local Storage", "IndexedDB"]

# Files to copy from the User Data root (not the profile subdir).
_ROOT_FILES = ["Local State"]

# Lock sentinel files — never copy these.
_LOCK_FILES = frozenset({
    "lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket",
    "LOCK",  # LevelDB lock sentinel
})

_CLONES_DIR_NAME = "_clones"
_ORPHAN_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours


# --- Lock Detection ---


def is_profile_locked(user_data_dir: str) -> bool:
    """Check if Chrome holds an OS lock on this User Data directory.

    Returns True if locked, False if not locked or directory doesn't exist.
    """
    if not os.path.isdir(user_data_dir):
        return False

    system = platform.system()
    if system == "Windows":
        return _is_locked_windows(user_data_dir)
    else:
        return _is_locked_unix(user_data_dir)


def _is_locked_windows(user_data_dir: str) -> bool:
    """Windows: try to acquire an exclusive lock on the lockfile."""
    lockfile_path = os.path.join(user_data_dir, "lockfile")
    if not os.path.exists(lockfile_path):
        return False

    try:
        fh = open(lockfile_path, "r+b")
        try:
            import msvcrt
            # Check file has content to lock (empty = stale/unused)
            fh.seek(0, 2)  # seek to end
            size = fh.tell()
            if size == 0:
                return False
            fh.seek(0)
            # Try to lock byte 0 — if Chrome holds it, this raises OSError
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            # Got the lock — profile is NOT locked by Chrome
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            return False
        except OSError:
            # Could not acquire lock — Chrome is using this profile
            return True
        finally:
            fh.close()
    except (PermissionError, OSError):
        # Cannot even open the file — locked
        return True


def _is_locked_unix(user_data_dir: str) -> bool:
    """Unix: check if SingletonLock symlink points to a live process."""
    singleton_path = os.path.join(user_data_dir, "SingletonLock")

    if not os.path.islink(singleton_path):
        return False

    try:
        target = os.readlink(singleton_path)
        # Format: "hostname-PID"
        parts = target.rsplit("-", 1)
        if len(parts) != 2:
            return False

        pid = int(parts[1])
        # Check if the process is alive
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False


# --- Active Profile Detection ---


def _detect_active_profile(user_data_dir: str) -> str:
    """Read Local State to find the active profile subdirectory name.

    Returns the directory name (e.g., 'Default', 'Profile 1').
    Falls back to 'Default' on any error.
    """
    local_state_path = os.path.join(user_data_dir, "Local State")
    try:
        with open(local_state_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("profile", {}).get("last_used", "Default") or "Default"
    except (FileNotFoundError, json.JSONDecodeError, KeyError, OSError):
        return "Default"


# --- Copy Helpers ---


def _copy_with_sqlite_fallback(src: str, dst: str) -> None:
    """Copy a file, falling back to esentutl/SQLite for locked databases.

    Chrome exclusively locks some SQLite databases (e.g., Network/Cookies)
    while running — no sharing flags, so even CreateFile with FILE_SHARE_ALL
    gets ERROR_SHARING_VIOLATION. Fallback chain:

    1. shutil.copy2 (normal copy)
    2. esentutl.exe /y (Windows only — uses Volume Shadow Copy, works on
       any locked file, no admin required)
    3. sqlite3.backup (works when SQLite-level locks allow opening)

    If all fail, the original PermissionError is re-raised.
    """
    try:
        shutil.copy2(src, dst)
    except PermissionError as original_err:
        # Fallback 1: esentutl.exe (Windows) — uses VSS to read locked files
        if platform.system() == "Windows":
            try:
                import subprocess
                result = subprocess.run(
                    ["esentutl.exe", "/y", src, "/d", dst, "/o"],
                    capture_output=True, timeout=30,
                )
                if result.returncode == 0 and os.path.exists(dst):
                    logger.debug("Used esentutl for locked file: %s", src)
                    return
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

        # Fallback 2: SQLite backup — works for some locked databases
        try:
            src_conn = sqlite3.connect(src, timeout=1)
            dst_conn = sqlite3.connect(dst)
            src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()
            logger.debug("Used SQLite backup for locked file: %s", src)
        except (sqlite3.Error, OSError):
            # All methods failed — re-raise original PermissionError
            raise original_err


# --- Profile Cloning ---


def _clones_base_dir() -> str:
    """Return the base directory for profile clones."""
    base = os.environ.get(
        "SCOUT_PROFILE_DIR",
        os.path.join(os.path.expanduser("~"), ".scout", "profiles"),
    )
    return os.path.join(base, _CLONES_DIR_NAME)


def clone_profile(
    source_dir: str, session_id: str
) -> tuple[str, list[str]]:
    """Selectively clone a locked Chrome profile for session use.

    Copies only session-essential files (cookies, login data, preferences,
    local storage) while skipping caches (~490MB savings). Automatically
    detects the active profile subdirectory from Local State.

    Args:
        source_dir: Path to the Chrome User Data directory.
        session_id: Unique session ID for the clone directory name.

    Returns:
        (clone_path, warnings) — clone_path is the absolute path to the
        cloned User Data directory; warnings is a list of non-fatal issues.
    """
    warnings: list[str] = []
    profile_subdir = _detect_active_profile(source_dir)

    clone_dir = os.path.join(_clones_base_dir(), session_id)
    os.makedirs(clone_dir, exist_ok=True)

    # 1. Copy root files (Local State, etc.)
    for filename in _ROOT_FILES:
        src = os.path.join(source_dir, filename)
        dst = os.path.join(clone_dir, filename)
        try:
            shutil.copy2(src, dst)
        except FileNotFoundError:
            logger.debug("Root file not found (skipping): %s", filename)
        except (PermissionError, OSError) as e:
            warnings.append(f"Could not copy {filename}: {e}")

    # 2. Create profile subdirectory in clone
    clone_profile_dir = os.path.join(clone_dir, profile_subdir)
    os.makedirs(clone_profile_dir, exist_ok=True)

    source_profile_dir = os.path.join(source_dir, profile_subdir)
    if not os.path.isdir(source_profile_dir):
        warnings.append(
            f"Profile subdirectory '{profile_subdir}' not found in source. "
            f"Clone may not contain session data."
        )
        return clone_dir, warnings

    # 3. Copy individual files by prefix glob (catches -journal, -wal, -shm)
    for prefix in _PROFILE_FILE_PREFIXES:
        pattern = os.path.join(source_profile_dir, f"{prefix}*")
        matches = glob(pattern)
        for src_path in matches:
            basename = os.path.basename(src_path)
            if basename in _LOCK_FILES:
                continue
            dst_path = os.path.join(clone_profile_dir, basename)
            try:
                _copy_with_sqlite_fallback(src_path, dst_path)
            except (PermissionError, OSError) as e:
                warnings.append(f"Could not copy {basename}: {e}")

    # 4. Copy subdirectories recursively (with SQLite fallback for locked DBs)
    for dirname in _PROFILE_DIRS:
        src_subdir = os.path.join(source_profile_dir, dirname)
        dst_subdir = os.path.join(clone_profile_dir, dirname)
        if not os.path.isdir(src_subdir):
            continue
        try:
            shutil.copytree(
                src_subdir,
                dst_subdir,
                dirs_exist_ok=True,
                copy_function=_copy_with_sqlite_fallback,
                ignore=shutil.ignore_patterns(*_LOCK_FILES),
            )
        except (PermissionError, OSError) as e:
            warnings.append(f"Could not copy directory {dirname}: {e}")

    logger.info(
        "Cloned profile from %s to %s (subdir=%s, warnings=%d)",
        source_dir, clone_dir, profile_subdir, len(warnings),
    )
    return clone_dir, warnings


# --- Cleanup ---


def cleanup_clone(clone_dir: str) -> None:
    """Remove a clone directory. Idempotent — no error if already gone."""
    if os.path.isdir(clone_dir):
        shutil.rmtree(clone_dir, ignore_errors=True)
        logger.info("Cleaned up clone directory: %s", clone_dir)


def cleanup_orphaned_clones() -> None:
    """Sweep the _clones/ directory for entries older than 24 hours.

    Called as best-effort housekeeping before creating a new clone.
    """
    clones_dir = _clones_base_dir()
    if not os.path.isdir(clones_dir):
        return

    now = time.time()
    for entry in os.scandir(clones_dir):
        if not entry.is_dir():
            continue
        try:
            age = now - entry.stat().st_mtime
            if age > _ORPHAN_MAX_AGE_SECONDS:
                shutil.rmtree(entry.path, ignore_errors=True)
                logger.info("Removed orphaned clone: %s (age=%.0fh)", entry.name, age / 3600)
        except OSError:
            pass
