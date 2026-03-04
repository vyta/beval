---
title: beval — Python
description: Python implementation of the beval behavioral evaluation framework
---

# beval — Python

Python implementation of the [beval behavioral evaluation framework](../SPEC.md).

## Installation

Requires [uv](https://docs.astral.sh/uv/). Core install (YAML loading, DSL, deterministic grading):

```bash
uv sync
```

With optional extras:

```bash
# JSON Schema validation
uv sync --extra validate

# OpenTelemetry tracing for process graders
uv sync --extra tracing

# Everything
uv sync --extra all

# Development dependencies
uv sync --extra dev --no-install-project
```

## Development

The repository provides containerized `make` targets for consistent builds without a local Python installation. If you have `nerdctl` or `docker` available, use the `make` targets. Otherwise, install [uv](https://docs.astral.sh/uv/) and run commands directly.

### With containers (recommended)

Run tests:

```bash
make python-test
```

Run linting:

```bash
make python-lint
```

Run both:

```bash
make python-check
```

All `make` targets use `nerdctl` by default. Override with `CONTAINER_RUNTIME=docker` if needed:

```bash
CONTAINER_RUNTIME=docker make python-test
```

### With uv (no containers)

Install dependencies, then run tools through `uv run`:

```bash
uv sync --extra dev
```

Run tests:

```bash
uv run pytest tests/
```

Run linting:

```bash
uv run ruff check src/ tests/
```

Run formatting check:

```bash
uv run ruff format --check src/ tests/
```

Run type checking:

```bash
uv run mypy src/beval/
```

## Integrating With Your Agent

beval evaluates the **outputs** of your AI agent or LLM-powered system. The
framework does not run your agent directly — you connect the two by writing a
thin adapter that invokes your system and normalizes its output into a
`Subject`.

### Integration pattern

The general flow is:

1. **Define cases** — describe what your agent should do and the quality criteria
2. **Register graders** — map criterion patterns to scoring functions
3. **Write a subject adapter** — call your agent, capture the response, wrap it in a `Subject`
4. **Run the evaluation** — the runner executes cases, feeds subjects to graders, and aggregates scores

```text
┌──────────────┐     ┌────────────┐     ┌──────────────┐     ┌──────────┐
│  Case YAML   │────▶│   Runner   │────▶│ Your Agent   │────▶│  Subject │
│  or @case()  │     │            │◀────│  (adapter)   │◀────│  output  │
└──────────────┘     │            │     └──────────────┘     └──────────┘
                     │            │────▶ Graders ────▶ Grades ────▶ Report
                     └────────────┘
```

### Step 1 — Define evaluation cases

Cases describe behavioral expectations. Use the Python DSL or YAML files.

**Python DSL:**

```python
from beval import case, CaseBuilder

@case("AI legislation search", category="legislation", tags=["search"])
def test_ai_legislation(s: CaseBuilder):
    s.given("a query", "What has Congress done on AI?")
    s.when("the agent researches this query")
    s.then("completion time should be under", 20.0)
    s.then("the answer should mention", "artificial intelligence")
    s.then("the answer should be", "comprehensive and well-sourced")
```

**YAML (cases/legislation.yaml):**

```yaml
cases:
  - name: AI legislation search
    id: ai_legislation
    category: legislation
    tags: [search]
    given:
      query: "What has Congress done on AI?"
    when: "the agent researches this query"
    then:
      - "completion time should be under": 20.0
      - "the answer should mention": "artificial intelligence"
      - "the answer should be": "comprehensive and well-sourced"
```

### Step 2 — Register graders

Graders score a `Subject` against a criterion. Register them by pattern prefix — the
runner matches each `then` clause to the grader with the longest matching prefix.

```python
from beval import register_grader, Grade, GraderLayer, Subject

def keyword_grader(criterion: str, args: list, subject: Subject, context) -> Grade:
    keyword = args[0] if args else ""
    found = keyword.lower() in subject.answer.lower()
    return Grade(
        criterion=criterion,
        score=1.0 if found else 0.0,
        metric="relevance",
        passed=found,
        detail=f"Keyword '{keyword}' {'found' if found else 'not found'}",
        layer=GraderLayer.DETERMINISTIC,
    )

register_grader(
    "the answer should mention",
    keyword_grader,
    layer=GraderLayer.DETERMINISTIC,
    metric="relevance",
)
```

### Step 3 — Write a subject adapter

The adapter is where you connect your actual agent. It takes the `given`
context from a case, calls your system, and returns a normalized `Subject`.

**Direct function call:**

```python
import time
from beval import Subject

def run_my_agent(query: str) -> Subject:
    """Call your agent and wrap the result as a Subject."""
    start = time.monotonic()

    # -- Replace this with your actual agent invocation --
    from my_agent import Agent
    agent = Agent()
    response = agent.run(query)
    # ----------------------------------------------------

    elapsed = time.monotonic() - start
    return Subject(
        input=query,
        output=response.text,
        completion_time=elapsed,
        metadata={
            "documents_retrieved": len(response.sources),
            "model": response.model_name,
        },
    )
```

**Microsoft Agent Framework agent:**

```python
import time
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from beval import Subject

async def run_autogen_agent(query: str) -> Subject:
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
    agent = AssistantAgent("researcher", model_client=model_client)
    termination = TextMentionTermination("TERMINATE")
    team = RoundRobinGroupChat([agent], termination_condition=termination)

    start = time.monotonic()
    result = await team.run(task=query)
    elapsed = time.monotonic() - start

    last_message = result.messages[-1]
    return Subject(
        input=query,
        output=last_message.content,
        completion_time=elapsed,
        metadata={"message_count": len(result.messages)},
    )
```

**Pre-recorded outputs (no live agent):**

For offline evaluation, load canned Subject data from a JSON file instead of
calling a live system:

```python
import json
from beval import Subject

def load_subject(path: str) -> Subject:
    with open(path) as f:
        data = json.load(f)
    return Subject(
        input=data.get("input", data.get("query", "")),
        output=data.get("output", data.get("answer", "")),
        completion_time=data.get("completion_time", 0.0),
        metadata=data.get("metadata", {}),
    )
```

### Step 4 — Run the evaluation

Wire the adapter into the Runner and execute:

```python
from beval import Runner, EvaluationMode, RunConfig
from beval.reporter import to_json

runner = Runner(
    mode=EvaluationMode.DEV,
    config=RunConfig(grade_pass_threshold=0.5, case_pass_threshold=0.7),
)
result = runner.run(label="nightly")

print(f"Score: {result.summary.overall_score:.2f}")
print(f"Passed: {result.summary.passed}/{result.summary.total}")

# Save results as JSON
print(to_json(result))
```

### Parameterized cases

Use `@examples` to run the same case across multiple inputs:

```python
from beval import case, examples, CaseBuilder

@case("Multi-source research", category="research")
@examples([
    {"query": "climate policy", "expected": "Paris Agreement"},
    {"query": "trade policy", "expected": "tariff"},
])
def test_multi_source(s: CaseBuilder):
    s.given("a query", s)
    s.when("the agent researches the topic")
    s.then("the answer should mention", s)
```

Each example row generates an independent case instance with its own grades
and pass/fail result.

### Evaluation modes

Modes control which grader layers are active:

| Mode | Active layers | Use case |
|---|---|---|
| `dev` | deterministic | Fast local iteration |
| `dev+process` | deterministic + process | Include trace/span checks |
| `validation` | deterministic + process + ai_judged | Full evaluation with LLM judges |

Graders for inactive layers emit skipped grades (excluded from scoring by
default). Cases remain identical across modes — you change the mode, not
the cases.

## CLI Usage

> [!NOTE]
> In version 0.1.0, only `beval version` is implemented. The remaining
> commands listed below are planned for future releases.

```bash
# Run evaluations
uv run beval run --mode dev
uv run beval run --mode validation --trials 3 --format json

# Validate case files and schemas
uv run beval validate --cases ./cases/

# Compare results across runs
uv run beval compare --results run1.json run2.json --format table

# Manage baselines
uv run beval baseline save
uv run beval baseline show
uv run beval baseline clear

# Cache management
uv run beval cache show
uv run beval cache clear

# Initialize a new project
uv run beval init --dir ./my-evals

# Print version information
uv run beval version
```

Run as a module:

```bash
uv run python -m beval version
```

### Environment variables

| Variable          | Overrides     | Example             |
|-------------------|---------------|---------------------|
| `BEVAL_MODE`      | `--mode`      | `BEVAL_MODE=dev`    |
| `BEVAL_OUTPUT_DIR`| `--output`    | `BEVAL_OUTPUT_DIR=./results` |
| `BEVAL_TRIALS`    | `--trials`    | `BEVAL_TRIALS=5`    |
| `NO_COLOR`        | `--no-color`  | `NO_COLOR=1`        |

## Project Structure

```text
python/
├── src/
│   └── beval/
│       ├── __init__.py      # Public API exports
│       ├── __main__.py      # python -m beval + console_main entry point
│       ├── cli.py           # CLI (argparse)
│       ├── types.py         # Core type definitions (frozen dataclasses)
│       ├── dsl.py           # DSL (@case decorator, Given/When/Then)
│       ├── graders/         # Grader registry and built-ins
│       ├── judge.py         # LLM judge interface
│       ├── runner.py        # Runner orchestration
│       ├── subject.py       # Subject normalization
│       ├── reporter.py      # Result reporting (JSON)
│       ├── loader.py        # YAML case loading (safe_load)
│       ├── schema.py        # JSON Schema validation (optional: beval[validate])
│       ├── tracing.py       # OpenTelemetry tracing (optional: beval[tracing])
│       └── py.typed         # PEP 561 marker
└── tests/
    ├── conftest.py          # Shared fixtures + registry isolation
    ├── test_types.py        # Core type tests
    ├── test_loader.py       # YAML loader tests
    ├── test_cli.py          # CLI tests
    └── test_conformance.py  # Cross-language conformance tests
```


