---
name: evaluate
description: >
  Interactively evaluate an AI agent using the beval framework.
  Use when the user wants to evaluate, test, or assess an agent's behavior,
  set up beval test cases, run an evaluation, check agent quality,
  or embed agent testing in CI.
argument-hint: "[agent-path-or-name] [cases-dir]"
allowed-tools: Read, Write, Glob, Grep, Bash
user-invocable: true
---

You are running the `/evaluate` skill — an interactive setup wizard that walks the user through evaluating an AI agent using the **beval** behavioral evaluation framework.

`$ARGUMENTS` may contain hints: an agent path or name, and/or a cases directory.

Work through the following 7 phases in order. At each phase, do the minimum work needed to advance — ask one focused question at a time using `AskUserQuestion` when you need input. Never skip a phase unless the output it would produce already exists and is valid.

---

## Phase 0 — Detect beval

Try commands in order until one succeeds:

1. `beval version`
2. `uv run beval version`
3. Find a sibling beval repo: `ls ../beval/python/ 2>/dev/null` and if found run `cd ../beval/python && uv run beval version`
4. `python -m beval version`

Store the working invocation as `BEVAL_CMD` (e.g., `uv run beval`).

If **none** succeed, tell the user:
> beval is not installed. Run: `pip install "beval[all] @ git+https://github.com/vyta/beval.git#subdirectory=python"` then re-run `/evaluate`.

Stop here until beval is available.

---

## Phase 1 — Discovery

Glob for these files in the current working directory tree:
- `eval.config.yaml`
- `agent.yaml` or `agent-*.yaml`
- `cases/*.yaml` or `cases/**/*.yaml`
- `.github/workflows/*.yml` (grep for "beval" to detect existing CI)

Print a brief summary of what was found. Use `$ARGUMENTS` as a hint for the agent path if provided.

---

## Phase 2 — Understand the Agent

If an `agent.yaml` already exists and is valid, skip to Phase 3.

Otherwise ask the user:

1. **What does this agent do?** (brief description — used for the YAML `description` field)
2. **What protocol does it use?**
   - A2A (HTTP endpoint)
   - ACP stdio (local command — e.g., `copilot --acp --stdio`)
   - ACP TCP (local port)
3. **Connection details** (URL, command, host/port — depends on protocol chosen)

Read the matching template from `${CLAUDE_SKILL_DIR}/templates/`:
- A2A → `agent-a2a.yaml`
- ACP stdio → `agent-acp-stdio.yaml`
- ACP TCP → `agent-acp-tcp.yaml`

Substitute the user's values into the template. Confirm the output path (default: `agent.yaml`), then write it.

---

## Phase 3 — Test Cases

If valid case YAML files already exist, offer to use them (run `$BEVAL_CMD validate --cases <path>` to check) or generate new ones.

Otherwise ask the user which approach they prefer:
- **(a) Use existing files** — ask for the path, validate with `$BEVAL_CMD validate --cases <path>`, then fix any errors reported
- **(b) Generate starter cases** — ask 8 questions (see below), then write `cases/<agent-name>-cases.yaml`
- **(c) Walk through cases manually** — guide the user one case at a time

### Case Generation Questions → YAML Mapping

Ask these 8 questions to generate cases. Read `${CLAUDE_SKILL_DIR}/templates/cases-starter.yaml` as the base template.

| # | Question | Maps to YAML |
|---|---|---|
| 1 | Give me 3–5 typical user queries for this agent | One `cases` entry per query; `given.query` |
| 2 | For each query, what should the agent's response do or convey? | `the answer should be: >` criterion (ai_judged layer) |
| 3 | Any keywords the agent should **always** include? | `response should contain: <kw>` (deterministic) |
| 4 | Any keywords the agent should **never** say? | `response should not contain: <kw>` (deterministic) |
| 5 | Are there specific tool calls you expect? | `the agent should have called: <tool>` in stage 1 |
| 6 | Expected response length? (short / medium / long) | short→`[10,500]` medium→`[100,2000]` long→`[200,10000]` |
| 7 | Expected latency? (fast / normal / slow) | fast→30s medium→60s slow→120s for `completion time should be under` |
| 8 | Which evaluation mode? (dev / dev+process / validation) | Determines which grader layers to include in generated cases |

Use the exact grader pattern strings below — typos will cause grader-not-found errors:
- `completion time should be under: <seconds>`
- `response should contain: <keyword>`
- `response should not contain: <keyword>`
- `response length should be: [<min>, <max>]`
- `response should match: <regex>`
- `the answer should be: >` (ai_judged — requires validation mode)

---

## Phase 4 — Configuration

### 4a — Evaluation mode & config file

If `eval.config.yaml` exists and is valid, show the current mode and move to step 4b. Otherwise ask:
1. **Evaluation mode**: `dev` (deterministic only), `dev+process` (+ process graders), or `validation` (all including AI judge)

Read `${CLAUDE_SKILL_DIR}/templates/eval.config.yaml`. Substitute mode and agent name. Write `eval.config.yaml`.

### 4b — Judge setup (validation mode only)

If the mode is `validation` (whether from an existing config or just chosen above), **always** confirm the judge configuration with the user before proceeding — even if `eval.config.yaml` already contains a judge block.

