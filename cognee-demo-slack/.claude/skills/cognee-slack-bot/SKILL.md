---
name: cognee-slack-bot
description: Build and verify a Cognee-powered Slack bot demo with /cognee-ask and /cognee-remember slash commands, using FastAPI, ngrok, Anthropic Claude as the LLM, and local fastembed embeddings. Use this skill whenever someone wants to set up the cognee Slack integration demo, build a Slack memory bot, connect cognee to Slack, replicate the hackathon Slack bot, or debug why their cognee Slack commands return errors like "invalid signature", "dispatch_failed", or Internal Server Error. Also use it when someone mentions cognee remember/recall with Slack slash commands, even if they don't say "bot".
---

# Cognee Slack Bot Demo

Build a minimal Slack bot backed by [cognee](https://github.com/topoteretes/cognee) memory:
`/cognee-remember <fact>` stores a fact in a knowledge graph, `/cognee-ask <question>` recalls it.
Everything below was verified end-to-end on a real setup; each step ends with a **Checkpoint** —
run it before moving on, because later failures almost always trace back to a skipped checkpoint.
When something fails, jump to the **Failure modes** table at the bottom and grep for the exact error string.

Architecture (deliberately minimal for a demo): one FastAPI endpoint receiving Slack slash commands,
Slack request-signature verification as the only security layer, one shared cognee dataset for the
whole workspace, replies sent back directly in the HTTP response (so no bot token or OAuth needed).

## Prerequisites

- Python 3.11+ with `venv`
- An Anthropic API key (any Claude-capable key)
- `ngrok` installed (free tier is fine)
- Rights to create a Slack app in some workspace

## Step 1 — Scaffold the project

Copy the five files from this skill's `assets/` directory into a fresh project directory:

| File | Purpose |
|---|---|
| `app.py` | FastAPI server: signature check + `/cognee-ask` + `/cognee-remember` handlers |
| `test_app.py` | Self-check with cognee mocked — no API key needed to run it |
| `requirements.txt` | Pins cognee to the **dev branch** with the `fastembed` extra |
| `.env.example` | Every env var the demo needs, with working defaults |
| `slack-manifest.yaml` | Slack app definition — has `<public-host>` placeholders to fill in later |

Then create the venv and install:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The install pulls cognee from `git+https://github.com/topoteretes/cognee.git@dev` — the demo
requires the dev branch (`1.5.0.dev*`), not the PyPI release. The `anthropic` package must also be
installed even though it never appears in your code: cognee imports it lazily when
`LLM_PROVIDER=anthropic` and fails at runtime otherwise.

**✅ Checkpoint:**
```bash
.venv/bin/pip show cognee | head -2   # expect Version: 1.5.0.dev1 (or later dev)
.venv/bin/python3 -c "import anthropic, fastembed; print('deps ok')"
```

## Step 2 — Configure environment

```bash
cp .env.example .env
```

Fill in `LLM_API_KEY` with the Anthropic key. Leave the rest as-is — the defaults matter:

```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5          # cheap + fast; supports the structured output cognee needs
EMBEDDING_PROVIDER=fastembed        # local embeddings — WITHOUT this, cognee silently sends
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5   # your Anthropic key to OpenAI's embedding API → 401
EMBEDDING_DIMENSIONS=384
```

Why these embedding lines exist: cognee's embedding config defaults to OpenAI and falls back to
`LLM_API_KEY` as the embedding key. With an Anthropic key that produces a confusing
`Incorrect API key provided: sk-ant-...` error *from OpenAI*. `fastembed` runs locally, needs no
key — but its default model name is still an OpenAI one, so `EMBEDDING_MODEL` must name a model
fastembed actually ships (hence `BAAI/bge-small-en-v1.5`, 384 dims, small download).

`SLACK_SIGNING_SECRET` stays empty for now — it doesn't exist until Step 5.

**✅ Checkpoint — live LLM round-trip (costs a fraction of a cent):**
```bash
set -a && source .env && set +a && .venv/bin/python3 -c "
import asyncio, cognee
async def main():
    await cognee.remember('The sky is blue.', dataset_name='slack')
    r = await cognee.recall('what color is the sky?', datasets=['slack'], top_k=3)
    print('RECALL:', [getattr(x, 'text', x) for x in r[:1]])
asyncio.run(main())"
```
Expect a `RECALL:` line mentioning blue. First run downloads the fastembed model (~30s).
Any error here → Failure modes table; do **not** continue to Slack until this passes.

## Step 3 — Run the mocked self-check

```bash
.venv/bin/python3 test_app.py
```

**✅ Checkpoint:** prints `ok`. This exercises signature verification (valid / invalid / expired)
and command routing with cognee mocked — it proves the web layer independently of the LLM layer,
which is exactly the split you want when debugging later.

## Step 4 — Start the server and tunnel

Two terminals:

```bash
set -a && source .env && set +a && .venv/bin/python3 app.py   # terminal 1 — port 8000
ngrok http 8000                                                # terminal 2
```

Always start the server with the **venv's** python (`.venv/bin/python3`), never bare `python3` —
running under the system interpreter (where the right cognee isn't installed) is the single most
common failure in this setup, and it produces misleading 500s much later. Also: env vars are read
at startup, so **restart the server after any `.env` change** — and if a stale copy is holding
port 8000 you'll get `address already in use`; find it with `lsof -nP -iTCP:8000 -sTCP:LISTEN`.

Note the ngrok forwarding URL (e.g. `https://something.ngrok-free.dev`).

**✅ Checkpoint:**
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<your-ngrok-host>/docs   # expect 200
```
Also verify the right interpreter: the server's startup log prints a `database_path` — it must
contain `.venv/`, not `/Library/Frameworks/...` or another system path.

## Step 5 — Create the Slack app

1. Edit `slack-manifest.yaml`: replace `<public-host>` with the ngrok host in **both** command
   URLs (missing one causes `dispatch_failed` for that command only — a confusingly asymmetric failure).
2. Go to https://api.slack.com/apps → **Create New App** → **From an app manifest** → paste the file.
3. Install the app to the workspace.
4. Copy **Signing Secret** from *Basic Information* into `.env` as `SLACK_SIGNING_SECRET`.
5. **Restart the server** (step 4 note — it won't see the new secret otherwise).

If you later edit the manifest (add a command, change a URL), Slack requires **reinstalling the
app to the workspace** before the change takes effect client-side.

**✅ Checkpoint — simulate a signed Slack request without Slack:**
```bash
source .env
TS=$(date +%s)
BODY="command=%2Fcognee-ask&text=what+color+is+the+sky%3F"
SIG="v0=$(printf '%s' "v0:${TS}:${BODY}" | openssl dgst -sha256 -hmac "$SLACK_SIGNING_SECRET" | sed 's/^.* //')"
curl -s -X POST "https://<your-ngrok-host>/api/v1/slack/commands" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "X-Slack-Request-Timestamp: $TS" -H "X-Slack-Signature: $SIG" --data "$BODY"
```
Expect a JSON reply with the remembered fact. A `401` here means secret mismatch; a `500` means
the web layer is fine but cognee is failing — check the server terminal and `~/.cognee/logs/`.

## Step 6 — Test in Slack

In any channel of the workspace:

```
/cognee-remember The hackathon demo bot is built with FastAPI and cognee
/cognee-ask what is the demo bot built with?
```

Both replies are ephemeral (only you see them). Recall should answer from the stored fact.
🎉 Done.

## Failure modes

Grep this table for the exact error string you're seeing. Every row is a failure that actually
occurred while building the reference setup.

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'anthropic'` (from cognee) | cognee imports the SDK lazily for `LLM_PROVIDER=anthropic` | `.venv/bin/pip install anthropic` |
| `LLMAPIKeyNotSetError: LLM API key is not set` | `.env` not loaded into the process | Start with `set -a && source .env && set +a` prefix, or check `load_dotenv()` runs |
| `Incorrect API key provided: sk-ant-...` from **OpenAI**, or `EmbeddingException` | Embeddings defaulted to OpenAI, reusing your Anthropic key | Set `EMBEDDING_PROVIDER=fastembed` (+ model/dims lines from Step 2), restart |
| `fastembed is required for FastembedEmbeddingEngine but is not installed` | Plain `cognee` installed without the extra | `.venv/bin/pip install 'cognee[fastembed] @ git+https://github.com/topoteretes/cognee.git@dev'` |
| `Model openai/text-embedding-3-large is not supported in TextEmbedding` | `EMBEDDING_PROVIDER=fastembed` set but `EMBEDDING_MODEL` left at default | Set `EMBEDDING_MODEL=BAAI/bge-small-en-v1.5` and `EMBEDDING_DIMENSIONS=384` |
| `[Errno 48] address already in use` on startup | A stale server still owns port 8000 — often started earlier with old config | `lsof -nP -iTCP:8000 -sTCP:LISTEN`, kill that PID, start fresh |
| HTTP 500 from the endpoint while a standalone cognee script works | Server runs the **system** python, not the venv (or has stale env) | Check `database_path` in server startup log; restart with `.venv/bin/python3 app.py` |
| `401 {"detail": "invalid signature"}` on your own test curl | Secret mismatch, stale server, or timestamp >5 min old | Re-copy the Signing Secret, restart server, use a fresh `date +%s` |
| `dispatch_failed` in Slack for **one** command but not the other | That command's URL still has `<public-host>` or an old ngrok host | Fix the manifest URL, **reinstall the app** to the workspace |
| `operation_timeout` in Slack while your own curl works fine | Slack enforces a 3s reply deadline; cognee calls take ~3.5s+ | Already handled in the bundled `app.py`: it acks with "Working on it…" instantly and posts the real answer to Slack's `response_url`. If you see this, your `app.py` predates that fix — re-copy it from assets |
| `pip install -r requirements.txt` doesn't change the cognee version | pip keeps an already-satisfied `cognee` | Add `--upgrade`, or `--force-reinstall --no-deps` for just cognee |
| `SSLCertVerificationError: unable to get local issuer certificate` posting to `hooks.slack.com` | macOS python.org-installer Python has no system CA certs; aiohttp (unlike httpx/litellm) doesn't bundle certifi | Already handled in the bundled `app.py` (`ssl.create_default_context(cafile=certifi.where())`); if hand-rolling, pass that context to the POST, or run `/Applications/Python 3.14/Install Certificates.command` once |
| ngrok URL stopped working after restart | Free tier mints a new host per run | Update the manifest URLs (and reinstall the app), or reserve a static domain |

## What's deliberately left out (add only if you need it)

- **Per-user memory** — everyone shares one `slack` dataset. Real per-person memory needs the
  `/cognee-link` OAuth flow from the [official integration docs](https://docs.cognee.ai/integrations/slack-integration).
- **Bot token / `chat.postMessage`** — replies ride the slash-command HTTP response, so the app
  needs only the `commands` scope.
- **"Remember this" message shortcut, channel allowlists, share-to-channel buttons** — see the
  official docs if the demo grows into a product.
