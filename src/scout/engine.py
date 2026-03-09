"""HTTP client for the scout-engine remote API."""

from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml


_CONFIG_FILENAME = ".claude/scout.local.md"


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def _is_ip_address(url: str) -> bool:
    """Check if the URL's host is an IP address (not a domain)."""
    try:
        host = urlparse(url).hostname or ""
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


class EngineClient:
    """Async wrapper around the scout-engine REST API."""

    def __init__(self, config_dir: Path | None = None):
        config = self._load_config(config_dir or Path.cwd())
        self.base_url: str = config.get("engine_url", "http://localhost:8000")
        self.api_key: str = config.get("engine_api_key", "")
        self._verify_tls: bool = not _is_ip_address(self.base_url)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _load_config(self, config_dir: Path) -> dict:
        """Load config from .claude/scout.local.md, falling back to env vars."""
        config: dict = {}

        # Priority 1: .claude/scout.local.md
        config_file = config_dir / _CONFIG_FILENAME
        if config_file.exists():
            config = _parse_frontmatter(config_file.read_text())

        # Priority 2: env vars (only fill gaps)
        if "engine_url" not in config:
            env_url = os.environ.get("SCOUT_ENGINE_URL")
            if env_url:
                config["engine_url"] = env_url
        if "engine_api_key" not in config:
            env_key = os.environ.get("SCOUT_ENGINE_API_KEY")
            if env_key:
                config["engine_api_key"] = env_key

        return config

    def _headers(self) -> dict:
        """Build request headers with auth if configured."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated request to the engine."""
        url = f"{self.base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(verify=self._verify_tls) as http:
            resp = await http.request(method, url, headers=self._headers(), **kwargs)
        if resp.status_code == 401:
            raise EngineAuthError("API key rejected. Run `/connect` to reconfigure.")
        if resp.status_code == 403:
            raise EngineAuthError("API key rejected. Run `/connect` to reconfigure.")
        return resp

    async def health(self) -> dict:
        """Check engine health."""
        try:
            resp = await self._request("GET", "/api/health")
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise EngineConnectionError(
                f"Cannot reach scout-engine at {self.base_url}. Is the server running?"
            )

    async def sync_workflow(self, workflow: dict) -> dict:
        """Upload a workflow JSON to the engine."""
        resp = await self._request("POST", "/api/workflows", json={"workflow": workflow})
        resp.raise_for_status()
        return resp.json()

    async def list_workflows(self) -> list[dict]:
        """List all workflows on the engine."""
        resp = await self._request("GET", "/api/workflows")
        resp.raise_for_status()
        return resp.json()

    async def run(self, workflow_id: str) -> dict:
        """Trigger a workflow execution."""
        resp = await self._request("POST", f"/api/workflows/{workflow_id}/run")
        resp.raise_for_status()
        return resp.json()

    async def list_executions(self) -> list[dict]:
        """List recent executions."""
        resp = await self._request("GET", "/api/executions")
        resp.raise_for_status()
        return resp.json()

    async def get_execution(self, execution_id: str) -> dict:
        """Get execution detail with step results."""
        resp = await self._request("GET", f"/api/executions/{execution_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_schedule(self, workflow_id: str, cron_expression: str, timezone: str = "UTC") -> dict:
        """Create a cron schedule for a workflow."""
        resp = await self._request("POST", "/api/schedules", json={
            "workflow_id": workflow_id,
            "cron_expression": cron_expression,
            "timezone": timezone,
        })
        resp.raise_for_status()
        return resp.json()

    async def list_schedules(self) -> list[dict]:
        """List all schedules."""
        resp = await self._request("GET", "/api/schedules")
        resp.raise_for_status()
        return resp.json()

    async def update_schedule(self, schedule_id: str, **kwargs) -> dict:
        """Update a schedule (cron, enabled, etc.)."""
        resp = await self._request("PUT", f"/api/schedules/{schedule_id}", json=kwargs)
        resp.raise_for_status()
        return resp.json()

    async def delete_schedule(self, schedule_id: str) -> dict:
        """Delete a schedule."""
        resp = await self._request("DELETE", f"/api/schedules/{schedule_id}")
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def save_config(config_dir: Path, url: str, api_key: str) -> Path:
        """Save engine config to .claude/scout.local.md."""
        config_file = config_dir / _CONFIG_FILENAME
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            f"---\nengine_url: {url}\nengine_api_key: {api_key}\n---\n"
        )
        return config_file


class EngineConnectionError(Exception):
    pass


class EngineAuthError(Exception):
    pass
