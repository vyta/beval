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
  converse run --verbose
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
