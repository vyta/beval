---
title: beval
description: A language-agnostic framework for behavioral evaluation of AI agents and LLM-powered systems.
ms.date: 2026-02-25
---

> [!IMPORTANT]
> This project is experimental and under active development. APIs, schemas, and
> CLI interfaces may change without notice. It is not intended for production use.

## Overview

beval (behavioral evaluation) is a framework for evaluating AI agents and
LLM-powered systems through scored, multi-dimensional metrics rather than
binary pass/fail assertions. It treats evaluation as a design tool, not a
verification afterthought.

The framework defines a readable DSL, three grader layers (deterministic,
process, AI-judged), and dual-mode execution that spans fast development
iteration through full validation. Agents are connected via a declarative YAML
adapter layer supporting ACP (stdio/TCP), A2A (HTTP), and custom protocols —
the same evaluation cases work across all of them.

## Specification

The complete framework specification lives in [SPEC.md](SPEC.md) (v0.1.0).
The agent adapter addendum is in [spec/agent-adapters.spec.md](spec/agent-adapters.spec.md).
The judges specification is in [spec/judges.spec.md](spec/judges.spec.md).
The Claude Code integration spec is in [spec/claude-code-integration.spec.md](spec/claude-code-integration.spec.md).

## Installation

beval is not yet published to PyPI. Install directly from GitHub:

```bash
pip install "beval[all] @ git+https://github.com/vyta/beval.git#subdirectory=python"
```

## Claude Code Integration

This repository ships with project-scoped Claude Code primitives in `.claude/`:

- **`/evaluate` skill** — an interactive 7-phase wizard that takes you from zero to a running beval evaluation: agent setup, case generation, config, run, results summary, and optional CI integration.
- **`beval-runner` sub-agent** — auto-triggers when you ask to re-run evaluations; remembers your project's file paths across sessions for instant re-runs.

Open this repository in Claude Code and type `/evaluate` to get started.

## Repository Structure

```text
beval/
├── SPEC.md              # Canonical specification
├── spec/                # Shared specification artifacts
│   ├── schemas/         # JSON Schema definitions (results, config, case, agent, comparison)
│   ├── cli.spec.yaml    # Machine-readable CLI interface contract
│   ├── agent-adapters.spec.md          # Agent adapter specification (§13)
│   ├── judges.spec.md                  # Judges specification (§14)
│   ├── claude-code-integration.spec.md # Claude Code skill + sub-agent specification
│   └── otel-conventions.md             # OpenTelemetry span naming conventions
├── .claude/             # Claude Code project-scoped primitives
│   ├── skills/evaluate/ # /evaluate interactive setup wizard
│   └── agents/          # beval-runner sub-agent
├── conformance/         # Cross-language conformance test suite
│   ├── fixtures/        # Input/expected pairs for conformance testing
│   └── runner.sh        # Orchestrates all implementations
├── samples/             # End-to-end evaluation samples
│   ├── klingon-agent/           # A2A agent with Azure Entra ID auth
│   ├── smart-inventory-advisor/ # ACP agent with multi-stage cases
│   └── dt-coach/                # Design Thinking coaching agent
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

See [COMPATIBILITY.md](COMPATIBILITY.md) for the spec-to-implementation version
matrix.
## Development

This repository uses containerized, ephemeral environments for all build, test, and lint operations via `make` targets. This approach ensures consistent behavior across different development environments without requiring local toolchain installations.

Run all tests:

```bash
make test
```

Run all linters:

```bash
make lint
```

Run conformance suite:

```bash
make conformance
```

Language-specific targets are available (e.g., `make python-test`, `make go-lint`, `make dotnet-build`). See the [Makefile](Makefile) for all available targets.

All commands use `nerdctl` by default; use `CONTAINER_RUNTIME=docker make <target>` to use Docker instead.


## Conformance Testing

The [conformance/](conformance/) directory contains fixture-based tests that all
implementations must pass. Each fixture provides a case definition, canned system
output, and the expected evaluation results. This ensures behavioral equivalence
across languages.

## Samples

The [samples/](samples/) directory contains runnable end-to-end examples:


| Sample | Protocol | Description |
|--------|----------|-------------|
| [klingon-agent](samples/klingon-agent/) | A2A | Remote agent with Azure Entra ID bearer auth |
| [smart-inventory-advisor](samples/smart-inventory-advisor/) | ACP | GHCP Agent. Multi-stage cases with deterministic + AI-judged graders |
| [dt-coach](samples/dt-coach/) | ACP | HVE Core Design Thinking coaching agent evaluation |

Each sample includes an `agent.yaml`, case files, and a `README.md` with run instructions.

## License

This project is licensed under the [MIT License](LICENSE).
