---
title: beval
description: A language-agnostic framework for behavioral evaluation of AI agents and LLM-powered systems.
ms.date: 2026-02-25
---

> [!IMPORTANT]
> This project is experimental and under active development. APIs, schemas, and
> CLI interfaces may change without notice. It is not intended for production use.

## Overview

**beval** (behavioral evaluation) is a framework for evaluating AI agents and
LLM-powered systems through scored, multi-dimensional metrics rather than
binary pass/fail assertions.

- **Evaluate any agent** — local coding agents (GitHub Copilot, Claude Code) via ACP stdio, remote agents via A2A/HTTP, or anything via custom adapters
- **Readable DSL** — define evaluation cases in YAML or Python with Given/When/Then clauses
- **Three grader layers** — deterministic checks, process validation, and AI-judged assessment, each running in progressive evaluation modes
- **Conversation simulation** — multi-turn dialogue evaluation with persona-driven simulated users
- **Scored signals** — every criterion produces a 0.0–1.0 score aggregated per metric, not a binary verdict

## Quick Start

```bash
# Install (Python; not yet on PyPI)
pip install "beval[all] @ git+https://github.com/vyta/beval.git#subdirectory=python"

# Scaffold a new evaluation project
beval init my-eval && cd my-eval
```

Define a case in `cases/example.yaml`:

```yaml
cases:
  - id: greets_user
    name: Agent greets the user
    category: general
    given:
      query: "Hello!"
    when:
      - the agent responds
    then:
      - "the answer should be: a friendly greeting"
      - "response_time < 5s"
```

Run the evaluation:

```bash
# Fast dev mode (deterministic graders only)
beval run --cases cases/ --handler echo

# Full validation (all grader layers, requires a judge model)
beval run --cases cases/ --agent agent.yaml --mode validation --judge-model o4-mini
```

See the [Python README](python/README.md) for the full integration guide — agent adapters, custom graders, programmatic usage, and CLI reference.

## How It Works

```
Case (Given/When/Then)
  → Agent produces output
    → Subject (normalized: input, output, time, metadata)
      → Graders score each criterion (0.0 – 1.0)
        → Grades aggregated per metric → overall score
```

**Cases** define behavioral specs: a setup (`given`), trigger (`when`), and
expected behaviors (`then`). Each `then` clause is a criterion string dispatched
to a **grader** by prefix matching (e.g. `response_time < 5s` →
deterministic latency grader, `the answer should be: ...` → AI judge).

**Three grader layers** run in progressive evaluation modes:

| Mode | Layers active | Use case |
|------|--------------|----------|
| `dev` | deterministic | Fast local iteration |
| `dev+process` | deterministic + process | CI pipelines |
| `validation` | all three | Pre-release quality gates |
| `monitoring` | all three | Production monitoring |

A case **passes** when its mean score across all non-skipped grades meets the
configured threshold (default 0.7). Results are JSON — per-grade scores,
per-metric averages, and an overall pass/fail for the run.

## Evaluating Local Agents

beval can evaluate agents running on your machine — not just cloud APIs. Using
the ACP stdio transport, beval spawns your agent as a subprocess, sends cases
over stdin/stdout via JSON-RPC, and collects responses for grading.

For example, to evaluate a GitHub Copilot custom agent:

```yaml
# agent.yaml
name: my-copilot-agent
protocol: acp
connection:
  transport: stdio
  command: ["copilot", "--acp", "--stdio", "--allow-all"]
  cwd: ${AGENT_REPO_ROOT}
init_prompt: "Launch my-agent.md"
timeout: 120
```

```bash
beval run --agent agent.yaml --cases cases/
```

beval manages the full subprocess lifecycle — spawn, initialize, evaluate, and
shut down. No extra infrastructure needed.

This works with any agent that speaks ACP over stdio, including GitHub Copilot
extensions and Claude Code. For agents already running locally, use `transport: tcp`
to connect to an existing process. For agents that don't speak ACP, the
`custom` protocol lets you provide your own Python adapter class.

See the [dt-coach](samples/dt-coach/) sample for a complete working example of
evaluating a GitHub Copilot agent locally.

## Conversation Simulation

beval can evaluate multi-turn dialogue by simulating users with configurable
personas and goals. A simulated user drives the conversation while graders
assess each turn and the conversation as a whole.

```
Simulator ──query──→ Agent
    ↑                  │
    └──agent_response──┘
         ↓
    Per-turn grading + progress tracking
         ↓
    Conversation-level grading + feedback
```

Define **personas** (who the simulated user is) and **goals** (what they're
trying to accomplish), then run:

```bash
beval converse run --config eval.config.yaml --output results/
```

