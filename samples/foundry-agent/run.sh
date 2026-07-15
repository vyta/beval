#!/bin/bash
export FOUNDRY_PROJECT_ENDPOINT="https://cortyxmvefoundry.services.ai.azure.com/api/projects/cortyx-mve-orchestration"
export FOUNDRY_AGENT_NAME="ecommerce-agent"

CASES="${1:-cases/cortyx}"
uv run --project ../../python beval -c eval.config.yaml run --cases "$CASES" --verbose -o results.json
