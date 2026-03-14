---
description: Claude Code integration specification for the Behavioral Evaluation Framework
---

# Claude Code Integration Specification

Addendum to the [Behavioral Evaluation Framework Specification](../SPEC.md).

Status: Draft
Version: 0.1.0

## Overview

This specification defines two Claude Code primitives bundled with the beval repository:

| Primitive | Type | Location |
|---|---|---|
| `/evaluate` | Skill | `.claude/skills/evaluate/` |
| `beval-runner` | Sub-agent | `.claude/agents/beval-runner.md` |

Both are **project-scoped**: they activate automatically when a user opens any project in Claude Code that contains the beval repository (or a project that has been cloned from it).

---

## 1. `/evaluate` Skill

### 1.1 Purpose

An interactive, 7-phase setup wizard that guides a user from zero to a running beval evaluation in a single Claude Code conversation. It is the canonical first-time setup path for any agent evaluation project.

### 1.2 Invocation

```
/evaluate [agent-path-or-name] [cases-dir]
```

Arguments are optional hints. The skill works interactively without them.

Natural-language triggers (Claude interprets intent and invokes the skill):
- "I want to evaluate my agent"
- "Let's test my agent"
- "Set up beval for this project"

### 1.3 Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Runs in main conversation | yes (no `context: fork`) | `AskUserQuestion`, file writes, and bash commands require the main conversation context |
| Allowed tools | `Read, Write, Glob, Grep, Bash` | Discovery, template rendering, validation runs |
| Model invocation | user-only | The full wizard should not auto-start spontaneously |

### 1.4 Phase Contract

The skill MUST execute the following phases in order. A phase MAY be skipped only if its output already exists and is valid.

| # | Phase | Exit condition |
|---|---|---|
| 0 | Detect beval | `BEVAL_CMD` is set to a working invocation |
| 1 | Discovery | Existing eval files catalogued; agent path hint applied |
| 2 | Understand the agent | `agent.yaml` exists and is valid |
| 3 | Test cases | At least one valid case YAML exists |
| 4 | Configuration | `eval.config.yaml` exists and is valid; judge confirmed for validation mode |
| 5 | Run | `beval run` completes; `results/results.json` written |
| 6 | Results | Summary shown; failed cases explained with fix suggestions |
| 7 | CI (optional) | `.github/workflows/beval.yml` written if user requests |

#### Phase 0 — beval detection

The skill MUST try the following invocations in order, stopping at the first that succeeds:

1. `beval version`
2. `uv run beval version`
3. Sibling repo: `ls ../beval/python/` → if found, `cd ../beval/python && uv run beval version`
4. `python -m beval version`

The working invocation is stored as `BEVAL_CMD` and used for all subsequent beval calls.

If no invocation succeeds, the skill MUST tell the user to install beval and stop.

#### Phase 2 — Agent protocol options

The skill supports three agent protocols. For each, it reads the corresponding template from `.claude/skills/evaluate/templates/`:

| Protocol | Template file | Required connection fields |
|---|---|---|
| A2A (HTTP) | `agent-a2a.yaml` | `url` (env var recommended) |
| ACP stdio | `agent-acp-stdio.yaml` | `command` array, `cwd` |
| ACP TCP | `agent-acp-tcp.yaml` | `host`, `port` |

#### Phase 3 — Case generation question-to-YAML mapping

When generating cases interactively, the skill MUST ask the following 8 questions and map answers to the corresponding YAML fields:

| Question | YAML field / grader criterion |
|---|---|
| 3–5 typical user queries | One `cases` entry per query; `given.query` |
| Behavioral expectation per query | `the answer should be: >` (ai_judged) |
| Keywords agent always includes | `response should contain: <kw>` |
| Keywords agent never says | `response should not contain: <kw>` |
| Expected tool calls | `the agent should have called: <tool>` (stage 1) |
| Response length: short/medium/long | `[10,500]` / `[100,2000]` / `[200,10000]` |
| Latency: fast/normal/slow | 30s / 60s / 120s threshold |
| Evaluation mode | Determines which grader layers to include |

#### Phase 5 — Run command form

```
<BEVAL_CMD> run \
  --cases <cases-path> \
  --agent <agent-path> \
  -c eval.config.yaml \
  -m <mode> \
  [-o results/results.json]
```

Exit code handling (per `spec/cli.spec.yaml`):

| Code | Meaning | Skill action |
|---|---|---|
| 0 | All cases passed | Proceed to Phase 6 |
| 1 | Some cases failed | Proceed to Phase 6 (show failures) |
| 2 | Invalid input | Show error; fix YAML; re-run |
| 3 | Agent unreachable | Help user debug `agent.yaml` |
| 4 | Internal error | Show full stderr |

### 1.5 Templates

Templates live in `.claude/skills/evaluate/templates/`. They use `__PLACEHOLDER__` tokens for substitution. All grader pattern strings in generated case files MUST exactly match the registered patterns in `python/src/beval/graders/deterministic.py` — a mismatch causes a grader-not-found error at runtime.

