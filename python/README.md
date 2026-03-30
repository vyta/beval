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
# ACP agent adapter (Agent Client Protocol)
uv sync --extra acp

# A2A agent adapter (Agent-to-Agent)
uv sync --extra a2a

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

beval evaluates the **outputs** of your AI agent or LLM-powered system. There
are two ways to connect beval to your agent:

1. **Agent YAML (declarative)** — define a YAML file describing how to reach
   your agent (protocol, connection, auth). The CLI uses this to connect
   automatically. Best for CI and team workflows.
2. **Programmatic handler (library)** — write a Python callable that invokes
   your agent and returns a `Subject`. Best for custom orchestration or when
   embedding beval in your own test harness.

### Integration pattern

The general flow is:

1. **Define cases** — describe what your agent should do and the quality criteria
2. **Register graders** — map criterion patterns to scoring functions
3. **Define the agent** — declare an agent YAML file *or* write a programmatic handler
4. **Run the evaluation** — the runner connects to the agent, executes cases, feeds subjects to graders, and aggregates scores

```text
┌──────────────┐     ┌────────────┐     ┌──────────────┐     ┌──────────┐
│  Case YAML   │────▶│            │────▶│ Your Agent   │────▶│  Subject │
│  or @case()  │     │   Runner   │◀────│  (adapter)   │◀────│  output  │
└──────────────┘     │            │     └──────────────┘     └──────────┘
┌──────────────┐     │            │────▶ Graders ────▶ Grades ────▶ Report
│  Agent YAML  │────▶│            │
│  or handler  │     └────────────┘
└──────────────┘
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

**Using the `@grader` decorator** (recommended):

```python
from beval import grader, Grade, GraderLayer, Subject

@grader("the answer should mention", layer=GraderLayer.DETERMINISTIC, metric="relevance")
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
```

**Using `register_grader` directly:**

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

### Step 3 — Connect your agent

#### Agent YAML (declarative)

Define an agent YAML file that tells beval how to reach your system. The
runner handles connection, invocation, and Subject construction automatically.

**ACP over stdio** (`agents/my-agent.yaml`):

```yaml
name: my-agent
protocol: acp
connection:
  transport: stdio
  command: ["python", "-m", "my_agent"]
timeout: 30
env:
  OPENAI_API_KEY: ${OPENAI_API_KEY}
metadata:
  version: "1.0"
```

**A2A (Agent2Agent) over HTTP** (`agents/remote-agent.yaml`):

```yaml
name: remote-agent
protocol: a2a
connection:
  url: "https://agent.example.com"
  auth:
    type: api_key
    header: "Authorization"
    value: ${A2A_API_KEY}
  streaming: true
timeout: 60
```

**Custom adapter** (`agents/custom-agent.yaml`):

```yaml
name: custom-agent
protocol: custom
connection:
  module: "my_package.adapters"
  class: "MyAdapter"
  config:
    endpoint: "https://custom.api"
    api_key: ${CUSTOM_KEY}
```

See the [Agent Adapters Specification](../spec/agent-adapters.spec.md) for the
full schema and protocol details.

#### Programmatic handler (library usage)

When using beval as a library, write a callable that takes the `given` context
from a case, calls your system, and returns a normalized `Subject`.

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

**CLI with an agent YAML file** (recommended):

```bash
uv run beval run --agent agents/my-agent.yaml --mode dev
uv run beval run --agent agents/my-agent.yaml --mode validation --trials 3 --format json
```

**Programmatic** (library usage):

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
| `monitoring` | deterministic + process + ai_judged | Production monitoring |

Graders for inactive layers emit skipped grades (excluded from scoring by
default). Cases remain identical across modes — you change the mode, not
the cases.

## Conversation Simulation

In addition to static single-turn evaluation, beval supports **conversation
simulation**: an AI-powered simulated user pursues a goal through multi-turn
dialogue with your agent, grading every turn and the conversation as a whole.

```text
┌────────────┐  generate_case()   ┌──────────────┐
│  Simulator │ ─────────────────▶ │  DynamicCase │
│  (persona+ │                    │  query+then  │
│   goal)    │                    └──────┬───────┘
└────────────┘                           │ invoke()
                                  ┌──────▼───────┐
                                  │  Your Agent  │
                                  └──────┬───────┘
                                         │ response
                                  ┌──────▼───────┐
                                  │   Graders    │ ◀── static goal criteria
                                  │  (§4 registry)│     + dynamic turn criteria
                                  └──────────────┘
