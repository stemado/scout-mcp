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
