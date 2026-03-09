"""Unit tests for scout.otp — 2FA code polling via Twilio Messages API."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scout.otp import poll_for_otp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(sid: str, body: str) -> dict:
    """Build a fake Twilio message dict."""
    return {"sid": sid, "body": body}


def _twilio_resp(*messages: dict) -> MagicMock:
    """Build a mock httpx Response returning a Twilio message list."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"messages": list(messages)}
    return resp


def _mock_client(*responses) -> MagicMock:
    """Build a mock httpx.AsyncClient yielding responses in sequence."""
    client = AsyncMock()
    client.get = AsyncMock(side_effect=list(responses))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_returns_code_when_matching_message_arrives():
    """Returns 6-digit code from first new SMS matching keyword."""
    baseline = _twilio_resp()  # empty inbox at call time
    poll1 = _twilio_resp(_msg("msg001", "847291 is your Paycom authentication code"))
    client = _mock_client(baseline, poll1)

    with (
        patch("scout.otp.httpx.AsyncClient", return_value=client),
        patch("scout.otp.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            poll_for_otp("ACtest", "authtest", "14155551234", "paycom", timeout=10)
        )

    assert result == "847291"


def test_skips_messages_at_or_before_baseline():
    """Messages present in baseline inbox are never matched."""
    # One old message already in inbox before tool is called
    baseline = _twilio_resp(_msg("old001", "111111 is your Paycom code"))
    # Poll 1: same old message, no new ones
    poll1 = _twilio_resp(_msg("old001", "111111 is your Paycom code"))
    # Poll 2: a new message arrives above the old baseline
    poll2 = _twilio_resp(
        _msg("new001", "999999 is your Paycom code"),
        _msg("old001", "111111 is your Paycom code"),
    )
    client = _mock_client(baseline, poll1, poll2)

    with (
        patch("scout.otp.httpx.AsyncClient", return_value=client),
        patch("scout.otp.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            poll_for_otp("ACtest", "authtest", "14155551234", "paycom", timeout=10)
        )

    assert result == "999999"


def test_keyword_filter_is_case_insensitive():
    """app_keyword match is case-insensitive."""
    baseline = _twilio_resp()
    poll1 = _twilio_resp(_msg("msg001", "Your PAYCOM verification code is 123456"))
    client = _mock_client(baseline, poll1)

    with (
        patch("scout.otp.httpx.AsyncClient", return_value=client),
        patch("scout.otp.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            poll_for_otp("ACtest", "authtest", "14155551234", "paycom", timeout=10)
        )

    assert result == "123456"


def test_skips_non_matching_messages():
    """New SMS from a different service is ignored; only keyword match is returned."""
    baseline = _twilio_resp()
    # Poll 1: unrelated SMS arrives (bank OTP, not paycom)
    poll1 = _twilio_resp(_msg("msg001", "Your bank verification code is 000000"))
    # Poll 2: real paycom code arrives on top
    poll2 = _twilio_resp(
        _msg("msg002", "555555 is your Paycom authentication code"),
        _msg("msg001", "Your bank verification code is 000000"),
    )
    client = _mock_client(baseline, poll1, poll2)

    with (
        patch("scout.otp.httpx.AsyncClient", return_value=client),
        patch("scout.otp.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            poll_for_otp("ACtest", "authtest", "14155551234", "paycom", timeout=10)
        )

    assert result == "555555"


def test_raises_timeout_when_no_code_arrives():
    """Raises TimeoutError if no matching SMS arrives before deadline."""
    # Fake monotonic clock: first call sets the deadline; all subsequent calls
    # return a value past the deadline. Using a function (not a finite iterator)
    # so the test stays correct if the implementation adds extra time.monotonic()
    # calls (an iterator would raise StopIteration instead of TimeoutError).
    _called = [False]

    def fake_monotonic() -> float:
        if not _called[0]:
            _called[0] = True
            return 0.0   # deadline = 0.0 + 0.5 = 0.5
        return 999.0     # every subsequent call is past the deadline

    baseline = _twilio_resp()
    client = _mock_client(baseline)  # baseline only — loop body never runs

    with (
        patch("scout.otp.httpx.AsyncClient", return_value=client),
        patch("scout.otp.asyncio.sleep", new_callable=AsyncMock),
        patch("scout.otp._monotonic", side_effect=fake_monotonic),
    ):
        with pytest.raises(TimeoutError, match="paycom"):
            asyncio.run(
                poll_for_otp("ACtest", "authtest", "14155551234", "paycom", timeout=0.5)
            )


# ---------------------------------------------------------------------------
# Input normalization and escaping
# ---------------------------------------------------------------------------

def test_app_keyword_with_regex_metacharacters():
    """Keywords containing regex metacharacters are treated as literals."""
    baseline = _twilio_resp()
    poll1 = _twilio_resp(_msg("msg001", "123456 is your C++ Academy verification code"))
    client = _mock_client(baseline, poll1)

    with (
        patch("scout.otp.httpx.AsyncClient", return_value=client),
        patch("scout.otp.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            poll_for_otp("ACtest", "authtest", "14155551234", "C++", timeout=10)
        )

    assert result == "123456"


def test_phone_number_with_formatting_is_normalized():
    """Phone numbers with non-digit characters are stripped to digits-only."""
    baseline = _twilio_resp()
    poll1 = _twilio_resp(_msg("msg001", "847291 is your Paycom code"))
    client = _mock_client(baseline, poll1)

    with (
        patch("scout.otp.httpx.AsyncClient", return_value=client),
        patch("scout.otp.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            poll_for_otp("ACtest", "authtest", "+1-415-555-1234", "paycom", timeout=10)
        )

    assert result == "847291"


def test_empty_phone_number_raises_value_error():
    """Phone number with no digits raises ValueError before any HTTP call."""
    with pytest.raises(ValueError):
        asyncio.run(
            poll_for_otp("ACtest", "authtest", "+++", "paycom", timeout=10)
        )
