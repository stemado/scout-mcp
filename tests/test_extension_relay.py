"""Tests for the extension relay CDP adapter.

These tests mock the WebSocket connection to verify CDP command routing,
event dispatching, and the ExtensionDriver interface without needing
a real Chrome browser or extension.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from scout.extension_relay import (
    CONNECT_TIMEOUT,
    ExtensionDriver,
    ExtensionRelay,
    _ExtensionElement,
    _ExtensionIframe,
    _FakeBrowser,
    _FakeTab,
    _wrap_for_cdp,
)
from scout.models import ConnectionMode


# --- Helpers ---


class MockRelay:
    """A minimal mock of ExtensionRelay for testing driver methods."""

    def __init__(self):
        self._connected = threading.Event()
        self._connected.set()
        self._ws = True  # Truthy to pass is_connected check
        self._loop = asyncio.new_event_loop()
        self._responses = {}
        self._pending = {}
        self._request_callbacks = []
        self._response_callbacks = []
        self._event_handlers = {}
        self._event_handler_lock = threading.Lock()
        self.tab_id = 1
        self.tab_url = "https://example.com"
        self._command_log = []  # Track commands for assertions
        self._mock_results = {}  # method -> result dict

    @property
    def is_connected(self):
        return self._connected.is_set() and self._ws is not None

    def send_cdp_command_sync(self, method, params=None, timeout=30.0):
        self._command_log.append({"method": method, "params": params or {}})
        if method in self._mock_results:
            result = self._mock_results[method]
            if callable(result):
                return result(params)
            return result
        # Default responses for common methods
        if method == "Runtime.evaluate":
            return {
                "result": {"type": "string", "value": "mock_value"},
            }
        if method == "Browser.getVersion":
            return {
                "userAgent": "MockChrome/1.0",
                "product": "MockChrome",
                "protocolVersion": "1.3",
            }
        if method == "Page.navigate":
            return {"frameId": "main"}
        if method.endswith(".enable"):
            return {}
        return {}

    def add_event_handler(self, method, callback):
        with self._event_handler_lock:
            self._event_handlers.setdefault(method, []).append(callback)

    def wait_for_extension(self, timeout=15):
        return True


# --- IIFE Wrapping Tests ---


class TestWrapForCdp:
    """_wrap_for_cdp wraps scripts with return statements in an IIFE."""

    def test_wraps_script_with_return(self):
        script = 'var x = 1; return x;'
        result = _wrap_for_cdp(script)
        assert result == f"(() => {{ {script} }})()"

    def test_leaves_expression_unwrapped(self):
        script = 'document.title'
        assert _wrap_for_cdp(script) == script

    def test_leaves_void_call_unwrapped(self):
        script = 'window.scrollTo(0, 0)'
        assert _wrap_for_cdp(script) == script

    def test_wraps_multiline_with_return(self):
        script = 'if (!el) return null;\nreturn {x: 1};'
        result = _wrap_for_cdp(script)
        assert result.startswith("(() => {")
        assert result.endswith("})()")


# --- ExtensionRelay Tests ---


class TestExtensionRelay:
    """Tests for the WebSocket relay server."""

    def test_initial_state(self):
        relay = ExtensionRelay()
        assert relay.tab_id is None
        assert relay.tab_url == "about:blank"
        assert not relay.is_connected

    def test_wait_for_extension_timeout(self):
        relay = ExtensionRelay()
        # Should timeout quickly since no extension connects
        assert not relay.wait_for_extension(timeout=0.1)

    def test_send_command_when_disconnected(self):
        relay = ExtensionRelay()
        with pytest.raises(RuntimeError, match="Extension not connected"):
            relay.send_cdp_command_sync("Runtime.evaluate", {"expression": "1+1"})


# --- ExtensionDriver Tests ---


class TestExtensionDriver:
    """Tests for the CDP adapter that replaces botasaurus Driver."""

    def setup_method(self):
        self.relay = MockRelay()
        self.driver = ExtensionDriver(self.relay)

    def test_run_js(self):
        """run_js sends Runtime.evaluate and returns the value."""
        self.relay._mock_results["Runtime.evaluate"] = {
            "result": {"type": "number", "value": 42},
        }
        result = self.driver.run_js("1 + 41")
        assert result == 42

        # Verify the command was sent with correct params
        eval_calls = [c for c in self.relay._command_log if c["method"] == "Runtime.evaluate"]
        last_call = eval_calls[-1]
        assert last_call["params"]["expression"] == "1 + 41"
        assert last_call["params"]["returnByValue"] is True

    def test_run_js_error(self):
        """run_js raises on JavaScript errors."""
        self.relay._mock_results["Runtime.evaluate"] = {
            "result": {"type": "undefined"},
            "exceptionDetails": {
                "text": "ReferenceError",
                "exception": {"description": "ReferenceError: foo is not defined"},
            },
        }
        with pytest.raises(RuntimeError, match="foo is not defined"):
            self.driver.run_js("foo")

    def test_get_navigates(self):
        """get() sends Page.navigate."""
        # Mock readyState check
        self.relay._mock_results["Runtime.evaluate"] = lambda params: {
            "result": {"type": "string", "value": "complete"}
        }
        self.driver.get("https://example.com")

        nav_calls = [c for c in self.relay._command_log if c["method"] == "Page.navigate"]
        assert len(nav_calls) == 1
        assert nav_calls[0]["params"]["url"] == "https://example.com"

    def test_current_url(self):
        """current_url evaluates window.location.href."""
        self.relay._mock_results["Runtime.evaluate"] = lambda params: {
            "result": {"type": "string", "value": "https://test.com/page"}
        }
        assert self.driver.current_url == "https://test.com/page"

    def test_run_cdp_command_generator_protocol(self):
        """run_cdp_command correctly handles PyCDP generator protocol."""
        from botasaurus_driver import cdp

        # Mock the relay to return a proper Runtime.evaluate response
        self.relay._mock_results["Runtime.evaluate"] = {
            "result": {
                "type": "number",
                "value": 2,
                "description": "2",
            }
        }

        cmd = cdp.runtime.evaluate(expression="1+1", return_by_value=True)
        result = self.driver.run_cdp_command(cmd)

        # Result should be parsed by the generator into PyCDP types
        assert result is not None
        remote_object, exception_details = result
        assert remote_object.value == 2
        assert exception_details is None

    def test_run_cdp_command_screenshot(self):
        """run_cdp_command works with Page.captureScreenshot."""
        from botasaurus_driver import cdp

        self.relay._mock_results["Page.captureScreenshot"] = {
            "data": "iVBORw0KGgo=",
        }

        cmd = cdp.page.capture_screenshot(format_="png")
        result = self.driver.run_cdp_command(cmd)

        # captureScreenshot returns base64 data string
        assert result is not None

    def test_run_cdp_command_input_events(self):
        """run_cdp_command works with Input.dispatchKeyEvent."""
        from botasaurus_driver import cdp

        self.relay._mock_results["Input.dispatchKeyEvent"] = {}

        cmd = cdp.input_.dispatch_key_event(
            type_="keyDown",
            key="Enter",
            code="Enter",
            windows_virtual_key_code=13,
        )
        self.driver.run_cdp_command(cmd)

        key_calls = [c for c in self.relay._command_log
                     if c["method"] == "Input.dispatchKeyEvent"]
        assert len(key_calls) >= 1

    def test_click(self):
        """click() sends Runtime.evaluate with scroll + click JS."""
        self.driver.click("#btn")
        eval_calls = [c for c in self.relay._command_log if c["method"] == "Runtime.evaluate"]
        assert len(eval_calls) >= 1
        # Should contain click-related JS
        assert "click" in eval_calls[-1]["params"]["expression"]

    def test_type(self):
        """type() focuses element then dispatches key events."""
        self.driver.type("#input", "abc")

        # Should have focus eval + 3 keyDown + 3 keyUp
        key_calls = [c for c in self.relay._command_log
                     if c["method"] == "Input.dispatchKeyEvent"]
        assert len(key_calls) == 6  # 3 chars * (keyDown + keyUp)

    def test_select(self):
        """select() returns an _ExtensionElement."""
        elem = self.driver.select("#test")
        assert isinstance(elem, _ExtensionElement)

    def test_select_iframe(self):
        """select_iframe() returns an _ExtensionIframe."""
        iframe = self.driver.select_iframe("iframe.content")
        assert isinstance(iframe, _ExtensionIframe)

    def test_before_request_sent(self):
        """before_request_sent registers network callback."""
        cb = MagicMock()
        self.driver.before_request_sent(cb)
        assert cb in self.relay._request_callbacks

    def test_after_response_received(self):
        """after_response_received registers network callback."""
        cb = MagicMock()
        self.driver.after_response_received(cb)
        assert cb in self.relay._response_callbacks

    def test_close(self):
        """close() sends detach message."""
        # close() should not raise even if relay is disconnected
        self.relay._ws = None
        self.relay._connected.clear()
        self.driver.close()  # Should not raise

    def test_enable_domains_on_init(self):
        """Driver enables CDP domains on initialization."""
        enable_calls = [c for c in self.relay._command_log
                        if c["method"].endswith(".enable")]
        domain_names = {c["method"].split(".")[0] for c in enable_calls}
        assert "Page" in domain_names
        assert "DOM" in domain_names
        assert "Runtime" in domain_names
        assert "Network" in domain_names
        assert "Input" in domain_names


# --- _FakeTab Tests ---


class TestFakeTab:
    """Tests for the _FakeTab CDP command relay."""

    def test_send_with_generator(self):
        """send() correctly processes PyCDP generator commands."""
        from botasaurus_driver import cdp

        relay = MockRelay()
        relay._mock_results["Runtime.evaluate"] = {
            "result": {"type": "boolean", "value": True},
        }
        tab = _FakeTab(relay)

        cmd = cdp.runtime.evaluate(expression="true", return_by_value=True)
        result = tab.send(cmd)

        assert result is not None
        remote_object, exception = result
        assert remote_object.value is True

    def test_send_fire_and_forget(self):
        """send(wait_for_response=False) doesn't wait for response."""
        from botasaurus_driver import cdp

        relay = MockRelay()
        # Mock the async send
        relay._ws = MagicMock()
        relay._loop = MagicMock()

        tab = _FakeTab(relay)
        cmd = cdp.page.screencast_frame_ack(session_id=1)

        # Should not raise, just fire and forget
        with patch("asyncio.run_coroutine_threadsafe"):
            result = tab.send(cmd, wait_for_response=False)
        assert result is None


