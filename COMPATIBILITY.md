---
title: Compatibility Matrix
description: Tracks which implementation versions conform to which spec versions.
ms.date: 2026-03-04
---

## Spec-to-Implementation Version Matrix

This table tracks conformance between the beval specification and each language
implementation. An entry indicates that the implementation version has passed
the conformance test suite for the corresponding spec version.

| Spec Version | Python | TypeScript | Go  | C#  |
|--------------|--------|------------|-----|-----|
| v0.2.0       | 0.1.0  | —          | —   | —   |

## Implementation Status

All implementations target spec v0.2.0 and ship as version 0.1.0. Python is the
only implementation with a functional evaluation pipeline. The remaining three
have foundational scaffolding (types, DSL, grader registry, CLI argument
parsing) but cannot execute evaluations end-to-end.

| Capability                     | Python      | TypeScript  | Go          | C#          |
|--------------------------------|-------------|-------------|-------------|-------------|
| Core types                     | Complete    | Complete    | Complete    | Complete    |
| DSL (case builder)             | Complete    | Complete    | Complete    | Complete    |
| Grader registry                | Complete    | Partial     | Partial     | Partial     |
| Built-in graders               | Complete    | Missing     | Missing     | Missing     |
| Runner pipeline                | Complete    | Stub        | Stub        | Stub        |
| YAML loader                    | Complete    | Partial     | Stub        | Partial     |
| Reporter (JSON output)         | Complete    | Partial     | Stub        | Partial     |
| CLI `version`                  | Complete    | Complete    | Complete    | Complete    |
| CLI `run`                      | Complete    | Stub        | Stub        | Stub        |
| CLI `validate`                 | Complete    | Stub        | Stub        | Stub        |
| CLI `baseline`                 | Complete    | Stub        | Stub        | Stub        |
| CLI `cache`                    | Complete    | Stub        | Stub        | Stub        |
| Judge interface                | Complete    | Complete    | Complete    | Complete    |
| Schema validation              | Complete    | Complete    | Stub        | Stub        |
| OpenTelemetry tracing          | Complete    | Partial     | Stub        | Partial     |
| Baseline management            | Complete    | Missing     | Missing     | Missing     |
| Cache management               | Complete    | Missing     | Missing     | Missing     |
| Multi-stage pipelines          | Complete    | Missing     | Missing     | Missing     |
| Multi-trial support            | Complete    | Missing     | Missing     | Missing     |
| Skip-mode scoring              | Complete    | Missing     | Missing     | Missing     |
| Conformance tests              | Passing     | Not runnable| Not runnable| Not runnable|
| Sensitive value scrubbing      | Complete    | Missing     | Missing     | Missing     |

**Legend**: Complete = fully implemented, Partial = API exists but incomplete,
Stub = code present but non-functional, Missing = not yet started
