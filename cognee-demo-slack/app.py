import hashlib
import hmac
import os
import ssl
import time

import aiohttp
import certifi
import cognee
import uvicorn
from cognee_community_vector_adapter_qdrant import register  # noqa: F401 registers "qdrant" as a vector_db_provider
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

load_dotenv()

SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
DATASET = "slack"
# macOS framework Python ships without system CA certs wired up; use certifi's bundle.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

app = FastAPI()


def verify_slack_signature(body: bytes, timestamp: str, signature: str, signing_secret: str) -> bool:
    if not timestamp or not signature or not signing_secret:
        return False
    if abs(time.time() - float(timestamp)) > 60 * 5:
        return False
    basestring = f"v0:{timestamp}:".encode() + body
    digest = "v0=" + hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def extract_text(result) -> str:
    for attr in ("text", "content", "answer"):
        value = getattr(result, attr, None)
        if value:
            return value
    return str(result)


async def handle_command(command: str, text: str) -> dict:
    text = text.strip()
    if not text:
        return {"response_type": "ephemeral", "text": f"Usage: `{command} <text>`"}

    if command == "/cognee-remember":
        await cognee.remember(text, dataset_name=DATASET)
        return {"response_type": "ephemeral", "text": f"🧠 Remembered: {text}"}

    if command == "/cognee-ask":
        results = await cognee.recall(text, datasets=[DATASET], top_k=5)
        if not results:
            return {"response_type": "ephemeral", "text": "No memory found for that yet."}
        lines = [extract_text(r) for r in results]
        return {"response_type": "ephemeral", "text": "\n".join(f"• {l}" for l in lines if l)}

    return {"response_type": "ephemeral", "text": f"Unknown command: {command}"}


async def run_and_post_reply(command: str, text: str, response_url: str) -> None:
    try:
        reply = await handle_command(command, text)
    except Exception as exc:
        reply = {"response_type": "ephemeral", "text": f"Something went wrong: {exc}"}
    async with aiohttp.ClientSession() as session:
        await session.post(response_url, json=reply, ssl=SSL_CONTEXT)


@app.post("/api/v1/slack/commands")
async def slack_commands(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    if not verify_slack_signature(
        body,
        request.headers.get("X-Slack-Request-Timestamp", ""),
        request.headers.get("X-Slack-Signature", ""),
        SIGNING_SECRET,
    ):
        raise HTTPException(status_code=401, detail="invalid signature")

    form = await request.form()
    command = form.get("command", "")
    text = form.get("text", "")
    response_url = form.get("response_url", "")

    # Slack requires an ack within 3s; cognee calls take longer, so answer async.
    if response_url:
        background_tasks.add_task(run_and_post_reply, command, text, response_url)
        return JSONResponse({"response_type": "ephemeral", "text": "🧠 Working on it…"})

    reply = await handle_command(command, text)
    return JSONResponse(reply)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
