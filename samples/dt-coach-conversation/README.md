# Design Thinking Coach — Conversation Simulation Sample

Conversation simulation evaluation for the **DT Coach**, testing end-to-end
multi-turn coaching sessions rather than isolated single-turn responses.

This is the companion to [`../dt-coach`](../dt-coach), which covers static
single-turn behavioral cases. Where the static sample asks "given this one
message, does the coach respond correctly?", this sample asks "given this
persona and goal, does the coach actually guide the user to an outcome across
a full session?"

Agent source: <https://github.com/microsoft/hve-core/blob/main/.github/agents/design-thinking/dt-coach.agent.md>

## Files

| File | Description |
|------|-------------|
| `eval.config.yaml` | Config with agent, judge, simulator, and conversation settings |
| `personas.yaml` | Two simulated user personas |
| `goals.yaml` | Three coaching session goals |

## How It Works

Each run spins up one actor per (persona, goal) pair. The actor:

1. **Initializes** a dedicated agent session (ACP session/initialize)
2. **Calls the simulator** each turn — an LLM playing the persona generates the next user message and 1–3 turn-specific evaluation criteria
3. **Invokes the agent** with that message
4. **Grades the turn** using both the static `each turn` criteria from the goal and the dynamic criteria from the simulator
5. **Repeats** until the goal is achieved (`progress == 1.0`) or the turn limit is hit
6. **Grades the full conversation** using the `on finish` criteria

All grading reuses the same judge configured in `eval.config.yaml` — no new evaluation infrastructure.

```
Simulator (Copilot)          DT Coach (Copilot)
      │                             │
      │  generate_case()            │
      │ ─────────────────────────▶  │  (produces query + turn criteria)
      │                             │
      │  invoke(query)              │
      │ ─────────────────────────▶  │
      │                             │  (coaching response)
      │ ◀─────────────────────────  │
      │                             │
      │  grade(turn criteria        │
      │    + goal each-turn         │
      │    criteria)                │
      │  ...repeat up to max_turns  │
      │                             │
      │  grade(on finish criteria)  │
```

## Personas

| ID | Name | Goals | Description |
|----|------|-------|-------------|
| `product_manager_new_to_dt` | Product Manager New to DT | `run_method1_session`, `recover_from_confusion` | Solution-mode thinker, first DT session, needs prompting to articulate human problems |
| `team_lead_returning_user` | Team Lead Returning User | `transition_to_method2` | Returning user with Method 1 context, wants to continue efficiently |

## Goals

| ID | Name | Max Turns | What It Tests |
|----|------|-----------|---------------|
| `run_method1_session` | Run a complete Method 1 session | 20 | Full session arc: initialization → active coaching → problem frame → close |
| `recover_from_confusion` | Coach recovers user from confusion | 10 | Progressive hints, empathy, re-orientation without methodology lectures |
| `transition_to_method2` | Transition from Method 1 to Method 2 | 15 | Session continuity, method transition, research planning |

This produces **3 conversations** per run (one per persona/goal pairing declared in `personas.yaml`).

## Prerequisites

| Requirement | Details |
|-------------|---------|
| `AGENT_REPO_ROOT` | Path to the cloned `hve-core` repo |
| `copilot` CLI | GitHub Copilot CLI with ACP support |
| Three Copilot instances | Agent (port 3000), Judge (port 3001), Simulator (port 3002) |

> **Why three instances?** The agent, judge, and simulator are all Copilot
> ACP sessions but play different roles. Separating them avoids cross-session
> context bleed and allows independent timeout tuning.

> **Concurrent sessions:** With `max_parallel_actors > 1`, each parallel actor
> opens its own ACP session on the simulator server simultaneously. The default
> config uses `max_parallel_actors: 1` (sequential) which is safe regardless
> of whether your Copilot build supports concurrent sessions. If your Copilot
> instance supports session multiplexing, you can raise this to run actors in
> parallel and reduce total wall-clock time.

Override the default ports via environment variables:

```bash
export AGENT_HOST=127.0.0.1    AGENT_PORT=3000
export JUDGE_HOST=127.0.0.1    JUDGE_PORT=3001
export SIMULATOR_HOST=127.0.0.1 SIMULATOR_PORT=3002
export AGENT_REPO_ROOT=/path/to/hve-core
```

## Running

### Start three Copilot ACP processes

```bash
# Terminal 1 — agent under test (dt-coach activated via init_prompt)
copilot --acp --port 3000 --allow-all

# Terminal 2 — judge
copilot --acp --port 3001 --allow-all

# Terminal 3 — simulator
copilot --acp --port 3002 --allow-all
```

### Run the conversation simulation

```bash
cd python && uv sync --extra acp

uv run beval -c ../samples/dt-coach-conversation/eval.config.yaml \
  converse run
```

Save results to file:

```bash
uv run beval -c ../samples/dt-coach-conversation/eval.config.yaml \
  converse run --output ../samples/dt-coach-conversation/results/
```

Run 3 independent actors per (persona, goal) pair to measure consistency:

```bash
uv run beval -c ../samples/dt-coach-conversation/eval.config.yaml \
  converse run --actor-count 3 --max-parallel 3
```

