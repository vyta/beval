---
title: Foundry Agent Sample Evaluation
description: Evaluates a Microsoft Foundry prompt agent using beval's built-in Foundry adapter with Entra ID authentication.
ms.date: 2026-07-14
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
├── run.sh                          # Run script with defaults
├── cases/
│   ├── foundry-eval.yaml           # 2 basic evaluation cases
│   └── cortyx/                     # eCommerce analytics cases (100 cases)
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
| `FOUNDRY_AGENT_NAME`       | No       | Agent name (default: `ecommerce-agent`)              |
| `FOUNDRY_MODEL_NAME`       | No       | Fallback model when agent name is not set (default: `gpt-4o`) |

## Setup

1. Sign in with Azure CLI so Entra ID credentials are available:

   ```bash
   az login
   ```

1. Install beval with the Foundry extra:

   ```bash
   pip install "beval[foundry] @ git+https://github.com/vyta/beval.git@eedorenko/update-foundry-adapter#subdirectory=python"
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
beval -c eval.config.yaml run --cases cases --verbose
```

Or use the run script with defaults:

```bash
./run.sh
```

**Validation mode** includes AI-judged criteria and requires a judge
configured in `eval.config.yaml` (see [LLM Judge](#llm-judge) below):

```bash
beval -c eval.config.yaml run --cases cases -m validation --verbose
```

**From the `python/` directory** (development):

```bash
cd python
uv run beval -c ../samples/foundry-agent/eval.config.yaml run \
  --cases ../samples/foundry-agent/cases \
  -m dev --verbose
```

## LLM Judge

To enable AI-judged graders in validation mode, add a `judge` section to
`eval.config.yaml`. Any OpenAI-compatible endpoint works, including Ollama
for fully local evaluation.

### Ollama (local)

1. Pull the default model (or any model you prefer):

   ```bash
   ollama pull gemma4:e2b
   ```

1. Add the judge config to `eval.config.yaml`:

   ```yaml
   eval:
     judge:
       protocol: openai
       model: ${JUDGE_MODEL_NAME:-gemma4:e2b}
       base_url: http://localhost:11434/v1
   ```

1. Set `OPENAI_API_KEY` to any non-empty value (Ollama ignores it, but the
   `openai` Python package requires it):

   ```bash
   export OPENAI_API_KEY=ollama
   ```

### OpenAI

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
          agent_name: ${FOUNDRY_AGENT_NAME:-ecommerce-agent}
          model: ${FOUNDRY_MODEL_NAME:-gpt-4o}
        timeout: 120
```