# --- _FakeBrowser Tests ---


class TestFakeBrowser:
    """Tests for the _FakeBrowser info property."""

    def test_info_property(self):
        relay = MockRelay()
        browser = _FakeBrowser(relay)
        info = browser.info

        assert info["User-Agent"] == "MockChrome/1.0"
        assert info["Browser"] == "MockChrome"
        assert info["Protocol-Version"] == "1.3"

    def test_info_caches(self):
        relay = MockRelay()
        browser = _FakeBrowser(relay)

        info1 = browser.info
        info2 = browser.info

        # Should only call Browser.getVersion once
        version_calls = [c for c in relay._command_log
                         if c["method"] == "Browser.getVersion"]
        assert len(version_calls) == 1
        assert info1 is info2


# --- _ExtensionElement Tests ---


class TestExtensionElement:
    """Tests for the element interaction proxy."""

    def test_run_js(self):
        relay = MockRelay()
        relay._mock_results["Runtime.evaluate"] = {
            "result": {"type": "string", "value": "hello"},
        }
        elem = _ExtensionElement(relay, "#test")
        result = elem.run_js("'hello'")
        assert result == "hello"

    def test_clear(self):
        relay = MockRelay()
        elem = _ExtensionElement(relay, "#input")
        elem.clear()

        eval_calls = [c for c in relay._command_log if c["method"] == "Runtime.evaluate"]
        assert len(eval_calls) >= 1
        assert "value = ''" in eval_calls[-1]["params"]["expression"]

    def test_select_option_by_value(self):
        relay = MockRelay()
        elem = _ExtensionElement(relay, "select#color")
        elem.select_option(value="red")

        eval_calls = [c for c in relay._command_log if c["method"] == "Runtime.evaluate"]
        assert len(eval_calls) >= 1
        assert "red" in eval_calls[-1]["params"]["expression"]

    def test_select_option_by_index(self):
        relay = MockRelay()
        elem = _ExtensionElement(relay, "select#size")
        elem.select_option(index=2)

        eval_calls = [c for c in relay._command_log if c["method"] == "Runtime.evaluate"]
        assert len(eval_calls) >= 1
        assert "selectedIndex = 2" in eval_calls[-1]["params"]["expression"]

    def test_wait_for_element_found(self):
        relay = MockRelay()
        relay._mock_results["Runtime.evaluate"] = {
            "result": {"type": "boolean", "value": True},
        }
        elem = _ExtensionElement(relay, "#parent")
        result = elem.wait_for_element("#child", wait=1)
        assert isinstance(result, _ExtensionElement)

    def test_wait_for_element_timeout(self):
        relay = MockRelay()
        relay._mock_results["Runtime.evaluate"] = {
            "result": {"type": "boolean", "value": False},
        }
        elem = _ExtensionElement(relay, "#parent")
        with pytest.raises(TimeoutError, match="Element not found"):
            elem.wait_for_element("#missing", wait=0.3)