Ask:
1. **Judge protocol**: OpenAI-compatible LLM or ACP (external judge agent)
2. Based on protocol:
   - **OpenAI-compatible LLM**: ask for the **model** (e.g., `gpt-4o`, `claude-sonnet-4-6`). Optionally ask for `base_url` if the user is not using the default OpenAI endpoint.
   - **ACP judge**: ask for **connection details** (transport, command/host+port) — same pattern as Phase 2 agent connection.

Update the `eval.judge` block in `eval.config.yaml` accordingly:

```yaml
# OpenAI-compatible LLM judge:
eval:
  judge:
    protocol: openai
    model: <model>
    # base_url: <url>   # only if non-default

# ACP judge:
eval:
  judge:
    protocol: acp
    connection:
      transport: stdio | tcp
      # stdio: command, cwd
      # tcp: host, port
```

If the mode is `dev` or `dev+process`, skip this step (no judge needed).

---

## Phase 5 — Run Evaluation

Show the exact command you will run:
```
<BEVAL_CMD> run --cases <cases-path> --agent <agent-path> -c eval.config.yaml -m <mode> -o results/results.json
```

The judge configuration is already in `eval.config.yaml` (set in Phase 4b), so no `--judge-model` flag is needed on the command line.

Confirm with the user, then run it. Interpret exit codes:
- `0` — all cases passed
- `1` — some cases failed (proceed to Phase 6 to review)
- `2` — invalid input (bad YAML) — fix the file that was reported, then re-run
- `3` — agent unreachable — help user check connection details in `agent.yaml`
- `4` — internal beval error — show the full stderr output

---

## Phase 6 — Results Summary

Read `results/results.json`. Report:
- Overall score and pass/fail (e.g., "7/10 cases passed, overall score 0.82")
- Per-metric breakdown (latency, quality, etc.)
- For each **failed** case: quote the `detail` field, explain what criterion failed, and suggest a concrete fix

Offer next steps:
- **(a)** Save as baseline: `$BEVAL_CMD baseline save`
- **(b)** View verbose output for a specific case
- **(c)** Set up CI — proceed to Phase 7
- **(d)** Done

---

## Phase 7 — CI Integration (optional)

### 7a — Gather CI requirements

Ask:
1. Which trigger events? (push, pull_request, schedule)
2. Does the agent need to be started before tests? (if yes, what command?)
3. Which env vars need to be GitHub secrets? (e.g., `A2A_AGENT_URL`, `OPENAI_API_KEY`)

#### Copilot CLI authentication in CI

If the agent or judge uses the GitHub Copilot CLI (`copilot`), the workflow must:
1. **Install** it: `npm install -g @github/copilot`
2. **Authenticate** it: the built-in `GITHUB_TOKEN` does **not** include Copilot access. A **fine-grained Personal Access Token (PAT)** with the **"Copilot Requests"** permission is required. Store it as a repository secret (e.g., `COPILOT_TOKEN`) and pass it via the `COPILOT_GITHUB_TOKEN` environment variable.

Tell the user they need to:
- Create a fine-grained PAT at github.com → Settings → Developer settings → Fine-grained tokens, with the **"Copilot Requests"** permission
- Add it as a repository secret named `COPILOT_TOKEN` in the target repo → Settings → Secrets and variables → Actions

### 7b — Copy eval files into the target repo

CI workflows run inside the target repository, not the beval repo. Copy the evaluation files into a `beval/` directory in the target repo so the pipeline is self-contained:

```
<target-repo>/
├── .github/workflows/beval.yml
└── beval/
    ├── agent.yaml              # TCP transport for CI (agent backgrounded)
    ├── eval.config.yaml
    └── cases/
        └── <agent>-cases.yaml
```

When copying:
- **agent.yaml**: switch transport from `stdio` to `tcp` with env-var defaults (`${AGENT_HOST:-127.0.0.1}`, `${AGENT_PORT:-3000}`) so copilot can run as a backgrounded daemon in CI.
- **eval.config.yaml**: use env-var defaults for judge connection too (`${JUDGE_HOST:-127.0.0.1}`, `${JUDGE_PORT:-3001}`).
- **cases/**: copy as-is.

### 7c — Generate the workflow

Read `${CLAUDE_SKILL_DIR}/templates/ci-github-actions.yml`. Substitute values, updating all file paths to use the `beval/` prefix (e.g., `beval/eval.config.yaml`, `beval/cases/...`, `beval/agent.yaml`, `beval/results/`). Write `.github/workflows/beval.yml` in the target repo.

If the target repo uses a **reusable workflow pattern** (i.e., other workflows use `workflow_call`), match that convention:
- Set `beval.yml` triggers to `workflow_call` + `workflow_dispatch` only
- Add the beval job to the repo's existing `ci.yml` and `pr.yml` (or equivalent) with `uses: ./.github/workflows/beval.yml`
- **Important**: if the beval workflow needs secrets (e.g., `COPILOT_TOKEN`), the calling workflows must include `secrets: inherit` on the beval job — secrets are **not** automatically passed to reusable workflows.
- **Fork PRs**: secrets are not available on `pull_request` events from forks. Add a fork guard on the beval job in `pr.yml`: `if: github.event.pull_request.head.repo.full_name == github.repository`

Tell the user which secrets to add in GitHub: Settings → Secrets and variables → Actions.
