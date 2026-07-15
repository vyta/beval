---
title: Foundry Agent Sample Evaluation
description: Evaluates a Microsoft Foundry prompt agent using beval's built-in Foundry adapter with Entra ID authentication.
ms.date: 2026-07-15
ms.topic: tutorial
---

## Foundry Agent Sample Evaluation

This sample evaluates a Microsoft Foundry prompt agent using beval's built-in
`foundry` adapter protocol. The adapter connects to the Foundry Responses API
via the `azure-ai-projects` SDK with Entra ID authentication.

## Files

```text
├── agent.yaml                      # Agent definition
├── eval.config.yaml                # Evaluation configuration
├── cases/
│   └── foundry-eval.yaml           # 2 evaluation cases
└── README.md
```

## Prerequisites

* Python 3.10+
* Azure CLI (`az login`) for Entra ID authentication
* A Microsoft Foundry project with a deployed prompt agent (or model deployment)
* **Foundry Project Manager** role assigned at the project scope
* (Optional) [Ollama](https://ollama.com) for local LLM judging

## Environment Variables

| Variable                   | Required | Description                                          |
|----------------------------|----------|------------------------------------------------------|
| `FOUNDRY_PROJECT_ENDPOINT` | Yes      | Foundry project endpoint URL                         |
| `FOUNDRY_AGENT_NAME`       | No       | Agent name (omit for direct model calls)             |
| `FOUNDRY_MODEL_NAME`       | No       | Fallback model when agent name is not set (default: `gpt-4o`) |
| `JUDGE_MODEL_NAME`         | No       | Ollama judge model (default: `gemma4:e2b`)           |
| `OPENAI_API_KEY`           | No       | Required for validation mode; set to `ollama` for local Ollama |

## Setup

1. Sign in with Azure CLI so Entra ID credentials are available:

   ```bash
   az login
   ```

1. Install beval with the Foundry extra:

   ```bash
   pip install beval[foundry]
   ```

1. Set the required environment variables:

   ```bash
   export FOUNDRY_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
   export FOUNDRY_AGENT_NAME="MyAgent"
   ```

## Run

**Dev mode** runs only deterministic graders (completion time, response length — no LLM judge required):

```bash
cd samples/foundry-agent
beval -c eval.config.yaml run --cases cases -m dev --verbose
```

**Validation mode** includes AI-judged criteria and requires a judge
configured in `eval.config.yaml` (see [LLM Judge](#llm-judge) below):

```bash
OPENAI_API_KEY=ollama beval -c eval.config.yaml run --cases cases --verbose
```

**From the `python/` directory** (development):

```bash
cd python
uv run beval -c ../samples/foundry-agent/eval.config.yaml run \
  --cases ../samples/foundry-agent/cases \
  -m dev --verbose
```

## LLM Judge

The `eval.config.yaml` configures an Ollama-based LLM judge for validation
mode. Any OpenAI-compatible endpoint works.

### Ollama (local)

1. Pull the default model (or any model you prefer):

   ```bash
   ollama pull gemma4:e2b
   ```

1. Set `OPENAI_API_KEY` to any non-empty value (Ollama ignores it, but the
   `openai` Python package requires it):

   ```bash
   export OPENAI_API_KEY=ollama
   ```

### OpenAI

Override the judge in `eval.config.yaml`:

```yaml
eval:
  judge:
    protocol: openai
    model: gpt-4o
```

Set `OPENAI_API_KEY` to your actual API key.

## Agent Definition

The agent is defined inline in `eval.config.yaml` using the built-in `foundry`
protocol:

```yaml
eval:
  agents:
    default: foundry-agent
    definitions:
      - name: foundry-agent
        protocol: foundry
        connection:
          endpoint: ${FOUNDRY_PROJECT_ENDPOINT}
          agent_name: ${FOUNDRY_AGENT_NAME:-}
          model: ${FOUNDRY_MODEL_NAME:-gpt-4o}
        timeout: 60
```
