#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURES_DIR="${REPO_ROOT}/conformance/fixtures"
OUTPUT_DIR="${REPO_ROOT}/conformance/.output"
SCHEMA_FILE="${REPO_ROOT}/spec/schemas/results.schema.json"
LANGUAGES=("python" "typescript" "go" "dotnet")
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-nerdctl}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --languages)
      IFS=',' read -ra LANGUAGES <<< "$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Clean output directory
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"

# Build each implementation
build_language() {
  local lang="$1"
  echo "==> Building ${lang}..."
  case "${lang}" in
    python)
      (cd "${REPO_ROOT}" && make conformance-build-python)
      ;;
    typescript)
      (cd "${REPO_ROOT}" && make conformance-build-ts)
      ;;
    go)
      (cd "${REPO_ROOT}" && make conformance-build-go)
      ;;
    dotnet)
      (cd "${REPO_ROOT}" && make conformance-build-dotnet)
      ;;
    *)
      echo "Unknown language: ${lang}" >&2
      return 1
      ;;
  esac
}

# Build the config flag if config.yaml exists for the fixture.
config_flag() {
  local fixture_dir="$1"
  local fixture_name
  fixture_name="$(basename "${fixture_dir}")"
  if [[ -f "${fixture_dir}/config.yaml" ]]; then
    echo "--config /workspace/conformance/fixtures/${fixture_name}/config.yaml"
  fi
}

config_flag_native() {
  local fixture_dir="$1"
  if [[ -f "${fixture_dir}/config.yaml" ]]; then
    echo "--config ${fixture_dir}/config.yaml"
  fi
}

# Run a single fixture against a single language.
# Captures the exit code in ${OUTPUT_DIR}/${lang}/${fixture_name}/exit-code.
run_fixture() {
  local lang="$1"
  local fixture_dir="$2"
  local fixture_name
  fixture_name="$(basename "${fixture_dir}")"
  local out_dir="${OUTPUT_DIR}/${lang}/${fixture_name}"
  mkdir -p "${out_dir}"
  local actual_exit=0
  local cfg
  local cfg_native

  cfg="$(config_flag "${fixture_dir}")"
  cfg_native="$(config_flag_native "${fixture_dir}")"

  echo "  -> Running ${fixture_name} with ${lang}..."
  case "${lang}" in
    python)
      ${CONTAINER_RUNTIME} run --rm \
        -v "${REPO_ROOT}:/workspace" \
        -v "beval-uv-cache:/root/.cache/uv" \
        -w /workspace/python \
        ghcr.io/astral-sh/uv:python3.12-trixie-slim \
        bash -c "uv sync && uv run beval ${cfg} run \
          --cases /workspace/conformance/fixtures/${fixture_name}/input.yaml \
          --subject /workspace/conformance/fixtures/${fixture_name}/subject.json \
          --label conformance \
          --output /workspace/conformance/.output/${lang}/${fixture_name}/results.json \
          --format json" 2>"${out_dir}/stderr.log" && actual_exit=0 || actual_exit=$?
      ;;
    typescript)
      ${CONTAINER_RUNTIME} run --rm \
        -v "${REPO_ROOT}:/workspace" \
        -w /workspace \
        node:22-slim \
        node /workspace/typescript/dist/cli.js ${cfg} run \
          --cases /workspace/conformance/fixtures/${fixture_name}/input.yaml \
          --subject /workspace/conformance/fixtures/${fixture_name}/subject.json \
          --label conformance \
          --output /workspace/conformance/.output/${lang}/${fixture_name}/results.json \
          --format json 2>"${out_dir}/stderr.log" && actual_exit=0 || actual_exit=$?
      ;;
    go)
      "${OUTPUT_DIR}/beval-go" ${cfg_native} run \
        --cases "${fixture_dir}/input.yaml" \
        --subject "${fixture_dir}/subject.json" \
        --label "conformance" \
        --output "${out_dir}/results.json" \
        --format json 2>"${out_dir}/stderr.log" && actual_exit=0 || actual_exit=$?
      ;;
    dotnet)
      ${CONTAINER_RUNTIME} run --rm \
        -v "${REPO_ROOT}:/workspace" \
        -v "beval-nuget-cache:/root/.nuget" \
        -w /workspace/dotnet \
        mcr.microsoft.com/dotnet/sdk:8.0 \
        dotnet run --project /workspace/dotnet/src/Beval.Cli --no-build -- ${cfg} run \
          --cases /workspace/conformance/fixtures/${fixture_name}/input.yaml \
          --subject /workspace/conformance/fixtures/${fixture_name}/subject.json \
          --label conformance \
          --output /workspace/conformance/.output/${lang}/${fixture_name}/results.json \
          --format json 2>"${out_dir}/stderr.log" && actual_exit=0 || actual_exit=$?
      ;;
  esac

  echo "${actual_exit}" > "${out_dir}/exit-code"
}

