---
description: Lean normative specification for the Behavioral Evaluation Framework
---

# Behavioral Evaluation Framework Specification

A language-agnostic framework for behavioral evaluation of AI agents and LLM-powered systems.

Status: Draft
Version: 0.1.0

## Table of Contents

1. Scope and Goals
2. Core Model
3. DSL Contract
4. Grader Contract
5. Scoring Contract
6. Execution Modes
7. Runner Contract
8. Results Contract
9. Configuration Contract
10. Security and Safety Requirements
11. Non-determinism and Multi-trial Evaluation
12. Extension Points

See [GUIDE.md](GUIDE.md) for informative companion material including
recommended vocabularies, implementation guidance, and optional advanced
features.

## 1. Scope and Goals

This specification defines the semantic contract for behavioral evaluation.
Implementations in different languages may vary in syntax but must preserve behavior.

The framework evaluates system behavior using scored graders across three layers:

* Deterministic
* Process
* AI-judged

Design goals:

* Keep evaluation authoring simple and readable
* Keep developer feedback fast in development mode
* Reuse the same case definitions across development, validation, and monitoring
* Emphasize scored quality signals over binary pass/fail alone

## 2. Core Model

### 2.1 Core entities

* Case: Behavioral specification with Given/When/Then clauses
* Grade: Single grader outcome with score, metric, pass/fail, and metadata
* CaseResult: Aggregated grades for one case
* Report: Aggregated CaseResults for one run
* Subject: Normalized output exposed to graders
* Runner: Orchestrator that executes cases and collects results
* Judge: Evaluator for AI-judged criteria

### 2.2 Required fields

Case:

* `id` (string, unique within a run)
* `name` (string)
* `category` (string)
* `tags` (string array, optional)

Grade:

* `criterion` (string)
* `score` (float, `0.0..1.0`)
* `metric` (string)
* `passed` (boolean)
* `detail` (string or null)
* `layer` (string: one of the built-in layers `deterministic`, `process`,
  `ai_judged`, or a custom layer registered by the implementation)
* `skipped` (boolean)
* `stage` (integer or null, optional)
* `stage_name` (string or null, optional)

Subject:

* `input` (string or message array) — the prompt, query, or instruction sent
  to the system. When the system accepts structured input (e.g., chat messages
  with roles), implementations should preserve the structured form. Graders
  that require string input must use the last user-role message or
  implementation-defined stringification.
* `output` (string or message array) — the system's primary response. When the
  system produces structured output, implementations should preserve it.
  Graders that require string output must use the last assistant-role message
  or implementation-defined stringification.
* `completion_time` (float seconds)
* `tool_calls` (tool-call array, optional) — tools invoked during execution
* `spans` (span array, optional) — trace spans captured during execution
* `metadata` (map) — open-ended key-value pairs for domain-specific data
* `stage` (integer or null)
* `stage_name` (string or null)
* `prior_subject` (Subject or null)

Domain-specific fields such as retrieval counts, citation counts, and source
lists belong in `metadata` rather than top-level Subject fields.
Graders access these values via `metadata` keys.

Subject field naming note: implementations may provide convenience aliases
(e.g., `query`/`answer`) but the canonical field names are `input`/`output`.

### 2.3 Invariants

* Subject is read-only to graders
* All scores are normalized to `0.0..1.0`
* Pass/fail is derived from score thresholds
* Missing grader matches produce a grade, not an exception

## 3. DSL Contract

### 3.1 Syntax semantics

The DSL uses `given`, `when`, and `then`.
`then` clauses map to grader patterns and produce scores.

Canonical form:

```text
case "AI legislation search" [category: legislation]
  given "a query" = "What actions has Congress taken on AI policy?"
  when  "the agent researches this query"
  then  "completion time should be under" 20
  then  "the answer should mention" "artificial intelligence"
  then  "the agent should have called" "search_govinfo"
  then  "the answer should be" "comprehensive and well-sourced"
```

The criterion strings in this example reference the recommended pattern
vocabulary in [GUIDE.md §1](GUIDE.md) and are illustrative, not normative.

### 3.2 Case identity and filtering keys

Each case must define `id`, `name`, and `category`.
Implementations should support optional `tags`.

### 3.3 Parameterization

