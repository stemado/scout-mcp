"""Async OTP polling for 2FA SMS codes via Twilio Messages API."""
from __future__ import annotations

import asyncio
import re
import time

import httpx

# Local alias — allows tests to patch scout.otp._monotonic without affecting
# the asyncio event loop, which also calls time.monotonic internally.
_monotonic = time.monotonic

_TWILIO_MESSAGES_URL = (
    "https://api.twilio.com/2010-04-01/Accounts/{account_sid}"
    "/Messages.json?To=%2B{phone_number}&PageSize=5"
)
_DEFAULT_POLL_INTERVAL_S = 3.0


async def poll_for_otp(
    account_sid: str,
    auth_token: str,
    phone_number: str,
    app_keyword: str,
    code_pattern: str = r"\d{6}",
    timeout: float = 60.0,
    poll_interval: float = _DEFAULT_POLL_INTERVAL_S,
) -> str:
    """Poll Twilio Messages API until a new SMS matching app_keyword arrives.

    Captures a baseline inbox state at call time, then polls every
    poll_interval seconds until a new message matching app_keyword contains
    a code matching code_pattern, or timeout seconds elapse.

    Args:
        account_sid: Twilio Account SID (e.g. 'ACxxxxxxxxxxxxxxxx').
        auth_token: Twilio Auth Token.
        phone_number: Digits-only phone number receiving 2FA SMS (e.g. '14155551234').
        app_keyword: Case-insensitive substring to match in SMS body (e.g. 'paycom').
        code_pattern: Regex to extract the code. Default: r'\\d{6}'.
        timeout: Seconds before raising TimeoutError. Default: 60.
        poll_interval: Seconds between polls. Default: 3.

    Returns:
        The extracted OTP code string (e.g. '847291').

    Raises:
        TimeoutError: No matching code received within timeout seconds.
        httpx.HTTPStatusError: Twilio API returned an error status.
    """
    # Normalize phone number — strip all non-digit characters so users can
    # paste numbers in any format (+1-415-555-1234, (415) 555-1234, etc.)
    phone_number = re.sub(r"[^\d]", "", phone_number)
    if not phone_number:
        raise ValueError("phone_number must contain at least one digit")
    url = _TWILIO_MESSAGES_URL.format(
        account_sid=account_sid,
        phone_number=phone_number,
    )
    keyword_re = re.compile(re.escape(app_keyword), re.IGNORECASE)
    code_re = re.compile(code_pattern)
    deadline = _monotonic() + timeout

    async with httpx.AsyncClient() as client:
        # Capture baseline — record most recent message SID before 2FA is triggered.
        # Claude should call this tool AFTER clicking "Send Code" in the browser;
        # Twilio delivery latency (2-10s) gives sufficient buffer.
        baseline_resp = await client.get(
            url, auth=(account_sid, auth_token), timeout=10
        )
        baseline_resp.raise_for_status()
        baseline_msgs = baseline_resp.json().get("messages", [])
        baseline_sid = baseline_msgs[0]["sid"] if baseline_msgs else None

        while _monotonic() < deadline:
            await asyncio.sleep(poll_interval)
            resp = await client.get(url, auth=(account_sid, auth_token), timeout=10)
            resp.raise_for_status()
            messages = resp.json().get("messages", [])

            for msg in messages:
                # Twilio returns messages newest-first; stop at baseline.
                if msg["sid"] == baseline_sid:
                    break
                body = msg.get("body", "")
                if not keyword_re.search(body):
                    continue
                match = code_re.search(body)
                if match:
                    return match.group(0)  # group(0)=full match; default pattern has no capture group

    raise TimeoutError(
        f"No 2FA code for '{app_keyword}' received within {timeout}s"
    )
