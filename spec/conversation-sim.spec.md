---
description: Conversation simulation specification for the Behavioral Evaluation Framework
parent: SPEC.md §15
---

# Conversation Simulation Specification

Addendum to the [Behavioral Evaluation Framework Specification](../SPEC.md).

Status: Draft
Version: 0.1.0

## 15.1 Overview

**Conversation simulation** extends static evaluation (one case → one
query/response → graded) with AI-driven conversational testing. A **simulated
user** (actor) dynamically generates messages to pursue a goal through
multi-turn dialogue with the agent under test. The framework evaluates every
turn and the conversation as a whole.

The test matrix is:

```
sum(|persona.goals|) × actor_count = total conversations
```

Each persona declares its own `goals` list (the goal IDs it pursues). Each
(persona, goal) pair runs as an independent **ConversationCase** with its own
actor, history, and grades. Multiple actors on the same persona/goal pair
produce variance data analogous to multi-trial evaluation (§11).

**Conversation simulation reuses the existing case runner.** Each turn, the
simulator generates a `DynamicCase` (query + dynamic `then` criteria). The
static per-turn criteria from the goal are merged in, and the combined
criterion list is executed by the same case runner that handles static cases —
the same §4 grader registry, the same §5 scoring, the same §6 mode gating.
No new evaluation infrastructure is introduced.

This section defines all normative behavior for conversation simulation.
Evaluation modes (§6), grader registry (§4), scoring (§5), and exit codes
(§7.4) are inherited unchanged from the core specification.

## 15.2 Core Entities

| Entity | Description |
|---|---|
| `Persona` | Reusable description of a simulated user's identity, tone, and constraints |
| `Goal` | Objective with circuit-breaker constraints, tags, and `when/then` evaluation stages |
| `ConversationCase` | A single run of one persona pursuing one goal; identity `{persona_id}:{goal_id}:{actor_index}` |
| `Turn` | One user-message / agent-response exchange |
| `Actor` | Running instance of a ConversationCase with its own adapter, simulator, and history |
| `TurnResult` | Recorded outcome of one Turn including grades and goal progress |
| `ConversationResult` | Aggregated result for one ConversationCase (mirrors CaseResult shape) |
| `ConversationRunResult` | Top-level result artifact for a full conversation simulation run |
| `UserSimulator` | AI-powered Case generator: produces a `DynamicCase` per turn including query, criteria, and goal progress |
| `DynamicCase` | Output of `generate_case()`: the turn query, dynamic `then` criteria, and `progress` (0.0–1.0); merged with static goal criteria and executed by the existing case runner |
| `ActorStatus` | Real-time status of a running actor for progress display |
| `ConversationRunStatus` | Aggregate status of the running simulation for progress display |

## 15.3 Persona Definition

### 15.3.1 Persona schema

Personas are defined in YAML library files (standalone or inline in config).
Each persona MUST follow this schema (see `spec/schemas/personas-goals.schema.json`):

```yaml
# personas.yaml
personas:
  - id: casual_user
    name: Casual User
    description: >
      A non-technical user asking questions in plain, conversational language.
      Patient and polite. Accepts partial answers but follows up if confused.
    goals: [find_refund_policy, check_order_status]
    traits:
      tone: friendly
      expertise: beginner
      patience: high
      verbosity: medium
      language: en
      style_notes: Uses informal contractions. Avoids jargon.
    metadata:
      team: ux-research
      reviewed: true
```

Required fields:

* `id` (string): unique within a library file; used in ConversationCase identity
* `name` (string): human-readable label
* `description` (string): prose description passed verbatim to the simulator
  prompt. Should describe identity, background, and behavioral tendencies.
* `goals` (array of string): goal IDs this persona pursues. Each ID MUST
  resolve against the loaded goal pool. A persona with no `goals` entry MUST
  produce exit code 2. Goal IDs not present in the loaded goal pool MUST
  produce exit code 2.

Optional fields:

* `traits` (object): structured attributes for the simulator to embody
  * `tone` (string): e.g., `friendly`, `formal`, `skeptical`, `hostile`
  * `expertise` (string): e.g., `beginner`, `intermediate`, `expert`
  * `patience` (string): e.g., `low`, `medium`, `high` — affects give-up
    threshold
  * `verbosity` (string): e.g., `terse`, `medium`, `verbose`
  * `language` (string): BCP 47 language tag, default `en`
  * `style_notes` (string): free-form additional style guidance
* `metadata` (object): arbitrary key-value pairs for tagging and filtering

### 15.3.2 Persona loading

Personas may be sourced from:

1. Standalone YAML files referenced in config via `personas` paths
2. Inline persona objects in `eval.conversation.personas`
3. CLI `--persona <id>` filter applied after loading

When the same `id` appears in multiple sources, the last definition wins.
Implementations MUST reject duplicate `id` values within a single file with
exit code 2.

## 15.4 Goal Definition

### 15.4.1 Goal schema

Goal structure mirrors the static Case as closely as possible: `given` carries
setup context, `stages` holds `when/then` evaluation blocks, and `tags` provides
filtering labels.

