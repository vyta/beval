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
├── agent.yaml                   # Standalone agent definition
├── eval.config.yaml             # Config file (with inline agent definition)
├── cases/
│   └── material-substitution.yaml   # 3 evaluation cases
└── README.md
```

## Running

All commands below assume you are in the `samples/smart-inventory-advisor/`
directory. For development, use `uv run` from the `python/` directory:

```bash
cd python && uv sync --extra dev
uv run beval run --cases ../samples/smart-inventory-advisor/cases/ \
  --agent ../samples/smart-inventory-advisor/agent.yaml
```

If beval is installed (`pip install beval[acp]`), you can run directly:

### With standalone agent file

```bash
beval run --cases cases/ --agent agent.yaml

# All grader layers including AI judge
beval run --cases cases/ --agent agent.yaml -m validation --judge-model gpt-4o

# Run only core cases
beval run --cases cases/ --agent agent.yaml -t core

# Save results as baseline
beval run --cases cases/ --agent agent.yaml --save-baseline
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
  domain-specific criteria specified in the `the answer should be` then-clauses

## TODO

1. Test copilot agent with TCP connection
2. Test with LLM judge
3. Test an agent with A2A
