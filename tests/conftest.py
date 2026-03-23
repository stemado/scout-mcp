"""Shared test fixtures — local HTTP server for integration tests."""

import json
import os
import time
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

# Allow localhost URLs in validation during tests
os.environ["SCOUT_ALLOW_LOCALHOST"] = "1"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class _TestHandler(SimpleHTTPRequestHandler):
    """Serves static fixtures from tests/fixtures/ plus dynamic test endpoints."""

    def do_GET(self):
        if self.path == "/api/data":
            self._json_response({"key": "value", "items": [1, 2, 3]})
        elif self.path == "/api/other":
            self._json_response({"other": True})
        elif self.path == "/download":
            body = b"col1,col2\na,b\n"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="report.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/slow":
            time.sleep(2)
            self._json_response({"slow": True})
        elif self.path == "/redirect-to-metadata":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/bot-block":
            body = b"<html><head><title>Just a moment...</title></head><body><script>challenge()</script></body></html>"
            self.send_response(403)
            self.send_header("Content-Type", "text/html")
            self.send_header("cf-ray", "fake-ray-id")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/plain":
            body = b"This is plain text content."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Suppress server logs during test runs


@pytest.fixture(scope="session")
def test_server():
    """Start a local HTTP server serving test fixtures. Session-scoped."""
    handler = partial(_TestHandler, directory=str(FIXTURES_DIR))
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="session")
def base_url(test_server):
    """Base URL for the local test server."""
    return test_server