```yaml
# goals.yaml
goals:
  - id: find_refund_policy
    name: Find Refund Policy
    tags: [customer-support, high-priority]
    given:
      objective: >
        Find the company's refund policy, including the time limit for returns
        and the conditions under which refunds are granted.
      max_turns: 30
      timeout_seconds: 300
    stages:
      - when: "each turn"
        then:
          - "the response should not contain sorry, I cannot help"
          - "response time should be under 10"
      - when: "on finish"
        then:
          - "the agent describes at least one condition for refund eligibility"
          - "the agent provided accurate policy information"
          - "number of turns should be under 30"
```

Required fields:

* `id` (string): unique within a library file
* `name` (string): human-readable label

Optional fields:

* `tags` (array of string): labels for filtering and categorization, same as
  Case tags
* `given` (object): setup block
  * `objective` (string): prose description of what the simulated user is
    trying to accomplish. Passed verbatim to the simulator prompt.
  * `max_turns` (integer, default `20`): **circuit breaker** — hard turn limit
    that terminates the loop. Produces no grade. Soft turn-count criteria belong
    in the `on finish` stage `then` clauses.
  * `timeout_seconds` (number, default `600`): **circuit breaker** — hard
    wall-clock timeout that terminates the loop. Produces no grade.
* `stages` (array): evaluation lifecycle hooks. Each entry has:
  * `when` (string): one of two well-known values (case-insensitive):
    * `"each turn"` — `then` clauses applied to TurnSubject after every agent
      response, via the §4 grader registry
    * `"on finish"` — `then` clauses applied to ConversationSubject after the
      conversation ends, via the §4 grader registry.
  * `then` (array of string): criterion strings dispatched through the §4
    grader registry by prefix matching, identical to static Case `then` clauses.
    Each item MUST be a single string.

Unrecognized `when` values MUST produce exit code 2. A goal with no `stages`
entry is valid; grading relies entirely on the simulator's `progress` signal
and the `on finish` stage graders.

### 15.4.2 Goal loading

Goals follow the same loading precedence as personas (§15.3.2).
Implementations MUST reject duplicate `id` values within a single file with
exit code 2.

## 15.5 Conversation Lifecycle

### 15.5.1 ConversationCase identity

Each ConversationCase is uniquely identified by:

```
{persona_id}:{goal_id}:{actor_index}
```

Where `actor_index` is a one-based integer from `1` to `actor_count`.
Single-actor runs use `actor_index=1` and include the suffix in the ID for
schema consistency.

### 15.5.2 Turn loop

The actor executes the following loop:

```text
adapter = create_adapter(agent_definition)
adapter.initialize()    # ACP: session/initialize
history = []
termination_reason = None
prior_subject = None

for turn_number = 1, 2, ..., goal.given.max_turns:
    if elapsed > goal.given.timeout_seconds:
        termination_reason = terminated_timeout
        break
    if cancelled:
        termination_reason = cancelled
        break

    dyn_case = simulator.generate_case(persona, goal, history, context)
    if dyn_case.progress == 1.0:
        termination_reason = goal_achieved
        break  # goal achieved — skip this turn
    user_message = dyn_case.query
    # AdapterInput: query=user_message, stage=turn_number,
    #               stage_name="turn {turn_number}", prior_subject=prior_subject
    try:
        subject = adapter.invoke(AdapterInput(query=user_message, stage=turn_number,
                                              stage_name=f"turn {turn_number}",
                                              prior_subject=prior_subject))
    except AgentError as e:
        turn_result = TurnResult(turn_number=turn_number, user_message=user_message,
                                 agent_response=None, error=str(e), grades=[], ...)
        history.append(turn_result)
        termination_reason = agent_error
        break

    # Construct TurnSubject (subject + stage metadata — see §15.8.1)
    turn_subject = TurnSubject(subject, stage=turn_number, persona_id=..., goal_id=..., ...)
    # Merge static goal criteria + dynamic case criteria, run via existing case runner
    all_then = goal.stages["each turn"].then + dyn_case.then
    grades = run_case_graders(all_then, turn_subject, context)  # §4 registry — see §15.8.1

    turn_result = TurnResult(turn_number=turn_number, user_message=user_message,
                             agent_response=subject.output, grades=grades, ...)
    history.append(turn_result)
    prior_subject = subject

else:
    # Loop completed all max_turns without break
    termination_reason = terminated_max_turns

adapter.close()    # ACP: session closes here
# Conversation-level grading via existing case runner (see §15.8.2)
conv_subject = ConversationSubject(history, ...)
conversation_grades = run_case_graders(goal.stages["on finish"].then, conv_subject, context)
```

Key behaviors:
- `goal_achieved` is set mid-loop the moment `dyn_case.progress == 1.0`; no
  post-loop assessment step.
- `give_up` is not a termination reason — the conversation runs until
  `goal_achieved`, a circuit breaker fires, or an error occurs.
- An agent error records a `TurnResult` with the error and breaks the loop.
- `AdapterInput` fields `stage`, `stage_name`, and `prior_subject` are set
  as specified (see §13.3 for the AdapterInput definition).

For ACP adapters: the adapter instance is initialized at actor start
(`session/initialize` called once). All turns within the conversation reuse
the same session via repeated `session/sendUserMessage` calls. The session is
closed at actor end via `adapter.close()`, regardless of termination reason.
This differs from the judge pattern (§14.2.4) where a fresh session is
created per `evaluate()` call.