# --- ConnectionMode Model Tests ---


class TestConnectionMode:
    """Tests for the ConnectionMode enum."""

    def test_values(self):
        assert ConnectionMode.LAUNCH.value == "launch"
        assert ConnectionMode.EXTENSION.value == "extension"

    def test_from_string(self):
        assert ConnectionMode("launch") == ConnectionMode.LAUNCH
        assert ConnectionMode("extension") == ConnectionMode.EXTENSION

    def test_invalid_mode(self):
        with pytest.raises(ValueError):
            ConnectionMode("invalid")


# --- Event Dispatch Tests ---


class TestEventDispatch:
    """Tests for CDP event forwarding."""

    def test_network_request_callback(self):
        """Network request callbacks receive (request_id, request, event) matching Driver API."""
        from scout.extension_relay import ExtensionRelay

        real_relay = ExtensionRelay()
        cb = MagicMock()
        real_relay._request_callbacks.append(cb)
        real_relay._dispatch_event({
            "method": "Network.requestWillBeSent",
            "params": {
                "requestId": "123",
                "request": {"url": "https://example.com", "method": "GET"},
                "type": "Document",
            },
        })

        cb.assert_called_once()
        request_id, request, event = cb.call_args[0]
        assert request_id == "123"
        assert request.url == "https://example.com"
        assert request.method == "GET"
        assert event.type == "Document"

    def test_network_response_callback(self):
        """Network response callbacks receive (request_id, response, event) matching Driver API."""
        relay = ExtensionRelay()
        cb = MagicMock()
        relay._response_callbacks.append(cb)

        relay._dispatch_event({
            "method": "Network.responseReceived",
            "params": {
                "requestId": "456",
                "response": {"url": "https://example.com", "status": 200, "mimeType": "text/html"},
            },
        })

        cb.assert_called_once()
        request_id, response, event = cb.call_args[0]
        assert request_id == "456"
        assert response.status == 200
        assert response.mime_type == "text/html"

    def test_custom_event_handler(self):
        relay = ExtensionRelay()
        cb = MagicMock()
        relay.add_event_handler("Page.loadEventFired", cb)

        relay._dispatch_event({
            "method": "Page.loadEventFired",
            "params": {"timestamp": 12345.0},
        })

        cb.assert_called_once_with({"timestamp": 12345.0})

    def test_event_handler_error_doesnt_crash(self):
        relay = ExtensionRelay()

        def bad_handler(params):
            raise ValueError("boom")

        relay.add_event_handler("Page.loadEventFired", bad_handler)

        # Should not raise
        relay._dispatch_event({
            "method": "Page.loadEventFired",
            "params": {},
        })


