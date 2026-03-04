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
iteration through full validation.

## Specification

The complete framework specification lives in [SPEC.md](SPEC.md) (v0.1.0).

## Repository Structure

```text
beval/
├── SPEC.md              # Canonical specification
├── spec/                # Shared specification artifacts
│   ├── schemas/         # JSON Schema definitions (results, config, case, comparison)
│   ├── cli.spec.yaml    # Machine-readable CLI interface contract
│   └── otel-conventions.md  # OpenTelemetry span naming conventions
├── conformance/         # Cross-language conformance test suite
│   ├── fixtures/        # Input/expected pairs for conformance testing
│   └── runner.sh        # Orchestrates all implementations
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

## License

This project is licensed under the [MIT License](LICENSE).