### 15.5.3 Termination reasons

| Reason | Condition |
|---|---|
| `goal_achieved` | `dyn_case.progress == 1.0` before the turn is sent |
| `terminated_max_turns` | Loop completed all `max_turns` with `progress < 1.0` |
| `terminated_timeout` | Elapsed time exceeds `timeout_seconds` |
| `cancelled` | SIGINT or programmatic `cancel()` received (§15.13) |
| `agent_error` | Adapter returns an error that exceeds retry budget |
| `simulator_error` | Simulator throws an unhandled exception |

### 15.5.4 History

The conversation history is an ordered array of `TurnResult` objects. Each
entry carries the full turn record including `user_message`, `agent_response`,
and `goal_progress`. The simulator receives the full history on each
`generate_case()` call.

### 15.5.5 ConversationSubject

For conversation-level graders, the framework constructs a `ConversationSubject`
that extends `Subject` (§2.2):

* `input`: the full message array `[{role: "user", content: turn.user_message},
  {role: "assistant", content: turn.agent_response}, ...]` in turn order
* `output`: the final agent response string
* `completion_time`: total wall-clock time for the conversation in seconds
* `metadata`:
  * `persona_id`: the persona ID
  * `goal_id`: the goal ID
  * `actor_index`: the actor index
  * `turn_count`: number of turns completed
  * `termination_reason`: the termination reason string
  * `goal_achieved`: boolean

## 15.6 UserSimulator Contract

### 15.6.1 Interface

```text
UserSimulatorInterface:
  generate_case(
    persona: Persona,
    goal: Goal,
    history: TurnResult[],
    context: EvalContext
  ) -> DynamicCase

  close() -> void
```

```text
DynamicCase:
  query:     string      # the user message to send (ignored when progress == 1.0)
  then:      string[]    # dynamic, query-specific criterion strings for this turn;
                         # merged with goal.stages["each turn"].then before grading
  progress:  float       # 0.0–1.0: estimated fraction of goal achieved so far.
                         # 1.0 = goal fully achieved; loop breaks without sending query.
```

The `close()` method MUST release any held resources (open connections, running
processes). The base interface provides a no-op default.

The simulator is an **AI-powered Case generator**. Each turn it produces a
`DynamicCase` carrying the next query, query-specific grader criteria, and a
goal progress estimate. The runner breaks the loop when `progress == 1.0`;
otherwise it merges the static goal criteria from `goal.stages["each turn"].then`
with `dyn_case.then` and executes via the existing §4 grader registry.
`dyn_case.then` MAY be empty `[]` for simulators that contribute only the query.

### 15.6.3 Built-in `openai` simulator

The built-in `openai` simulator calls an OpenAI-compatible chat completions API.
`SimulatorConfig` for `protocol: openai` uses the same fields as `JudgeConfig`
(§14.3): `model`, `api_key`, `base_url`, `auth`, `max_answer_chars`, `timeout`.

Configuration block:

```yaml
eval:
  conversation:
    simulator:
      protocol: openai
      model: gpt-4o
      api_key: ${OPENAI_API_KEY}
      base_url: ${SIMULATOR_BASE_URL}   # optional
      auth: entra_id                    # optional (Azure DefaultAzureCredential)
      max_answer_chars: 500             # optional: truncate agent response in prompt
      timeout: 30                       # optional
```

#### 15.6.3.1 generate_case prompt

The `openai` simulator makes a single LLM call per turn that produces both the
user message (`query`) and the dynamic evaluation criteria (`then`) for that
turn. The implementation MUST send two messages:

1. **System message**:

```
You are a simulated user in a conversation evaluation scenario.

Persona:
{persona.description}

Traits:
{persona.traits formatted as key: value lines}

Your goal:
{goal.given.objective}

Completion criteria (for reference):
{goal.stages["on finish"].then as a numbered list, or omit if empty}

Instructions:
- Stay in character as described by the persona
- Generate your next message to the agent, pursuing your goal naturally
- Also generate 1–3 evaluation criteria specific to your message — what a
  good response to your exact question should contain or address
- Estimate how much of the goal has been achieved so far (0.0 = nothing, 1.0 = fully done)
- If progress is 1.0, query is ignored — the conversation will end
- Do NOT break character or reveal that you are a simulator

You MUST respond with a JSON object containing exactly:
- "progress": number 0.0–1.0 — fraction of the goal achieved based on the conversation so far
- "query": string — the user message to send (stay in character); ignored when progress == 1.0
- "then": array of strings — criterion strings to evaluate the agent's response
  to this specific message. Use the same style as static then clauses (e.g.,
  "the agent addressed the international shipping aspect of the question").
  These are dispatched through the §4 grader registry. May be empty when progress == 1.0.
```

2. **User message**:

```
Conversation so far:

User: {turn.user_message}
<agent_response>
{turn.agent_response}
</agent_response>

User: {turn.user_message}
<agent_response>
{turn.agent_response}
</agent_response>

Generate your next turn. Respond with JSON only.
```

