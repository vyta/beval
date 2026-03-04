# beval — TypeScript

> [!IMPORTANT]
> This implementation is incomplete and under active development. Core types,
> the grader registry, and the CLI are in place, but the runner pipeline, subject
> handling, and judge integration are not fully wired. Expect breaking changes.

TypeScript implementation of the beval behavioral evaluation framework.

See the root [SPEC.md](../SPEC.md) for the full specification (v0.1.0).

## Prerequisites

- Node.js 18+
- npm

## CLI

```bash
npx beval --help
npx beval version
npx beval run -m dev -l my-label
```

## Development

The repository uses containerized environments via `make` targets for all development operations. This ensures consistent behavior without requiring a local Node.js installation.

Run tests:

```bash
make ts-test
```

Run linting:

```bash
make ts-lint
```

All commands use containerized environments with `nerdctl` (or `docker` with `CONTAINER_RUNTIME=docker make ts-test`).

## Project structure

```text
src/
  index.ts        Public API exports
  types.ts        Core type definitions
  dsl.ts          DSL fluent builder
  graders/        Grader registry and implementations
  judge.ts        LLM judge interface
  runner.ts       Runner orchestration
  subject.ts      Subject normalization
  reporter.ts     Result reporting
  loader.ts       YAML case loading
  schema.ts       JSON Schema validation
  tracing.ts      OpenTelemetry tracing
  cli.ts          CLI entrypoint
tests/
  types.test.ts   Type tests
  loader.test.ts  Loader tests
```