Each actor replays the same goal from scratch with a different simulated
conversation. This produces 9 results instead of 3 and answers questions like
"does the coach reliably guide users to a problem frame, or does it only
succeed 1 out of 3 times?" — analogous to `--trials` in static evaluation.

### OpenAI simulator (alternative)

If you prefer an OpenAI model as the simulator instead of a Copilot instance:

```bash
export OPENAI_API_KEY=sk-...

uv run beval -c ../samples/dt-coach-conversation/eval.config.yaml \
  converse run --simulator-model gpt-4o
```

## Console Output

When running in a terminal (TTY), beval renders a live dashboard that updates after every completed turn:

```
  Starting 1 conversation(s)...  transcripts → results/transcripts

  Persona                       Goal                   Done    Act    Turn  Score            Goal%
  ──────────────────────────────────────────────────────────────────────────────────────────────────
  product_manager_new_to_dt     recover_from_confusi    0/1      1    3/10  --              ~30%
  ──────────────────────────────────────────────────────────────────────────────────────────────────
  Total: 0/1 done   Goal rate: 0%   Avg score: 0.00
```

**One row per persona×goal pair** — aggregates all actors for that pair so the table stays compact regardless of `actor_count`.

| Column | While running | When done |
|--------|--------------|-----------|
| **Done** | `0/1` (completed/total) | `1/1` |
| **Act** | Active actors right now | `0` |
| **Turn** | `3/10` (current/max) | `5 turns` (avg across completed actors) |
| **Score** | `--` until first actor completes | `[######--] 0.74` (avg) |
| **Goal%** | `~30%` (live goal progress) | `100%` (achievement rate) |

When not running in a TTY (e.g. CI pipes), output falls back to per-turn lines:

```
  → product_manager_new_to_dt:recover_from_confusion:1
    [product_manager_new_to_dt:recover_from_confusion:1] turn 1: Hey, so I've been trying...
    [product_manager_new_to_dt:recover_from_confusion:1] turn 2: Okay, that makes sense...
  ✓ product_manager_new_to_dt:recover_from_confusion:1: score=0.74  turns=5  [goal_achieved]
```

## Transcript Files

When `--output <dir>` is specified, beval writes one JSON file per actor to `<dir>/transcripts/`:

```
results/
  conversation_results.json          ← full run summary (all actors)
  transcripts/
    product_manager_new_to_dt_recover_from_confusion_1.json
    product_manager_new_to_dt_run_method1_session_1.json
    team_lead_returning_user_transition_to_method2_1.json
```

**Transcripts are written live** — the file is created as soon as the actor starts and updated after each turn, so you can monitor a running conversation in real time with any JSON viewer.

Each transcript follows the `ConversationResult` schema. During the run it has `"status": "in_progress"`:

```json
{
  "id": "product_manager_new_to_dt:recover_from_confusion:1",
  "persona_id": "product_manager_new_to_dt",
  "goal_id": "recover_from_confusion",
  "actor_index": 1,
  "status": "in_progress",
  "turns": [
    {
      "turn_number": 1,
      "user_message": "Hey, so I've been trying to use design thinking...",
      "agent_response": "That feeling of 'I'm more confused now' is actually the research working...",
      "completion_time_seconds": 44.2,
      "goal_progress": 0.0,
      "grades": [
        {
          "criterion": "completion time should be under 120",
          "score": 0.63, "metric": "latency", "layer": "deterministic", ...
        },
        {
          "criterion": "the answer should be: responds with curiosity and empathy...",
          "score": 0.85, "metric": "quality", "layer": "ai_judged", ...
        }
      ],
      "overall_score": 0.74
    }
  ]
}
```

When the actor completes the file is overwritten with the full `ConversationResult` (adds `termination_reason`, `goal_achieved`, `time_seconds`, `metric_scores`, `grades` for `on finish` criteria, etc.).

**Grades per turn** come from three sources:
1. `completion time should be under 120` — deterministic latency check
2. Static `each turn` criterion from the goal (e.g. "responds with empathy")
3. 1 dynamic criterion generated by the simulator for that specific message

## Grading

| Layer | Source | What it grades |
|-------|--------|----------------|
| Deterministic | `each turn` → `response time should be under 120` | Turn latency |
| AI-judged (per turn) | `each turn` goal criteria + simulator dynamic criteria | Coaching style, boundary adherence per message |
| AI-judged (conversation) | `on finish` goal criteria | End-state outcomes: problem frame quality, continuity, user re-orientation |

The `on finish` criteria are the primary signal — they answer whether the coaching session actually achieved its objective, which single-turn tests cannot capture.

## Comparison With the Static Sample

| Aspect | `dt-coach` (static) | `dt-coach-conversation` |
|--------|---------------------|--------------------------|
| What is tested | One message → one response | Full multi-turn session arc |
| Input | Fixed query string | Dynamically generated by simulator |
| Context | Single turn, no prior turns | Full conversation history |
| Failure modes caught | Wrong response to specific prompt | Context loss, coaching drift, inability to re-orient a confused user |
| Variability | Deterministic | Non-deterministic (use `actor_count > 1` for variance) |
| Recommended use | Fast regression checks in CI | Periodic deep evaluation of session quality |