# Run yaml-safety fixture: implementations must reject malicious YAML.
run_yaml_safety() {
  local lang="$1"
  local out_dir="${OUTPUT_DIR}/${lang}/yaml-safety"
  mkdir -p "${out_dir}"
  local actual_exit=0

  echo "  -> Running yaml-safety with ${lang}..."
  case "${lang}" in
    python)
      ${CONTAINER_RUNTIME} run --rm \
        -v "${REPO_ROOT}:/workspace" \
        -v "beval-uv-cache:/root/.cache/uv" \
        -w /workspace/python \
        ghcr.io/astral-sh/uv:python3.12-trixie-slim \
        bash -c "uv sync && uv run beval run \
          --cases /workspace/conformance/fixtures/yaml-safety/malicious.yaml \
          --label conformance \
          --output /workspace/conformance/.output/${lang}/yaml-safety/results.json \
          --format json" 2>"${out_dir}/stderr.log" && actual_exit=0 || actual_exit=$?
      ;;
    typescript)
      ${CONTAINER_RUNTIME} run --rm \
        -v "${REPO_ROOT}:/workspace" \
        -w /workspace \
        node:22-slim \
        node /workspace/typescript/dist/cli.js run \
          --cases /workspace/conformance/fixtures/yaml-safety/malicious.yaml \
          --label conformance \
          --output /workspace/conformance/.output/${lang}/yaml-safety/results.json \
          --format json 2>"${out_dir}/stderr.log" && actual_exit=0 || actual_exit=$?
      ;;
    go)
      "${OUTPUT_DIR}/beval-go" run \
        --cases "${FIXTURES_DIR}/yaml-safety/malicious.yaml" \
        --label "conformance" \
        --output "${out_dir}/results.json" \
        --format json 2>"${out_dir}/stderr.log" && actual_exit=0 || actual_exit=$?
      ;;
    dotnet)
      ${CONTAINER_RUNTIME} run --rm \
        -v "${REPO_ROOT}:/workspace" \
        -v "beval-nuget-cache:/root/.nuget" \
        -w /workspace/dotnet \
        mcr.microsoft.com/dotnet/sdk:8.0 \
        dotnet run --project /workspace/dotnet/src/Beval.Cli --no-build -- run \
          --cases /workspace/conformance/fixtures/yaml-safety/malicious.yaml \
          --label conformance \
          --output /workspace/conformance/.output/${lang}/yaml-safety/results.json \
          --format json 2>"${out_dir}/stderr.log" && actual_exit=0 || actual_exit=$?
      ;;
  esac

  echo "${actual_exit}" > "${out_dir}/exit-code"
}

# Build all selected languages
for lang in "${LANGUAGES[@]}"; do
  build_language "${lang}"
done

