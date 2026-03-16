# Smart Inventory Advisor — Sample Evaluation

This sample demonstrates how to evaluate an ACP-based agent using beval's
agent adapter system (SPEC §13).

## Agent

The **Smart Inventory Advisor** is a GitHub Copilot custom agent that
investigates material substitutions in an industrial inventory knowledge
graph. It uses MCP-based tools (RDF Explorer, Databricks, PDF Reader)
and communicates over the Agent Client Protocol (ACP).

## Files

```
├── agent.yaml                   # Standalone agent definition (stdio transport)
├── agent-tcp.yaml               # Standalone agent definition (TCP transport)
├── eval.config.yaml             # Config file (with both agent definitions)
├── cases/
│   └── material-substitution.yaml   # 3 evaluation cases
└── README.md
```

## Prerequisites

The agent definition references `${AGENT_REPO_ROOT}` — the path to the
repository containing `.github/agents/material-substitution.agent.md`.
Export it before running:

```bash
export AGENT_REPO_ROOT=/path/to/your/agent/repo
```

You also need the `copilot` CLI installed and authenticated.

## Running

All commands below assume you are in the `samples/smart-inventory-advisor/`
directory. For development, use `uv run` from the `python/` directory:

```bash
cd python && uv sync --extra dev --extra acp

# Basic run (dev mode, deterministic graders only)
uv run beval run --cases ../samples/smart-inventory-advisor/cases/ \
  --agent ../samples/smart-inventory-advisor/agent.yaml

# Verbose output (prints truncated agent responses to stderr)
uv run beval --verbose run --cases ../samples/smart-inventory-advisor/cases/ \
  --agent ../samples/smart-inventory-advisor/agent.yaml

# Save results to file
uv run beval run --cases ../samples/smart-inventory-advisor/cases/ \
  --agent ../samples/smart-inventory-advisor/agent.yaml \
  --output results.json

# Verbose + output to file (full responses in file, previews on stderr)
uv run beval --verbose run --cases ../samples/smart-inventory-advisor/cases/ \
  --agent ../samples/smart-inventory-advisor/agent.yaml \
  --output results.json
```

If beval is installed (`pip install beval[acp,judge]`), run directly:

### With standalone agent file

```bash
beval run --cases cases/ --agent agent.yaml

# Verbose output
beval --verbose run --cases cases/ --agent agent.yaml

# Save results to file
beval run --cases cases/ --agent agent.yaml --output results.json

# Verbose + output to file
beval --verbose run --cases cases/ --agent agent.yaml --output results.json

# All grader layers including AI judge
beval run --cases cases/ --agent agent.yaml -m validation --judge-model gpt-4o

# Run only core cases
beval run --cases cases/ --agent agent.yaml -t core
```

### With TCP transport

Start the copilot agent as a TCP server first. The `--acp --port` flags
tell copilot to listen for ACP connections on the given port:

```bash
cd $AGENT_REPO_ROOT
copilot --acp --port 3000 --agent material-substitution --allow-all
```

Then in another terminal, run the evaluation:

```bash
# Using standalone agent-tcp.yaml (defaults to 127.0.0.1:3000)
beval run --cases cases/ --agent agent-tcp.yaml

# Override host/port via environment variables
export AGENT_HOST=192.168.1.100
export AGENT_PORT=4000
beval run --cases cases/ --agent agent-tcp.yaml

# Using the TCP agent from config file
beval run --cases cases/ -c eval.config.yaml --agent smart-inventory-advisor-tcp
```

### With LLM judge (validation mode)

Validation mode activates the `ai_judged` grading layer, which uses an LLM
to assess answer quality against the `the answer should be` criteria in each
case. This requires the `--judge-model` flag and an OpenAI-compatible endpoint.

**Azure OpenAI (Entra ID auth):**

```bash
export AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com

beval --verbose run --cases cases/ --agent agent-tcp.yaml \
  -m validation --judge-model gpt-4.1 --output results.json
```

**Azure OpenAI (API key auth):**

```bash
export AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
export AZURE_OPENAI_API_KEY=your-key

beval --verbose run --cases cases/ --agent agent-tcp.yaml \
  -m validation --judge-model gpt-4.1 --output results.json
```

**Standard OpenAI:**

```bash
export OPENAI_API_KEY=sk-...

beval --verbose run --cases cases/ --agent agent-tcp.yaml \
  -m validation --judge-model gpt-4o --output results.json
```

### With config file

```bash
# Uses agents.default from config
beval run --cases cases/ -c eval.config.yaml

# Override with a different agent
beval run --cases cases/ -c eval.config.yaml --agent other-agent
```

### With environment variable

```bash
export BEVAL_AGENT=agent.yaml
beval run --cases cases/
```

## Cases

| ID | Name | Tags | Description |
|----|------|------|-------------|
| `material_substitution_query` | Identify substitute materials | core | Lists valid substitutes for O-ring 10001 |
| `slow_moving_inventory` | Slow-moving inventory items | core | Retrieves structured inventory status |
| `material_compatibility` | NBR vs Viton compatibility | core | Assesses material compatibility in WIX filter |

## Grading Layers

- **Deterministic** (`dev` mode): keyword presence, response length, completion time
- **AI-judged** (`validation` mode): LLM judge evaluates answer quality against
  domain-specific criteria specified in the `the answer should be` then-clauses.
  Supports Azure OpenAI (Entra ID or API key) and standard OpenAI endpoints.
  Requires `pip install beval[judge]` and `--judge-model`.