---
description: Agent adapter specification for the Behavioral Evaluation Framework
parent: SPEC.md §13
---

# Agent Adapters Specification

Addendum to the [Behavioral Evaluation Framework Specification](../SPEC.md).

Status: Draft
Version: 0.1.0

## 13.1 Overview

An **agent** is the system under test. This section defines a declarative way
to specify how the runner connects to an agent, replacing or complementing the
programmatic `handler` callable (§7).

Agent definitions decouple evaluation case authoring from connection mechanics.
The same case files can evaluate agents reachable via different protocols
without modification.

## 13.2 Agent definition schema

An agent is defined in a YAML file with the following structure:

```yaml
name: my-agent
description: Optional human-readable description
protocol: acp | a2a | custom
connection:
  # Protocol-specific connection parameters (see §13.4)
timeout: 30               # Request timeout in seconds (default: 30)
retry:
  max_attempts: 3         # Maximum retry attempts (default: 1, no retry)
  backoff: 1.0            # Initial backoff in seconds (default: 1.0)
env:                      # Environment variable bindings
  API_KEY: ${MY_AGENT_KEY}
metadata:                 # Open-ended key-value pairs surfaced in results
  version: "1.0"
```

Required fields:

* `name` (string): unique agent identifier within a project
* `protocol` (string): one of `acp`, `a2a`, `custom`
* `connection` (object): protocol-specific parameters (see §13.4)

Optional fields:

* `description` (string)
* `timeout` (number, seconds, default `30`)
* `retry` (object): retry policy with `max_attempts` (integer, default `1`)
  and `backoff` (number, seconds, default `1.0`)
* `env` (object): environment variable bindings using `${VAR_NAME}` syntax.
  Values MUST be resolved from the process environment at load time. Missing
  variables MUST produce exit code 2 (invalid input).
* `metadata` (object): open-ended key-value pairs surfaced in results output

Agent definition files MUST use safe YAML loading (§10.2).

## 13.3 Adapter interface

An adapter translates between the framework's execution model and a specific
agent protocol. All adapters, whether built-in or custom, MUST implement the
following contract:

```text
AdapterInterface:
  invoke(input: AdapterInput) -> Subject
  close() -> void
```

Where `AdapterInput` carries:

* `query` (string or message array): the input derived from case givens
* `givens` (map): full givens from the case definition
* `context` (EvalContext): runtime context (§4.3)
* `stage` (integer or null): current stage number
* `stage_name` (string or null): current stage when-clause text
* `prior_subject` (Subject or null): prior stage output

The adapter MUST return a Subject (§2.2) with at minimum `input`, `output`,
and `completion_time` populated. The adapter SHOULD populate `tool_calls`,
`spans`, and `metadata` when the protocol provides this information.

## 13.4 Built-in adapters

### 13.4.1 ACP (Agent Client Protocol)

Protocol identifier: `acp`

The Agent Client Protocol is a lightweight protocol using JSON-RPC 2.0 over
stdio or TCP, designed for direct agent interaction with minimal overhead.

Connection parameters:

```yaml
connection:
  transport: stdio | tcp          # Required
  command: ["node", "agent.js"]   # Required when transport is stdio
  host: "127.0.0.1"              # Required when transport is tcp
  port: 3000                      # Required when transport is tcp
  env:                            # Additional env vars for subprocess (stdio only)
    OPENAI_API_KEY: ${OPENAI_API_KEY}
```

Behavior:

* **stdio transport**: The adapter MUST spawn the command as a subprocess,
  communicate via stdin/stdout using newline-delimited JSON-RPC 2.0, and
  terminate the subprocess when `close()` is called.
* **tcp transport**: The adapter MUST connect to `host:port` using
  newline-delimited JSON-RPC 2.0.
* The adapter MUST send `session/initialize` before the first invocation
  and `session/sendUserMessage` for each case invocation.
* The adapter MUST collect streamed response chunks and assemble them into
  the Subject `output` field.
* The adapter SHOULD populate `Subject.tool_calls` from tool-use events in
  the protocol stream when available.
* The adapter SHOULD populate `Subject.metadata` with protocol-level metadata
  (e.g., `session_id`, `model`).
* Environment variables for the subprocess (stdio) MUST be inherited from the
  parent process, with `connection.env` entries merged on top.

### 13.4.2 A2A (Agent2Agent)

Protocol identifier: `a2a`

The Agent2Agent protocol is an HTTP-based protocol using JSON-RPC 2.0 with
optional SSE streaming, designed for remote and enterprise agent communication.

Connection parameters:

```yaml
connection:
  url: "https://agent.example.com"                    # Required: base URL
  agent_card_path: "/.well-known/agent.json"           # Optional (default)
  auth:
    type: api_key | oauth2 | none                      # Default: none
    header: "Authorization"                            # Header name (api_key)
    value: ${A2A_API_KEY}                              # Token value (api_key)
    # OAuth2 fields (when type is oauth2):
    token_url: "https://auth.example.com/token"
    client_id: ${A2A_CLIENT_ID}
    client_secret: ${A2A_CLIENT_SECRET}
    scopes: ["agent:invoke"]
  streaming: true                                      # Use SSE (default: true)
```

Behavior:

* The adapter SHOULD fetch the Agent Card from `{url}{agent_card_path}` on
  first invocation to discover capabilities and supported content types.
  Failure to fetch the card SHOULD produce a warning, not an error, unless
  the card is required for message formatting.
* The adapter MUST send messages via `POST` using JSON-RPC 2.0 to the agent
  endpoint.
