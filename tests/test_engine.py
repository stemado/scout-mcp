"""Tests for EngineClient."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, mock_open

from scout.engine import EngineClient


# --- Config discovery ---

def test_config_from_local_md(tmp_path):
    """Reads engine_url and engine_api_key from .claude/scout.local.md frontmatter."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://example.com\nengine_api_key: secret-key\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client.base_url == "https://example.com"
    assert client.api_key == "secret-key"


def test_config_from_env_vars(tmp_path, monkeypatch):
    """Falls back to env vars when no .local.md exists."""
    monkeypatch.setenv("SCOUT_ENGINE_URL", "https://env.example.com")
    monkeypatch.setenv("SCOUT_ENGINE_API_KEY", "env-key")
    client = EngineClient(config_dir=tmp_path)
    assert client.base_url == "https://env.example.com"
    assert client.api_key == "env-key"


def test_config_local_md_overrides_env(tmp_path, monkeypatch):
    """local.md takes precedence over env vars."""
    monkeypatch.setenv("SCOUT_ENGINE_URL", "https://env.example.com")
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://file.example.com\nengine_api_key: file-key\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client.base_url == "https://file.example.com"


def test_config_defaults(tmp_path):
    """Defaults to localhost:8000 with no key."""
    client = EngineClient(config_dir=tmp_path)
    assert client.base_url == "http://localhost:8000"
    assert client.api_key == ""


def test_is_configured_true(tmp_path):
    """is_configured returns True when API key is set."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://x.com\nengine_api_key: key\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client.is_configured is True


def test_is_configured_false(tmp_path):
    """is_configured returns False when no API key."""
    client = EngineClient(config_dir=tmp_path)
    assert client.is_configured is False


# --- TLS verification ---

def test_tls_verify_disabled_for_ip(tmp_path):
    """Skip TLS verification when URL is an IP address."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://178.104.0.194\nengine_api_key: k\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client._verify_tls is False


def test_tls_verify_enabled_for_domain(tmp_path):
    """Verify TLS normally when URL is a domain."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://scout.example.com\nengine_api_key: k\n---\n")
    client = EngineClient(config_dir=tmp_path)
    assert client._verify_tls is True


# --- API methods (mocked HTTP) ---

@pytest.fixture
def client(tmp_path):
    """Client with config pointing to a fake server."""
    local_md = tmp_path / ".claude" / "scout.local.md"
    local_md.parent.mkdir(parents=True)
    local_md.write_text("---\nengine_url: https://test.example.com\nengine_api_key: test-key\n---\n")
    return EngineClient(config_dir=tmp_path)


def _response(status_code: int, json: dict | list) -> httpx.Response:
    """Build an httpx.Response with a dummy request (required for raise_for_status)."""
    return httpx.Response(status_code, json=json, request=httpx.Request("GET", "https://test.example.com"))


async def test_sync_workflow(client):
    """sync_workflow POSTs workflow JSON to /api/workflows."""
    workflow = {"name": "test-wf", "steps": []}
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(200, {"id": "abc-123", "name": "test-wf"})
        result = await client.sync_workflow(workflow)
    mock.assert_called_once_with("POST", "/api/workflows", json={"workflow": workflow})
    assert result["id"] == "abc-123"


async def test_list_workflows(client):
    """list_workflows GETs /api/workflows."""
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(200, [{"id": "1", "name": "wf1"}])
        result = await client.list_workflows()
    mock.assert_called_once_with("GET", "/api/workflows")
    assert len(result) == 1


async def test_run(client):
    """run POSTs to /api/workflows/{id}/run."""
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(202, {"id": "exec-1", "status": "pending"})
        result = await client.run("wf-id-123")
    mock.assert_called_once_with("POST", "/api/workflows/wf-id-123/run")
    assert result["status"] == "pending"


async def test_list_executions(client):
    """list_executions GETs /api/executions."""
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(200, [{"id": "e1", "status": "completed"}])
        result = await client.list_executions()
    mock.assert_called_once_with("GET", "/api/executions")
    assert result[0]["status"] == "completed"


async def test_get_execution(client):
    """get_execution GETs /api/executions/{id}."""
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(200, {"id": "e1", "steps": []})
        result = await client.get_execution("e1")
    mock.assert_called_once_with("GET", "/api/executions/e1")
    assert result["id"] == "e1"


async def test_create_schedule(client):
    """create_schedule POSTs to /api/schedules."""
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(200, {"id": "s1"})
        result = await client.create_schedule("wf-id", "0 9 * * MON-FRI", "UTC")
    mock.assert_called_once_with("POST", "/api/schedules", json={
        "workflow_id": "wf-id", "cron_expression": "0 9 * * MON-FRI", "timezone": "UTC"
    })
    assert result["id"] == "s1"


async def test_list_schedules(client):
    """list_schedules GETs /api/schedules."""
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(200, [{"id": "s1"}])
        result = await client.list_schedules()
    mock.assert_called_once_with("GET", "/api/schedules")


async def test_update_schedule(client):
    """update_schedule PUTs to /api/schedules/{id}."""
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(200, {"id": "s1", "enabled": False})
        result = await client.update_schedule("s1", enabled=False)
    mock.assert_called_once_with("PUT", "/api/schedules/s1", json={"enabled": False})


async def test_delete_schedule(client):
    """delete_schedule DELETEs /api/schedules/{id}."""
    with patch.object(client, "_request") as mock:
        mock.return_value = _response(200, {"ok": True})
        result = await client.delete_schedule("s1")
    mock.assert_called_once_with("DELETE", "/api/schedules/s1")
