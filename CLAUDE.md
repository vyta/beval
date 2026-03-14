# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

beval is a language-agnostic framework for behavioral evaluation of AI agents and LLM-powered systems. It uses a specification-driven approach (SPEC.md) with scored, multi-dimensional evaluation rather than binary pass/fail. The spec defines three grader layers: deterministic, process, and ai_judged.

Implementations exist in Python (complete), TypeScript, Go, and C# (all incomplete). A shared conformance test suite in `conformance/` ensures behavioral equivalence across implementations.

## Build & Test Commands

**All development uses containerized environments via `make` targets. Do not run commands directly with local toolchains.** The container runtime defaults to `nerdctl`; override with `CONTAINER_RUNTIME=docker` if needed.

```bash
# Python
make python-test       # pytest
make python-lint       # ruff check
make python-typecheck  # mypy
make python-check      # lint + test

# TypeScript
make ts-test           # vitest run
make ts-lint           # eslint

# Go
make go-test           # go test ./...
make go-lint           # go vet ./...

# .NET
make dotnet-build
make dotnet-test

# Cross-language
make conformance       # Run all conformance fixtures across all implementations
make test              # All language tests
make lint              # All language linters
make clean             # Remove containers, caches, build artifacts
```

### Running single tests locally (when containerized runs are impractical)

```bash
# Python (requires uv)
cd python && uv sync --extra dev
uv run pytest tests/test_runner.py               # single file
uv run pytest tests/test_runner.py::test_name    # single test
uv run pytest -k "skip_mode"                     # pattern match

# TypeScript
cd typescript && npm install
npm test -- --run tests/types.test.ts

# Go
cd go && go test ./... -run TestGraderRegistry

# .NET
cd dotnet && dotnet test --filter "ClassName=TestName"
```

## Architecture

### Specification (normative)

- **SPEC.md** — The normative specification (v0.1.0). All implementations must conform to it.
- **spec/schemas/** — JSON Schema definitions for results, config, case, and comparison formats.
- **spec/cli.spec.yaml** — Machine-readable CLI interface contract.
- **GUIDE.md** — Informative companion with best practices and recommended vocabularies.

### Evaluation Model

**Entities**: Case → Subject → Grade → CaseResult → RunResult

- **Case**: Behavioral spec with Given/When/Then clauses
- **Subject**: Normalized system output (input, output, completion_time, metadata, spans, tool_calls)
- **Grade**: Single grader outcome (criterion, score 0.0–1.0, metric, layer, passed)
- **Score aggregation**: per-metric mean → overall mean, with case pass threshold (default 0.7)

**Evaluation modes** control which grader layers run: `dev` (deterministic only), `dev+process`, `validation` (all), `monitoring` (all).

**Exit codes**: 0=pass, 1=fail, 2=input error, 3=infrastructure error, 4=internal error.

### Per-Language Implementation Structure

Each implementation follows the same module layout:

| Module | Purpose |
|--------|---------|
| `types` | Core frozen/immutable data types (Grade, Subject, CaseResult, etc.) |
| `dsl` | Case definition DSL with fluent builder pattern |
| `runner` | Orchestration + score aggregation |
| `graders/` | Grader registry + built-in handlers |
| `judge` | LLM judge interface (pluggable) |
| `loader` | YAML case file parsing (safe mode only) |
| `cli` | CLI entry point (run, validate, baseline, cache, version) |
| `reporter` | JSON result formatting |
| `cache` | Output caching |
| `baseline` | Baseline save/compare |

### Grader Handler Signature (all languages)

All grader handlers take `(criterion, args, subject, context)` and return a `Grade`. Graders are registered with a pattern prefix string and dispatched by the runner via pattern matching.

### Conformance Fixtures

Each fixture in `conformance/fixtures/` contains `input.yaml`, `subject.json`, `expected.json`, optional `config.yaml`, and `expected-exit-code`. Fixtures use pre-resolved grades to bypass grader lookup and test pure aggregation/scoring logic.
