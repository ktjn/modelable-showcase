#!/usr/bin/env bash
# Install the Modelable CLI in one of two modes:
#
#   MODELABLE_REF unset -> install the pinned release from .modelable-version
#                          (reproducible, default local/CI mode).
#   MODELABLE_REF=<ref> -> install from https://github.com/ktjn/modelable at
#                          that branch/tag/commit (canary mode). See
#                          UPSTREAM_POLICY.md for when canary mode applies.
#
# Installs via `uv tool install` into uv's per-user tool environment - no
# global machine mutation, and CI can reproduce the exact same install.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UPSTREAM_URL="https://github.com/ktjn/modelable"
PYTHON_VERSION="3.14"

# shellcheck source=./modelable-env.sh
source "${SCRIPT_DIR}/modelable-env.sh"

if ! command -v uv >/dev/null 2>&1; then
  echo "install-modelable.sh: 'uv' is required but was not found on PATH." >&2
  echo "  Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

echo "install-modelable.sh: ensuring Python ${PYTHON_VERSION} is available via uv (Modelable requires >=3.14)" >&2
uv python install "${PYTHON_VERSION}" >/dev/null

if [ -z "${MODELABLE_REF:-}" ]; then
  version="$(tr -d ' \t\n\r' < "${REPO_ROOT}/.modelable-version")"
  if [ -z "${version}" ]; then
    echo "install-modelable.sh: .modelable-version is empty." >&2
    exit 1
  fi
  echo "install-modelable.sh: MODELABLE_REF unset - installing pinned release modelable==${version}" >&2
  uv tool install --force --python "${PYTHON_VERSION}" "modelable==${version}"
else
  echo "install-modelable.sh: MODELABLE_REF=${MODELABLE_REF} - installing from ${UPSTREAM_URL} (canary mode)" >&2

  if [[ "${MODELABLE_REF}" =~ ^[0-9a-fA-F]{40}$ ]]; then
    resolved_sha="${MODELABLE_REF}"
  else
    resolved_sha="$(git ls-remote "${UPSTREAM_URL}" "${MODELABLE_REF}" | cut -f1 | head -n1)"
    if [ -z "${resolved_sha}" ]; then
      echo "install-modelable.sh: could not resolve ref '${MODELABLE_REF}' on ${UPSTREAM_URL}" >&2
      echo "  Confirm the branch/tag exists upstream." >&2
      exit 1
    fi
  fi
  echo "install-modelable.sh: resolved upstream commit: ${resolved_sha}" >&2

  # The installable package lives in cli/ (see cli/pyproject.toml upstream).
  uv tool install --force --python "${PYTHON_VERSION}" \
    "git+${UPSTREAM_URL}@${resolved_sha}#subdirectory=cli"
fi

echo "install-modelable.sh: installed $(modelable --version)" >&2
