---
description: >
  Informative companion to SPEC.md with recommended vocabularies,
  implementation guidance, and optional advanced features for the
  Behavioral Evaluation Framework.
---

# Implementation Guide

This document collects informative (non-normative) material that
complements the [Behavioral Evaluation Framework Specification](SPEC.md).
Nothing in this guide overrides or adds to the normative requirements in
SPEC.md. When the two documents conflict, SPEC.md takes precedence.

## Table of Contents

1. Recommended Pattern Vocabulary
2. Recommended Metric Vocabulary
3. Implementation Guidance
4. Optional Advanced Features

## 1. Recommended Pattern Vocabulary

The following pattern vocabulary is a recommended shared starting point
for built-in graders. Implementations should support these patterns when
applicable to their target domain. The specific patterns, detail
messages, and registration order are not normative.

| Pattern prefix                       | Layer         | Metric      | Description                          |
|--------------------------------------|---------------|-------------|--------------------------------------|
| `the answer should mention`          | deterministic | relevance   | Substring presence in output         |
| `the answer should not mention`      | deterministic | relevance   | Substring absence in output          |
| `completion time should be under`    | deterministic | latency     | Latency threshold check              |
| `there should be at least`           | deterministic | coverage    | Metadata count threshold             |
| `the agent should have called`       | process       | correctness | Tool-call presence in spans/metadata |
| `no tool call should have failed`    | process       | correctness | Tool-call failure absence            |
| `the answer should be`               | ai_judged     | quality     | Generic quality criterion via judge  |

Implementations may register additional built-in graders beyond this table.

## 2. Recommended Metric Vocabulary

The following metric categories provide a shared vocabulary for score
grouping across implementations. Implementations should recognize these
names when applicable. Additional categories may be defined freely.

* `latency`
* `coverage`
* `relevance`
* `groundedness`
* `correctness`
* `quality`
* `safety`
* `cost`

## 3. Implementation Guidance

### 3.1 Caching strategies

Recommended cache key structures:

* Output cache: keyed by input content and configuration hash
* Judge-response cache: keyed by answer, criterion, model identifier,
  and prompt version

Provide cache bypass and cache-clear controls to support iterative
development.

### 3.2 Grader execution safety

Recommended controls for custom grader isolation:

* Grader allow-lists for validation and monitoring modes
* Per-grader execution timeouts
* Restricted network access for custom graders by default

### 3.3 Monitoring data governance

When evaluating live traffic, consider these controls:

* PII handling and redaction policies
* Data retention limits
* Data classification boundaries
* Asynchronous evaluation to avoid production latency impact

### 3.4 Trial best practices

* Use trials >= 3 for AI-judged graders in `validation` mode to reduce
  score noise
* Use `median` aggregation to mitigate outlier effects from
  non-determinism
* Track score variance over time as a stability signal; rising variance
  indicates the system or the evaluation is becoming unreliable
* Pin model versions and temperature settings in configuration to
  minimize uncontrolled variance

## 4. Optional Advanced Features

These features are recommended for mature deployments but are not
required for conformance.

### 4.1 Judge calibration

Periodic comparison of judge scores against human-labeled benchmark sets
helps detect drift in evaluation quality.

### 4.2 Multi-judge consensus

Consensus across multiple judge models improves evaluation reliability.
A recommended default is median consensus with disagreement flags.

### 4.3 Baselines and regression checks

Baseline snapshot save/compare workflows and metric regression
thresholds support continuous quality tracking.

### 4.4 Watch mode

File-watch workflows that re-run affected cases after case or prompt
changes accelerate development iteration.
