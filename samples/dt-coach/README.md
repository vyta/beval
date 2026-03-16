# Design Thinking Coach — beval Sample

Behavioral evaluation cases for the **DT Coach**, a GitHub Copilot custom agent
that guides teams through the 9 Design Thinking for HVE methods using a
Think / Speak / Empower philosophy.

Agent source: <https://github.com/microsoft/hve-core/blob/main/.github/agents/design-thinking/dt-coach.agent.md>

## Files

| File | Description |
|------|-------------|
| `agent.yaml` | ACP agent definition — stdio transport |
| `agent-tcp.yaml` | ACP agent definition — TCP transport |
| `eval.config.yaml` | Centralized config with both agent variants |
| `cases/coaching-behaviors.yaml` | Core philosophy & coaching boundaries (6 cases) |
| `cases/session-phases.yaml` | Session lifecycle — init, coaching, transition, closure (7 cases) |
| `cases/method-guidance.yaml` | Method-specific guidance across all 9 methods (10 cases) |
| `cases/progressive-hints-and-navigation.yaml` | Hint engine, non-linear navigation, anti-patterns (7 cases) |

## Prerequisites

| Requirement | Details |
|-------------|---------|
| `AGENT_REPO_ROOT` | Path to the cloned `hve-core` repo (stdio transport) |
| `copilot` CLI | GitHub Copilot CLI with ACP support |
| `AGENT_HOST` / `AGENT_PORT` | Agent endpoint (TCP transport only, defaults to `127.0.0.1:3000`) |
| `JUDGE_HOST` / `JUDGE_PORT` | Judge endpoint (TCP transport only, defaults to `127.0.0.1:3001`) |

## Running

The judge is configured in `eval.config.yaml` using the Copilot ACP backend
(`protocol: acp`). No `--judge-model` flag is needed.

### Stdio transport

```bash
cd python && uv sync --extra acp
uv run beval -c ../samples/dt-coach/eval.config.yaml run \
  --cases ../samples/dt-coach/cases \
  -m validation --verbose
```

### TCP transport

Start the agent and judge as separate processes (different ports):

```bash
# Agent — runs the dt-coach custom agent
copilot --acp --port 3000 --agent dt-coach --allow-all &

# Judge — plain Copilot LLM, no custom agent
copilot --acp --port 3001 --allow-all &
```

Then run the evaluation:

```bash
cd python && uv sync --extra acp
uv run beval -c ../samples/dt-coach/eval.config.yaml run \
  --cases ../samples/dt-coach/cases \
  --agent ../samples/dt-coach/agent-tcp.yaml \
  -m validation --verbose
```

## Cases (30 total)

### Coaching Behaviors (6 cases)

| ID | Tags | What it tests |
|----|------|---------------|
| `think_speak_empower_pattern` | philosophy, core | Response follows Think/Speak/Empower structure |
| `short_conversational_responses` | conversation-style, core | Concise responses — no methodology lectures |
| `empowers_with_choices` | philosophy, core | Ends with choices, not directives |
| `collaborate_not_execute` | boundaries, core | Works WITH users, does not produce artifacts for them |
| `no_prescriptive_solutions` | boundaries, core | Guides exploration instead of prescribing fixes |
| `never_make_users_feel_foolish` | boundaries, tone | Stays curious and supportive when users are confused |

### Session Phases (7 cases)

| ID | Tags | What it tests |
|----|------|---------------|
| `init_asks_for_project_slug` | phase-1, initialization, core | Asks for kebab-case project slug |
| `init_clarifies_context` | phase-1, initialization, core | Gathers role, team, method focus |
| `init_defaults_to_method_1` | phase-1, initialization | Starts new projects with Method 1 |
| `active_coaching_open_ended_questions` | phase-2, active-coaching, core | Asks open-ended questions to discover real problems |
| `active_coaching_periodic_summary` | phase-2, active-coaching | Summarizes progress and checks direction |
| `method_transition_recap_and_confirm` | phase-3, transition, core | Recaps and confirms method change |
| `session_closure_summary` | phase-4, closure, core | Summarizes session and suggests next steps |

### Method Guidance (10 cases)

| ID | Tags | What it tests |
|----|------|---------------|
| `method_1_frozen_vs_fluid` | method-1, problem-space, core | Assesses frozen vs fluid requests |
| `method_1_identify_stakeholders` | method-1, problem-space, core | Guides stakeholder identification |
| `method_2_research_planning` | method-2, problem-space | Helps plan systematic research |
| `method_3_pattern_recognition` | method-3, problem-space, core | Guides pattern recognition from research |
| `method_4_divergent_ideation` | method-4, solution-space, core | Facilitates divergent brainstorming |
| `method_5_concept_validation` | method-5, solution-space | Guides concept creation for validation |
| `method_6_scrappy_prototypes` | method-6, solution-space | Steers toward low-fidelity prototyping |
| `method_7_feasibility_testing` | method-7, implementation-space | Guides technical feasibility testing |
| `method_8_systematic_validation` | method-8, implementation-space | Structures user testing for validation |
| `method_9_continuous_optimization` | method-9, implementation-space | Guides iteration at scale |

### Progressive Hints & Navigation (7 cases)

| ID | Tags | What it tests |
|----|------|---------------|
| `hint_broad_direction_first` | hints, core | Starts with broad hints when user is stuck |
| `hint_escalation_on_repeated_confusion` | hints, escalation | Escalates to specific guidance on continued confusion |
| `backward_transition_accepted` | navigation, non-linear, core | Accepts backward method transitions as normal |
| `transparent_method_shift` | navigation, transparency, core | Announces method shifts transparently |
| `no_multiple_choice_quizzes` | anti-pattern, conversation-style | Avoids quiz-like numbered option lists |
| `no_unsolicited_method_change` | anti-pattern, navigation | Stays in current method without silently shifting |
| `session_resumption` | session-management, resumption | Resumes session with prior context |

## Grading

This sample defaults to `validation` mode because the cases primarily evaluate
coaching quality through AI-judged criteria (Think/Speak/Empower adherence,
boundary respect, method-appropriate guidance). The judge is configured in
`eval.config.yaml` using the Copilot ACP backend — no separate API key is
required. Deterministic graders (completion time, response length) provide
basic guardrails alongside the AI judge.
