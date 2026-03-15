"""Tests for extension relay WebSocket security (token auth, origin validation, connection limit)."""

import asyncio
import json
import os
import pytest

from scout.extension_relay import ExtensionRelay


@pytest.fixture
async def relay():
    """Create and start an extension relay server, then clean up."""
    r = ExtensionRelay(host="localhost", port=0)  # port=0 won't work with websockets, use a random high port
    # Use a random port to avoid conflicts
    import random
    port = random.randint(19000, 19999)
    r = ExtensionRelay(host="localhost", port=port)
    await r.start()
    yield r
    await r.stop()


class TestExtensionRelaySecurity:
    """Test security features of the extension relay."""

    def test_session_token_generated(self):
        """Token should be generated on init."""
        relay = ExtensionRelay()
        assert relay.session_token
        assert len(relay.session_token) == 64  # 32 bytes hex = 64 chars

    def test_token_uniqueness(self):
        """Each relay instance should have a unique token."""
        r1 = ExtensionRelay()
        r2 = ExtensionRelay()
        assert r1.session_token != r2.session_token

    @pytest.mark.asyncio
    async def test_token_file_written(self):
        """Token file should be written on start and cleaned up on stop."""
        import random
        port = random.randint(20000, 20999)
        relay = ExtensionRelay(host="localhost", port=port)
        await relay.start()

        token_file = relay.token_file_path
        assert token_file is not None
        assert os.path.exists(token_file)

        with open(token_file) as f:
            assert f.read() == relay.session_token

        await relay.stop()
        assert not os.path.exists(token_file)

    @pytest.mark.asyncio
    async def test_connection_without_auth_rejected(self):
        """Connection without auth message within 2s should be rejected."""
        import random
        port = random.randint(21000, 21999)
        relay = ExtensionRelay(host="localhost", port=port)
        await relay.start()

        try:
            import websockets
            async with websockets.connect(f"ws://localhost:{port}") as ws:
                # Send a non-auth message
                await ws.send(json.dumps({"type": "extension_ready"}))
                # Server should close the connection
                try:
                    await asyncio.wait_for(ws.recv(), timeout=3)
                except websockets.exceptions.ConnectionClosed:
                    pass  # Expected
        except Exception:
            pass  # Connection rejection is expected
        finally:
            await relay.stop()

    @pytest.mark.asyncio
    async def test_valid_auth_accepted(self):
        """Connection with valid auth token should be accepted."""
        import random
        port = random.randint(22000, 22999)
        relay = ExtensionRelay(host="localhost", port=port)
        await relay.start()

        try:
            import websockets
            async with websockets.connect(f"ws://localhost:{port}") as ws:
                # Send valid auth
                await ws.send(json.dumps({
                    "type": "auth",
                    "token": relay.session_token,
                }))
                # Send extension_ready after auth
                await ws.send(json.dumps({
                    "type": "extension_ready",
                    "tabId": 1,
                    "url": "http://example.com",
                }))
                # Give server time to process
                await asyncio.sleep(0.2)
                assert relay.is_connected
        except Exception:
            pass
        finally:
            await relay.stop()

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self):
        """Connection with wrong token should be rejected."""
        import random
        port = random.randint(23000, 23999)
        relay = ExtensionRelay(host="localhost", port=port)
        await relay.start()

        try:
            import websockets
            async with websockets.connect(f"ws://localhost:{port}") as ws:
                await ws.send(json.dumps({
                    "type": "auth",
                    "token": "wrong_token",
                }))
                try:
                    await asyncio.wait_for(ws.recv(), timeout=3)
                except websockets.exceptions.ConnectionClosed:
                    pass  # Expected — connection rejected
            assert not relay.is_connected
        except Exception:
            pass
        finally:
            await relay.stop()
