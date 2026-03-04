---
description: "Repository-wide GitHub Copilot instructions for the beval project"
---

## Build and Run Environment

This repository uses containerized, ephemeral environments for all build, test, and lint operations. Always use the `make` targets defined in the root `Makefile` when running commands.

### Required Practices

Use make targets for all development operations. The Makefile orchestrates containerized environments via `nerdctl` (or `docker` if configured), ensuring consistent builds without local toolchain pollution.

**Examples:**

* Run Python tests: `make python-test`
* Lint Go code: `make go-lint`
* Build .NET project: `make dotnet-build`
* Run all tests: `make test`

### Adding New Make Targets

When implementing new functionality that requires build, test, or run commands, add corresponding make targets to the root `Makefile`. Follow the existing pattern:

* Use `$(CONTAINER_RUNTIME)` variable (defaults to `nerdctl`)
* Mount the workspace as a volume
* Create and use named volumes for caching (e.g., `beval-<lang>-cache`)
* Set the working directory to the language-specific subdirectory
* Use officially maintained base images matching the project version

### Prohibited Practices

Do not instruct users to run commands directly with local toolchains. Avoid patterns like:

* `cd python && pytest tests/`
* `go test ./...`
* `npm test`
* `dotnet build`

Instead, always reference the corresponding make target that provides the containerized environment.

### Container Runtime Configuration

The `CONTAINER_RUNTIME` variable defaults to `nerdctl` but supports `docker` as an alternative:

```bash
make python-test                          # uses nerdctl
CONTAINER_RUNTIME=docker make python-test # uses docker
```

When users encounter environment issues, verify they have `nerdctl` installed or direct them to override with `CONTAINER_RUNTIME=docker`.
