"""Abstract base class for platform-specific scheduler backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel


class ScheduleInfo(BaseModel):
    """Parsed info about a scheduled task (platform-agnostic)."""

    name: str
    task_name: str
    status: str
    schedule_type: str
    start_time: str
    next_run: str
    task_to_run: str
    days: str = ""


class UnsupportedPlatformError(Exception):
    """Raised when the current platform has no scheduler backend."""

    def __init__(self, platform: str) -> None:
        self.platform = platform
        super().__init__(
            f"Scheduling is not supported on '{platform}'. "
            f"Supported platforms: Windows, macOS, Linux."
        )


class BaseScheduler(ABC):
    """Platform-specific scheduler backend interface."""

    TASK_NAMESPACE = "SCOUT"

    @abstractmethod
    def create(
        self,
        name: str,
        run_script: str,
        schedule: str = "DAILY",
        time: str = "08:00",
        days: str | None = None,
    ) -> bool:
        """Create or update a scheduled task. Returns True on success."""
        ...

    @abstractmethod
    def delete(self, name: str) -> bool:
        """Delete a scheduled task. Returns True on success."""
        ...

    @abstractmethod
    def query(self, name: str) -> ScheduleInfo | None:
        """Query a single scheduled task by name. Returns None if not found."""
        ...

    @abstractmethod
    def list_all(self) -> list[ScheduleInfo]:
        """List all Scout scheduled tasks."""
        ...

    @abstractmethod
    def generate_run_script(self, workflow_dir: str, script_name: str) -> Path:
        """Generate a platform-appropriate run script wrapper."""
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform name (e.g., 'Windows', 'macOS', 'Linux')."""
        ...