See the [klingon-conversation](samples/klingon-conversation/) and
[dt-coach-conversation](samples/dt-coach-conversation/) samples for
working examples, or the [Conversation Simulation](python/README.md#conversation-simulation)
section of the Python README for the full guide.

## Samples

The [samples/](samples/) directory contains runnable end-to-end examples:

| Sample | Protocol | Description |
|--------|----------|-------------|
| [klingon-agent](samples/klingon-agent/) | A2A | Klingon tutor agent with Azure Entra ID auth |
| [klingon-conversation](samples/klingon-conversation/) | A2A | Multi-turn conversation evaluation for the Klingon Tutor |
| [smart-inventory-advisor](samples/smart-inventory-advisor/) | ACP | Multi-stage cases with deterministic + AI-judged graders |
| [dt-coach](samples/dt-coach/) | ACP | Design Thinking coaching agent evaluation |
| [dt-coach-conversation](samples/dt-coach-conversation/) | ACP | Multi-turn conversation evaluation for the DT Coach |

Each sample includes configuration, case files, and a `README.md` with setup and run instructions.

## Specification

The complete framework specification lives in [SPEC.md](SPEC.md) (v0.1.0).

| Document | Description |
|----------|-------------|
| [SPEC.md](SPEC.md) | Canonical specification (v0.1.0) |
| [spec/agent-adapters.spec.md](spec/agent-adapters.spec.md) | Agent adapter contract (§13) |
| [spec/judges.spec.md](spec/judges.spec.md) | Judge interface contract (§14) |
| [spec/conversation-sim.spec.md](spec/conversation-sim.spec.md) | Conversation simulation contract (§15) |
| [GUIDE.md](GUIDE.md) | Non-normative companion with recommended vocabularies and patterns |

## Installation

beval is not yet published to PyPI. Install directly from GitHub:

```bash
# Core only
pip install "beval @ git+https://github.com/vyta/beval.git#subdirectory=python"

# With all optional extras (ACP, A2A, validation, tracing)
pip install "beval[all] @ git+https://github.com/vyta/beval.git#subdirectory=python"
```

## Repository Structure

```text
beval/
├── SPEC.md              # Canonical specification
├── GUIDE.md             # Non-normative companion guide
├── spec/                # Shared specification artifacts
│   ├── schemas/         # JSON Schema definitions (results, config, case, agent, comparison)
│   ├── cli.spec.yaml    # Machine-readable CLI interface contract
│   ├── agent-adapters.spec.md          # Agent adapter specification (§13)
│   ├── judges.spec.md                  # Judges specification (§14)
│   ├── conversation-sim.spec.md        # Conversation simulation specification (§15)
│   └── otel-conventions.md             # OpenTelemetry span naming conventions
├── .claude/             # Claude Code project-scoped primitives
│   ├── skills/evaluate/ # /evaluate interactive setup wizard
│   └── agents/          # beval-runner sub-agent
├── conformance/         # Cross-language conformance test suite
│   ├── fixtures/        # Input/expected pairs for conformance testing
│   └── runner.sh        # Orchestrates all implementations
├── samples/             # End-to-end evaluation samples
│   ├── klingon-agent/           # A2A agent with Azure Entra ID auth
│   ├── klingon-conversation/    # Conversation simulation for Klingon Tutor
│   ├── smart-inventory-advisor/ # ACP agent with multi-stage cases
│   ├── dt-coach/                # Design Thinking coaching agent
│   └── dt-coach-conversation/   # Conversation simulation for DT Coach
├── python/              # Python implementation
├── typescript/          # TypeScript implementation
├── go/                  # Go implementation
└── dotnet/              # C# implementation
```

## Implementations

Each language implementation provides:

- A library for programmatic evaluation (DSL, graders, runner)
- A CLI (`beval`) conforming to [spec/cli.spec.yaml](spec/cli.spec.yaml)
- Conformance with the shared [JSON schemas](spec/schemas/)

| Language | Directory | Status |
|----------|-----------|--------|
| Python | [python/](python/) | Alpha |
| TypeScript | [typescript/](typescript/) | Alpha |
| Go | [go/](go/) | Alpha |
| C# | [dotnet/](dotnet/) | Alpha |

See [COMPATIBILITY.md](COMPATIBILITY.md) for the spec-to-implementation version matrix.

## Development

This repository uses containerized, ephemeral environments for all build, test, and lint operations via `make` targets. This approach ensures consistent behavior across different development environments without requiring local toolchain installations.

```bash
make test          # Run all tests
make lint          # Run all linters
make conformance   # Run conformance suite
```

Language-specific targets are available (e.g., `make python-test`, `make go-lint`, `make dotnet-build`). See the [Makefile](Makefile) for all available targets.

All commands use `nerdctl` by default; use `CONTAINER_RUNTIME=docker make <target>` to use Docker instead.

## Conformance Testing

The [conformance/](conformance/) directory contains fixture-based tests that all
implementations must pass. Each fixture provides a case definition, canned system
output, and the expected evaluation results. This ensures behavioral equivalence
across languages.

## Claude Code Integration

This repository ships with project-scoped Claude Code primitives in `.claude/`:

- **`/evaluate` skill** — an interactive 7-phase wizard that takes you from zero to a running beval evaluation: agent setup, case generation, config, run, results summary, and optional CI integration.
- **`beval-runner` sub-agent** — auto-triggers when you ask to re-run evaluations; remembers your project's file paths across sessions for instant re-runs.

Open this repository in Claude Code and type `/evaluate` to get started.

## License

This project is licensed under the [MIT License](LICENSE).
