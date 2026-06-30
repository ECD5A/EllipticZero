#!/usr/bin/env bash
# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p "$ROOT_DIR/.ellipticzero/tmp" "$ROOT_DIR/.ellipticzero/pip-cache"
export TMPDIR="$ROOT_DIR/.ellipticzero/tmp"
export PIP_CACHE_DIR="$ROOT_DIR/.ellipticzero/pip-cache"
export PIP_DISABLE_PIP_VERSION_CHECK=1

PROFILE="lab"
VENV_DIR="${ELLIPTICZERO_VENV_DIR:-.venv}"
MANAGED_SOLC_VERSIONS=("0.8.20" "0.8.24" "0.8.25" "0.8.30")
SKIP_MANAGED_SOLC="0"
RUN_DOCTOR="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --venv-dir)
      VENV_DIR="$2"
      shift 2
      ;;
    --managed-solc-version)
      MANAGED_SOLC_VERSIONS=("$2")
      shift 2
      ;;
    --skip-managed-solc)
      SKIP_MANAGED_SOLC="1"
      shift
      ;;
    --no-doctor)
      RUN_DOCTOR="0"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

case "$PROFILE" in
  lab)
    PROFILE_EXTRA="lab"
    ;;
  smart-contract-basic)
    PROFILE_EXTRA="smart_contract_basic"
    ;;
  smart-contract-static)
    PROFILE_EXTRA="smart_contract_static"
    ;;
  *)
    echo "Unsupported profile: $PROFILE" >&2
    exit 2
    ;;
esac

if [[ -z "$VENV_DIR" ]]; then
  echo "Virtual environment directory must not be empty." >&2
  exit 2
fi

if [[ "$VENV_DIR" = /* ]]; then
  VENV_PATH="$VENV_DIR"
else
  VENV_PATH="$ROOT_DIR/$VENV_DIR"
fi

echo
echo "==> Preparing local environment: $VENV_PATH"
if [[ ! -x "$VENV_PATH/bin/python" ]]; then
  if ! python3 -m venv "$VENV_PATH"; then
    echo "Could not create the virtual environment." >&2
    echo "On Ubuntu/Debian, install python3-venv and run this script again." >&2
    exit 1
  fi
fi

PYTHON_BIN="$VENV_PATH/bin/python"

echo
echo "==> Upgrading pip"
"$PYTHON_BIN" -m pip install --disable-pip-version-check --upgrade pip

echo
echo "==> Installing project profile: $PROFILE"
"$PYTHON_BIN" -m pip install --disable-pip-version-check -e ".[${PROFILE_EXTRA}]"

if [[ "$SKIP_MANAGED_SOLC" != "1" ]]; then
  echo
  echo "==> Provisioning managed Solidity compiler"
  BOOTSTRAP_ARGS=(scripts/bootstrap_smart_contract_toolchain.py)
  for version in "${MANAGED_SOLC_VERSIONS[@]}"; do
    BOOTSTRAP_ARGS+=(--solc-version "$version")
  done
  "$PYTHON_BIN" "${BOOTSTRAP_ARGS[@]}"
fi

echo
echo "==> Checking optional local research tools"
if command -v sage >/dev/null 2>&1; then
  echo "Sage detected: $(command -v sage)"
else
  echo "Sage not detected. SymPy / Hypothesis / z3-based paths are ready; Sage remains optional."
fi

if [[ "$RUN_DOCTOR" == "1" ]]; then
  echo
  echo "==> Running system doctor"
  "$PYTHON_BIN" -m app.main --doctor
fi

echo
echo "Local lab environment is ready in: $VENV_PATH"
echo "All Python-installable research dependencies are now local to this project folder."
echo "Run interactive console with:"
echo "  \"$PYTHON_BIN\" -m app.main --interactive"
