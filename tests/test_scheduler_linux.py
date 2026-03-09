"""Tests for Linux crontab scheduler backend."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scout.scheduler import ScheduleInfo
from scout.scheduler.linux import LinuxScheduler


class TestLinuxPlatformName:
    def test_platform_name(self):
        scheduler = LinuxScheduler()
        assert scheduler.platform_name == "Linux"


class TestGenerateRunScript:
    def test_creates_sh_file(self, tmp_path):
        workflow_dir = tmp_path / "workflows" / "enrollment"
        workflow_dir.mkdir(parents=True)

        scheduler = LinuxScheduler()
        result = scheduler.generate_run_script(str(workflow_dir), "enrollment.py")
        assert result.exists()
        assert result.name == "run.sh"

    def test_sh_content(self, tmp_path):
        workflow_dir = tmp_path / "workflows" / "enrollment"
        workflow_dir.mkdir(parents=True)

        scheduler = LinuxScheduler()
        result = scheduler.generate_run_script(str(workflow_dir), "enrollment.py")
        content = result.read_text()

        assert content.startswith("#!/bin/bash\n")
        assert f'cd "{workflow_dir}"' in content
        assert "python3 enrollment.py" in content

    @pytest.mark.skipif(sys.platform == "win32", reason="NTFS ignores chmod")
    def test_sh_file_is_executable(self, tmp_path):
        workflow_dir = tmp_path / "workflows" / "enrollment"
        workflow_dir.mkdir(parents=True)

        scheduler = LinuxScheduler()
        result = scheduler.generate_run_script(str(workflow_dir), "enrollment.py")
        import stat
        assert result.stat().st_mode & stat.S_IXUSR


class TestCronExpression:
    """Verify cron expression generation from schedule parameters."""

    def test_daily_expression(self):
        scheduler = LinuxScheduler()
        expr = scheduler._build_cron_expression("DAILY", "06:45")
        assert expr == "45 6 * * *"

    def test_weekly_single_day(self):
        scheduler = LinuxScheduler()
        expr = scheduler._build_cron_expression("WEEKLY", "08:00", "MON")
        assert expr == "0 8 * * 1"

    def test_weekly_multiple_days(self):
        scheduler = LinuxScheduler()
        expr = scheduler._build_cron_expression("WEEKLY", "08:00", "MON,WED,FRI")
        assert expr == "0 8 * * 1,3,5"

    def test_weekdays(self):
        scheduler = LinuxScheduler()
        expr = scheduler._build_cron_expression("WEEKLY", "09:00", "MON,TUE,WED,THU,FRI")
        assert expr == "0 9 * * 1,2,3,4,5"


class TestCrontabParsing:
    """Verify reading/writing crontab text."""

    def test_parse_scout_entries(self):
        scheduler = LinuxScheduler()
        crontab = (
            "# some other cron job\n"
            "0 5 * * * /usr/bin/backup\n"
            "# SCOUT:enrollment\n"
            "45 6 * * * /path/to/run.sh\n"
            "# SCOUT:report\n"
            "0 8 * * 1,3,5 /path/to/report/run.sh\n"
        )
        entries = scheduler._parse_scout_entries(crontab)
        assert len(entries) == 2
        assert "enrollment" in entries
        assert "report" in entries
        assert entries["enrollment"]["cron"] == "45 6 * * * /path/to/run.sh"
        assert entries["report"]["cron"] == "0 8 * * 1,3,5 /path/to/report/run.sh"

    def test_add_entry_to_crontab(self):
        scheduler = LinuxScheduler()
        existing = "0 5 * * * /usr/bin/backup\n"
        new = scheduler._add_entry(existing, "enrollment", "45 6 * * * /path/to/run.sh")
        assert "# SCOUT:enrollment" in new
        assert "45 6 * * * /path/to/run.sh" in new
        assert "0 5 * * * /usr/bin/backup" in new

    def test_replace_existing_entry(self):
        scheduler = LinuxScheduler()
        existing = (
            "# SCOUT:enrollment\n"
            "45 6 * * * /old/path/run.sh\n"
        )
        new = scheduler._add_entry(existing, "enrollment", "0 7 * * * /new/path/run.sh")
        assert "0 7 * * * /new/path/run.sh" in new
        assert "/old/path/run.sh" not in new

    def test_remove_entry_from_crontab(self):
        scheduler = LinuxScheduler()
        existing = (
            "0 5 * * * /usr/bin/backup\n"
            "# SCOUT:enrollment\n"
            "45 6 * * * /path/to/run.sh\n"
            "# SCOUT:report\n"
            "0 8 * * 1 /path/to/report/run.sh\n"
        )
        new = scheduler._remove_entry(existing, "enrollment")
        assert "# SCOUT:enrollment" not in new
        assert "/path/to/run.sh" not in new
        assert "# SCOUT:report" in new
        assert "/usr/bin/backup" in new

    def test_remove_entry_handles_blank_line_between_marker_and_cron(self):
        """Fix for review issue 8: blank line between marker and expression."""
        scheduler = LinuxScheduler()
        existing = (
            "# SCOUT:enrollment\n"
            "\n"
            "45 6 * * * /path/to/run.sh\n"
        )
        new = scheduler._remove_entry(existing, "enrollment")
        assert "# SCOUT:enrollment" not in new
        assert "45 6 * * * /path/to/run.sh" not in new

    def test_remove_entry_marker_at_end_of_file(self):
        """Marker as last line with no following cron expression."""
        scheduler = LinuxScheduler()
        existing = (
            "0 5 * * * /usr/bin/backup\n"
            "# SCOUT:orphan\n"
        )
        new = scheduler._remove_entry(existing, "orphan")
        assert "# SCOUT:orphan" not in new
        assert "/usr/bin/backup" in new


class TestCreateSchedule:
    @patch("scout.scheduler.linux.subprocess.run")
    def test_create_writes_crontab(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # crontab -l
            MagicMock(returncode=0, stdout="", stderr=""),  # crontab -
        ]
        scheduler = LinuxScheduler()
        result = scheduler.create(
            name="enrollment",
            run_script="/path/to/run.sh",
            schedule="DAILY",
            time="06:45",
        )
        assert result is True
        write_call = mock_run.call_args_list[1]
        assert "crontab" in write_call[0][0]
        assert "-" in write_call[0][0]

    @patch("scout.scheduler.linux.subprocess.run")
    def test_create_handles_empty_crontab(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="no crontab for user"),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        scheduler = LinuxScheduler()
        result = scheduler.create(
            name="enrollment",
            run_script="/path/to/run.sh",
            schedule="DAILY",
            time="06:45",
        )
        assert result is True


class TestDeleteSchedule:
    @patch("scout.scheduler.linux.subprocess.run")
    def test_delete_removes_entry(self, mock_run):
        existing_crontab = (
            "# SCOUT:enrollment\n"
            "45 6 * * * /path/to/run.sh\n"
        )
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=existing_crontab, stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        scheduler = LinuxScheduler()
        result = scheduler.delete("enrollment")
        assert result is True

    @patch("scout.scheduler.linux.subprocess.run")
    def test_delete_returns_false_when_not_found(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        scheduler = LinuxScheduler()
        result = scheduler.delete("nonexistent")
        assert result is False


class TestQuerySchedule:
    @patch("scout.scheduler.linux.subprocess.run")
    def test_query_parses_entry(self, mock_run):
        crontab = (
            "# SCOUT:enrollment\n"
            "45 6 * * * /path/to/run.sh\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=crontab, stderr="")
        scheduler = LinuxScheduler()
        info = scheduler.query("enrollment")
        assert info is not None
        assert info.name == "enrollment"
        assert info.schedule_type == "Daily"
        assert "6:45" in info.start_time or "06:45" in info.start_time

    @patch("scout.scheduler.linux.subprocess.run")
    def test_query_returns_none_when_not_found(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scheduler = LinuxScheduler()
        assert scheduler.query("nonexistent") is None


class TestListSchedules:
    @patch("scout.scheduler.linux.subprocess.run")
    def test_lists_all_scout_entries(self, mock_run):
        crontab = (
            "# SCOUT:enrollment\n"
            "45 6 * * * /path/to/enrollment/run.sh\n"
            "# SCOUT:report\n"
            "0 8 * * 1,3,5 /path/to/report/run.sh\n"
        )
        mock_run.return_value = MagicMock(returncode=0, stdout=crontab, stderr="")
        scheduler = LinuxScheduler()
        tasks = scheduler.list_all()
        assert len(tasks) == 2

    @patch("scout.scheduler.linux.subprocess.run")
    def test_returns_empty_on_no_entries(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        scheduler = LinuxScheduler()
        assert scheduler.list_all() == []
