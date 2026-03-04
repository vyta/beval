---
title: OpenTelemetry Span Conventions for beval
description: Span naming patterns, required attributes, and status code mapping for process graders across all implementations.
ms.date: 2026-02-25
---

## Purpose

This document defines the OpenTelemetry span naming conventions that all beval
implementations must follow. Consistent span names and attributes ensure that
process graders produce identical evaluation results regardless of language.

## Span Naming Pattern

All beval spans follow the pattern:

```text
beval.{component}.{action}
```

### Standard Span Names

| Span Name | Component | Description |
|-----------|-----------|-------------|
| `beval.runner.execute_run` | runner | Top-level span for an entire evaluation run |
| `beval.runner.execute_case` | runner | Execution of a single evaluation case |
| `beval.grader.evaluate` | grader | Execution of a single grader against a subject |
| `beval.judge.evaluate` | judge | Execution of an AI judge grader |
| `beval.system.invoke` | system | Invocation of the system being evaluated |
| `beval.cache.lookup` | cache | Cache lookup for a system or judge response |

### System-Emitted Span Names

System instrumentation uses OpenTelemetry semantic conventions rather than the
`beval.*` prefix. Process graders match against these patterns:

| Span Name Pattern | Represents |
|-------------------|------------|
| `tool.call.{tool_name}` | A tool or function invocation |
| `agent.run.{agent_name}` | An agent's execution loop |
| `llm.request` | An LLM API call |

## Required Span Attributes

### Runner Spans

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `beval.run.id` | string | Yes | Unique identifier for the evaluation run |
| `beval.run.mode` | string | Yes | Evaluation mode (dev, dev+process, validation, monitoring) |
| `beval.run.label` | string | No | Optional run label |

### Case Spans

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `beval.case.id` | string | Yes | Case identifier |
| `beval.case.name` | string | Yes | Human-readable case name |
| `beval.case.category` | string | Yes | Case category |
| `beval.case.stage` | int | No | Stage index for multi-stage cases |

### Grader Spans

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `beval.grader.name` | string | Yes | Grader pattern or name |
| `beval.grader.layer` | string | Yes | Grader layer (deterministic, process, ai_judged) |
| `beval.grader.metric` | string | Yes | Metric category for the grade |
| `beval.grader.score` | float | Yes | Score produced by the grader (0.0 to 1.0) |
| `beval.grader.passed` | bool | Yes | Whether the grade passed the threshold |

### System Span Attributes

Process graders inspect these attributes on system-emitted spans:

| Attribute | Type | Used By |
|-----------|------|---------|
| `tool.name` | string | "the agent should have called" grader |
| `tool.status` | string (`ok` or `error`) | "no tool calls should have failed" grader |
| `agent.name` | string | "agent runs should be at most" grader |

## Status Code Mapping

Beval maps grader scores to OpenTelemetry span status codes:

| Condition | OTel Status | Status Code |
|-----------|-------------|-------------|
| `score >= grade_pass_threshold` | OK | 1 |
| `score < grade_pass_threshold` | ERROR | 2 |
| Grader skipped due to mode | UNSET | 0 |
| Grader threw an exception | ERROR | 2 |

Set the span status message to the grade detail string when the status is ERROR.

## Span Relationship Model

Spans form a parent-child hierarchy reflecting the evaluation structure:

```text
beval.runner.execute_run
  └── beval.runner.execute_case (per case)
        ├── beval.system.invoke
        │     ├── agent.run.{name}
        │     │     ├── tool.call.{name}
        │     │     └── llm.request
        │     └── ...
        └── beval.grader.evaluate (per grader)
```

For multi-stage cases, each stage invocation is a child of the case span:

```text
beval.runner.execute_case
  ├── beval.system.invoke [stage=0]
  ├── beval.grader.evaluate [stage=0, grader 1]
  ├── beval.grader.evaluate [stage=0, grader 2]
  ├── beval.system.invoke [stage=1]
  ├── beval.grader.evaluate [stage=1, grader 1]
  └── ...
```

## InMemorySpanExporter Usage

For offline evaluation, implementations must use an in-memory span exporter to
capture system traces for process graders. The lifecycle per case:

1. Clear the in-memory exporter.
2. Invoke the system (spans are captured automatically).
3. Read captured spans from the exporter.
4. Attach spans to the Subject.
5. Execute process graders with access to the span data.

Implementations should use the standard OpenTelemetry SDK's in-memory exporter
for the target language (e.g., `InMemorySpanExporter` in Python and Java,
`InMemoryExporter` in .NET, `tracetest` or `sdktrace` in Go).

## Dual-Mode Tracing

The same system instrumentation supports both evaluation and production
observability. Implementations configure two exporters simultaneously:

| Exporter | Purpose | When Active |
|----------|---------|-------------|
| In-memory | Process grader evaluation | Always (offline eval) |
| Cloud (e.g., Application Insights) | Production observability | When connection string is configured |

This ensures no separate instrumentation is required for development versus
production environments.
