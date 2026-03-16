# Klingon Agent — Sample Evaluation

This sample evaluates a testing agent that responds in Klingon, using the
A2A (Agent2Agent) protocol. You can run against a local agent server
(included) or a remote Azure-deployed agent.

## Files

```
├── agent.yaml                      # Agent definition (remote Azure, bearer auth)
├── agent-local.yaml                # Agent definition (local server, no auth)
├── server.py                       # Local A2A agent server
├── cases/
│   └── klingon-responses.yaml      # 2 evaluation cases
└── README.md
```

## LLM Judge Configuration

This sample uses an LLM judge to verify responses are in Klingon, so you need
an LLM endpoint for both the agent server and the evaluation judge.

**OpenAI:**

```bash
export OPENAI_API_KEY=sk-...
```

**Azure OpenAI:**

```bash
export AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
# If not using `az login` / DefaultAzureCredential:
export AZURE_OPENAI_API_KEY=...
```

The `--judge-model` flag selects which model the judge uses (e.g. `gpt-4.1`,
`gpt-4o-mini`). The agent server model is configured separately via the
`KLINGON_MODEL` env var (default: `gpt-4o-mini`).

## Option A: Local Agent

### Prerequisites

- LLM credentials configured (see above)
- Optional: `KLINGON_MODEL` to override the agent's model (default: `gpt-4o-mini`)

### Install dependencies and start the server

```bash
cd python && uv sync --extra a2a-server

# From the samples/klingon-agent/ directory:
cd ../samples/klingon-agent
uv run --project ../../python python server.py

# Or on a custom port:
uv run --project ../../python python server.py --port 9000
```

The server exposes the agent card at `http://localhost:8000/.well-known/agent-card.json`.

### Run evaluation

In a separate terminal:

```bash
cd python && uv sync --extra dev --extra a2a

uv run beval --verbose run --cases ../samples/klingon-agent/cases/ \
  --agent ../samples/klingon-agent/agent-local.yaml \
  -m validation --judge-model gpt-4o-mini
```

## Option B: Remote Azure Agent

### Prerequisites

- The agent must be running and accessible via the A2A protocol
- Azure credentials configured (e.g. `az login`) for Entra ID bearer auth
- LLM credentials configured for the judge (see above)

### Set the agent URL

```bash
export A2A_AGENT_URL=https://your-agent-endpoint.azure.com
# Optional: override the auth scope (defaults to cognitiveservices)
# export A2A_AUTH_SCOPE=https://your-scope/.default
```

### Run evaluation

```bash
cd python && uv sync --extra dev --extra a2a

uv run beval --verbose run --cases ../samples/klingon-agent/cases/ \
  --agent ../samples/klingon-agent/agent.yaml \
  -m validation --judge-model gpt-4.1 --output results.json
```

## Cases

| ID | Name | Tags | Description |
|----|------|------|-------------|
| `greeting` | Agent greets in Klingon | core | Verifies greeting response is in Klingon |
| `simple_question` | Agent answers a question in Klingon | core | Verifies Q&A response is in Klingon |

## Grading Layers

- **Deterministic**: completion time, response length
- **AI-judged**: LLM judge verifies responses are in Klingon