Canonical grader pattern strings:

```
completion time should be under: <seconds>
response should contain: <keyword>
response should not contain: <keyword>
response length should be: [<min>, <max>]
response should match: <regex>
the answer should be: >
```

| Template file | Purpose |
|---|---|
| `agent-a2a.yaml` | A2A (HTTP) agent skeleton |
| `agent-acp-stdio.yaml` | ACP stdio agent skeleton |
| `agent-acp-tcp.yaml` | ACP TCP agent skeleton |
| `eval.config.yaml` | Evaluation configuration skeleton |
| `cases-starter.yaml` | Starter case file skeleton |
| `ci-github-actions.yml` | GitHub Actions workflow skeleton |

---

## 2. `beval-runner` Sub-agent

### 2.1 Purpose

A lightweight, persistent runner for **day-to-day re-runs** of existing evaluations. Complements the `/evaluate` skill: the skill handles first-time setup; the sub-agent handles routine re-runs.

### 2.2 Configuration

| Property | Value |
|---|---|
| Model | `haiku` (fast and cheap for routine runs) |
| Memory | `project` (persists discovered paths across sessions) |
| Tools | `Read, Glob, Grep, Bash` (no Write — reads existing config only) |

### 2.3 Trigger conditions

The sub-agent MUST be invoked proactively when the user expresses intent matching any of:
- "run my evaluations"
- "test my agent"
- "re-run beval"
- "check agent quality"

### 2.4 Workflow

1. **Check memory** for previously discovered `BEVAL_CMD`, `CASES_PATH`, `AGENT_PATH`, `CONFIG_PATH`
2. **Glob for config** if memory is empty: `eval.config.yaml`, `agent.yaml`/`agent-*.yaml`, `cases/*.yaml`
3. If no config found: tell the user to run `/evaluate` first
4. **Detect beval** using the same probe sequence as Phase 0 of the skill
5. **Run**: `<BEVAL_CMD> run --cases <path> --agent <path> -c eval.config.yaml -o results/results.json`
6. **Summarize**: overall score, pass/fail counts, per-metric breakdown, failed case details
7. **Update memory**: save all discovered paths and the last run summary

### 2.5 Memory schema

The sub-agent MUST persist the following keys in project memory after each successful run:

```
BEVAL_CMD        working beval invocation
CASES_PATH       path to case YAML files or directory
AGENT_PATH       path to agent.yaml
CONFIG_PATH      path to eval.config.yaml
LAST_RUN_DATE    ISO 8601 date
LAST_RUN_SCORE   overall score (float)
LAST_RUN_PASSED  cases passed (int/total)
```

---

## 3. Repository File Layout

```
.claude/
  skills/
    evaluate/
      SKILL.md                           # /evaluate skill definition
      templates/
        agent-a2a.yaml                   # A2A agent template
        agent-acp-stdio.yaml             # ACP stdio agent template
        agent-acp-tcp.yaml               # ACP TCP agent template
        eval.config.yaml                 # Config template
        cases-starter.yaml               # Starter cases template
        ci-github-actions.yml            # CI workflow template
  agents/
    beval-runner.md                      # beval-runner sub-agent
```

---

## 4. Design Decisions

### 4.1 Skill runs in main conversation

The `/evaluate` skill does not use `context: fork`. Interactive Q&A (`AskUserQuestion`), file writes, and bash commands all require the main conversation context. A forked context would prevent the skill from prompting the user for decisions during the wizard flow.

### 4.2 Sub-agent uses haiku + project memory

Routine re-runs are mechanical: find config, run beval, parse JSON, print summary. Haiku is sufficient and minimizes latency and cost. Project memory eliminates the discovery step on subsequent sessions, making re-runs instant.

### 4.3 Separation of concerns

The skill and sub-agent are intentionally separated by function:

| | `/evaluate` skill | `beval-runner` sub-agent |
|---|---|---|
| When | First-time setup | Day-to-day re-runs |
| Writes files | Yes | No |
| Asks questions | Yes | No |
| Remembers across sessions | No | Yes (project memory) |
| Model | Sonnet (main conversation) | Haiku |

### 4.4 Templates use `__PLACEHOLDER__` tokens

Double-underscore tokens (`__LIKE_THIS__`) were chosen to avoid collisions with shell variable syntax (`${LIKE_THIS}`) which appears in the templates themselves as literal content (env var references for users to set at runtime).

---

## 5. Conformance

An implementation of this spec is conformant if:

1. `/evaluate` successfully guides a user from zero config to a passing `beval run` in a single session
2. Generated `agent.yaml` is valid against `spec/schemas/agent.schema.json` (when it exists)
3. Generated `cases/*.yaml` passes `beval validate --cases`
4. `beval-runner` auto-triggers on natural-language re-run requests
5. `beval-runner` correctly recalls `BEVAL_CMD` and file paths from project memory in a new session without re-probing
6. Generated CI workflow is valid YAML