Implementations may support examples-driven case expansion.
Each example row becomes an independent case instance with derived ID:

* `{case_id}[{index}]`

Required behavior:

* Instances inherit category and tags from parent case
* Each instance has independent grading and pass/fail status

### 3.4 Shared context

Implementations may support reusable background Given values.
When both background and case define the same key, case-level value wins.

### 3.5 Multi-stage pipelines

A case may declare multiple `when` clauses.
Each `when` starts a stage.
`then` clauses following a `when` grade that stage output.

Required behavior:

* Stages execute sequentially
* Prior stage Subject is available as next stage input via `prior_subject`
* Single-stage cases remain valid without changes

### 3.6 Pre-resolved grades

A case may supply pre-resolved grades in place of `then` clauses. When
`grades` is present the runner bypasses grader pattern matching and uses
the supplied grades directly.

Each entry in the `grades` array carries the same fields as a Grade (§2.2):
`criterion`, `score`, `metric`, `layer`, `passed`, `detail`, and `skipped`.
The `stage` and `stage_name` fields are derived from the enclosing stage
context when the case uses multi-stage pipelines.

In multi-stage cases each stage may use `grades` instead of `then`, and may
include an `error` string to simulate a stage execution failure.

Pre-resolved grades enable deterministic conformance testing of framework
mechanics (score aggregation, skip-mode behavior, result schema compliance,
multi-stage orchestration) without coupling to any specific grader
implementation.

## 4. Grader Contract

### 4.1 Registration interface

```text
register_grader(pattern: string, handler: GraderHandler, options: GraderOptions)

GraderHandler = (criterion: string, args: any[], subject: Subject, context: EvalContext) -> Grade

GraderOptions:
  layer: deterministic | process | ai_judged
  metric: string
```

### 4.2 Pattern matching

Required resolution order:

1. Exact match (case-insensitive)
2. Longest prefix match (case-insensitive): among all registered patterns that
   are a prefix of the criterion, select the pattern with the longest length
3. Ambiguous match: if two or more patterns share the same longest prefix
   length, the runner must fail the grade with `score: 0.0` and a diagnostic
   detail naming the conflicting patterns. Implementations must not silently
   pick one.
4. No match: grade with `score: 0.0` and diagnostic detail

Pattern collision detection: implementations must detect and report collisions
at grader registration time when one pattern is a prefix of another and both
are registered to different handlers. A warning is acceptable at registration;
resolution-time ambiguity is always an error as described in step 3.

### 4.3 EvalContext

EvalContext provides runtime dependencies and mode:

* `evaluators` (map of string to Evaluator): named evaluator backends
  available to graders. The key `"judge"` is reserved for the primary
  LLM-as-judge evaluator when configured. Implementations must also
  support `llm_judge` as a convenience alias for `evaluators["judge"]`
  for backward compatibility.
* `mode` (evaluation mode)
* `config` (non-sensitive config view)

Credential handling requirement:

* EvalContext must not expose raw secrets to graders

### 4.4 Grader layers

Implementations must support these three built-in layers:

* Deterministic: objective checks against Subject
* Process: checks against traces/spans
* AI-judged: subjective checks via configured judge/evaluator

Implementations may define additional custom layers (e.g., `safety`,
`cost`, `regression`). Custom layers must follow the same grading and
scoring contracts as built-in layers. Mode definitions (§6.1) control
which layers are active for a given run.

### 4.5 Built-in graders

Implementations should ship built-in graders and must document their
registered patterns, including the pattern string, layer, metric, and
expected arguments. The specific grader inventory is an implementation
concern; [GUIDE.md §1](GUIDE.md) provides a recommended starting-point
vocabulary.

Built-in grader correctness (pattern matching, subject evaluation,
detail messages) is validated through per-implementation unit tests, not
cross-language conformance tests. Conformance fixtures test framework
mechanics only: score aggregation, skip-mode behavior, result schema
compliance, and multi-stage orchestration. All conformance cases supply
pre-resolved grades (§3.6) so that passes are not coupled to identical
grader detail strings or registration order across languages.

## 5. Scoring Contract

### 5.1 Score range

All grades and aggregate scores must use float values in `0.0..1.0`.

### 5.2 Default aggregation

