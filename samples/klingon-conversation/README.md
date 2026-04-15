# Klingon Language Tutor — Conversation Simulation Sample

Conversation simulation evaluation for the **Klingon Language Tutor** agent,
testing multi-turn language teaching sessions over the A2A protocol.

This sample demonstrates beval's conversation simulation with a simple,
self-contained A2A agent — no external services beyond an LLM. The agent
maintains per-session conversation history so it can build vocabulary across
turns, correct student attempts, and stay in character throughout.

Agent source: [`samples/klingon-agent/server.py`](../klingon-agent/server.py)

## What Makes This a Good Sample

- **Simple A2A server** you can read in 150 lines and run locally
- **Returns full conversational responses** via `Message` (not task artifacts)
- **Stateful across turns** via `context_id`-keyed chat history
- **Evaluable outcomes**: did the agent teach real phrases? Did it maintain character? Did it build on prior turns?
- **Azure AI Foundry** for both simulator and judge (Entra ID auth)

## Files

| File | Description |
|------|-------------|
| `eval.config.yaml` | A2A agent + Azure AI Foundry judge and simulator |
| `personas.yaml` | Linguistics student and Starfleet diplomat |
| `goals.yaml` | Three Klingon learning goals |
| `criteria.yaml` | Evaluation criteria matched to goals by tags |

## Personas

| ID | Description | Goals |
|----|-------------|-------|
| `eager_linguist` | PhD student who attempts phrases and asks cultural questions | `learn_greetings`, `understand_warrior_phrases` |
| `starfleet_diplomat` | Officer who needs practical phrases fast for a meeting | `mission_critical_phrases` |

## Goals

| ID | Turns | What It Tests |
|----|-------|---------------|
| `learn_greetings` | 8 | Does the agent teach greetings with translations and respond to student attempts? |
| `understand_warrior_phrases` | 8 | Does the agent explain cultural context, not just translate? |
| `mission_critical_phrases` | 8 | Does the agent give practical, specific phrases for a high-stakes scenario? |

This produces **3 conversations** per run.

## Prerequisites

### 1. Klingon agent

```bash
cd samples/klingon-agent

# Azure AI Foundry (Entra ID — recommended)
az login
export AZURE_OPENAI_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>/openai/v1
export AZURE_OPENAI_API_VERSION=2025-04-01-preview
export KLINGON_MODEL=o4-mini

# OR standard OpenAI
export OPENAI_API_KEY=sk-...
export KLINGON_MODEL=o4-mini

cd ../../python && uv sync --extra a2a-server

# From the samples/klingon-agent/ directory:
cd ../samples/klingon-agent
uv run --project ../../python python server.py

# Or on a custom port:
uv run --project ../../python python server.py --port 9000
```

The agent runs on http://localhost:8000.

### 2. Azure AI Foundry (judge and simulator)

```bash
az login

export FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>/openai/v1
export FOUNDRY_MODEL=o4-mini
export OPENAI_API_VERSION=2025-04-01-preview
```

### 3. beval

```bash
cd python && uv sync --extra dev --extra a2a --extra judge
```

## Running

```bash
uv run beval -c ../samples/klingon-conversation/eval.config.yaml \
  converse run \
  --output ../samples/klingon-conversation/results/
```

Single goal for quick iteration:

```bash
uv run beval -c ../samples/klingon-conversation/eval.config.yaml \
  converse run \
  --persona eager_linguist \
  --goal learn_greetings \
  --output ../samples/klingon-conversation/results/
```

## How It Works

```
Simulator (Azure AI Foundry)       Klingon Tutor (A2A HTTP)
      │                                     │
      │  "I want to learn how to greet      │
      │   a Klingon warrior"                │
      │ ───────────────────────────────────▶│
      │                                     │  context_id → chat history
      │                                     │  LLM call with full history
      │  "nuqneH (What do you want?)        │
      │   — that's how Klingons greet"      │
      │ ◀───────────────────────────────────│
      │                                     │
      │  grade(query criteria)              │
      │  ...repeat up to max_turns          │
      │                                     │
      │  grade(conversation criteria)       │
```

The agent carries `context_id` in every `Message` response. beval's
`A2AAdapter` sends the same `context_id` on subsequent turns, so the
agent's in-memory chat history grows across the conversation — it
remembers which phrases it taught and can build vocabulary progressively.

## Grading

| Layer | Source | What it grades |
|-------|--------|----------------|
| Deterministic | `latency` criteria → `completion time should be under 30` | Latency (30s for a simple LLM call) |
| AI-judged (per turn) | per-goal query criteria + 1 dynamic simulator criterion | Does each response teach something useful with a translation? |
| AI-judged (conversation) | per-goal conversation criteria | Did the full session deliver on the learning goal? |