All agent turns in the history MUST be wrapped in `<agent_response>` tags.
The above template shows the repeating pattern; one `User:` / `<agent_response>`
block is emitted per prior turn in `history`.

When `history` is empty (first turn), omit the conversation history block and
instruct the simulator to open the conversation.

**Response parsing for generate_case:**
1. Strip markdown code fences if present
2. Parse as JSON object
3. Extract `progress` (number, default `0.0` if absent); clamp to `[0.0, 1.0]`
4. If `progress == 1.0`: return `DynamicCase(query="", then=[], progress=1.0)`; skip remaining validation
5. Validate `query` (non-empty string) and `then` (array of strings) fields
6. If `then` is absent or not an array → treat as `[]`, log warning
7. If `query` is absent or empty → treat as `generate_case` throws (§15.6.5)
8. Return `DynamicCase(query=..., then=..., progress=...)`

### 15.6.4 Built-in `acp` simulator

The built-in `acp` simulator invokes any ACP-compatible agent (e.g., GitHub
Copilot) as the simulator. The agent plays the simulated-user role: it receives
the generate_case prompt and returns the `DynamicCase` JSON shape.

Configuration:

```yaml
eval:
  conversation:
    simulator:
      protocol: acp
      connection:
        transport: stdio
        command: [copilot, --acp, --stdio, --allow-all]
      timeout: 60    # optional, default 30
```

#### 15.6.4.1 Prompt delivery

The `acp` simulator sends the generate_case prompt (§15.6.3.1 system message +
user message) as a **single combined prompt block** to the ACP agent, following
the §14.2.3 pattern:

```
{system message text}

---

{user message text}
```

The ACP agent MUST respond with the same `DynamicCase` JSON shape as the
`openai` simulator (§15.6.3.1 response parsing applies identically).

#### 15.6.4.2 Session lifecycle

One ACP session is created when the actor starts (`session/initialize`). All
`generate_case` calls within a single actor reuse that session via repeated
`session/sendUserMessage` calls. The session is closed when the actor
terminates, regardless of termination reason.

This differs from the judge ACP pattern (§14.2.4) where a fresh session is
created per `evaluate()` call.

### 15.6.5 Error handling

| Error | Behavior |
|---|---|
| `generate_case` throws | Record `simulator_error`, terminate conversation |
| Invalid JSON from `generate_case` | Same as `generate_case` throws |
| `progress` absent in response | Default to `0.0`; do not abort turn |
| `progress` outside `[0.0, 1.0]` | Clamped; not an error |
| `query` missing or empty when `progress < 1.0` | Same as `generate_case` throws |
| `then` missing or not an array | Use `[]` for dynamic criteria, log warning; do not abort turn |
| Simulator `close()` throws | Log warning, do not propagate |

Simulator errors MUST NOT abort the run. Conversations with simulator errors
complete with `termination_reason=simulator_error` and record the error in
`ConversationResult.error`.

### 15.6.6 Configuration precedence

The active simulator is resolved (highest to lowest precedence):

1. CLI flag `--simulator-model <model>`: shorthand for `protocol: openai` with
   the given model; `api_key` from `OPENAI_API_KEY`
2. CLI flag `--simulator-agent <command>`: shorthand for `protocol: acp` with
   `connection: {transport: stdio, command: <command split on spaces>}`
3. Environment variable `BEVAL_SIMULATOR_MODEL`: same as `--simulator-model`
4. Environment variable `BEVAL_SIMULATOR_AGENT`: same as `--simulator-agent`
5. Config key `eval.conversation.simulator`: full simulator block
6. No simulator: exit code 2 (conversation simulation requires a simulator)

`--simulator-model` and `--simulator-agent` are mutually exclusive; providing
both MUST produce exit code 2.

## 15.7 Actor Model

### 15.7.1 Actor isolation

Each actor is an independent execution of one ConversationCase. An actor MUST
have its own:

* Adapter instance (no sharing with other actors or with static runs)
* Simulator instance (no sharing)
* Turn history (no sharing)

Each adapter type maintains conversation context for the duration of the actor
using a protocol-appropriate mechanism:

| Adapter protocol | Conversation context mechanism |
|---|---|
| ACP | Server-side session: `session/initialize` at actor start, `session/sendUserMessage` per turn, `session/close` at actor end |
| OpenAI (chat completions) | Client-side messages array: adapter accumulates `{role, content}` pairs internally across `invoke()` calls; full history sent with every request |

Both achieve the same effect — the agent sees the full conversation history on
each turn — but the state is managed server-side for ACP and client-side for
OpenAI. In both cases the adapter instance is initialized at actor start and
closed at actor end (§15.5.2).

### 15.7.2 Concurrency

Actors run concurrently up to `max_parallel_actors`. Implementations MUST
support sequential execution (`max_parallel_actors=1`). Parallel execution is
RECOMMENDED. Implementations that do not support parallel execution MUST
document this limitation and treat `max_parallel_actors > 1` as equivalent
to `max_parallel_actors=1`. When parallel execution is supported and
`max_parallel_actors > 1`, actors execute as concurrent tasks (threads, async
tasks, or processes — implementation choice).