# --- Task 2: Cross-Platform Token File ---


class TestTokenFileCrossPlatform:
    """Token file uses tempfile.gettempdir() and fixed name."""

    def test_token_file_fixed_name_no_pid(self):
        """Token file should be a fixed name, no PID suffix."""
        from scout.extension_relay import TOKEN_FILENAME
        assert TOKEN_FILENAME == "scout-extension-token"
        expected = os.path.join(tempfile.gettempdir(), TOKEN_FILENAME)
        assert "scout-extension-token" in expected
        assert str(os.getpid()) not in expected


class TestServerBindAddress:
    """Server must bind to 127.0.0.1 explicitly."""

    def test_default_host_is_ipv4_loopback(self):
        from scout.extension_relay import DEFAULT_HOST
        assert DEFAULT_HOST == "127.0.0.1"


# --- Task 3: Path Enforcement + auth_ok + TOCTOU ---


class TestPathEnforcement:
    """Server must reject connections to wrong paths."""

    @pytest.mark.asyncio
    async def test_rejects_wrong_path(self):
        """_check_request should return 404 for non-matching paths."""
        relay = ExtensionRelay()
        mock_request = MagicMock()
        mock_request.path = "/wrong-path"
        mock_request.headers = MagicMock()
        mock_request.headers.raw_items.return_value = []

        result = await relay._check_request(None, mock_request)
        assert result is not None
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_accepts_correct_path(self):
        """_check_request should return None for correct path with no Origin."""
        relay = ExtensionRelay()
        mock_request = MagicMock()
        mock_request.path = "/scout-extension"
        mock_request.headers = MagicMock()
        mock_request.headers.raw_items.return_value = []

        result = await relay._check_request(None, mock_request)
        assert result is None

    @pytest.mark.asyncio
    async def test_rejects_web_origin_on_correct_path(self):
        """Web page origins (http/https) should be rejected with 403."""
        relay = ExtensionRelay()
        mock_request = MagicMock()
        mock_request.path = "/scout-extension"
        mock_request.headers = MagicMock()
        mock_request.headers.raw_items.return_value = [("origin", "https://evil.com")]

        result = await relay._check_request(None, mock_request)
        assert result is not None
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_allows_chrome_extension_origin(self):
        """chrome-extension:// origins from MV3 service workers should be allowed."""
        relay = ExtensionRelay()
        mock_request = MagicMock()
        mock_request.path = "/scout-extension"
        mock_request.headers = MagicMock()
        mock_request.headers.raw_items.return_value = [
            ("origin", "chrome-extension://mjialmenlimilhhjgjjjofneeflihccn")
        ]

        result = await relay._check_request(None, mock_request)
        assert result is None


# --- Task 5: NM Registration Wiring ---


class TestNMRegistrationWiring:
    """ensure_native_messaging_host is called during relay start()."""

    @pytest.mark.asyncio
    async def test_start_calls_nm_registration(self):
        with patch("scout.native_messaging.ensure_native_messaging_host") as mock_nm:
            relay = ExtensionRelay()
            try:
                await relay.start()
            except Exception:
                pass  # May fail due to port binding, that's fine
            mock_nm.assert_called_once()
