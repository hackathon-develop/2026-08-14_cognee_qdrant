Use this exact 60–90 second script.

  Opening

  “Teams lose decisions and context in Slack constantly. We used Cognee with Qdrant to turn
  Slack into a shared memory layer, then built a weekly digest generator on top of it.”

  Setup line

  “This Slack bot supports three commands: remember, ask, and digest.”

  Live demo steps

  1. Store a few team memories

  “First, I’ll save a few things that normally disappear into chat.”

  - /cognee-remember Decision: use Qdrant Cloud for the demo
  - /cognee-remember Blocker: ngrok URL changes on restart
  - /cognee-remember Owner: Alice is handling Slack app setup
  - /cognee-remember Question: should we support per-channel memory?

  Say:

  “Each item is stored in shared memory through Cognee and indexed in Qdrant for retrieval.”

  2. Ask a direct question

  - /cognee-ask who is handling Slack app setup

  Say:

  “So this is not just note storage. The team can query its memory in natural language.”

  3. Generate the digest

  - /cognee-digest this week

  Say:

  “Now the bot turns scattered remembered items into a compact weekly digest: decisions,
  blockers, owners, and open questions.”

  What to emphasize while the result appears

  “Instead of asking someone to reconstruct the week manually, the team gets an instant recap  from shared memory.”

  Closing pitch

  “Our project is a Slack-native team memory and recap agent. Cognee handles memory
  orchestration, Qdrant handles semantic retrieval, and the result is a lightweight workflow
  teams can actually use during the week, not just after it.”

  Judge-oriented closer

  “This scores on depth rather than breadth: Slack integration, Cognee memory, Qdrant
  retrieval, and a concrete workflow on top. The novelty is treating memory as an operational  layer for teams, not just a chatbot feature.”

  If they ask “why is this useful?”

  “Because status, decisions, owners, and blockers are already discussed in Slack, but they
  are hard to recover later. We make that memory reusable.”

  If they ask “what would you build next?”

  “Two things: automatic memory capture from selected channels, and scheduled Friday digests
  posted back into Slack.”