```

The simulator calls an LLM (or an ACP agent like GitHub Copilot) to generate
the next message and 1–3 turn-specific evaluation criteria. Grading reuses the
same §4 grader registry as static evaluation — no new infrastructure.

### Quick start

**1. Define personas and goals** (`personas.yaml`, `goals.yaml`):

```yaml
# personas.yaml
personas:
  - id: casual_user
    name: Casual User
    description: >
      A non-technical user asking questions in plain, conversational language.
      Patient and polite.
    goals: [find_refund_policy]
    traits:
      tone: friendly
      expertise: beginner
```

```yaml
# goals.yaml
goals:
  - id: find_refund_policy
    name: Find Refund Policy
    given:
      objective: >
        Find the company's refund policy, including the time limit for returns
        and conditions under which refunds are granted.
      max_turns: 10
    stages:
      - when: "each turn"
        then:
          - "response time should be under 10"
      - when: "on finish"
        then:
          - "the agent describes at least one condition for refund eligibility"
          - "the agent provided accurate policy information"
```

**2. Add conversation config** (`eval.config.yaml`):

```yaml
eval:
  conversation:
    simulator:
      protocol: openai
      model: gpt-4o
      api_key: ${OPENAI_API_KEY}
    personas:
      - file: personas.yaml
    goals:
      - file: goals.yaml
    actor_count: 1
    max_parallel_actors: 5
```

**3. Run:**

```bash
uv run beval converse run \
  --agent agents/my-agent.yaml \
  --output results/conversation.json
```

Or with shorthand flags (no config file needed):

```bash
uv run beval converse run \
  --agent agents/my-agent.yaml \
  --simulator-model gpt-4o \
  --output results/conversation.json
```

### Pairing model

Personas declare which goals they pursue in their `goals` list — this is not a
cartesian product. If persona A lists `[goal_1, goal_2]` and persona B lists
`[goal_2]`, the run produces three conversations:
`(A, goal_1)`, `(A, goal_2)`, `(B, goal_2)`.

Set `actor_count > 1` for variance data (analogous to `--trials` for static
evaluation): multiple independent actors run the same persona/goal pair.

### Simulator options

| Method | Config / Flag |
|---|---|
| OpenAI-compatible LLM | `--simulator-model gpt-4o` or `eval.conversation.simulator.protocol: openai` |
| ACP agent (e.g., Copilot) | `--simulator-agent "copilot --acp --stdio"` or `eval.conversation.simulator.protocol: acp` |

### Parallelism

Set `max_parallel_actors` to run multiple actors concurrently. Actors are async
tasks (not threads or processes) — each is I/O-bound (waiting on the agent and
simulator APIs), so the implementation scales to 1000 concurrent actors on a
single process without significant overhead.

### Results

Conversation results follow the same shape as static `CaseResult` — the same
reporting tooling (`beval compare`, baseline diffing) works unchanged.

```json
{
  "mode": "validation",
  "summary": {
    "overall_score": 0.82,
    "goal_achievement_rate": 0.75,
    "passed": 6,
    "total": 8,
    "total_turns": 34,
    "mean_turns_to_goal": 4.2
  },
  "conversations": [...]
}
```

---

## CLI Usage

```bash
# Run evaluations
uv run beval run --cases ./cases/ --agent agents/my-agent.yaml --mode dev
uv run beval run --cases ./cases/ --agent agents/my-agent.yaml --mode validation --trials 3 --format json

