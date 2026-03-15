"""Tests for the Native Messaging host script."""

import json
import os
import struct
import subprocess
import sys
import tempfile

import pytest


def _encode_nm_message(obj: dict) -> bytes:
    """Encode a dict as a Chrome NM wire-format message."""
    body = json.dumps(obj).encode("utf-8")
    return struct.pack("<I", len(body)) + body


def _decode_nm_message(data: bytes) -> dict:
    """Decode a Chrome NM wire-format response."""
    if len(data) < 4:
        pytest.fail(f"Response too short: {len(data)} bytes")
    length = struct.unpack("<I", data[:4])[0]
    body = data[4:4 + length]
    return json.loads(body)


NM_HOST_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "native-messaging-host",
    "scout_nm_host.py",
)


def _run_nm_host(input_msg: dict) -> dict:
    """Run the NM host script with the given input message and return the response."""
    encoded = _encode_nm_message(input_msg)
    result = subprocess.run(
        [sys.executable, NM_HOST_SCRIPT],
        input=encoded,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 0, f"NM host exited with {result.returncode}: {result.stderr.decode()}"
    return _decode_nm_message(result.stdout)


class TestNMHostTokenRead:
    """Test token file reading."""

    def test_returns_token_when_file_exists(self, tmp_path):
        token_file = tmp_path / "scout-extension-token"
        token_file.write_text("abc123deadbeef")

        encoded = _encode_nm_message({"type": "get_token"})
        result = subprocess.run(
            [sys.executable, NM_HOST_SCRIPT],
            input=encoded,
            capture_output=True,
            timeout=5,
            env={**os.environ, "TMPDIR": str(tmp_path), "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        )
        resp = _decode_nm_message(result.stdout)
        assert resp["token"] == "abc123deadbeef"

    def test_returns_error_when_no_token_file(self, tmp_path):
        encoded = _encode_nm_message({"type": "get_token"})
        result = subprocess.run(
            [sys.executable, NM_HOST_SCRIPT],
            input=encoded,
            capture_output=True,
            timeout=5,
            env={**os.environ, "TMPDIR": str(tmp_path), "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        )
        resp = _decode_nm_message(result.stdout)
        assert resp["error"] == "scout_not_running"

    def test_handles_malformed_input(self):
        result = subprocess.run(
            [sys.executable, NM_HOST_SCRIPT],
            input=b"\x00\x00\x00\x00",  # zero-length message
            capture_output=True,
            timeout=5,
        )
        # Should not crash
        assert result.returncode == 0