* Case overall score: arithmetic mean of non-skipped grade scores
* Dataset/run overall score: arithmetic mean of case overall scores, excluding errored cases

Skipped grades must be excluded from score aggregation by default.
See §6.2 for skip semantics and alternative modes.

### 5.3 Threshold defaults

Default thresholds:

* Grade pass threshold: `0.5` where pass is `score > threshold`
* Case pass threshold: `0.7` where pass is `overall_score >= threshold`

### 5.4 Metric categories

Grades carry a free-form `metric` string for score grouping.
Implementations must document their supported metric categories.
[GUIDE.md §2](GUIDE.md) provides a recommended starting-point vocabulary.

### 5.5 Weighted scoring

Implementations must support metric-level weights.
When weights are specified in case definitions or configuration, use:

```text
overall_score = sum(grade.score * metric_weight) / sum(metric_weight)
```

Unspecified metric weights default to `1.0`, which produces behavior identical
to unweighted arithmetic mean.

Skipped grades are excluded from weighted aggregation unless an alternative
skip mode is active (see §6.2).

Portability requirement: because weights affect scores, all implementations
must honor weight values present in case definitions. An implementation that
encounters weights it cannot process must report an error, not silently
ignore them.

## 6. Execution Modes

### 6.1 Required modes

Implementations must support at least these named modes:

* `dev`: deterministic only
* `dev+process`: deterministic + process
* `validation`: deterministic + process + ai_judged

Monitoring mode is optional but recommended.

Implementations should additionally support custom mode definitions that
specify an explicit set of active layers. Named modes above are shorthand
for their layer sets. When custom layers exist (§4.4), custom modes
provide the mechanism to include or exclude them.

### 6.2 Skip semantics

If a grader layer is inactive for the current mode, the runner must emit a
skipped grade with `skipped: true`.

Skipped grades are excluded from score aggregation by default. This ensures
that running in `dev` mode produces scores reflecting only deterministic
graders, without inflation or deflation from inactive layers.

Implementations must support three skip modes, selectable via configuration:

* `exclude` (default): skipped grades are omitted from score aggregation
* `optimistic`: skipped grades score `1.0` and are included in aggregation
* `strict`: skipped grades score `0.0` and are included in aggregation

Skipped grades must always appear in the `grades` array of CaseResult
regardless of skip mode, to maintain visibility into which graders were
not executed.

### 6.3 Mode ownership

Mode selection is a runner concern, not a case concern.
Cases remain unchanged across modes.

## 7. Runner Contract

### 7.1 Responsibilities

Runner responsibilities:

1. Discover and filter cases
2. Execute the target system
3. Build normalized Subject
4. Execute applicable graders
5. Collect CaseResults
6. Produce a Report

### 7.2 Execution lifecycle

```text
for each case:
  clear trace capture
  execute system
  normalize output to Subject
  execute Then clauses as graders
  collect grades and case result
aggregate report
```

Multi-stage behavior:

* Execute stages in order
* Halt subsequent stages when a stage execution fails
* Preserve stage-indexed diagnostics in results

### 7.3 Filtering support

Runner should support filtering by:

* Case ID
* Category
* Tag
* Mode

### 7.4 Exit codes

Runner must use these process exit codes:

* `0`: all cases pass
* `1`: one or more cases fail
* `2`: invalid input (unparseable YAML, schema violations, missing files)
* `3`: infrastructure error (judge API unreachable, container failure, timeout)
* `4`: internal error (unexpected exception in the runner itself)

When multiple error categories occur in a single run, the runner must return
the highest applicable exit code.

## 8. Results Contract

### 8.1 Output format

Results must be persisted as JSON for one run.

Required top-level fields:

* `label` (optional)
* `timestamp`
* `mode`
* `config` (non-sensitive subset)
* `summary`
* `cases`

### 8.2 Summary fields

`summary` must include:

* `overall_score`
* `passed`
* `failed`
* `errored`
* `total`
* `metrics` map of metric averages

### 8.3 Case fields

Each case result must include:

* `id`, `name`, `category`
* `overall_score`, `passed`
* `time_seconds`
* `metric_scores`
* `error` (string or null)
* `grades` array

When multi-stage is used, include `stages` summary per stage.
When trials > 1, include trial statistics.

### 8.4 Minimal example

