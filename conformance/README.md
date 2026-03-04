---
title: Conformance Test Suite
description: Cross-language conformance tests ensuring all beval implementations produce identical results for the same inputs.
ms.date: 2026-03-02
---

## Purpose

The conformance test suite verifies that all beval implementations (Python,
TypeScript, Go, C#) produce identical evaluation results for a given set of
inputs. Because beval is a specification-driven framework, behavioral
equivalence across implementations is a first-class requirement.

## Fixture Structure

Each fixture set follows a multi-file pattern:

| File                 | Purpose                                                   |
|----------------------|-----------------------------------------------------------|
| `input.yaml`         | Case definition using pre-resolved grades (SPEC §3.6)    |
| `subject.json`       | Minimal subject placeholder (grades bypass grader lookup) |
| `expected.json`      | Expected results that all implementations must produce    |
| `config.yaml`        | Optional configuration overrides for the fixture          |
| `expected-exit-code` | Expected process exit code (SPEC §7.4)                    |

The `yaml-safety` fixture is an exception: it contains only `malicious.yaml`
with unsafe YAML constructs that all implementations must reject.

## Design Philosophy

Conformance fixtures test **framework mechanics**, not grader implementations.
Cases supply pre-resolved grades directly (see SPEC §3.6), so the framework
only needs to demonstrate correct score aggregation, skip-mode behavior, result
schema compliance, and multi-stage orchestration.

Built-in grader correctness (matching patterns, evaluating subjects, producing
detail messages) is validated through per-implementation unit tests. This
separation ensures that conformance passes are not coupled to identical grader
detail strings or specific grader registration order across languages.

## Running Conformance Tests

The conformance test suite uses containerized builds via `make` targets to ensure consistent, reproducible artifacts across all implementations.

Run all conformance tests:

```bash
make conformance
```

Or run the conformance script directly (after building):

```bash
./conformance/runner.sh
```

Run conformance tests for specific languages:

```bash
./conformance/runner.sh --languages python,go
```

### Build Process

The conformance suite builds each implementation in an isolated container:

```bash
make conformance-build-python   # Build Python implementation
make conformance-build-go       # Build Go implementation
make conformance-build-dotnet   # Build .NET implementation
make conformance-build-ts       # Build TypeScript implementation
```

These containerized builds ensure consistent environments regardless of local toolchain state. All build operations use `nerdctl` by default (override with `CONTAINER_RUNTIME=docker`).

### Execution Flow

Each implementation's conformance execution:

1. Reads `input.yaml` and parses it as a beval case.
2. Loads `subject.json` as context (not used for grading when grades are pre-resolved).
3. Loads `config.yaml` if present and applies configuration overrides.
4. Uses pre-resolved grades directly from the case definition.
5. Aggregates grades into case results and a run summary.
6. Produces a results JSON.
7. Compares the produced results against `expected.json`.

### Verification Phases

The runner performs four verification phases:

1. **Output comparison**: results JSON must match `expected.json` exactly (after stripping volatile fields like `timestamp` and `time_seconds`).
2. **Exit code verification**: process exit code must match `expected-exit-code` per SPEC §7.4.
3. **YAML safety**: malicious YAML must be rejected with a non-zero exit and no valid results produced.
4. **Schema validation**: all results JSON files must validate against `spec/schemas/results.schema.json`.

## Fixture Design Principles

Fixtures supply pre-resolved grades to ensure reproducible, grader-independent
results across languages and platforms. AI-judged grades can be included with
`skipped: true` to test skip-mode aggregation.

Expected results include exact numeric scores to verify cross-language
floating-point consistency. Implementations must produce scores that match to
at least six decimal places. Fixture authors should choose score values that
produce exact IEEE 754 results (e.g., 0.5, 0.25, 0.75, 0.875) to avoid
cross-language rounding discrepancies.

Configuration overrides (thresholds, weights, skip modes) are specified in an
optional `config.yaml` file in the fixture directory. The runner passes this
file via `--config` when present.

## Fixture Sets

### basic-deterministic

Validates core evaluation flow with a single case and two pre-resolved grades.
Verifies that two deterministic grades with `score: 1.0` aggregate to an
overall score of `1.0` and the case passes. Exit code: `0`.

### scoring-aggregation

Tests score aggregation across multiple grades with varying scores and metric
categories. Verifies correct arithmetic mean calculation for both per-case
overall score and per-metric averages (relevance: mean of 1.0 and 0.8 = 0.9,
latency: 0.6, coverage: 1.0, overall: 0.85). Exit code: `0`.

### mixed-scores

Tests aggregation when grades have a mix of passing and failing scores.
One grade scores `1.0` and another scores `0.0`, producing an overall of
`0.5`. The case must be marked as failed (`0.5 < 0.7` threshold). Exit code: `1`.

### skipped-grade-aggregation

Verifies that skipped grades are excluded from score aggregation in the
default `exclude` skip mode. The case includes two deterministic grades scoring
`1.0` and one AI-judged grade marked `skipped: true`. The overall score must be
`1.0` (reflecting only the two non-skipped grades). The skipped grade must
still appear in the grades array. Exit code: `0`.

### optimistic-skip-mode

Tests the `optimistic` skip mode (SPEC §6.2). Skipped grades score `1.0` and
are included in aggregation. Four grades: two deterministic (1.0, 0.5) and two
AI-judged skipped. Overall = (1.0 + 0.5 + 1.0 + 1.0) / 4 = 0.875. Case
passes. Uses `config.yaml` with `skip_mode: optimistic`. Exit code: `0`.

### strict-skip-mode

Tests the `strict` skip mode (SPEC §6.2). Skipped grades score `0.0` and are
included in aggregation. Same four grades as optimistic fixture. Overall =
(1.0 + 0.5 + 0.0 + 0.0) / 4 = 0.375. Case fails (`0.375 < 0.7`). Uses
`config.yaml` with `skip_mode: strict`. Exit code: `1`.

### weighted-scoring

Tests metric-level weighted scoring (SPEC §5.5). Two grades: relevance (0.8)
with weight 3.0 and latency (1.0) with weight 1.0. Weighted overall =
(0.8 × 3 + 1.0 × 1) / (3 + 1) = 0.85. Uses `config.yaml` with
`metric_weights`. Exit code: `0`.

### multi-case-aggregation

Tests cross-case aggregation with errored case exclusion (SPEC §5.2). Three
cases: one passing (overall 1.0), one failing (overall 0.5), one errored
(multi-stage with stage 2 error). Summary overall = mean of non-errored =
(1.0 + 0.5) / 2 = 0.75. Errored case excluded from summary metrics. Exit
code: `3` (infrastructure error from errored case).

### config-override

Tests configuration precedence (SPEC §9.1). Uses `config.yaml` with
`case_pass_threshold: 0.4`. A case with overall 0.5 that would fail under the
default threshold (0.7) passes with the lowered threshold. Exit code: `0`.

### multi-stage-failure

Tests multi-stage pipeline behavior when a later stage fails. Stage 1 supplies
passing grades. Stage 2 includes an error and zero-score grades. The case must
be marked as errored with stage-indexed diagnostics preserved. Summary metrics
exclude the errored case. Exit code: `3`.

### yaml-safety

Contains YAML documents with unsafe constructs (arbitrary code execution tags,
billion-laughs entity expansion). All implementations must reject these inputs
with a non-zero exit code rather than processing them.

## Adding New Fixtures

To add a new conformance fixture:

1. Create a directory under `conformance/fixtures/` with a descriptive name.
2. Add `input.yaml` with the case definition using pre-resolved grades.
3. Add `subject.json` (can be `{}` when grades are pre-resolved).
4. Generate `expected.json` by computing the expected aggregation by hand. Use
   score values that produce exact IEEE 754 floating-point results.
5. Add `expected-exit-code` with the expected process exit code per SPEC §7.4.
6. Optionally add `config.yaml` for threshold, weight, or skip-mode overrides.
7. Verify all four implementations pass the new fixture.
8. Document the fixture's purpose in this README.