Implementations SHOULD support `max_parallel_actors` values up to **1000**.
At this scale each actor is I/O-bound (waiting on the agent and simulator APIs),
so async task-based concurrency is strongly preferred over thread-per-actor or
process-per-actor models. Implementations MUST NOT impose an arbitrary low
ceiling on `max_parallel_actors` (e.g., hard-coding a limit of 10 or 50).

### 15.7.3 Actor lifecycle

```text
Actor states: pending → running → {completed | failed | cancelled}
```

Each actor MUST transition through these states and record timestamps at each
transition in its `ActorStatus`.

The final actor state is determined by `termination_reason` as follows:

| `termination_reason` | Actor state |
|---|---|
| `goal_achieved` | `completed` |
| `terminated_max_turns` | `completed` |
| `terminated_timeout` | `completed` |
| `cancelled` | `cancelled` |
| `agent_error` | `failed` |
| `simulator_error` | `failed` |

### 15.7.4 actor_count as multi-trial analogue

`actor_count > 1` runs multiple independent actors for the same persona/goal
pair. This is the conversation-simulation analogue of multi-trial evaluation
(§11): it reveals variance in conversation outcomes arising from simulator
non-determinism and agent non-determinism.

When `actor_count > 1`, `ConversationRunResult.summary` MUST include
aggregate `goal_achievement_rate` and `mean_turns_to_goal` across all actors.

## 15.8 Evaluation Model

Conversation simulation **does not introduce a separate evaluation model**.
Every grade — whether from a static goal criterion or a dynamic criterion
generated by the simulator — is produced by the §4 grader registry via the
same case runner used for static cases. The conversation runner's evaluation
loop is:

```
for each turn:
    dyn_case = simulator.generate_case(...)           # AI generates the Case
    if dyn_case.progress == 1.0: break                # goal achieved — early exit
    all_then = goal.stages["each turn"].then          # static goal criteria
             + dyn_case.then                          # dynamic per-turn criteria
    grades   = run_case_graders(all_then, turn_subj)  # existing case runner (§4)

after all turns:
    conv_grades = run_case_graders(                   # existing case runner (§4)
                      goal.stages["on finish"].then,
                      conv_subject)
```

The simulator's only role is Case generation per turn (`generate_case`).
Grading, scoring, and mode gating are entirely delegated to the existing
case runner.

### 15.8.1 Per-turn evaluation

For each turn, the framework constructs a **TurnSubject** from the agent
adapter's returned Subject with the following additions:

* `stage`: the one-based turn number
* `stage_name`: `"turn {turn_number}"` (e.g., `"turn 3"`)
* `metadata` additions: `persona_id`, `goal_id`, `actor_index`, `goal_progress`

Per-turn grades are produced by running a merged criterion list through the
existing case runner pipeline (§4 grader registry):

```
all_then = goal.stages["each turn"].then   # static — same every turn
         + dyn_case.then                   # dynamic — specific to this query
```

