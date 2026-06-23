---
title: Foundry Agent Sample Evaluation
description: Evaluates a Microsoft Foundry prompt agent using beval's custom adapter protocol with Entra ID authentication.
ms.date: 2026-06-19
ms.topic: tutorial
---

## Foundry Agent Sample Evaluation

This sample evaluates a Microsoft Foundry prompt agent using beval's custom
adapter protocol. The adapter connects directly to the Foundry Responses API
via the `azure-ai-projects` SDK with Entra ID authentication.

## Files

```text
├── agent.yaml                      # Agent definition (custom adapter)
├── beval_foundry_adapter.py        # Custom adapter implementation
├── eval.config.yaml                # Evaluation configuration (judge, agents)
├── cases/
│   └── foundry-eval.yaml           # 2 evaluation cases
└── README.md
```

## Prerequisites

* Python 3.10+
* Azure CLI (`az login`) for Entra ID authentication
* A Microsoft Foundry project with a deployed prompt agent (or model deployment)
* **Foundry User** role assigned at the project level
* (Optional) [Ollama](https://ollama.com) for local LLM judging

## Environment Variables

| Variable                   | Required | Description                                          |
|----------------------------|----------|------------------------------------------------------|
| `FOUNDRY_PROJECT_ENDPOINT` | Yes      | Foundry project endpoint URL                         |
| `FOUNDRY_AGENT_NAME`       | No       | Agent name (omit for direct model calls)             |
| `FOUNDRY_MODEL_NAME`       | No       | Model name (default: `gpt-4o`)                       |
| `JUDGE_MODEL_NAME`         | No       | Ollama judge model (default: `gemma4:e2b`)           |
| `OPENAI_API_KEY`           | No       | Required for LLM judge; set to `ollama` when local   |

## Setup

1. Sign in with Azure CLI so Entra ID credentials are available:

   ```bash
   az login
   ```

1. Install the required Python packages:

   ```bash
   pip install azure-ai-projects azure-identity
   ```

1. Set the required environment variables. `FOUNDRY_PROJECT_ENDPOINT` is
   required; the others have defaults or are optional.

   **Bash / Linux / macOS:**

   ```bash
   export FOUNDRY_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
   export FOUNDRY_AGENT_NAME="MyAgent"
   ```

   **PowerShell / Windows:**

   ```powershell
   $env:FOUNDRY_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
   $env:FOUNDRY_AGENT_NAME = "MyAgent"
   ```

## Run

The custom adapter module (`beval_foundry_adapter.py`) must be importable when
beval starts. Run from this directory with `PYTHONPATH=.` so Python can find
the module.

**Dev mode** runs only deterministic graders (fast, no LLM judge required):

```bash
cd samples/foundry-agent
PYTHONPATH=. beval run --cases cases --agent agent.yaml -m dev --verbose
```

**Validation mode** includes AI-judged criteria and requires a judge
configured in `eval.config.yaml` (see [LLM Judge](#llm-judge) below). Pass
`-c` before the `run` subcommand:

```bash
PYTHONPATH=. OPENAI_API_KEY=ollama beval -c eval.config.yaml run \
  --cases cases --agent agent.yaml -m validation --verbose
```

On PowerShell, set environment variables first:

```powershell
cd samples\foundry-agent
$env:PYTHONPATH = "."
$env:OPENAI_API_KEY = "ollama"
beval -c eval.config.yaml run --cases cases --agent agent.yaml -m validation --verbose
```

**From the `python/` directory:**

```bash
cd python
PYTHONPATH=../samples/foundry-agent uv run beval run \
  --cases ../samples/foundry-agent/cases \
  --agent ../samples/foundry-agent/agent.yaml \
  -m dev --verbose
```

## LLM Judge

The `eval.config.yaml` file configures the LLM judge used for AI-judged
graders in validation mode. Any OpenAI-compatible endpoint works, including
Ollama for fully local evaluation.

### Ollama (local)

1. Pull the default model (or any model you prefer):

   ```bash
   ollama pull gemma4:e2b
   ```

1. The judge is already configured in `eval.config.yaml`:

   ```yaml
   eval:
     judge:
       protocol: openai
       model: ${JUDGE_MODEL_NAME:-gemma4:e2b}
       base_url: http://localhost:11434/v1
   ```

   Override the model at runtime by setting `JUDGE_MODEL_NAME`.

1. Set `OPENAI_API_KEY` to any non-empty value (Ollama ignores it, but the
   `openai` Python package requires it):

   ```bash
   export OPENAI_API_KEY=ollama
   ```

> [!NOTE]
> Judge quality depends on model reasoning capability. Larger models like
> `gemma4` or `llama3:70b` produce more reliable scores.

### OpenAI

```yaml
eval:
  judge:
    protocol: openai
    model: gpt-4o
```

Set `OPENAI_API_KEY` to your actual API key.

## Inline Agent Definition (Alternative)

You can define the agent inline in `eval.config.yaml` instead of using a
separate `agent.yaml`:

```yaml
eval:
  mode: validation
  agents:
    default: foundry-agent
    definitions:
      - name: foundry-agent
        protocol: custom
        connection:
          module: beval_foundry_adapter
          class: FoundryAdapter
          config:
            endpoint: ${FOUNDRY_PROJECT_ENDPOINT}
            agent_name: ${FOUNDRY_AGENT_NAME:-}
            model: ${FOUNDRY_MODEL_NAME:-gpt-4o}
        timeout: 60
```

Then run without `--agent`:

```bash
PYTHONPATH=. beval run --cases cases
```
