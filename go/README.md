# beval — Go

> [!IMPORTANT]
> This implementation is incomplete and under active development. Core types, the
> grader registry, and the CLI scaffold are in place, but the runner pipeline,
> subject handling, and judge integration are not fully wired. Expect breaking
> changes.

Go implementation of the beval behavioral evaluation framework.

## Overview

This package provides a Go library and CLI for defining, running, and reporting
behavioral evaluations of AI agents and LLM-powered systems. It implements the
[beval specification](../SPEC.md) using idiomatic Go constructs.

## Installation

```bash
go get github.com/org/beval/go
```

## Quick start

```go
package main

import (
    eval "github.com/org/beval/go"
)

func main() {
    s := eval.Case("AI legislation search", eval.Category("legislation"))
    s.Given("a query", "What actions has Congress taken on AI policy?")
    s.When("the agent researches this query")
    s.Then("completion time should be under", 20)
    s.Then("the answer should mention", "artificial intelligence")
}
```

## CLI

```bash
go run ./cmd/beval run --mode dev --label my-agent
go run ./cmd/beval validate --cases ./cases/
go run ./cmd/beval version
```

## Project layout

| Path | Description |
| --- | --- |
| `*.go` | Public library (package `beval`) |
| `graders/` | Grader registry and interface (package `graders`) |
| `internal/cli/` | Internal CLI implementation |
| `cmd/beval/` | CLI entrypoint |

## Development
The repository uses containerized environments via `make` targets for all development operations. This ensures consistent behavior without requiring a local Go installation.

Run tests:


```bash
make go-test
```

Run linting:

```bash
make go-lint
```

All commands use containerized environments with `nerdctl` (or `docker` with `CONTAINER_RUNTIME=docker make go-test`).

## Specification conformance

This implementation targets [beval spec v0.2.0](../SPEC.md). Cross-language
conformance fixtures live in [`../conformance/`](../conformance/).
