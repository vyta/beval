CONTAINER_RUNTIME ?= nerdctl
PYTHON_IMAGE     := ghcr.io/astral-sh/uv:python3.12-trixie-slim
GO_IMAGE         := golang:1.23
DOTNET_IMAGE     := mcr.microsoft.com/dotnet/sdk:8.0
NODE_IMAGE       := node:22-slim

.PHONY: python-test python-lint python-typecheck python-check \
        go-test go-lint \
        dotnet-test dotnet-build \
        ts-test ts-lint \
		test lint clean \
		conformance conformance-build-python conformance-build-go conformance-build-dotnet conformance-build-ts

# --- Python ---
python-test:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-uv-cache:/root/.cache/uv" \
		-w /workspace/python \
		$(PYTHON_IMAGE) \
		bash -c "uv sync --extra dev && uv run pytest tests/"

python-lint:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-uv-cache:/root/.cache/uv" \
		-w /workspace/python \
		$(PYTHON_IMAGE) \
		bash -c "uv sync --extra dev && uv run ruff check src/ tests/"

python-typecheck:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-uv-cache:/root/.cache/uv" \
		-w /workspace/python \
		$(PYTHON_IMAGE) \
		bash -c "uv sync --extra dev && uv run mypy src/"

python-check: python-lint python-test

# --- Go ---
go-test:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-go-cache:/go/pkg" \
		-w /workspace/go \
		$(GO_IMAGE) \
		go test ./...

go-lint:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-go-cache:/go/pkg" \
		-w /workspace/go \
		$(GO_IMAGE) \
		bash -c "go vet ./..."

# --- .NET ---
dotnet-build:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-nuget-cache:/root/.nuget" \
		-w /workspace/dotnet \
		$(DOTNET_IMAGE) \
		dotnet build

dotnet-test:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-nuget-cache:/root/.nuget" \
		-w /workspace/dotnet \
		$(DOTNET_IMAGE) \
		dotnet test

# --- TypeScript ---
ts-test:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-npm-cache:/root/.npm" \
		-w /workspace/typescript \
		$(NODE_IMAGE) \
		bash -c "npm ci && npm test"

ts-lint:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-npm-cache:/root/.npm" \
		-w /workspace/typescript \
		$(NODE_IMAGE) \
		bash -c "npm ci && npm run lint"
# --- Conformance Build ---
conformance-build-python:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-uv-cache:/root/.cache/uv" \
		-w /workspace/python \
		$(PYTHON_IMAGE) \
		bash -c "uv sync && uv build --wheel"

conformance-build-go:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-go-cache:/go/pkg" \
		-w /workspace/go \
		$(GO_IMAGE) \
		go build -o /workspace/conformance/.output/beval-go ./cmd/beval/

conformance-build-dotnet:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-nuget-cache:/root/.nuget" \
		-w /workspace/dotnet \
		$(DOTNET_IMAGE) \
		dotnet build --nologo -v quiet

conformance-build-ts:
	$(CONTAINER_RUNTIME) run --rm \
		-v "$$(pwd):/workspace" \
		-v "beval-npm-cache:/root/.npm" \
		-w /workspace/typescript \
		$(NODE_IMAGE) \
		bash -c "npm ci && npm run build"

# --- Conformance ---
conformance: conformance-build-python conformance-build-go conformance-build-dotnet conformance-build-ts
	./conformance/runner.sh


# --- Aggregate ---
test: python-test go-test dotnet-test ts-test

lint: python-lint go-lint ts-lint

clean:
	$(CONTAINER_RUNTIME) volume rm -f beval-uv-cache beval-go-cache beval-nuget-cache beval-npm-cache 2>/dev/null || true
	rm -rf conformance/.output \
		python/.venv python/.mypy_cache python/.pytest_cache python/.ruff_cache \
		python/src/beval/__pycache__ python/src/beval/graders/__pycache__ python/tests/__pycache__ \
		typescript/dist
	find dotnet -type d \( -name obj -o -name bin \) -prune -exec rm -rf {} +