* When `streaming` is true, the adapter MUST consume SSE events to track task
  state transitions (`PENDING` → `WORKING` → `COMPLETED`/`FAILED`/`CANCELED`).
* When `streaming` is false, the adapter MUST poll for task completion.
* Task state `FAILED` or `CANCELED` MUST be mapped to an errored CaseResult
  with exit code 3 (infrastructure_error).
* Task state `INPUT_REQUIRED` or `AUTH_REQUIRED` MUST be mapped to an errored
  CaseResult with exit code 3 and a diagnostic message indicating the agent
  requires additional input or authentication.
* The adapter MUST populate `Subject.output` from the task's artifact content.
* The adapter SHOULD populate `Subject.tool_calls` and `Subject.metadata` from
  task metadata when available.

### 13.4.3 Custom

Protocol identifier: `custom`

Connection parameters:

```yaml
connection:
  module: "my_package.adapters"       # Required: module path
  class: "MyAdapter"                  # Required: class implementing AdapterInterface
  config:                             # Optional: passed to adapter constructor
    endpoint: "https://custom.api"
    api_key: ${CUSTOM_KEY}
```

Behavior:

* The runner MUST dynamically load the specified module and instantiate the
  class.
* The class MUST implement the `AdapterInterface` (§13.3).
* The `config` object, if present, MUST be passed to the constructor.
* Custom adapter loading failures MUST produce exit code 2 (invalid input).
* Security: implementations SHOULD restrict custom adapter loading to
  explicitly allowed module paths in validation and monitoring modes (§10.4).

## 13.5 Agent resolution

The runner resolves the active agent using the following precedence (highest
first):

1. **CLI flag** `--agent <path-or-name>`: path to an agent YAML file, or a
   name matching an agent defined in the config file
2. **Config file** `eval.agents.default`: the default agent name referencing
   an entry in `eval.agents.definitions`
3. **Programmatic handler**: the `handler` callable passed to the Runner
   constructor (library usage)
4. **No agent**: the runner uses stub subjects (existing behavior)

When `--agent` is a file path (contains `/` or ends with `.yaml`/`.yml`), the
runner MUST load the agent definition from that file directly.

When `--agent` is a bare name, the runner MUST look up the name in
`eval.agents.definitions` from the config file. If not found, the runner MUST
report exit code 2 (invalid input).

## 13.6 CLI changes

New flag on the `run` command:

```text
--agent, -a <path-or-name>
    Agent to evaluate. Accepts a path to an agent YAML file or a name
    defined in the configuration file's agents section.
```

New environment variable mapping:

```text
BEVAL_AGENT → eval.agents.default
```

## 13.7 Configuration changes

The config schema gains a new `agents` block under `eval`:

```yaml
eval:
  agents:
    default: my-agent              # Name of the default agent
    definitions:
      - name: my-agent
        protocol: acp
        connection:
          transport: stdio
          command: ["python", "-m", "my_agent"]
        timeout: 30
      - name: production-agent
        protocol: a2a
        connection:
          url: "https://agent.prod.example.com"
          auth:
            type: api_key
            header: "X-API-Key"
            value: ${PROD_API_KEY}
```

The `agents` block is optional. When absent, agent configuration is not
available and the runner falls back to the programmatic handler or stub
behavior.

The `definitions` array uses the same schema as standalone agent YAML files
(§13.2). Implementations MUST reject duplicate names with exit code 2.

## 13.8 Error handling

Agent adapter errors map to the exit code scheme in §7.4:

| Error category | Exit code | Examples |
|---|---|---|
| Invalid agent definition | 2 (invalid input) | Missing required fields, unknown protocol, unresolvable `${VAR}`, duplicate names |
| Connection failure | 3 (infrastructure_error) | TCP connection refused, HTTP 5xx, DNS resolution failure, subprocess crash |
| Timeout | 3 (infrastructure_error) | Request exceeds configured `timeout` |
| Protocol error | 3 (infrastructure_error) | Malformed JSON-RPC response, unexpected task state, invalid SSE stream |
| Authentication failure | 3 (infrastructure_error) | HTTP 401/403, OAuth token exchange failure |
| Custom adapter load failure | 2 (invalid input) | Module not found, class does not implement AdapterInterface |
| Adapter internal error | 4 (internal error) | Unhandled exception within adapter code |

When retries are configured (§13.2, `retry`), the adapter MUST retry on
connection failures and timeouts up to `max_attempts` with exponential backoff
starting from `backoff` seconds. Authentication failures (401/403) MUST NOT be
retried.

The adapter MUST include diagnostic information in the CaseResult `error`
field, including the protocol, error type, and any server-provided error
message.

## 13.9 Results integration

When an agent adapter is active, the results output (§8) MUST include the
agent identity in the top-level `config` block:

```json
{
  "config": {
    "agent": {
      "name": "my-agent",
      "protocol": "acp"
    },
    "grade_pass_threshold": 0.5,
    "case_pass_threshold": 0.7
  }
}
```

The `agent` object MUST contain `name` and `protocol`. It MUST NOT contain
connection secrets or credentials.

## 13.10 Security requirements

Agent adapter security extends the requirements in §10:

* Connection credentials resolved via `${VAR}` MUST NOT appear in logs,
  results output, or error messages. Implementations MUST redact resolved
  values.
* Subprocess environment variables (ACP stdio) MUST be scrubbed from results
  output.
* OAuth tokens MUST NOT be logged or persisted.
* Custom adapter classes MUST be loaded only from explicitly configured module
  paths; wildcard or arbitrary module loading is prohibited in validation and
  monitoring modes.
