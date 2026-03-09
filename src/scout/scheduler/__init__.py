"""Cross-platform task scheduler for Scout workflows.

Usage:
    from scout.scheduler import get_scheduler, ScheduleInfo

    scheduler = get_scheduler()  # auto-detects platform
    scheduler.create("enrollment", "/path/to/run.sh", "DAILY", "06:45")
"""

from __future__ import annotations

import sys

from .base import BaseScheduler, ScheduleInfo, UnsupportedPlatformError

__all__ = ["BaseScheduler", "ScheduleInfo", "UnsupportedPlatformError", "get_scheduler"]


def get_scheduler() -> BaseScheduler:
    """Return the scheduler backend for the current platform."""
    match sys.platform:
        case "win32":
            from .windows import WindowsScheduler
            return WindowsScheduler()
        case "darwin":
            from .macos import MacOSScheduler
            return MacOSScheduler()
        case "linux":
            from .linux import LinuxScheduler
            return LinuxScheduler()
        case _:
            raise UnsupportedPlatformError(sys.platform)