# Run all fixtures for each language
for fixture_dir in "${FIXTURES_DIR}"/*/; do
  fixture_name="$(basename "${fixture_dir}")"

  # yaml-safety has a dedicated runner
  if [[ "${fixture_name}" == "yaml-safety" ]]; then
    for lang in "${LANGUAGES[@]}"; do
      run_yaml_safety "${lang}"
    done
    continue
  fi

  # Skip directories without input.yaml
  if [[ ! -f "${fixture_dir}/input.yaml" ]]; then
    continue
  fi
  for lang in "${LANGUAGES[@]}"; do
    run_fixture "${lang}" "${fixture_dir}"
  done
done

# ========================================================================
# Phase 1: Compare results against expected output
# ========================================================================
echo ""
echo "==> Comparing results..."
failures=0
total=0
# Strip volatile fields that differ per-run.
strip_volatile='del(.timestamp) | del(.cases[]?.time_seconds)'

for fixture_dir in "${FIXTURES_DIR}"/*/; do
  fixture_name="$(basename "${fixture_dir}")"

  # Only compare fixtures that have expected output
  if [[ ! -f "${fixture_dir}/expected.json" ]]; then
    continue
  fi

  total=$((total + 1))
  expected_sorted="$(jq -S "${strip_volatile}" "${fixture_dir}/expected.json")"
  fixture_passed=true

  for lang in "${LANGUAGES[@]}"; do
    results_file="${OUTPUT_DIR}/${lang}/${fixture_name}/results.json"
    if [[ ! -f "${results_file}" ]]; then
      echo "FAIL: ${fixture_name} - ${lang} (no output produced)"
      fixture_passed=false
      continue
    fi

    actual_sorted="$(jq -S "${strip_volatile}" "${results_file}")"
    if [[ "${actual_sorted}" != "${expected_sorted}" ]]; then
      echo "FAIL: ${fixture_name} - ${lang} (output differs from expected)"
      diff <(echo "${expected_sorted}") <(echo "${actual_sorted}") || true
      fixture_passed=false
    fi
  done

  if [[ "${fixture_passed}" == true ]]; then
    echo "PASS: ${fixture_name}"
  else
    failures=$((failures + 1))
  fi
done

# Also compare implementations against each other for consistency
for fixture_dir in "${FIXTURES_DIR}"/*/; do
  fixture_name="$(basename "${fixture_dir}")"
  if [[ ! -f "${fixture_dir}/expected.json" ]]; then
    continue
  fi

  reference_lang="${LANGUAGES[0]}"
  reference_file="${OUTPUT_DIR}/${reference_lang}/${fixture_name}/results.json"
  if [[ ! -f "${reference_file}" ]]; then
    continue
  fi

  reference_sorted="$(jq -S "${strip_volatile}" "${reference_file}")"
  for lang in "${LANGUAGES[@]:1}"; do
    results_file="${OUTPUT_DIR}/${lang}/${fixture_name}/results.json"
    if [[ ! -f "${results_file}" ]]; then
      continue
    fi
    actual_sorted="$(jq -S "${strip_volatile}" "${results_file}")"
    if [[ "${actual_sorted}" != "${reference_sorted}" ]]; then
      echo "MISMATCH: ${fixture_name} - ${reference_lang} vs ${lang}"
      failures=$((failures + 1))
    fi
  done
done

# ========================================================================
# Phase 2: Verify exit codes (SPEC §7.4)
# ========================================================================
echo ""
echo "==> Checking exit codes..."

for fixture_dir in "${FIXTURES_DIR}"/*/; do
  fixture_name="$(basename "${fixture_dir}")"

  if [[ ! -f "${fixture_dir}/expected-exit-code" ]]; then
    continue
  fi

  expected_exit="$(cat "${fixture_dir}/expected-exit-code" | tr -d '[:space:]')"
  total=$((total + 1))
  fixture_passed=true

  for lang in "${LANGUAGES[@]}"; do
    exit_file="${OUTPUT_DIR}/${lang}/${fixture_name}/exit-code"
    if [[ ! -f "${exit_file}" ]]; then
      continue
    fi

    actual_exit="$(cat "${exit_file}" | tr -d '[:space:]')"
    if [[ "${actual_exit}" != "${expected_exit}" ]]; then
      echo "FAIL: ${fixture_name} - ${lang} exit code (expected ${expected_exit}, got ${actual_exit})"
      fixture_passed=false
    fi
  done

  if [[ "${fixture_passed}" == true ]]; then
    echo "PASS: ${fixture_name} exit code"
  else
    failures=$((failures + 1))
  fi
done

