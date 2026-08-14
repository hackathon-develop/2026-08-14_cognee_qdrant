import hashlib
import hmac
import os
import ssl
import time
from datetime import datetime, timezone

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
DEFAULT_DIGEST_WINDOW = "this week"
DIGEST_SECTIONS = (
    ("Decisions", "decisions, agreements, chosen approaches"),
    ("Blockers", "blockers, risks, issues, things that are stuck"),
    ("Owners", "owners, responsibilities, people assigned to work"),
    ("Open questions", "open questions, unresolved topics, pending decisions"),
)


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


def timestamped_memory(text: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"[saved {stamp}] {text}"


def format_bullets(lines: list[str], fallback: str) -> str:
    items = [line.strip() for line in lines if line and line.strip()]
    if not items:
        return fallback
    return "\n".join(f"• {item}" for item in items)


async def build_digest(topic: str) -> dict:
    scope = topic.strip() or DEFAULT_DIGEST_WINDOW
    seen = set()
    sections = []

    for title, hint in DIGEST_SECTIONS:
        query = f"{hint} from {scope} in the Slack team memory dataset"
        results = await cognee.recall(query, datasets=[DATASET], top_k=3)
        lines = []
        for result in results or []:
            text = extract_text(result).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            lines.append(text)
        if lines:
            sections.append(f"*{title}*\n{format_bullets(lines, '')}")

    if not sections:
        return {
            "response_type": "ephemeral",
            "text": f"No digestable memory found for {scope} yet. Add a few `/cognee-remember` items first.",
        }

    header = f"🗞️ Weekly digest for {scope}"
    return {"response_type": "ephemeral", "text": f"{header}\n\n" + "\n\n".join(sections)}


async def handle_command(command: str, text: str) -> dict:
    text = text.strip()
    if not text and command in {"/cognee-remember", "/cognee-ask"}:
        return {"response_type": "ephemeral", "text": f"Usage: `{command} <text>`"}

    if command == "/cognee-remember":
        memory = timestamped_memory(text)
        await cognee.remember(memory, dataset_name=DATASET)
        return {"response_type": "ephemeral", "text": f"🧠 Remembered: {memory}"}

    if command == "/cognee-ask":
        results = await cognee.recall(text, datasets=[DATASET], top_k=5)
        if not results:
            return {"response_type": "ephemeral", "text": "No memory found for that yet."}
        lines = [extract_text(r) for r in results]
        return {"response_type": "ephemeral", "text": format_bullets(lines, "No memory found for that yet.")}

    if command == "/cognee-digest":
        return await build_digest(text)

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
