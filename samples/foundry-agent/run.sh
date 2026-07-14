#!/bin/bash
export FOUNDRY_PROJECT_ENDPOINT="https://cortyxmvefoundry.services.ai.azure.com/api/projects/cortyx-mve-orchestration"
export FOUNDRY_AGENT_NAME="ecommerce-agent"

uv run --project ../../python beval -c eval.config.yaml run --cases cases/cortyx --verbose -o results.json