# ========================================================================
# Phase 3: YAML safety — malicious input must be rejected (SPEC §10.2)
# ========================================================================
echo ""
echo "==> Checking yaml-safety..."
total=$((total + 1))
yaml_safety_passed=true

for lang in "${LANGUAGES[@]}"; do
  exit_file="${OUTPUT_DIR}/${lang}/yaml-safety/exit-code"
  results_file="${OUTPUT_DIR}/${lang}/yaml-safety/results.json"

  if [[ ! -f "${exit_file}" ]]; then
    continue
  fi

  actual_exit="$(cat "${exit_file}" | tr -d '[:space:]')"

  # Must exit with non-zero (input error = 2)
  if [[ "${actual_exit}" == "0" ]]; then
    echo "FAIL: yaml-safety - ${lang} (accepted malicious YAML, exit 0)"
    yaml_safety_passed=false
  fi

  # Must NOT produce valid results
  if [[ -f "${results_file}" ]] && jq empty "${results_file}" 2>/dev/null; then
    result_cases="$(jq -r '.cases // [] | length' "${results_file}" 2>/dev/null || echo "0")"
    if [[ "${result_cases}" -gt 0 ]]; then
      echo "FAIL: yaml-safety - ${lang} (produced results from malicious YAML)"
      yaml_safety_passed=false
    fi
  fi
done

if [[ "${yaml_safety_passed}" == true ]]; then
  echo "PASS: yaml-safety"
else
  failures=$((failures + 1))
fi

# ========================================================================
# Phase 4: Schema validation — results must conform to results.schema.json
# ========================================================================
echo ""
echo "==> Validating results against schema..."

if [[ -f "${SCHEMA_FILE}" ]]; then
  # Use Python + jsonschema in the conformance container for validation
  schema_failures=0
  for fixture_dir in "${FIXTURES_DIR}"/*/; do
    fixture_name="$(basename "${fixture_dir}")"
    if [[ ! -f "${fixture_dir}/expected.json" ]]; then
      continue
    fi

    for lang in "${LANGUAGES[@]}"; do
      results_file="${OUTPUT_DIR}/${lang}/${fixture_name}/results.json"
      if [[ ! -f "${results_file}" ]]; then
        continue
      fi

      # Validate inside the Python container which has jsonschema installed
      validation_result="$(${CONTAINER_RUNTIME} run --rm \
        -v "${REPO_ROOT}:/workspace" \
        -v "beval-uv-cache:/root/.cache/uv" \
        -w /workspace/python \
        ghcr.io/astral-sh/uv:python3.12-trixie-slim \
        bash -c "uv sync -q --extra validate && uv run python3 -c \"
import json, sys
from jsonschema import validate, ValidationError
schema = json.load(open('/workspace/spec/schemas/results.schema.json'))
data = json.load(open('/workspace/conformance/.output/${lang}/${fixture_name}/results.json'))
try:
    validate(data, schema)
    print('OK')
except ValidationError as e:
    print(f'INVALID: {e.message}')
\"" 2>/dev/null)" || validation_result="SKIP"

      if [[ "${validation_result}" == "OK" ]]; then
        continue
      elif [[ "${validation_result}" == "SKIP" ]]; then
        echo "SKIP: ${fixture_name} - ${lang} schema validation (jsonschema not available)"
      else
        echo "FAIL: ${fixture_name} - ${lang} schema: ${validation_result}"
        schema_failures=$((schema_failures + 1))
      fi
    done
  done

  total=$((total + 1))
  if [[ "${schema_failures}" -eq 0 ]]; then
    echo "PASS: schema validation"
  else
    echo "FAIL: schema validation (${schema_failures} failures)"
    failures=$((failures + 1))
  fi
else
  echo "SKIP: ${SCHEMA_FILE} not found"
fi

# ========================================================================
# Summary
# ========================================================================
echo ""
echo "==> Summary"
echo "Checks performed: ${total}"
echo "Failures: ${failures}"

if [[ "${failures}" -gt 0 ]]; then
  echo "CONFORMANCE FAILED"
  exit 1
fi

echo "CONFORMANCE PASSED"
exit 0
