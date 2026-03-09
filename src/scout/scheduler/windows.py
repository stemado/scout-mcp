"""Windows Task Scheduler backend — wraps schtasks.exe.

All tasks are namespaced under \\SCOUT\\ in Task Scheduler.
Uses schtasks.exe — no admin rights required for user-level tasks.
"""

from __future__ import annotations

import csv
import io
import os
import subprocess
from pathlib import Path

from .base import BaseScheduler, ScheduleInfo

_TASK_FOLDER = "\\SCOUT"


class WindowsScheduler(BaseScheduler):
    """Windows Task Scheduler backend using schtasks.exe."""

    @property
    def platform_name(self) -> str:
        return "Windows"

    def _run_schtasks(self, *args: str) -> subprocess.CompletedProcess:
        """Run schtasks.exe with MSYS_NO_PATHCONV=1 (required for Git Bash)."""
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        return subprocess.run(
            ["schtasks.exe", *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def generate_run_script(self, workflow_dir: str, script_name: str) -> Path:
        """Generate a run.bat wrapper that sets the working directory."""
        workflow_path = Path(workflow_dir)
        bat_path = workflow_path / "run.bat"
        bat_path.write_text(
            f'@echo off\ncd /d "{workflow_path}"\npython {script_name}\n',
            encoding="utf-8",
        )
        return bat_path

    def create(
        self,
        name: str,
        run_script: str,
        schedule: str = "DAILY",
        time: str = "08:00",
        days: str | None = None,
    ) -> bool:
        """Create or update a scheduled task via schtasks /create /f."""
        task_name = f"{_TASK_FOLDER}\\{name}"
        args = ["/create", "/tn", task_name, "/tr", f'"{run_script}"',
                "/sc", schedule, "/st", time, "/f"]
        if days:
            args.extend(["/d", days])
        result = self._run_schtasks(*args)
        return result.returncode == 0

    def delete(self, name: str) -> bool:
        """Delete a scheduled task via schtasks /delete /f."""
        task_name = f"{_TASK_FOLDER}\\{name}"
        result = self._run_schtasks("/delete", "/tn", task_name, "/f")
        return result.returncode == 0

    def query(self, name: str) -> ScheduleInfo | None:
        """Query a single scheduled task by name."""
        task_name = f"{_TASK_FOLDER}\\{name}"
        result = self._run_schtasks("/query", "/tn", task_name, "/fo", "CSV", "/v", "/nh")
        if result.returncode != 0:
            return None
        reader = csv.reader(io.StringIO(result.stdout.strip()))
        for row in reader:
            if row:
                return self._parse_csv_row(row)
        return None

    def list_all(self) -> list[ScheduleInfo]:
        """List all Scout scheduled tasks."""
        result = self._run_schtasks("/query", "/tn", f"{_TASK_FOLDER}\\", "/fo", "CSV", "/v", "/nh")
        if result.returncode != 0:
            return []
        tasks = []
        reader = csv.reader(io.StringIO(result.stdout.strip()))
        for row in reader:
            if row:
                info = self._parse_csv_row(row)
                if info:
                    tasks.append(info)
        return tasks

    @staticmethod
    def _parse_csv_row(row: list[str]) -> ScheduleInfo | None:
        """Parse a single CSV row from schtasks /fo CSV /v /nh output."""
        if len(row) < 23:
            return None
        full_name = row[1].strip()
        short_name = full_name.replace(f"{_TASK_FOLDER}\\", "", 1)
        return ScheduleInfo(
            name=short_name,
            task_name=full_name,
            status=row[3].strip(),
            schedule_type=row[18].strip(),
            start_time=row[19].strip(),
            next_run=row[2].strip(),
            task_to_run=row[8].strip(),
            days=row[22].strip(),
        )