# Verbose output (prints truncated agent responses to stderr)
uv run beval --verbose run --cases ./cases/ --agent agents/my-agent.yaml

# Save results to file
uv run beval run --cases ./cases/ --agent agents/my-agent.yaml --output results.json

# Verbose + output to file (full responses in file, truncated previews on stderr)
uv run beval --verbose run --cases ./cases/ --agent agents/my-agent.yaml --output results.json

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

# Conversation simulation
uv run beval converse run --agent agents/my-agent.yaml --simulator-model gpt-4o
uv run beval converse run --agent agents/my-agent.yaml --simulator-agent "copilot --acp --stdio"
uv run beval converse run --agent agents/my-agent.yaml --actor-count 3 --max-parallel 10 --output results/
```

Run as a module:

```bash
uv run python -m beval version
```

### Global flags

| Flag | Description |
|------|-------------|
| `--verbose` | Print truncated agent responses to stderr; include full responses in output file |

### Environment variables

| Variable                     | Overrides                    | Description |
|------------------------------|------------------------------|-------------|
| `BEVAL_AGENT`                | `--agent`                    | Agent YAML file or config name |
| `BEVAL_MODE`                 | `--mode`                     | Evaluation mode |
| `BEVAL_OUTPUT_DIR`           | `--output`                   | Results output directory |
| `BEVAL_TRIALS`               | `--trials`                   | Number of trial executions |
| `BEVAL_SIMULATOR_MODEL`      | `--simulator-model`          | Conversation simulator LLM model |
| `BEVAL_SIMULATOR_AGENT`      | `--simulator-agent`          | Conversation simulator ACP command |
| `BEVAL_ACTOR_COUNT`          | `--actor-count`              | Actors per persona/goal pair |
| `BEVAL_CONVERSATION_HISTORY_DIR` | `eval.conversation.history_dir` | History directory |
| `NO_COLOR`                   | `--no-color`                 | Disable colored output |

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
│       ├── adapters/        # Agent adapters (ACP, A2A, custom)
│       │   ├── __init__.py  # Interface, loader, factory
│       │   ├── acp.py       # ACP adapter (optional: beval[acp])
│       │   ├── a2a.py       # A2A adapter (optional: beval[a2a])
│       │   └── custom.py    # Custom adapter (dynamic class loading)
│       ├── graders/         # Grader registry and built-ins
│       │   ├── __init__.py  # Registry, @grader decorator
│       │   ├── deterministic.py  # Built-in deterministic graders
│       │   ├── process.py        # Built-in process graders
│       │   └── ai_judged.py      # AI-judged grader (LLM judge)
│       ├── judge.py         # LLM judge interface
│       ├── runner.py        # Runner orchestration
│       ├── subject.py       # Subject normalization
│       ├── reporter.py      # Result reporting (JSON)
│       ├── loader.py        # YAML case loading (safe_load)
│       ├── schema.py        # JSON Schema validation (optional: beval[validate])
│       ├── tracing.py       # OpenTelemetry tracing (optional: beval[tracing])
│       ├── conversation/    # Conversation simulation (§15)
│       │   ├── __init__.py
│       │   ├── types.py     # Persona, Goal, DynamicCase, ConversationResult, …
│       │   ├── simulator.py # UserSimulatorInterface, OpenAISimulator, ACPSimulator
│       │   ├── actor.py     # run_actor() async coroutine (turn loop)
│       │   └── runner.py    # ConversationRunner (asyncio orchestration)
│       └── py.typed         # PEP 561 marker
└── tests/
    ├── conftest.py          # Shared fixtures + registry isolation
    ├── test_types.py        # Core type tests
    ├── test_loader.py       # YAML loader tests
    ├── test_adapters.py     # Agent adapter tests
    ├── test_graders.py      # Grader tests
    ├── test_cli.py          # CLI tests
    ├── test_conversation.py # Conversation simulation tests
    └── test_conformance.py  # Cross-language conformance tests
```


