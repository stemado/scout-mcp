"""WebSocket relay server and CDP adapter for Chrome extension connection mode.

When connection_mode='extension', Scout connects to the user's existing Chrome
browser via a Chrome extension that bridges chrome.debugger CDP access over
WebSocket. This module provides:

  - ExtensionRelay: async WebSocket server that accepts the extension connection
  - ExtensionDriver: sync CDP adapter matching the botasaurus Driver interface
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import random
import threading
import time
import uuid
from typing import TYPE_CHECKING, Any, Generator

logger = logging.getLogger(__name__)


class _AttrDict(dict):
    """Dict subclass that allows attribute access — bridges CDP JSON dicts
    to the attribute-access interface that botasaurus-driver's callbacks expect.
    """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            # Try camelCase -> snake_case conversion
            snake = "".join(f"_{c.lower()}" if c.isupper() else c for c in name)
            if snake in self:
                return self[snake]
            raise AttributeError(f"No attribute '{name}'")


# Default relay server settings
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9222
DEFAULT_PATH = "/scout-extension"
CONNECT_TIMEOUT = 15  # seconds to wait for extension to connect


class ExtensionRelay:
    """Async WebSocket server that relays CDP commands between Scout and the Chrome extension.

    Lifecycle:
        1. start() — launches the WebSocket server
        2. wait_for_extension() — blocks until extension connects or timeout
        3. send_cdp_command() — sends a CDP command and waits for response
        4. stop() — shuts down the server and cleans up
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self._host = host
        self._port = port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server_task: asyncio.Task | None = None
        self._ws = None  # Active WebSocket connection
        self._connected = threading.Event()
        self._stop_event = asyncio.Event()

        # Extension metadata received on connection
        self.tab_id: int | None = None
        self.tab_url: str = "about:blank"

        # Request/response matching for CDP commands
        self._pending: dict[str, threading.Event] = {}
        self._responses: dict[str, dict] = {}
        self._lock = threading.Lock()

        # CDP event callbacks: method -> list of callbacks
        self._event_handlers: dict[str, list] = {}
        self._event_handler_lock = threading.Lock()

        # Network event callbacks (mirroring Driver API)
        self._request_callbacks: list = []
        self._response_callbacks: list = []

        self._server = None

    async def start(self) -> None:
        """Start the WebSocket server."""
        try:
            import websockets
            import websockets.asyncio.server
        except ImportError:
            raise ImportError(
                "websockets package required for extension mode. "
                "Install with: uv add websockets"
            )

        self._loop = asyncio.get_running_loop()

        self._server = await websockets.asyncio.server.serve(
            self._handle_connection,
            self._host,
            self._port,
        )
        logger.info("Extension relay server listening on ws://%s:%d%s",
                     self._host, self._port, DEFAULT_PATH)

    async def _handle_connection(self, websocket) -> None:
        """Handle a WebSocket connection from the Chrome extension."""
        logger.info("Extension connected from %s", websocket.remote_address)
        self._ws = websocket
        self._connected.set()

        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from extension: %s", raw_message[:200])
                    continue

                msg_type = message.get("type")

                if msg_type == "extension_ready":
                    self.tab_id = message.get("tabId")
                    self.tab_url = message.get("url", "about:blank")
                    logger.info("Extension ready: tab=%s url=%s", self.tab_id, self.tab_url)

                elif msg_type == "cdp_response":
                    req_id = message.get("id")
                    if req_id:
                        with self._lock:
                            self._responses[req_id] = message
                            event = self._pending.get(req_id)
                        if event:
                            event.set()

                elif msg_type == "cdp_event":
                    self._dispatch_event(message)

                elif msg_type == "tab_changed":
                    self.tab_id = message.get("tabId")
                    self.tab_url = message.get("url", "about:blank")
                    logger.info("Tab changed: tab=%s url=%s", self.tab_id, self.tab_url)

                else:
                    logger.debug("Unknown message type from extension: %s", msg_type)

        except Exception as e:
            logger.warning("Extension WebSocket closed: %s", e)
        finally:
            self._ws = None
            self._connected.clear()
            # Wake up any pending requests with an error
            with self._lock:
                for req_id, event in self._pending.items():
                    if req_id not in self._responses:
                        self._responses[req_id] = {
                            "error": "Extension disconnected"
                        }
                    event.set()

    def _dispatch_event(self, message: dict) -> None:
        """Dispatch a CDP event to registered handlers."""
        method = message.get("method", "")
        params = message.get("params", {})

        # Dispatch to method-specific handlers
        with self._event_handler_lock:
            handlers = self._event_handlers.get(method, [])

        for handler in handlers:
            try:
                handler(params)
            except Exception as e:
                logger.warning("Event handler error for %s: %s", method, e)

        # Dispatch network events to Driver-compatible callbacks.
        # NetworkMonitor._on_request expects (request_id, request, event)
        # where request/event have attribute access (.url, .method, etc.)
        if method == "Network.requestWillBeSent":
            request_id = params.get("requestId", "")
            request = _AttrDict(params.get("request", {}))
            event = _AttrDict(params)
            for cb in self._request_callbacks:
                try:
                    cb(request_id, request, event)
                except Exception as e:
                    logger.warning("Request callback error: %s", e)
        elif method == "Network.responseReceived":
            request_id = params.get("requestId", "")
            response_data = params.get("response", {})
            # Map CDP camelCase to botasaurus attribute names
            response_data["mime_type"] = response_data.pop("mimeType", "")
            response = _AttrDict(response_data)
            event = _AttrDict(params)
            for cb in self._response_callbacks:
                try:
                    cb(request_id, response, event)
                except Exception as e:
                    logger.warning("Response callback error: %s", e)

    def wait_for_extension(self, timeout: float = CONNECT_TIMEOUT) -> bool:
        """Block until the extension connects. Returns True if connected."""
        return self._connected.wait(timeout=timeout)

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set() and self._ws is not None

    def send_cdp_command_sync(self, method: str, params: dict | None = None,
                               timeout: float = 30.0) -> dict:
        """Send a CDP command and wait for the response (sync, thread-safe).

        This is called from worker threads via ExtensionDriver.
        """
        if not self.is_connected:
            raise RuntimeError("Extension not connected")

        req_id = uuid.uuid4().hex[:8]
        event = threading.Event()

        with self._lock:
            self._pending[req_id] = event

        message = json.dumps({
            "type": "cdp_command",
            "id": req_id,
            "method": method,
            "params": params or {},
        })

        # Schedule the send on the async event loop
        future = asyncio.run_coroutine_threadsafe(
            self._ws.send(message), self._loop
        )
        future.result(timeout=5)  # Wait for send to complete

        # Wait for response
        if not event.wait(timeout=timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            raise TimeoutError(f"CDP command {method} timed out after {timeout}s")

        with self._lock:
            self._pending.pop(req_id, None)
            response = self._responses.pop(req_id, {})

        if "error" in response:
            raise RuntimeError(f"CDP error ({method}): {response['error']}")

        return response.get("result", {})

    def add_event_handler(self, method: str, callback) -> None:
        """Register a handler for CDP events of the given method."""
        with self._event_handler_lock:
            self._event_handlers.setdefault(method, []).append(callback)

    async def stop(self) -> None:
        """Shut down the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._ws = None
        self._connected.clear()


class _FakeTab:
    """Mimics driver._tab interface for code that accesses it directly."""

    def __init__(self, relay: ExtensionRelay) -> None:
        self._relay = relay

    def send(self, cmd: Generator, wait_for_response: bool = True) -> Any:
        """Send a CDP command using the generator protocol."""
        request = next(cmd)
        method = request["method"]
        params = request.get("params", {})

        if not wait_for_response:
            # Fire-and-forget (used by screencast frame ACK)
            if self._relay.is_connected and self._relay._loop:
                msg = json.dumps({
                    "type": "cdp_command",
                    "id": uuid.uuid4().hex[:8],
                    "method": method,
                    "params": params,
                    "no_response": True,
                })
                asyncio.run_coroutine_threadsafe(
                    self._relay._ws.send(msg), self._relay._loop
                )
            return None

        result = self._relay.send_cdp_command_sync(method, params)
        try:
            cmd.send(result)
        except StopIteration as e:
            return e.value
        return None

    def add_handler(self, event_class, callback) -> None:
        """Register a CDP event handler.

        The event_class is a PyCDP event class. We extract the CDP event name
        from the class and register a wrapper that constructs the event object.
        """
        # PyCDP event classes have a from_json classmethod and
        # their CDP method name can be derived from module + class name
        module = event_class.__module__
        class_name = event_class.__name__

        # e.g. botasaurus_driver.cdp.page -> "Page"
        # event class "ScreencastFrame" -> "Page.screencastFrame"
        domain = module.rsplit(".", 1)[-1]
        # Strip trailing underscore (PyCDP uses input_ to avoid Python keyword)
        domain = domain.rstrip("_")
        # Convert domain to PascalCase (e.g. "page" -> "Page", "browser" -> "Browser")
        domain_pascal = domain.capitalize()
        # Convert class name to camelCase for CDP method
        event_name = class_name[0].lower() + class_name[1:]
        cdp_method = f"{domain_pascal}.{event_name}"

        def wrapper(params: dict):
            try:
                event_obj = event_class.from_json(params)
                callback(event_obj)
            except Exception as e:
                logger.warning("Event handler wrapper error for %s: %s", cdp_method, e)

        self._relay.add_event_handler(cdp_method, wrapper)


class _FakeBrowser:
    """Mimics driver._browser interface."""

    def __init__(self, relay: ExtensionRelay) -> None:
        self._relay = relay
        self._info: dict | None = None

    @property
    def info(self) -> dict:
        if self._info is None:
            try:
                result = self._relay.send_cdp_command_sync(
                    "Browser.getVersion", timeout=5.0
                )
                self._info = {
                    "User-Agent": result.get("userAgent", ""),
                    "Browser": result.get("product", ""),
                    "Protocol-Version": result.get("protocolVersion", ""),
                }
            except Exception:
                self._info = {}
        return self._info


class _ExtensionElement:
    """Minimal element-like object for extension mode.

    Provides click(), type(), clear(), select_option(), run_js() that work
    via CDP command relay. Matches the interface used by actions.py.
    """

    def __init__(self, relay: ExtensionRelay, selector: str) -> None:
        self._relay = relay
        self._selector = selector

    def click(self, selector: str | None = None) -> None:
        sel = selector or self._selector
        js = f"""
        (() => {{
            const el = document.querySelector({json.dumps(sel)});
            if (!el) throw new Error('Element not found: ' + {json.dumps(sel)});
            el.scrollIntoView({{block: 'center', behavior: 'instant'}});
            el.click();
        }})()
        """
        self._relay.send_cdp_command_sync("Runtime.evaluate", {
            "expression": js,
            "awaitPromise": True,
            "userGesture": True,
        })
        # Humanized delay after click
        time.sleep(random.uniform(0.08, 0.25))

    def type(self, selector: str | None = None, text: str = "",
             clear_existing: bool = False, **kwargs) -> None:
        sel = selector or self._selector
        if isinstance(text, int):
            text = str(text)

        # Focus the element
        focus_js = f"""
        (() => {{
            const el = document.querySelector({json.dumps(sel)});
            if (!el) throw new Error('Element not found: ' + {json.dumps(sel)});
            el.scrollIntoView({{block: 'center', behavior: 'instant'}});
            el.focus();
            if ({json.dumps(clear_existing)}) {{
                el.value = '';
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
            }}
        }})()
        """
        self._relay.send_cdp_command_sync("Runtime.evaluate", {
            "expression": focus_js,
            "awaitPromise": True,
            "userGesture": True,
        })

        # Type characters one by one with humanized delays
        for char in text:
            self._relay.send_cdp_command_sync("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": char,
                "key": char,
                "unmodifiedText": char,
            })
            self._relay.send_cdp_command_sync("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": char,
            })
            time.sleep(random.uniform(0.03, 0.08))

    def clear(self, selector: str | None = None) -> None:
        sel = selector or self._selector
        js = f"""
        (() => {{
            const el = document.querySelector({json.dumps(sel)});
            if (!el) throw new Error('Element not found: ' + {json.dumps(sel)});
            el.focus();
            el.value = '';
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
        }})()
        """
        self._relay.send_cdp_command_sync("Runtime.evaluate", {
            "expression": js,
            "awaitPromise": True,
            "userGesture": True,
        })

    def select_option(self, selector: str | None = None,
                      value: str | None = None, index: int | None = None) -> None:
        sel = selector or self._selector
        if index is not None:
            js = f"""
            (() => {{
                const el = document.querySelector({json.dumps(sel)});
                if (!el) throw new Error('Element not found: ' + {json.dumps(sel)});
                el.selectedIndex = {index};
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }})()
            """
        else:
            js = f"""
            (() => {{
                const el = document.querySelector({json.dumps(sel)});
                if (!el) throw new Error('Element not found: ' + {json.dumps(sel)});
                el.value = {json.dumps(value or '')};
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }})()
            """
        self._relay.send_cdp_command_sync("Runtime.evaluate", {
            "expression": js,
            "awaitPromise": True,
            "userGesture": True,
        })

    def wait_for_element(self, selector: str, wait: float = 10) -> Any:
        """Poll for element existence."""
        deadline = time.time() + wait
        while time.time() < deadline:
            result = self._relay.send_cdp_command_sync("Runtime.evaluate", {
                "expression": f"!!document.querySelector({json.dumps(selector)})",
                "returnByValue": True,
            })
            remote = result.get("result", {})
            if remote.get("value") is True:
                return _ExtensionElement(self._relay, selector)
            time.sleep(0.25)
        raise TimeoutError(f"Element not found within {wait}s: {selector}")

    def upload_file(self, selector: str, file_path: str) -> None:
        """Upload a file via DOM.setFileInputFiles CDP command."""
        # First find the node
        result = self._relay.send_cdp_command_sync("Runtime.evaluate", {
            "expression": f"""
            (() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) throw new Error('Element not found: ' + {json.dumps(selector)});
                return true;
            }})()
            """,
            "returnByValue": True,
            "userGesture": True,
        })

        # Get DOM node ID
        doc_result = self._relay.send_cdp_command_sync("DOM.getDocument", {})
        node_result = self._relay.send_cdp_command_sync("DOM.querySelector", {
            "nodeId": doc_result.get("root", {}).get("nodeId", 1),
            "selector": selector,
        })
        node_id = node_result.get("nodeId")
        if not node_id:
            raise ValueError(f"Element not found for file upload: {selector}")

        self._relay.send_cdp_command_sync("DOM.setFileInputFiles", {
            "files": [file_path],
            "nodeId": node_id,
        })

    def run_js(self, script: str) -> Any:
        """Execute JavaScript and return the result."""
        result = self._relay.send_cdp_command_sync("Runtime.evaluate", {
            "expression": script,
            "returnByValue": True,
            "awaitPromise": True,
            "userGesture": True,
        })
        remote = result.get("result", {})
        exception = result.get("exceptionDetails")
        if exception:
            text = exception.get("text", "")
            exc_obj = exception.get("exception", {})
            desc = exc_obj.get("description", text)
            raise RuntimeError(f"JavaScript error: {desc}")
        return remote.get("value")


class _ExtensionIframe:
    """Iframe handle for extension mode.

    Executes JS in the iframe's context using Runtime.evaluate with
    the iframe's execution context ID.
    """

    def __init__(self, relay: ExtensionRelay, selector: str) -> None:
        self._relay = relay
        self._selector = selector
        self._context_id: int | None = None

    def _get_context_id(self) -> int:
        """Get the execution context ID for this iframe."""
        if self._context_id is not None:
            return self._context_id

        # Find iframe's contentWindow execution context
        js = f"""
        (() => {{
            const iframe = document.querySelector({json.dumps(self._selector)});
            if (!iframe) throw new Error('Iframe not found: ' + {json.dumps(self._selector)});
            if (!iframe.contentDocument) throw new Error('Cannot access iframe (cross-origin?): ' + {json.dumps(self._selector)});
            return true;
        }})()
        """
        self._relay.send_cdp_command_sync("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
        })

        # Use Page.getFrameTree to find the frame ID, then get its context
        frame_tree = self._relay.send_cdp_command_sync("Page.getFrameTree", {})
        frame_id = self._find_frame_id(frame_tree.get("frameTree", {}))

        if frame_id:
            # Create an isolated world or use the default context
            result = self._relay.send_cdp_command_sync(
                "Page.createIsolatedWorld", {
                    "frameId": frame_id,
                    "worldName": "scout_iframe",
                    "grantUniveralAccess": True,
                }
            )
            self._context_id = result.get("executionContextId")

        if self._context_id is None:
            raise RuntimeError(f"Could not get execution context for iframe: {self._selector}")

        return self._context_id

    def _find_frame_id(self, tree: dict) -> str | None:
        """Recursively find frame ID matching our iframe selector."""
        frame = tree.get("frame", {})
        # Check child frames
        for child in tree.get("childFrames", []):
            child_frame = child.get("frame", {})
            # Match by name or URL
            frame_id = child_frame.get("id")
            if frame_id:
                return frame_id
            deeper = self._find_frame_id(child)
            if deeper:
                return deeper
        return None

    def run_js(self, script: str) -> Any:
        """Execute JavaScript in the iframe context."""
        try:
            ctx_id = self._get_context_id()
            result = self._relay.send_cdp_command_sync("Runtime.evaluate", {
                "expression": script,
                "contextId": ctx_id,
                "returnByValue": True,
                "awaitPromise": True,
                "userGesture": True,
            })
        except Exception:
            # Fallback: evaluate in the iframe via contentWindow
            result = self._relay.send_cdp_command_sync("Runtime.evaluate", {
                "expression": f"""
                (() => {{
                    const iframe = document.querySelector({json.dumps(self._selector)});
                    if (!iframe || !iframe.contentWindow) return null;
                    return iframe.contentWindow.eval({json.dumps(script)});
                }})()
                """,
                "returnByValue": True,
                "awaitPromise": True,
                "userGesture": True,
            })

        remote = result.get("result", {})
        exception = result.get("exceptionDetails")
        if exception:
            text = exception.get("text", "")
            exc_obj = exception.get("exception", {})
            desc = exc_obj.get("description", text)
            raise RuntimeError(f"JavaScript error in iframe: {desc}")
        return remote.get("value")

    # Delegate DOM interaction methods to an element within the iframe
    def click(self, selector: str) -> None:
        self.run_js(f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) throw new Error('Element not found in iframe: ' + {json.dumps(selector)});
            el.scrollIntoView({{block: 'center', behavior: 'instant'}});
            el.click();
        }})()
        """)
        time.sleep(random.uniform(0.08, 0.25))

    def type(self, selector: str, text: str = "", clear_existing: bool = False, **kwargs) -> None:
        if isinstance(text, int):
            text = str(text)
        self.run_js(f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) throw new Error('Element not found in iframe: ' + {json.dumps(selector)});
            el.focus();
            if ({json.dumps(clear_existing)}) {{
                el.value = '';
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
            }}
        }})()
        """)
        for char in text:
            self._relay.send_cdp_command_sync("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": char,
                "key": char,
                "unmodifiedText": char,
            })
            self._relay.send_cdp_command_sync("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": char,
            })
            time.sleep(random.uniform(0.03, 0.08))

    def clear(self, selector: str) -> None:
        self.run_js(f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) throw new Error('Element not found in iframe: ' + {json.dumps(selector)});
            el.focus();
            el.value = '';
            el.dispatchEvent(new Event('input', {{bubbles: true}}));
            el.dispatchEvent(new Event('change', {{bubbles: true}}));
        }})()
        """)

    def select_option(self, selector: str, value: str | None = None,
                      index: int | None = None) -> None:
        if index is not None:
            self.run_js(f"""
            (() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) throw new Error('Element not found in iframe: ' + {json.dumps(selector)});
                el.selectedIndex = {index};
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }})()
            """)
        else:
            self.run_js(f"""
            (() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) throw new Error('Element not found in iframe: ' + {json.dumps(selector)});
                el.value = {json.dumps(value or '')};
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
            }})()
            """)

    def wait_for_element(self, selector: str, wait: float = 10) -> Any:
        deadline = time.time() + wait
        while time.time() < deadline:
            found = self.run_js(f"!!document.querySelector({json.dumps(selector)})")
            if found:
                return self
            time.sleep(0.25)
        raise TimeoutError(f"Element not found in iframe within {wait}s: {selector}")


