---
title: "beval — C#"
description: "C# implementation of the beval behavioral evaluation framework"
---

> [!IMPORTANT]
> This implementation is incomplete and under active development. Core types, the
> grader registry, DSL builder, and loader are in place, but the runner pipeline
> (`Runner.RunCase`) is not yet implemented. Expect breaking changes.

## Overview

C# implementation of the beval behavioral evaluation framework targeting .NET 8.

This package provides a class library and CLI tool for defining, running, and
reporting behavioral evaluations of AI agents and LLM-powered systems. It
implements the [beval specification](../SPEC.md) using idiomatic C# constructs.

## Prerequisites

- .NET 8 SDK

## CLI

```bash
dotnet run --project src/Beval.Cli -- --help
dotnet run --project src/Beval.Cli -- version
dotnet run --project src/Beval.Cli -- run -m dev -l my-label
```

## Development

The repository uses containerized environments via `make` targets for all development operations. This ensures consistent behavior without requiring a local .NET SDK installation.

Build:

```bash
make dotnet-build
```

Run tests:

```bash
make dotnet-test
```

All commands use containerized environments with `nerdctl` (or `docker` with `CONTAINER_RUNTIME=docker make dotnet-test`).

## Project structure

```text
src/
  Beval/                Class library (NuGet: Beval)
    Models/             Core type definitions
    Dsl/                DSL fluent builder
    Graders/            Grader registry and interface
    Judges/             LLM judge interface
    Reporters/          Result reporting
    Runner.cs           Runner orchestration
    Loader.cs           YAML case loading
    Schema.cs           JSON Schema validation
    Tracing.cs          OpenTelemetry tracing
  Beval.Cli/            CLI tool (dotnet tool: beval)
    Program.cs          CLI entrypoint
test/
  Beval.Tests/          xUnit tests
```

## Specification conformance

This implementation targets [beval spec v0.1.0](../SPEC.md). Cross-language
conformance is validated using shared fixtures in [`../conformance/`](../conformance/).