`goal.stages["each turn"].then` are the static criteria defined in the goal.
`dyn_case.then` are the query-specific criteria generated by
`simulator.generate_case()` for this turn (e.g., "the agent addressed the
international shipping aspect of the question").

Both sets are dispatched identically through the §4 grader registry —
no new evaluation infrastructure is involved. The simulator acts as an
AI-powered Case generator; grading is always handled by the existing case
runner. Mode gating (§6) applies equally to all criteria in `all_then`.

### 15.8.2 Conversation-level evaluation

After the conversation terminates, the framework constructs a
**ConversationSubject** (§15.5.5) and passes it to all
`goal.stages["on finish"].then` criterion strings via the §4 grader registry.

### 15.8.3 goal_achievement_score

```text
goal_achievement_score = last dyn_case.progress in history   (or 1.0 if goal_achieved)
```

`goal_achievement_score` is taken from the last `DynamicCase.progress` value
produced before the loop ended:

* If `termination_reason == goal_achieved`: `goal_achievement_score = 1.0`.
* Otherwise: `goal_achievement_score` = `progress` from the last
  `generate_case()` call (clamped to `[0.0, 1.0]`).
* If no turns completed (e.g., `cancelled`, `agent_error`, `simulator_error`
  on the first turn): `goal_achievement_score = 0.0`.

### 15.8.4 ConversationResult.overall_score

```text
overall_score = mean(
    [grade.score for grade in all per_turn grades (non-skipped)] +
    [grade.score for grade in all conversation grades (non-skipped)]
)
```

If all grades are skipped (e.g., in `dev` mode with no deterministic per-turn
graders), `overall_score` defaults to `goal_achievement_score`.

### 15.8.5 ConversationResult.passed

```text
passed = (overall_score >= case_pass_threshold)
```

Uses the same `case_pass_threshold` (§5.3) as static evaluation.

### 15.8.6 Grader inheritance

`per_turn` and `conversation` criterion strings are dispatched through the
same §4 grader registry as static `then` clauses. No new grader machinery is
needed. Mode definitions (§6.1) control which grader layers are active for
conversation runs identically to static runs.

## 15.9 Configuration

### 15.9.1 eval.conversation block

```yaml
eval:
  conversation:
    simulator:
      protocol: openai | acp
      # ...protocol-specific fields (see §15.6.3, §15.6.4)

    personas:
      - file: personas/standard.yaml          # path to persona library file
      - file: personas/adversarial.yaml
      # OR inline:
      - id: quick_test
        name: Quick Test User
        description: A user who asks one focused question.
        goals: [simple_query]                 # goal IDs this persona pursues

    goals:
      - file: goals/support.yaml             # path to goal library file
      # OR inline:
      - id: simple_query
        name: Simple Query
        given:
          objective: Get a direct answer to a factual question.
        stages:
          - when: "on finish"
            then:
              - "the agent provides a direct factual answer"

    actor_count: 3                # default: 1
    max_parallel_actors: 5        # default: 1
    history_dir: .beval_history   # default: .beval_history
    history_retention_days: 30    # default: 30 (0 = keep forever)
    run_timeout_seconds: 3600     # default: none
```

The `personas` and `goals` arrays load definitions into their respective pools.
The pairing model is **persona-centric**: each persona's `goals` field lists
which goal IDs from the loaded pool it pursues. Goal IDs referenced in a
persona's `goals` list that are not present in the loaded goal pool MUST
produce exit code 2. This is not a cartesian product — only the pairings
declared in each persona's `goals` field are executed.

### 15.9.2 Environment variable mappings

| Variable | Config key | Description |
|---|---|---|
| `BEVAL_SIMULATOR_MODEL` | `eval.conversation.simulator.model` | Shorthand simulator model (openai protocol) |
| `BEVAL_SIMULATOR_AGENT` | `eval.conversation.simulator.connection` | Shorthand acp simulator stdio command |
| `BEVAL_ACTOR_COUNT` | `eval.conversation.actor_count` | Number of actors per pair |
| `BEVAL_CONVERSATION_HISTORY_DIR` | `eval.conversation.history_dir` | History directory |

## 15.10 Results Schema

### 15.10.1 TurnResult

```json
{
  "turn_number": 3,
  "user_message": "What is the return window?",
  "agent_response": "You can return items within 30 days.",
  "completion_time_seconds": 1.2,
  "goal_progress": 0.5,
  "grades": [...],
  "metric_scores": { "quality": 0.9 },
  "overall_score": 0.9,
  "error": null
}
```

Required fields:

* `turn_number` (integer, ≥1): one-based turn index
* `user_message` (string): message sent by the simulator
* `agent_response` (string): agent's text response
* `completion_time_seconds` (number, ≥0): adapter response time
* `goal_progress` (Score): `DynamicCase.progress` value for this turn
* `grades` (Grade array): per-turn grades
* `metric_scores` (object): per-metric averages for this turn
* `overall_score` (Score): mean of non-skipped per-turn grades
* `error` (string or null): error message if the turn errored

### 15.10.2 ConversationResult

Mirrors the `CaseResult` shape (§8.3) with conversation-specific additions:

```json
{
  "id": "casual_user:find_refund_policy:1",
  "name": "Casual User → Find Refund Policy (actor 1)",
  "category": "casual_user/find_refund_policy",
  "persona_id": "casual_user",
  "goal_id": "find_refund_policy",
  "actor_index": 1,
  "overall_score": 0.82,
  "goal_achievement_score": 1.0,
  "passed": true,
  "goal_achieved": true,
  "termination_reason": "goal_achieved",
  "turn_count": 4,
  "time_seconds": 12.3,
  "metric_scores": { "quality": 0.85, "latency": 0.78 },
  "error": null,
  "turns": [...],
  "grades": [...]
}
```

Required fields:

* `id` (string): `{persona_id}:{goal_id}:{actor_index}`
* `name` (string): human-readable label including actor index
* `category` (string): `"{persona_id}/{goal_id}"` — derived grouping key that
  matches `CaseResult.category` shape for result tooling reuse
* `persona_id` (string)
* `goal_id` (string)
* `actor_index` (integer, ≥1)
* `overall_score` (Score)
* `goal_achievement_score` (Score)
* `passed` (boolean)
* `goal_achieved` (boolean)
* `termination_reason` (string): one of the reasons in §15.5.3
* `turn_count` (integer, ≥0)
* `time_seconds` (number, ≥0): total wall-clock time
* `metric_scores` (object)
* `error` (string or null)
* `turns` (TurnResult array)
* `grades` (Grade array): conversation-level grades only

### 15.10.3 ConversationRunResult

```json
{
  "label": "support-agent-v2",
  "timestamp": "2025-06-01T14:22:00Z",
  "mode": "validation",
  "config": { "grade_pass_threshold": 0.5, "case_pass_threshold": 0.7 },
  "summary": {
    "overall_score": 0.81,
    "goal_achievement_rate": 0.75,
    "passed": 6,
    "failed": 2,
    "errored": 0,
    "cancelled": 0,
    "total": 8,
    "total_turns": 34,
    "mean_turns_to_goal": 4.2,
    "metrics": { "quality": 0.85, "latency": 0.78 }
  },
  "conversations": [...]
}
```

Required fields (top-level):

* `label` (string, optional)
* `timestamp` (ISO 8601 datetime)
* `mode` (EvaluationMode)
* `config` (RunConfig)
* `summary` (ConversationRunSummary)
* `conversations` (ConversationResult array)

### 15.10.4 ConversationRunSummary

Required fields:

* `overall_score` (Score): mean of all ConversationResult.overall_scores
* `goal_achievement_rate` (Score): fraction of conversations where `goal_achieved=true`
* `passed` (integer): count of passed conversations
* `failed` (integer): count of failed conversations
* `errored` (integer): count of errored conversations
* `cancelled` (integer): count of cancelled conversations
* `total` (integer): total conversations
* `total_turns` (integer): sum of all turn counts
* `mean_turns_to_goal` (number or null): mean turn count across goal-achieved
  conversations; null if no conversations achieved the goal
* `metrics` (object): per-metric averages across all conversations

## 15.11 Progress Tracking

### 15.11.1 ActorStatus

```json
{
  "actor_id": "casual_user:find_refund_policy:2",
  "persona_id": "casual_user",
  "goal_id": "find_refund_policy",
  "actor_index": 2,
  "state": "running",
  "turn_count": 3,
  "max_turns": 20,
  "goal_progress": 0.5,
  "current_score": 0.78,
  "started_at": "2025-06-01T14:22:05Z",
  "updated_at": "2025-06-01T14:22:18Z",
  "error": null
}
```

Required fields:

* `actor_id` (string): ConversationCase identity
* `persona_id`, `goal_id` (string)
* `actor_index` (integer)
* `state` (string): `pending | running | completed | failed | cancelled`
* `turn_count` (integer): turns completed so far
* `max_turns` (integer): goal constraint value
* `goal_progress` (Score): last `DynamicCase.progress` from `generate_case()`
* `current_score` (Score): current `overall_score` including all graded turns
* `started_at` (ISO 8601 or null)
* `updated_at` (ISO 8601): last status update time
* `error` (string or null)

### 15.11.2 ConversationRunStatus

```json
{
  "run_id": "run-20250601-142200",
  "state": "running",
  "elapsed_seconds": 45.2,
  "actors_total": 8,
  "actors_running": 3,
  "actors_completed": 4,
  "actors_failed": 0,
  "actors_cancelled": 0,
  "actors_pending": 1,
  "goal_achievement_rate_so_far": 0.75,
  "current_overall_score": 0.81,
  "actor_statuses": [...]
}
```

Required fields:

* `run_id` (string): opaque identifier for the run
* `state` (string): `running | completed | cancelled | failed`
* `elapsed_seconds` (number)
* `actors_total` (integer)
* `actors_running`, `actors_completed`, `actors_failed`, `actors_cancelled`,
  `actors_pending` (integers)
* `goal_achievement_rate_so_far` (Score): fraction among completed actors
* `current_overall_score` (Score): mean of completed actor scores
* `actor_statuses` (ActorStatus array)

### 15.11.3 Progress delivery

Implementations MUST provide a console progress display (e.g., a live table
of ActorStatus rows) during active runs, unless `--quiet` is set.

Implementations SHOULD write `status.json` (ConversationRunStatus) to the
configured `output.dir` directory and update it after each turn completes.
The file path is `{output.dir}/conversation-status.json`.

Implementations MAY expose an HTTP endpoint (e.g., `GET /status`) that returns
the current ConversationRunStatus as JSON. The endpoint address MUST be printed
at run start if enabled.

Both console output and status.json writing are suppressible via `--quiet`.

## 15.12 Run History

### 15.12.1 Persistence

At the end of each conversation simulation run (successful, failed, or
partially cancelled), the implementation MUST write a `ConversationRunResult`
to **both** of the following locations:

1. `{history_dir}/conversation-results-{timestamp}.json` — accumulates across
   runs for historical tracking. `{timestamp}` is ISO 8601 UTC formatted as
   `YYYYMMDDTHHMMSSZ` (e.g., `20250601T142200Z`).
2. `{output.dir}/conversation-results.json` — overwritten on each run,
   consistent with static run output location.

Partial results MUST be written on cancellation to both locations. The
`summary` MUST reflect only the conversations that completed before
cancellation.

### 15.12.2 `beval converse history` subcommand

The `history` subcommand reads `ConversationRunResult` files from
`history_dir` and reports aggregate statistics:

```text
beval converse history [options]
```

Options:

| Flag | Description |
|---|---|
| `--since <date>` | Include only runs on or after this date (ISO 8601) |
| `--persona <id>` | Filter conversations by persona ID |
| `--goal <id>` | Filter conversations by goal ID |
| `--history-dir <path>` | Override history directory |
| `--format json` | Output as JSON instead of console table |

Output includes per-run summary rows, trend direction (improving/degrading),
and per-goal/persona breakdown.

### 15.12.3 Retention

When `history_retention_days > 0`, implementations SHOULD delete
`ConversationRunResult` files older than `history_retention_days` days on
run start (best-effort: log a warning on deletion failure, do not abort).
`history_retention_days=0` disables automatic deletion.

## 15.13 Cancellation

### 15.13.1 SIGINT handling

When the process receives SIGINT (Ctrl-C), the implementation MUST:

1. Stop dispatching new actors
2. Allow currently running actors to complete their current turn (do NOT
   interrupt mid-turn)
3. After each running actor's current turn completes, mark the actor as
   `cancelled` and do not start the next turn
4. Mark pending (not-yet-started) actors as `cancelled`
5. Write a partial `ConversationRunResult` with all completed and cancelled
   conversations
6. Exit with code `1`

A second SIGINT (before the first completes) MUST force-terminate all actors
immediately.

### 15.13.2 Programmatic cancellation

Implementations MUST expose a `cancel()` method on the run controller that
triggers the same behavior as §15.13.1. The `cancel()` method is non-blocking
and returns immediately.

### 15.13.3 run_timeout_seconds

When `run_timeout_seconds` is set and the run duration exceeds this value,
the implementation MUST trigger cancellation as in §15.13.1. The exit code
is still `1`.

## 15.14 CLI Changes

### 15.14.1 `beval converse` command group

A new command group `converse` is added alongside the existing `run` command:

```text
beval converse <subcommand> [options]
```

Subcommands:

| Subcommand | Description |
|---|---|
| `run` | Execute a conversation simulation run |
| `history` | Query historical run results |
| `validate` | Validate persona/goal library files against schema |

### 15.14.2 `beval converse run` flags

| Flag | Default | Description |
|---|---|---|
| `--config <path>` | `eval.config.yaml` | Config file path |
| `--persona <id>` | all | Run only this persona (repeatable) |
| `--goal <id>` | all | Run only this goal (repeatable) |
| `--actor-count <n>` | from config | Override actor count |
| `--max-parallel <n>` | from config | Override max parallel actors |
| `--simulator-model <model>` | — | Shorthand openai simulator model |
| `--simulator-agent <command>` | — | Shorthand acp simulator; stdio command (e.g., `copilot --acp --stdio`) |
| `--mode <mode>` | from config | Evaluation mode |
| `--label <label>` | — | Label for this run |
| `--output-dir <path>` | `eval_results` | Results output directory |
| `--history-dir <path>` | `.beval_history` | History directory |
| `--timeout <seconds>` | — | Override run_timeout_seconds |

`--quiet` is a global flag defined in `cli.spec.yaml` and applies to all
subcommands including `beval converse run`. When set, it suppresses the
conversation-specific console progress display and `status.json` writes.

### 15.14.3 `beval converse validate` flags

| Flag | Description |
|---|---|
| `--personas <path>` | Persona library file to validate |
| `--goals <path>` | Goal library file to validate |

### 15.14.4 New environment variables

| Variable | Description |
|---|---|
| `BEVAL_SIMULATOR_MODEL` | Shorthand simulator model (openai protocol) |
| `BEVAL_SIMULATOR_AGENT` | Shorthand acp simulator stdio command |
| `BEVAL_ACTOR_COUNT` | Number of actors per persona/goal pair |
| `BEVAL_CONVERSATION_HISTORY_DIR` | Override history directory |

## 15.15 Security

### 15.15.1 Simulator prompt safety

Agent responses included in simulator prompts MUST be delimited by
`<agent_response>` tags (§10.3 pattern). The simulator system message MUST
instruct the simulator to evaluate only the delimited content.

Agent responses in `generate_case` history MUST be delimited by
`<agent_response>` tags in the conversation-history block of the
`generate_case` prompt (§15.6.3.1).

### 15.15.2 max_answer_chars truncation

When `max_answer_chars` is configured, agent response content MUST be
truncated to that length before inclusion in simulator prompts. Truncation
MUST be noted in the prompt (e.g., `[truncated]`) to avoid misleading the
simulator.

### 15.15.3 Secret redaction

`${VAR}` references in simulator config (e.g., `api_key`) MUST be resolved
from the process environment at load time and MUST NOT appear in logs,
results, or error messages (§10.1 pattern).

### 15.15.4 Adapter session isolation

Each actor MUST receive its own adapter instance. Adapter sessions MUST NOT
be shared between actors or between actors and static evaluation runs.
This prevents cross-actor context contamination.

### 15.15.5 Conversation history retention

`history_dir` files contain conversation transcripts. Implementations SHOULD
document the PII implications of storing conversation history and SHOULD
support `history_retention_days` to limit retention (§15.12.3). This extends
the monitoring data governance requirements of §10.5 to conversation history.

## 15.16 Schema Changes

### 15.16.1 config.schema.json additions

The following definitions are added to `config.schema.json`:

* `ConversationConfig`: top-level `eval.conversation` block
* `SimulatorConfig`: simulator protocol and connection details
* `PersonaSource`: union of file-path reference and inline persona
* `GoalSource`: union of file-path reference and inline goal

The `EvalConfig` definition gains a new optional `conversation` property:

```json
"conversation": {
  "$ref": "#/$defs/ConversationConfig",
  "description": "Conversation simulation configuration. See spec/conversation-sim.spec.md §15."
}
```

Full schema definitions are specified in `spec/schemas/config.schema.json`.

### 15.16.2 New schema files

* `spec/schemas/personas-goals.schema.json`: validates persona and goal
  library files (§15.3, §15.4)
* `spec/schemas/conversation-results.schema.json`: validates
  `ConversationRunResult`, `ConversationResult`, `TurnResult`,
  `ConversationRunSummary` (§15.10)
