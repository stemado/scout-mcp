"""Linux crontab scheduler backend.

Scout tasks are identified in crontab by comment markers: # SCOUT:<name>
Each task occupies two lines: the marker comment and the cron expression.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import BaseScheduler, ScheduleInfo

_MARKER_PREFIX = "# SCOUT:"

# cron uses 0=Sunday, 1=Monday, ..., 6=Saturday
_DAY_MAP = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3,
    "THU": 4, "FRI": 5, "SAT": 6,
}

_REVERSE_DAY_MAP = {v: k for k, v in _DAY_MAP.items()}


class LinuxScheduler(BaseScheduler):
    """Linux crontab scheduler backend."""

    @property
    def platform_name(self) -> str:
        return "Linux"

    def generate_run_script(self, workflow_dir: str, script_name: str) -> Path:
        """Generate a run.sh wrapper."""
        workflow_path = Path(workflow_dir)
        sh_path = workflow_path / "run.sh"
        sh_path.write_text(
            f'#!/bin/bash\ncd "{workflow_path}"\npython3 {script_name}\n',
            encoding="utf-8",
        )
        sh_path.chmod(0o755)
        return sh_path

    def _read_crontab(self) -> str:
        """Read the current user's crontab. Returns empty string if none."""
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return ""
        return result.stdout

    def _write_crontab(self, content: str) -> bool:
        """Write new crontab content via pipe to 'crontab -'."""
        result = subprocess.run(
            ["crontab", "-"],
            input=content,
            capture_output=True, text=True,
        )
        return result.returncode == 0

    def _build_cron_expression(
        self, schedule: str, time: str, days: str | None = None,
    ) -> str:
        """Build a cron expression from Scout schedule parameters."""
        hour, minute = (int(x) for x in time.split(":"))

        if schedule == "DAILY":
            return f"{minute} {hour} * * *"
        elif schedule == "WEEKLY" and days:
            day_list = [d.strip().upper() for d in days.split(",")]
            cron_days = ",".join(str(_DAY_MAP[d]) for d in day_list if d in _DAY_MAP)
            return f"{minute} {hour} * * {cron_days}"
        elif schedule == "ONCE":
            # One-time: daily expression (caller handles cleanup)
            return f"{minute} {hour} * * *"
        else:
            return f"{minute} {hour} * * *"

    def _parse_scout_entries(self, crontab: str) -> dict[str, dict]:
        """Parse all Scout entries from crontab text.

        Returns dict mapping name -> {"cron": "full cron line"}.
        Handles blank lines between marker and cron expression.
        """
        entries: dict[str, dict] = {}
        lines = crontab.strip().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith(_MARKER_PREFIX):
                name = line[len(_MARKER_PREFIX):].strip()
                # Scan forward past blank lines to find the cron expression
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    cron_line = lines[j].strip()
                    entries[name] = {"cron": cron_line}
                    i = j + 1
                    continue
            i += 1
        return entries

    def _add_entry(self, crontab: str, name: str, cron_line: str) -> str:
        """Add or replace a Scout entry in crontab text."""
        cleaned = self._remove_entry(crontab, name)
        if cleaned and not cleaned.endswith("\n"):
            cleaned += "\n"
        return f"{cleaned}{_MARKER_PREFIX}{name}\n{cron_line}\n"

    def _remove_entry(self, crontab: str, name: str) -> str:
        """Remove a Scout entry (marker + cron line) from crontab text.

        Handles blank lines between the marker and cron expression:
        skips the marker, any following blank lines, then the next
        non-blank line (the cron expression).
        """
        lines = crontab.split("\n")
        result = []
        i = 0
        while i < len(lines):
            if lines[i].strip() == f"{_MARKER_PREFIX}{name}":
                # Skip marker line
                i += 1
                # Skip any blank lines between marker and cron expression
                while i < len(lines) and not lines[i].strip():
                    i += 1
                # Skip the cron expression line itself
                if i < len(lines):
                    i += 1
                continue
            result.append(lines[i])
            i += 1
        return "\n".join(result)

    def create(
        self,
        name: str,
        run_script: str,
        schedule: str = "DAILY",
        time: str = "08:00",
        days: str | None = None,
    ) -> bool:
        """Add or update a crontab entry."""
        cron_expr = self._build_cron_expression(schedule, time, days)
        cron_line = f"{cron_expr} {run_script}"

        existing = self._read_crontab()
        new_crontab = self._add_entry(existing, name, cron_line)
        return self._write_crontab(new_crontab)

    def delete(self, name: str) -> bool:
        """Remove a crontab entry."""
        existing = self._read_crontab()
        entries = self._parse_scout_entries(existing)
        if name not in entries:
            return False

        new_crontab = self._remove_entry(existing, name)
        return self._write_crontab(new_crontab)

    def query(self, name: str) -> ScheduleInfo | None:
        """Query a single Scout crontab entry."""
        existing = self._read_crontab()
        entries = self._parse_scout_entries(existing)
        if name not in entries:
            return None

        return self._cron_to_schedule_info(name, entries[name]["cron"])

    def list_all(self) -> list[ScheduleInfo]:
        """List all Scout crontab entries."""
        existing = self._read_crontab()
        if not existing.strip():
            return []

        entries = self._parse_scout_entries(existing)
        tasks = []
        for entry_name, data in entries.items():
            info = self._cron_to_schedule_info(entry_name, data["cron"])
            if info:
                tasks.append(info)
        return tasks

    @staticmethod
    def _cron_to_schedule_info(name: str, cron_line: str) -> ScheduleInfo | None:
        """Convert a cron line to ScheduleInfo."""
        parts = cron_line.strip().split()
        if len(parts) < 6:
            return None

        minute, hour, dom, month, dow = parts[:5]
        command = " ".join(parts[5:])

        if dow == "*" and dom == "*":
            schedule_type = "Daily"
            days = ""
        elif dow != "*":
            schedule_type = "Weekly"
            day_nums = dow.split(",")
            day_names = [_REVERSE_DAY_MAP.get(int(d), "?") for d in day_nums]
            days = ", ".join(day_names)
        else:
            schedule_type = "Daily"
            days = ""

        return ScheduleInfo(
            name=name,
            task_name=f"SCOUT/{name}",
            status="Active",
            schedule_type=schedule_type,
            start_time=f"{int(hour):02d}:{int(minute):02d}",
            next_run="(managed by cron)",
            task_to_run=command,
            days=days,
        )