```json
{
  "mode": "validation",
  "summary": {
    "overall_score": 0.88,
    "passed": 9,
    "failed": 0,
    "errored": 0,
    "total": 9,
    "metrics": {
      "latency": 0.79,
      "coverage": 0.72,
      "quality": 0.80
    }
  },
  "cases": [
    {
      "id": "ai_legislation",
      "name": "AI legislation search",
      "category": "legislation",
      "overall_score": 0.79,
      "passed": true,
      "time_seconds": 11.5,
      "metric_scores": {
        "latency": 0.71,
        "coverage": 0.50,
        "quality": 0.80
      },
      "error": null,
      "grades": [
        {
          "criterion": "completion time should be under 20.0s",
          "score": 0.71,
          "metric": "latency",
          "passed": true,
          "detail": "11.5s (threshold: 20.0s)",
          "layer": "deterministic",
          "skipped": false
        }
      ]
    }
  ]
}
```

## 9. Configuration Contract

### 9.1 Precedence

Configuration precedence must be:

* CLI flags override config file
* Config file overrides defaults

### 9.2 Configurable parameters

Implementations must expose configuration for all normative parameters
in this specification, including mode (§6.1), thresholds (§5.3),
weights (§5.5), skip mode (§6.2), output format (§8.1), and judge
backends (§4.3).

### 9.3 Environment overrides

Implementations should support environment variables for mode, output location, judge model, and trials.

### 9.4 Caching

Implementations should support output and judge-response caching with
bypass and clear controls. See [GUIDE.md §3.1](GUIDE.md) for recommended
cache key strategies.

## 10. Security and Safety Requirements

### 10.1 Secret handling

Implementations must:

* Redact resolved secret values in logs
* Exclude credentials from results output
* Prevent sensitive span attributes from leaking to exporters

### 10.2 YAML safety

All YAML loading must use safe parser functions.
Unsafe object deserialization is prohibited.

### 10.3 Judge prompt-injection mitigations

Implementations must:

* Delimit evaluated content in judge prompts
* Instruct judge to evaluate only delimited content
* Validate judge output schema strictly
* Validate score is within `0.0..1.0`
* Derive `passed` from score thresholds

### 10.4 Grader execution safety

Implementations should isolate custom grader execution from the host
environment. See [GUIDE.md §3.2](GUIDE.md) for recommended controls
including allow-lists, timeouts, and network restrictions.

### 10.5 Monitoring data governance

When monitoring mode evaluates live traffic, implementations must
provide data governance controls. See [GUIDE.md §3.3](GUIDE.md) for
recommended measures including PII handling, retention, and
classification.

## 11. Non-determinism and Multi-trial Evaluation

AI system outputs are inherently non-deterministic. The framework must account
for this to produce trustworthy results.

### 11.1 Trial support

Implementations must support running multiple trials per case.
The default trial count is `1`. When trials > 1, the runner executes the
target system independently for each trial and collects per-trial grades.

### 11.2 Aggregation strategies

Implementations must support at least these aggregation strategies:

* `mean` (default): arithmetic mean of per-trial overall scores
* `median`: median of per-trial overall scores
* `worst`: minimum per-trial overall score

Implementations should additionally support:

* `pass_at_k`: case passes if at least *k* of *n* trials pass
* `pass_all`: case passes only if all trials pass

### 11.3 Variance reporting

When trials > 1, each CaseResult must include:

* `trials` (integer): number of trials executed
* `score_stddev` (float): standard deviation of per-trial scores
* `score_min` (float): minimum per-trial score
* `score_max` (float): maximum per-trial score
* `pass_rate` (string): fraction of passing trials, e.g. `"7/10"`
* `per_trial` (array): individual TrialResult objects

High variance (stddev > 0.15) should be flagged in results output to alert
users to flaky evaluations.

### 11.4 Recommended practices

See [GUIDE.md §3.4](GUIDE.md) for trial configuration guidance.

## 12. Extension Points

Implementations may extend the framework through:

* Custom graders
* Custom metric categories
* Custom judges and evaluator backends
* Custom reporters for CI and dashboards
* Custom subject normalizers
* Case loaders from YAML, CSV, JSON, or production samples

Cross-SUT comparison is an external workflow built from multiple result artifacts, not a required core runner feature.
