import asyncio
import hashlib
import hmac
import time
from unittest.mock import AsyncMock, patch

from app import extract_text, handle_command, run_and_post_reply, verify_slack_signature


def test_signature_valid():
    secret = "shh"
    ts = str(int(time.time()))
    body = b"command=/cognee-ask&text=hi"
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:".encode() + body, hashlib.sha256).hexdigest()
    assert verify_slack_signature(body, ts, sig, secret) is True


def test_signature_invalid():
    assert verify_slack_signature(b"x", str(int(time.time())), "v0=bad", "shh") is False


def test_signature_expired():
    secret = "shh"
    ts = str(int(time.time()) - 999)
    body = b"x"
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:".encode() + body, hashlib.sha256).hexdigest()
    assert verify_slack_signature(body, ts, sig, secret) is False


async def _run_handle_command_cases():
    with patch("app.cognee.remember", new=AsyncMock(return_value=None)) as remember_mock:
        reply = await handle_command("/cognee-remember", "the sky is blue")
        remember_mock.assert_awaited_once()
        assert "Remembered" in reply["text"]

    class FakeResult:
        text = "the sky is blue"

    with patch("app.cognee.recall", new=AsyncMock(return_value=[FakeResult()])):
        reply = await handle_command("/cognee-ask", "what color is the sky")
        assert "sky is blue" in reply["text"]

    reply = await handle_command("/cognee-ask", "")
    assert "Usage" in reply["text"]

    reply = await handle_command("/unknown-command", "text")
    assert "Unknown command" in reply["text"]


def test_handle_command():
    asyncio.run(_run_handle_command_cases())


async def _run_async_reply_case():
    posted = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json, **kwargs):
            posted["url"] = url
            posted["json"] = json

    with patch("app.cognee.remember", new=AsyncMock(return_value=None)), \
         patch("app.aiohttp.ClientSession", new=FakeSession):
        await run_and_post_reply("/cognee-remember", "a fact", "https://hooks.slack.test/abc")

    assert posted["url"] == "https://hooks.slack.test/abc"
    assert "Remembered" in posted["json"]["text"]


def test_run_and_post_reply():
    asyncio.run(_run_async_reply_case())


def test_extract_text():
    class R:
        text = "hello"

    assert extract_text(R()) == "hello"

    class Empty:
        pass

    fallback = Empty()
    assert extract_text(fallback) == str(fallback)


if __name__ == "__main__":
    test_signature_valid()
    test_signature_invalid()
    test_signature_expired()
    test_handle_command()
    test_run_and_post_reply()
    test_extract_text()
    print("ok")
