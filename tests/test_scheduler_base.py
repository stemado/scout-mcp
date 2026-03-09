"""Tests for scheduler base class and factory."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scout.scheduler import ScheduleInfo, get_scheduler
from scout.scheduler.base import BaseScheduler, UnsupportedPlatformError


class TestScheduleInfoModel:
    """Verify ScheduleInfo Pydantic model."""

    def test_creates_with_required_fields(self):
        info = ScheduleInfo(
            name="enrollment",
            task_name="SCOUT/enrollment",
            status="Ready",
            schedule_type="Daily",
            start_time="06:45",
            next_run="2026-03-01 06:45",
            task_to_run="/path/to/run.sh",
        )
        assert info.name == "enrollment"
        assert info.days == ""  # default

    def test_days_field_optional(self):
        info = ScheduleInfo(
            name="report",
            task_name="SCOUT/report",
            status="Ready",
            schedule_type="Weekly",
            start_time="08:00",
            next_run="2026-03-01 08:00",
            task_to_run="/path/to/run.sh",
            days="MON,WED,FRI",
        )
        assert info.days == "MON,WED,FRI"


class TestGetSchedulerFactory:
    """Verify factory returns correct backend per platform."""

    @patch("scout.scheduler.sys")
    def test_returns_windows_scheduler_on_win32(self, mock_sys):
        mock_sys.platform = "win32"
        scheduler = get_scheduler()
        assert scheduler.platform_name == "Windows"
        assert isinstance(scheduler, BaseScheduler)

    @patch("scout.scheduler.sys")
    def test_returns_macos_scheduler_on_darwin(self, mock_sys):
        mock_sys.platform = "darwin"
        scheduler = get_scheduler()
        assert scheduler.platform_name == "macOS"
        assert isinstance(scheduler, BaseScheduler)

    @patch("scout.scheduler.sys")
    def test_returns_linux_scheduler_on_linux(self, mock_sys):
        mock_sys.platform = "linux"
        scheduler = get_scheduler()
        assert scheduler.platform_name == "Linux"
        assert isinstance(scheduler, BaseScheduler)

    @patch("scout.scheduler.sys")
    def test_raises_on_unsupported_platform(self, mock_sys):
        mock_sys.platform = "freebsd"
        with pytest.raises(UnsupportedPlatformError, match="freebsd"):
            get_scheduler()
