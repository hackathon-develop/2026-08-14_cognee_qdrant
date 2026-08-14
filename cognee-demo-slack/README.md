# Cognee Slack demo

Minimal Slack bot:

- `/cognee-remember <fact>` stores it in Cognee memory
- `/cognee-ask <question>` recalls it
- `/cognee-digest [topic or time window]` builds a lightweight weekly digest

One shared memory dataset for the whole workspace — no per-user account
linking, no OAuth, no bot token needed since replies go back directly in the
slash-command response.

## Run it

```bash
pip3 install -r requirements.txt
# the qdrant adapter's pin fights the cognee dev-branch pin above, so it's a separate,
# --no-deps install (see requirements.txt) — also needs --ignore-requires-python since
# no released version yet declares support for Python 3.14
pip3 install --no-deps --ignore-requires-python cognee-community-vector-adapter-qdrant==0.4.0
cp .env.example .env   # fill in LLM_API_KEY with your Anthropic key
python3 app.py          # serves on :8000
ngrok http 8000          # get a public https URL
```

Vector store is Qdrant (see `.env.example`). Fastest way to get one:

- **Cloud (no Docker needed):** sign up free at https://cloud.qdrant.io, create a cluster, copy its URL + API key into `VECTOR_DB_URL` / `VECTOR_DB_KEY` in `.env`.
- **Local:** `docker run -p 6333:6333 qdrant/qdrant`, leave `VECTOR_DB_URL` as `http://localhost:6333`.

Put the ngrok URL into `slack-manifest.yaml` in place of `<public-host>`
(both slash command URLs), then:

1. Go to https://api.slack.com/apps -> Create New App -> From an app manifest
2. Paste the contents of `slack-manifest.yaml`
3. Install the app to your workspace
4. Copy **Signing Secret** (Basic Information) into `.env` as `SLACK_SIGNING_SECRET`, restart `app.py`
5. In Slack, try:
   - `/cognee-remember Decision: use Qdrant Cloud for the demo`
   - `/cognee-remember Blocker: ngrok URL changes on restart`
   - `/cognee-remember Owner: Alice is handling Slack app setup`
   - `/cognee-ask who is handling Slack app setup`
   - `/cognee-digest this week`

## Test

```bash
python3 test_app.py
```

Covers signature verification (valid/invalid/expired) and command handling,
with `cognee.remember`/`cognee.recall` mocked — no LLM calls in the test.

## Hackathon framing

This repo now fits a "Weekly Digest Generator" demo:

- remember decisions, blockers, owners, and questions during the session
- ask ad hoc questions with `/cognee-ask`
- generate a concise recap with `/cognee-digest`

For the best live result, prefix memories with labels like `Decision:`,
`Blocker:`, `Owner:`, or `Question:`.

## Skipped for this demo

- `/cognee-link` per-user account linking — everyone shares one `slack`
  dataset instead. Add per-user OAuth + encrypted token storage if you need
  private-per-person memory.
- "Remember this" message shortcut, channel allowlist admin endpoints,
  `chat.postMessage`/share-to-channel button — not needed for a single-command demo.
- ngrok free tier gives a new URL on restart; update the manifest URLs (or
  get a reserved domain) if it changes.