class ExtensionDriver:
    """Drop-in replacement for botasaurus Driver that routes CDP commands
    through the Chrome extension WebSocket relay.

    Supports all methods/properties used by Scout's actions.py, scout.py,
    network.py, download_manager.py, and screencast.py.
    """

    def __init__(self, relay: ExtensionRelay) -> None:
        self._relay = relay
        self._tab = _FakeTab(relay)
        self._browser = _FakeBrowser(relay)
        self._current_url = relay.tab_url

        # Enable necessary CDP domains
        self._enable_domains()

    def _enable_domains(self) -> None:
        """Enable CDP domains needed by Scout."""
        for domain in ["Page", "DOM", "Runtime", "Network", "Input"]:
            try:
                self._relay.send_cdp_command_sync(f"{domain}.enable", {})
            except Exception as e:
                logger.debug("Failed to enable %s domain: %s", domain, e)

    @property
    def current_url(self) -> str:
        """Get current page URL."""
        try:
            result = self._relay.send_cdp_command_sync("Runtime.evaluate", {
                "expression": "window.location.href",
                "returnByValue": True,
            })
            url = result.get("result", {}).get("value", self._current_url)
            self._current_url = url
            return url
        except Exception:
            return self._current_url

    def get(self, url: str, **kwargs) -> None:
        """Navigate to a URL."""
        self._relay.send_cdp_command_sync("Page.navigate", {"url": url})
        # Wait for load
        time.sleep(0.5)
        try:
            deadline = time.time() + 15
            while time.time() < deadline:
                result = self._relay.send_cdp_command_sync("Runtime.evaluate", {
                    "expression": "document.readyState",
                    "returnByValue": True,
                })
                state = result.get("result", {}).get("value", "")
                if state in ("complete", "interactive"):
                    break
                time.sleep(0.3)
        except Exception:
            pass
        self._current_url = url

    def run_js(self, script: str) -> Any:
        """Execute JavaScript and return the result value."""
        result = self._relay.send_cdp_command_sync("Runtime.evaluate", {
            "expression": script,
            "returnByValue": True,
            "awaitPromise": True,
            "userGesture": True,
        })
        remote = result.get("result", {})
        exception = result.get("exceptionDetails")
        if exception:
            text = exception.get("text", "")
            exc_obj = exception.get("exception", {})
            desc = exc_obj.get("description", text)
            raise RuntimeError(f"JavaScript error: {desc}")
        return remote.get("value")

    def run_cdp_command(self, cmd: Generator) -> Any:
        """Execute a CDP command using the PyCDP generator protocol.

        This is the core method — all cdp.xxx.yyy() calls go through here.
        """
        request = next(cmd)
        method = request["method"]
        params = request.get("params", {})

        result = self._relay.send_cdp_command_sync(method, params)

        try:
            cmd.send(result)
        except StopIteration as e:
            return e.value

        return None

    def click(self, selector: str) -> None:
        elem = _ExtensionElement(self._relay, selector)
        elem.click(selector)

    def type(self, selector: str, text: str = "", **kwargs) -> None:
        elem = _ExtensionElement(self._relay, selector)
        elem.type(selector, text, **kwargs)

    def clear(self, selector: str) -> None:
        elem = _ExtensionElement(self._relay, selector)
        elem.clear(selector)

    def select_option(self, selector: str, **kwargs) -> None:
        elem = _ExtensionElement(self._relay, selector)
        elem.select_option(selector, **kwargs)

    def select(self, selector: str) -> _ExtensionElement:
        """Select an element — returns an element-like object."""
        return _ExtensionElement(self._relay, selector)

    def select_iframe(self, selector: str) -> _ExtensionIframe:
        """Select an iframe — returns an iframe handle."""
        return _ExtensionIframe(self._relay, selector)

    def wait_for_element(self, selector: str, wait: float = 10) -> _ExtensionElement:
        return _ExtensionElement(self._relay, selector).wait_for_element(selector, wait)

    def upload_file(self, selector: str, file_path: str) -> None:
        elem = _ExtensionElement(self._relay, selector)
        elem.upload_file(selector, file_path)

    def before_request_sent(self, callback) -> None:
        """Register a callback for Network.requestWillBeSent events."""
        self._relay._request_callbacks.append(callback)

    def after_response_received(self, callback) -> None:
        """Register a callback for Network.responseReceived events."""
        self._relay._response_callbacks.append(callback)

    def close(self) -> None:
        """Clean up — detach debugger via extension."""
        try:
            if self._relay.is_connected and self._relay._loop:
                msg = json.dumps({"type": "detach"})
                asyncio.run_coroutine_threadsafe(
                    self._relay._ws.send(msg), self._relay._loop
                ).result(timeout=3)
        except Exception:
            pass
